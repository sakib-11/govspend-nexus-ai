from typing import Dict, Any, Optional
import hashlib
from datetime import datetime
from pathlib import Path
import mimetypes
import os
from config import PolicyIngestionConfig
import logging

logger = logging.getLogger(__name__)

class MetadataService:
    """Service for extracting and managing document metadata"""
    
    def __init__(self, config: PolicyIngestionConfig):
        self.config = config
    
    async def extract_metadata(
        self,
        file_path: str,
        basic_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract metadata from a file"""
        
        metadata = basic_metadata or {}
        
        # File system metadata
        stat = os.stat(file_path)
        metadata.update({
            "file_size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "file_extension": Path(file_path).suffix.lower(),
            "mime_type": mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        })
        
        # File hash
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            metadata["file_hash"] = file_hash
        
        # Add any additional metadata based on file type
        # This can be extended for specific formats
        
        return metadata
    
    def validate_metadata(self, metadata: Dict[str, Any]) -> bool:
        """Validate metadata against required fields"""
        # Basic validation - can be extended
        required_fields = ["file_hash", "file_size"]
        for field in required_fields:
            if field not in metadata:
                logger.warning(f"Missing required metadata field: {field}")
                return False
        return True
    
    def enrich_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich metadata with additional computed fields"""
        enriched = metadata.copy()
        
        # Add content type classification
        if "mime_type" in enriched:
            if enriched["mime_type"].startswith("text/"):
                enriched["content_type"] = "text"
            elif enriched["mime_type"] == "application/pdf":
                enriched["content_type"] = "document"
            elif enriched["mime_type"] in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                                          "application/msword"]:
                enriched["content_type"] = "document"
            elif enriched["mime_type"].startswith("image/"):
                enriched["content_type"] = "image"
            else:
                enriched["content_type"] = "other"
        
        return enriched
