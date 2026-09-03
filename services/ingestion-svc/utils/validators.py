"""File validation utilities."""

from fastapi import UploadFile
from typing import List, Dict, Any, Optional
from pathlib import Path
import mimetypes
import magic

class FileValidator:
    """Validate uploaded files."""
    
    ALLOWED_MIME_TYPES = {
        'application/pdf': ['.pdf'],
        'image/png': ['.png'],
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/tiff': ['.tiff', '.tif'],
        'image/bmp': ['.bmp'],
    }
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    
    async def validate(
        self,
        file: UploadFile,
        max_size: Optional[int] = None,
        allowed_extensions: Optional[List[str]] = None,
        allowed_mime_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Validate uploaded file.
        
        Returns:
            Dict with 'valid' bool and 'errors' list
        """
        errors = []
        
        # Check file size
        file_size = await self._get_file_size(file)
        max_size = max_size or self.MAX_FILE_SIZE
        
        if file_size > max_size:
            errors.append(f"File size {file_size} bytes exceeds maximum {max_size} bytes")
        
        # Check file extension
        extension = self._get_extension(file.filename)
        allowed_extensions = allowed_extensions or ['.pdf', '.png', '.jpg', '.jpeg', '.tiff']
        
        if extension.lower() not in allowed_extensions:
            errors.append(f"File extension '{extension}' not allowed. Allowed: {allowed_extensions}")
        
        # Check MIME type
        mime_type = await self._get_mime_type(file)
        allowed_mime_types = allowed_mime_types or list(self.ALLOWED_MIME_TYPES.keys())
        
        if mime_type not in allowed_mime_types:
            errors.append(f"MIME type '{mime_type}' not allowed. Allowed: {allowed_mime_types}")
        
        # Check if file is empty
        if file_size == 0:
            errors.append("File is empty")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "file_size": file_size,
            "extension": extension,
            "mime_type": mime_type,
            "filename": file.filename
        }
    
    async def _get_file_size(self, file: UploadFile) -> int:
        """Get file size by reading first few bytes."""
        # Read first chunk to check size
        chunk = await file.read(1024 * 1024)  # Read up to 1MB
        size = len(chunk)
        
        # Read more if needed (for small files)
        if size > 0 and size < 1024 * 1024:
            # Read rest of file
            more_chunks = []
            while True:
                more = await file.read(1024 * 1024)
                if not more:
                    break
                more_chunks.append(more)
            size = len(chunk) + sum(len(c) for c in more_chunks)
            
            # Create a new file-like object for reading
            # We need to reset the file position for later processing
            await file.seek(0)
        
        return size
    
    def _get_extension(self, filename: str) -> str:
        """Extract file extension."""
        return Path(filename).suffix.lower()
    
    async def _get_mime_type(self, file: UploadFile) -> str:
        """Detect MIME type of file."""
        # First try using magic library
        try:
            chunk = await file.read(1024)
            await file.seek(0)
            mime_type = magic.from_buffer(chunk, mime=True)
            if mime_type:
                return mime_type
        except:
            pass
        
        # Fallback to mimetypes library
        mime_type, _ = mimetypes.guess_type(file.filename)
        return mime_type or 'application/octet-stream'
