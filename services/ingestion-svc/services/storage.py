"""Storage service for file management."""

from pathlib import Path
from fastapi import UploadFile
from typing import Optional, Dict, Any
import shutil
import uuid
import os
import json
import logging
from datetime import datetime

from ..config import Settings

logger = logging.getLogger(__name__)

class StorageService:
    """Handle file storage operations."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.upload_dir = Path(self.settings.upload_dir)
        self.processed_dir = Path(self.settings.processed_dir)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create necessary directories."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Storage directories created: {self.upload_dir}, {self.processed_dir}")
    
    async def initialize(self):
        """Initialize storage service."""
        self._ensure_directories()
        return self
    
    async def save_temp_file(
        self,
        file: UploadFile,
        upload_id: str,
        original_filename: str
    ) -> Path:
        """Save uploaded file to temporary location."""
        # Create subdirectory for upload
        upload_path = self.upload_dir / upload_id
        upload_path.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = upload_path / original_filename
        
        # Write file in chunks
        with open(file_path, 'wb') as f:
            while chunk := await file.read(8192):
                f.write(chunk)
        
        logger.info(f"File saved: {file_path} (upload_id: {upload_id})")
        return file_path
    
    async def move_to_processed(
        self,
        temp_path: Path,
        upload_id: str,
        ocr_result: Dict[str, Any] = None
    ) -> Path:
        """Move processed file to processed directory."""
        # Create processed directory
        processed_path = self.processed_dir / upload_id
        processed_path.mkdir(parents=True, exist_ok=True)
        
        # Move file
        new_path = processed_path / temp_path.name
        shutil.move(str(temp_path), str(new_path))
        
        # Save OCR metadata
        if ocr_result:
            metadata_path = processed_path / "ocr_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(ocr_result, f, default=str, indent=2)
        
        # Clean up temp directory
        temp_parent = temp_path.parent
        if temp_parent.exists() and not any(temp_parent.iterdir()):
            temp_parent.rmdir()
        
        logger.info(f"File moved to processed: {new_path}")
        return new_path
    
    async def cleanup_temp_file(self, file_path: Path):
        """Clean up temporary file."""
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Cleaned up temp file: {file_path}")
            
            # Remove empty parent directory
            parent = file_path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {file_path}: {str(e)}")
    
    async def get_upload_status(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an upload."""
        processed_path = self.processed_dir / upload_id
        if processed_path.exists():
            return {
                "upload_id": upload_id,
                "status": "processed",
                "path": str(processed_path),
                "files": [f.name for f in processed_path.iterdir() if f.is_file()],
                "last_modified": datetime.fromtimestamp(processed_path.stat().st_mtime).isoformat()
            }
        
        temp_path = self.upload_dir / upload_id
        if temp_path.exists():
            return {
                "upload_id": upload_id,
                "status": "processing",
                "path": str(temp_path),
                "last_modified": datetime.fromtimestamp(temp_path.stat().st_mtime).isoformat()
            }
        
        return None
    
    async def health_check(self) -> bool:
        """Check if storage is operational."""
        try:
            # Test write
            test_dir = self.upload_dir / ".health_check"
            test_dir.mkdir(exist_ok=True)
            test_dir.rmdir()
            return True
        except Exception as e:
            logger.error(f"Storage health check failed: {str(e)}")
            return False

