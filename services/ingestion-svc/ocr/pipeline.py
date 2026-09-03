"""Complete OCR extraction pipeline."""

from typing import Dict, Any, Optional
import logging
from datetime import datetime
from pathlib import Path

from .core import OCRResult
from .extractors.invoice_extractor import InvoiceDataExtractor
from .extractors.confidence_scorer import ConfidenceScorer
from .extractors.validator import FieldValidator
from ..models.extraction import ExtractionResult

logger = logging.getLogger(__name__)

class ExtractionPipeline:
    """Complete extraction pipeline orchestrator."""
    
    def __init__(self):
        self.extractor = InvoiceDataExtractor()
        self.confidence_scorer = ConfidenceScorer()
        self.validator = FieldValidator()
        
    async def process(
        self,
        ocr_result: OCRResult,
        upload_id: str,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Process OCR result through complete extraction pipeline.
        
        Args:
            ocr_result: OCR result from OCR service
            upload_id: Unique upload identifier
            validate: Whether to validate extracted fields
            
        Returns:
            Dictionary with extraction results and metadata
        """
        start_time = datetime.now()
        
        logger.info(f"Starting extraction pipeline for upload: {upload_id}")
        
        # Step 1: Extract structured data
        extraction_result = await self.extractor.extract(
            ocr_result=ocr_result.to_dict(),
            upload_id=upload_id
        )
        
        # Step 2: Validate fields if requested
        if validate:
            validation_result = self.validator.validate_all(
                extraction_result.extracted_fields
            )
            extraction_result.warnings.extend(validation_result.get('warnings', []))
        
        # Step 3: Build structured invoice data
        invoice_data = self.extractor.extract_from_fields(
            extraction_result.extracted_fields
        )
        
        # Step 4: Prepare final response
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            'upload_id': upload_id,
            'extraction_result': extraction_result,
            'invoice_data': invoice_data,
            'extracted_fields': {
                name: {
                    'value': field.value,
                    'confidence': field.confidence,
                    'source': field.source,
                    'validated': field.validated,
                    'validation_errors': field.validation_errors
                }
                for name, field in extraction_result.extracted_fields.items()
            },
            'confidence_scores': extraction_result.confidence_scores,
            'overall_confidence': extraction_result.overall_confidence,
            'warnings': extraction_result.warnings,
            'processing_time_ms': processing_time,
            'timestamp': datetime.now().isoformat()
        }

