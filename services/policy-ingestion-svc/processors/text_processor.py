from typing import Dict, Any
import hashlib
import os
import logging

logger = logging.getLogger(__name__)

class TextProcessor:
    """Processor for text documents"""
    
    def __init__(self, config):
        self.config = config
    
    async def process(
        self,
        file_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process a text file"""
        
        result = {
            "content": "",
            "metadata": metadata or {},
            "page_count": 0
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            result["content"] = content
            result["word_count"] = len(content.split())
            
            # Generate file hash
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
                result["file_hash"] = file_hash
            
            return result
            
        except Exception as e:
            logger.error(f"Text processing error: {e}")
            raise
