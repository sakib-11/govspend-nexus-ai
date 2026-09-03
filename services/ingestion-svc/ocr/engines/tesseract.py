"""Tesseract OCR engine implementation."""

import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import pytesseract
from PIL import Image
import pdf2image
import io
import base64
import logging
from datetime import datetime

from ..core import BaseOCREngine, OCRResult

logger = logging.getLogger(__name__)

class TesseractEngine(BaseOCREngine):
    """Tesseract OCR engine with PDF support."""
    
    def __init__(
        self,
        tesseract_path: str = "/usr/bin/tesseract",
        language: str = "eng",
        psm: int = 6,
        max_pages: int = 20,
        dpi: int = 300,
    ):
        self.tesseract_path = tesseract_path
        self.language = language
        self.psm = psm
        self.max_pages = max_pages
        self.dpi = dpi
        
        # Verify Tesseract installation
        try:
            subprocess.run([tesseract_path, "--version"], capture_output=True, check=True)
            logger.info(f"Tesseract found at {tesseract_path}")
        except Exception as e:
            logger.warning(f"Tesseract not found: {str(e)}")
    
    async def process(
        self,
        file_path: Path,
        content_type: str = "application/pdf",
        options: Optional[Dict[str, Any]] = None
    ) -> OCRResult:
        """Process document with Tesseract."""
        options = options or {}
        language = options.get("language", self.language)
        psm = options.get("psm", self.psm)
        dpi = options.get("dpi", self.dpi)
        
        all_text = []
        all_confidence = []
        pages_processed = 0
        
        try:
            # Check if PDF or Image
            if file_path.suffix.lower() == ".pdf":
                # Convert PDF to images
                images = pdf2image.convert_from_bytes(
                    file_path.read_bytes(),
                    dpi=dpi,
                    first_page=1,
                    last_page=self.max_pages
                )
                
                for page_num, image in enumerate(images, 1):
                    if page_num > self.max_pages:
                        break
                    
                    # Process each page
                    page_text, page_confidence = await self._process_image(
                        image, language, psm
                    )
                    
                    all_text.append(f"--- Page {page_num} ---\n{page_text}")
                    all_confidence.append(page_confidence)
                    pages_processed += 1
                    
            else:
                # Process as image
                image = Image.open(file_path)
                text, confidence = await self._process_image(image, language, psm)
                all_text.append(text)
                all_confidence.append(confidence)
                pages_processed = 1
            
            # Combine results
            combined_text = "\n\n".join(all_text)
            average_confidence = sum(all_confidence) / len(all_confidence) if all_confidence else 0.0
            
            # Extract fields using regex patterns
            extracted_fields = self._extract_fields(combined_text)
            
            return OCRResult(
                raw_text=combined_text,
                confidence=average_confidence,
                extracted_fields=extracted_fields,
                page_count=pages_processed,
                warnings=[],
                metadata={
                    "engine": "tesseract",
                    "language": language,
                    "psm": psm,
                    "dpi": dpi,
                    "pages_processed": pages_processed
                }
            )
            
        except Exception as e:
            logger.error(f"Tesseract processing failed: {str(e)}")
            raise
    
    async def _process_image(self, image, language: str, psm: int) -> tuple:
        """Process a single image with Tesseract."""
        try:
            # OCR with Tesseract
            config = f"--psm {psm} -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.,$%&@!? "
            text = pytesseract.image_to_string(
                image,
                lang=language,
                config=config
            )
            
            # Get confidence data
            confidence_data = pytesseract.image_to_data(
                image,
                lang=language,
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate average confidence
            confidences = [float(c) for c in confidence_data['conf'] if c != '-1' and c != '']
            average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return text.strip(), average_confidence / 100.0
            
        except Exception as e:
            logger.error(f"Image processing failed: {str(e)}")
            raise
    
    def _extract_fields(self, text: str) -> Dict[str, Any]:
        """Extract structured fields from raw text using regex."""
        import re
        
        fields = {}
        
        # Common invoice patterns
        patterns = {
            "invoice_number": r'(?:INVOICE|INV|DOCUMENT)[\s#:]+([A-Z0-9\-]+)',
            "purchase_order": r'(?:PO|PURCHASE ORDER|ORDER)[\s#:]+([A-Z0-9\-]+)',
            "date": r'DATE[\s:]+(\d{2}[/\-]\d{2}[/\-]\d{4}|\d{4}[/\-]\d{2}[/\-]\d{2})',
            "due_date": r'DUE[\s:]+(\d{2}[/\-]\d{2}[/\-]\d{4}|\d{4}[/\-]\d{2}[/\-]\d{2})',
            "total_amount": r'(?:TOTAL|AMOUNT|GRAND TOTAL)[\s$:]+([\d,]+\.?\d*)',
            "vendor_name": r'(?:VENDOR|SUPPLIER|FROM)[\s:]+([A-Za-z\s\.,&]+)',
            "vendor_tax_id": r'(?:TAX ID|EIN|GST)[\s:]+([A-Z0-9\-]+)',
            "buyer_name": r'(?:BUYER|TO|CUSTOMER)[\s:]+([A-Za-z\s\.,&]+)',
        }
        
        for field_name, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fields[field_name] = match.group(1).strip()
        
        # Try to detect line items
        line_items = self._extract_line_items(text)
        if line_items:
            fields["line_items"] = line_items
        
        return fields
    
    def _extract_line_items(self, text: str) -> list:
        """Extract line items from invoice text."""
        # Simplified line item extraction
        lines = text.split('\n')
        items = []
        
        for line in lines:
            # Look for patterns like "Item description | Qty | Price | Amount"
            # This is a simplified example - real implementation would be more robust
            if '$' in line and any(char.isdigit() for char in line):
                parts = line.split()
                if len(parts) >= 3:
                    items.append({
                        "description": " ".join(parts[:-3]) if len(parts) > 3 else "",
                        "quantity": 1,
                        "unit_price": 0.0,
                        "total": 0.0
                    })
        
        return items
    
    async def health_check(self) -> bool:
        """Check if Tesseract is operational."""
        try:
            result = subprocess.run(
                [self.tesseract_path, "--version"],
                capture_output=True,
                timeout=5,
                check=True
            )
            return True
        except Exception:
            return False

