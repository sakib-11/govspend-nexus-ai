from typing import Dict, Any, Optional
import hashlib
import io
import os
from pathlib import Path
import pypdf
import pytesseract
from PIL import Image
import pdf2image
import logging

logger = logging.getLogger(__name__)

class PDFProcessor:
    """Processor for PDF documents"""
    
    def __init__(self, config):
        self.config = config
        self.ocr_enabled = config.ocr_enabled
    
    async def process(
        self,
        file_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process a PDF file and extract text"""
        
        result = {
            "content": "",
            "metadata": metadata or {},
            "pages": []
        }
        
        try:
            # Extract text using PyPDF
            with open(file_path, 'rb') as f:
                pdf_reader = pypdf.PdfReader(f)
                result["page_count"] = len(pdf_reader.pages)
                
                # Extract text from each page
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    
                    # If text extraction failed and OCR is enabled, use OCR
                    if not page_text.strip() and self.ocr_enabled:
                        page_text = await self._ocr_page(file_path, page_num)
                    
                    result["pages"].append({
                        "page_number": page_num + 1,
                        "text": page_text
                    })
            
            # Combine all pages
            result["content"] = "\n\n".join([
                f"Page {p['page_number']}:\n{p['text']}"
                for p in result["pages"]
            ])
            
            # Generate file hash
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
                result["file_hash"] = file_hash
            
            return result
            
        except Exception as e:
            logger.error(f"PDF processing error: {e}")
            raise
    
    async def _ocr_page(self, file_path: str, page_num: int) -> str:
        """Perform OCR on a specific page"""
        
        try:
            # Convert PDF page to image
            images = pdf2image.convert_from_path(
                file_path,
                first_page=page_num + 1,
                last_page=page_num + 1,
                dpi=300
            )
            
            if not images:
                return ""
            
            # Perform OCR
            image = images[0]
            text = pytesseract.image_to_string(image)
            
            return text
            
        except Exception as e:
            logger.error(f"OCR error on page {page_num + 1}: {e}")
            return ""
