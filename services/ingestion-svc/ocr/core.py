"""Core OCR service implementation."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import logging
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class OCREngine(str, Enum):
    TESSERACT = "tesseract"
    AWS_TEXTRACT = "aws_textract"
    AZURE = "azure"
    GOOGLE = "google"

@dataclass
class OCRResult:
    """Structured OCR extraction result."""
    raw_text: str
    confidence: float
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    bounding_boxes: Optional[List[Dict[str, Any]]] = None
    processing_time_ms: float = 0.0
    engine: str = ""
    page_count: int = 0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    cached_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "raw_text": self.raw_text[:1000] + "..." if len(self.raw_text) > 1000 else self.raw_text,
            "confidence": self.confidence,
            "extracted_fields": self.extracted_fields,
            "processing_time_ms": self.processing_time_ms,
            "engine": self.engine,
            "page_count": self.page_count,
            "warnings": self.warnings,
            "metadata": self.metadata
        }

class BaseOCREngine(ABC):
    """Base abstract class for OCR engines."""
    
    @abstractmethod
    async def process(
        self,
        file_path: Path,
        content_type: str = "application/pdf",
        options: Optional[Dict[str, Any]] = None
    ) -> OCRResult:
        """Process a document and extract structured data."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the OCR engine is operational."""
        pass

class OCRService:
    """Main OCR service orchestrator."""
    
    def __init__(
        self,
        primary_engine: BaseOCREngine,
        fallback_engine: Optional[BaseOCREngine] = None,
        cache_enabled: bool = True,
        cache_ttl: int = 86400,  # 24 hours
    ):
        self.primary_engine = primary_engine
        self.fallback_engine = fallback_engine
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, tuple] = {}  # key -> (result, timestamp)
        
        logger.info(f"OCR Service initialized with {primary_engine.__class__.__name__}")
        if fallback_engine:
            logger.info(f"Fallback engine: {fallback_engine.__class__.__name__}")
    
    async def process_document(
        self,
        file_path: Path,
        content_type: str = "application/pdf",
        options: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False,
    ) -> OCRResult:
        """
        Process a document with caching and automatic fallback.
        """
        # Generate cache key
        cache_key = self._generate_cache_key(file_path, options)
        
        # Check cache
        if self.cache_enabled and not force_refresh and cache_key in self._cache:
            cached_result, cached_time = self._cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                logger.debug(f"Returning cached OCR result for {file_path.name}")
                return cached_result
        
        logger.info(f"Processing document: {file_path.name} with {self.primary_engine.__class__.__name__}")
        start_time = datetime.now()
        
        # Try primary engine
        try:
            result = await self.primary_engine.process(file_path, content_type, options)
            result.engine = self.primary_engine.__class__.__name__
            
            # Check confidence
            if result.confidence < 0.4 and self.fallback_engine:
                logger.warning(f"Low confidence ({result.confidence:.2f}) with primary, trying fallback")
                fallback_result = await self._process_with_fallback(file_path, content_type, options)
                if fallback_result.confidence > result.confidence:
                    result = fallback_result
                    result.engine = f"{result.engine} (fallback from low confidence)"
                    
        except Exception as e:
            logger.error(f"Primary OCR failed: {str(e)}")
            if self.fallback_engine:
                try:
                    result = await self._process_with_fallback(file_path, content_type, options)
                    result.engine = f"{result.engine} (fallback from primary failure)"
                except Exception as fallback_error:
                    raise RuntimeError(
                        f"Both primary and fallback OCR engines failed. "
                        f"Primary: {str(e)}, Fallback: {str(fallback_error)}"
                    )
            else:
                raise RuntimeError(f"OCR processing failed: {str(e)}")
        
        # Calculate processing time
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Add metadata
        result.metadata.update({
            "file_size": file_path.stat().st_size,
            "filename": file_path.name,
            "content_type": content_type,
            "processed_at": datetime.now().isoformat()
        })
        
        # Cache result
        if self.cache_enabled:
            self._cache[cache_key] = (result, datetime.now())
            logger.debug(f"Cached OCR result for {file_path.name}")
        
        return result
    
    async def _process_with_fallback(
        self,
        file_path: Path,
        content_type: str,
        options: Optional[Dict[str, Any]]
    ) -> OCRResult:
        """Process with fallback engine."""
        if not self.fallback_engine:
            raise ValueError("No fallback engine configured")
        
        logger.info(f"Processing with fallback engine: {self.fallback_engine.__class__.__name__}")
        result = await self.fallback_engine.process(file_path, content_type, options)
        result.engine = self.fallback_engine.__class__.__name__
        return result
    
    def _generate_cache_key(self, file_path: Path, options: Optional[Dict[str, Any]]) -> str:
        """Generate a cache key based on file content and options."""
        try:
            # Hash file content (first 1MB for performance)
            file_hash = hashlib.sha256()
            with open(file_path, 'rb') as f:
                chunk = f.read(1024 * 1024)  # Read first 1MB
                file_hash.update(chunk)
            file_hash_digest = file_hash.hexdigest()
        except Exception:
            # Fallback to full file hash
            file_hash_digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        
        # Hash options
        options_str = json.dumps(options or {}, sort_keys=True)
        options_hash = hashlib.sha256(options_str.encode()).hexdigest()
        
        return f"{file_hash_digest}:{options_hash}"
    
    async def health_check(self) -> bool:
        """Check if OCR service is healthy."""
        try:
            primary_health = await self.primary_engine.health_check()
            if self.fallback_engine:
                fallback_health = await self.fallback_engine.health_check()
                return primary_health and fallback_health
            return primary_health
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
    
    def clear_cache(self):
        """Clear the OCR cache."""
        self._cache.clear()
        logger.info("OCR cache cleared")

