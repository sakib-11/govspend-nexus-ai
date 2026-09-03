"""Confidence scoring for extracted fields."""

from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import date
import re
import logging

from ...models.extraction import ExtractedField, ExtractionResult, ExtractionConfidence

logger = logging.getLogger(__name__)

class ConfidenceScorer:
    """Score confidence of extracted fields."""
    
    def __init__(self):
        self.field_weights = self._initialize_weights()
        self.validation_rules = self._initialize_validation_rules()
        
    def _initialize_weights(self) -> Dict[str, float]:
        """Initialize field importance weights."""
        return {
            'invoice_number': 0.15,
            'vendor_name': 0.20,
            'total_amount': 0.25,
            'date': 0.15,
            'vendor_tax_id': 0.05,
            'subtotal': 0.05,
            'tax_total': 0.05,
            'line_items': 0.10,
        }
    
    def _initialize_validation_rules(self) -> Dict[str, callable]:
        """Initialize validation functions for each field."""
        return {
            'invoice_number': self._validate_invoice_number,
            'vendor_name': self._validate_vendor_name,
            'total_amount': self._validate_amount,
            'date': self._validate_date,
            'vendor_tax_id': self._validate_tax_id,
            'subtotal': self._validate_amount,
            'tax_total': self._validate_amount,
            'line_items': self._validate_line_items,
        }
    
    def calculate_field_confidence(
        self,
        field: ExtractedField,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Calculate confidence for a single field."""
        confidence = field.confidence
        
        # Adjust based on source
        source_boost = {
            'heuristic_rules': 0.1,
            'line_item_extraction': 0.05,
            'calculated_from_line_items': -0.1,
            'ocr_fallback': -0.2,
        }
        confidence += source_boost.get(field.source, 0)
        
        # Adjust based on validation
        if field.validated:
            confidence += 0.1
        
        # Adjust based on alternatives
        if field.alternatives:
            # If there are multiple alternatives, confidence might be lower
            confidence *= (1 - 0.05 * min(len(field.alternatives), 3))
        
        # Apply field-specific validation
        validator = self.validation_rules.get(field.name)
        if validator:
            confidence = validator(field.value, confidence)
        
        # Clamp between 0 and 1
        return max(0.0, min(1.0, confidence))
    
    def calculate_overall_confidence(
        self,
        fields: Dict[str, ExtractedField],
        weighted: bool = True
    ) -> float:
        """Calculate overall confidence score."""
        if not fields:
            return 0.0
        
        total_confidence = 0.0
        total_weight = 0.0
        
        for name, field in fields.items():
            weight = self.field_weights.get(name, 0.1)
            if weighted:
                total_confidence += field.confidence * weight
                total_weight += weight
            else:
                total_confidence += field.confidence
                total_weight += 1
        
        if total_weight == 0:
            return 0.0
        
        return total_confidence / total_weight
    
    def get_confidence_level(self, confidence: float) -> ExtractionConfidence:
        """Get confidence level from score."""
        if confidence >= 0.8:
            return ExtractionConfidence.HIGH
        elif confidence >= 0.5:
            return ExtractionConfidence.MEDIUM
        return ExtractionConfidence.LOW
    
    # ===== Field Validators =====
    
    def _validate_invoice_number(self, value: Any, confidence: float) -> float:
        """Validate invoice number and adjust confidence."""
        if not value or not isinstance(value, str):
            return confidence * 0.3
        
        cleaned = re.sub(r'[^A-Za-z0-9\-]', '', value)
        if 4 <= len(cleaned) <= 25:
            return confidence
        return confidence * 0.5
    
    def _validate_vendor_name(self, value: Any, confidence: float) -> float:
        """Validate vendor name and adjust confidence."""
        if not value or not isinstance(value, str):
            return confidence * 0.3
        
        if len(value) < 2:
            return confidence * 0.3
        
        # Check for suspicious patterns
        if value.isupper() and len(value) > 20:
            return confidence * 0.7
        
        if len(re.findall(r'\d', value)) > len(value) * 0.3:
            return confidence * 0.6
        
        return confidence
    
    def _validate_amount(self, value: Any, confidence: float) -> float:
        """Validate amount and adjust confidence."""
        try:
            if isinstance(value, (int, float, Decimal)):
                if value >= 0 and value < 10**12:
                    return confidence
                return confidence * 0.5
            if isinstance(value, str):
                cleaned = re.sub(r'[$,€£]', '', value)
                if re.match(r'^\d*\.?\d+$', cleaned):
                    return confidence
                return confidence * 0.5
        except:
            pass
        return confidence * 0.3
    
    def _validate_date(self, value: Any, confidence: float) -> float:
        """Validate date and adjust confidence."""
        if isinstance(value, date):
            # Check if date is in a reasonable range
            if 1900 <= value.year <= 2100:
                return confidence
            return confidence * 0.5
        return confidence * 0.3
    
    def _validate_tax_id(self, value: Any, confidence: float) -> float:
        """Validate tax ID and adjust confidence."""
        if not value or not isinstance(value, str):
            return confidence * 0.3
        
        cleaned = re.sub(r'[^A-Za-z0-9]', '', value)
        if 5 <= len(cleaned) <= 15:
            return confidence
        return confidence * 0.5
    
    def _validate_line_items(self, value: Any, confidence: float) -> float:
        """Validate line items and adjust confidence."""
        if not value or not isinstance(value, list):
            return confidence * 0.3
        
        if len(value) == 0:
            return confidence * 0.5
        
        # Check if items have required fields
        valid_items = 0
        for item in value:
            if isinstance(item, dict) and 'description' in item:
                valid_items += 1
        
        item_ratio = valid_items / len(value) if value else 0
        return confidence * (0.5 + 0.5 * item_ratio)

