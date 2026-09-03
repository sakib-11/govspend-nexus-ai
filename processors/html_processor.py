from typing import Dict, Any
import hashlib
import logging
from bs4 import BeautifulSoup
import requests
import os

logger = logging.getLogger(__name__)

class HtmlProcessor:
    """Processor for HTML documents"""
    
    def __init__(self, config):
        self.config = config
    
    async def process(
        self,
        file_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process an HTML file and extract text"""
        
        result = {
            "content": "",
            "metadata": metadata or {},
            "word_count": 0,
            "page_count": 1  # HTML is considered as one page
        }
        
        try:
            # Check if it's a URL or local file
            if file_path.startswith('http://') or file_path.startswith('https://'):
                # Fetch from URL
                response = requests.get(file_path)
                response.raise_for_status()
                html_content = response.text
                # Update metadata with URL info
                if metadata is None:
                    metadata = {}
                metadata["source_url"] = file_path
            else:
                # Read from local file
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            
            # Parse HTML and extract text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Break into lines and remove leading and trailing space on each
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Remove blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            result["content"] = text
            result["word_count"] = len(text.split())
            
            # Generate file hash (for local files) or content hash (for URLs)
            if file_path.startswith('http'):
                # For URL, hash the content
                file_hash = hashlib.sha256(text.encode()).hexdigest()
            else:
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
            result["file_hash"] = file_hash
            
            return result
            
        except Exception as e:
            logger.error(f"HTML processing error: {e}")
            raise
