"""Field mapping with context awareness and fallback strategies."""

from typing import Dict, Any, Optional, List, Tuple
import re
from decimal import Decimal
from datetime import date
import logging

from .heuristic_rules import HeuristicRulesEngine
from ...models.extraction import ExtractedField, ExtractionResult

logger = logging.getLogger(__name__)

class FieldMapper:
    """Map OCR-extracted fields with context awareness."""
    
    def __init__(self):
        self.rules_engine = HeuristicRulesEngine()
        self.field_contexts = self._initialize_contexts()
        
    def _initialize_contexts(self) -> Dict[str, Dict[str, Any]]:
        """Initialize field contexts for better extraction."""
        return {
            'vendor_name': {
                'context_words': ['vendor', 'supplier', 'from', 'seller', 'company'],
                'exclude_words': ['invoice', 'statement', 'payment', 'total'],
                'min_length': 2,
                'max_length': 40,
            },
            'total_amount': {
                'context_words': ['total', 'grand total', 'amount due', 'payment due'],
                'exclude_words': ['subtotal', 'tax', 'shipping'],
            },
            'invoice_number': {
                'context_words': ['invoice', 'inv', 'document', 'bill'],
                'pattern': r'^[A-Z0-9\-]{6,20}$',
            },
        }
    
    def map_fields(
        self,
        text: str,
        lines: List[str],
        ocr_results: Dict[str, Any]
    ) -> Dict[str, ExtractedField]:
        """Map all fields from OCR results."""
        extracted_fields = {}
        
        # 1. Extract using heuristic rules
        for field_name in self.rules_engine.rules.keys():
            results = self.rules_engine.extract_with_rules(text, field_name)
            if results:
                best_value, confidence, raw_text = results[0]
                extracted_fields[field_name] = ExtractedField(
                    name=field_name,
                    value=best_value,
                    confidence=confidence,
                    alternatives=[r[0] for r in results[1:3]],
                    source="heuristic_rules",
                    raw_text=raw_text
                )
        
        # 2. Extract line items
        line_items = self._extract_line_items(text, lines)
        if line_items:
            extracted_fields['line_items'] = ExtractedField(
                name='line_items',
                value=line_items,
                confidence=0.7,
                source="line_item_extraction",
                raw_text='\n'.join([li.get('raw_text', '') for li in line_items])
            )
        
        # 3. Validate and clean fields
        extracted_fields = self._validate_fields(extracted_fields)
        
        # 4. Fill missing fields from OCR results
        extracted_fields = self._fill_missing_from_ocr(extracted_fields, ocr_results)
        
        return extracted_fields
    
    def _extract_line_items(self, text: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Extract line items from text."""
        line_items = []
        in_line_item_section = False
        
        # Detect line item section
        section_markers = [
            r'(?:ITEM|LINE|QTY|DESCRIPTION|PRICE|AMOUNT)',
            r'QTY\s+DESCRIPTION\s+UNIT PRICE\s+AMOUNT',
        ]
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Check if we're in a line item section
            if not in_line_item_section:
                for marker in section_markers:
                    if re.search(marker, line, re.IGNORECASE):
                        in_line_item_section = True
                        break
            
            # Extract line items
            if in_line_item_section and line:
                item = self._parse_line_item(line)
                if item:
                    line_items.append(item)
            
            # End of line item section
            if in_line_item_section and re.search(r'(?:SUBTOTAL|TOTAL|TAX)', line, re.IGNORECASE):
                in_line_item_section = False
        
        return line_items
    
    def _parse_line_item(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single line item."""
        # Try different patterns
        patterns = [
            # Pattern: Qty Description @ Unit Price = Total
            r'(\d+)\s+([A-Za-z0-9\s\.,\-]+)\s+@\s+([\d,]+\.?\d*)\s*=\s*([\d,]+\.?\d*)',
            # Pattern: Description | Qty | Price | Total (pipe or tab separated)
            r'^([A-Za-z0-9\s\.,\-]+)\s*[|\t]\s*(\d+)\s*[|\t]\s*([\d,]+\.?\d*)\s*[|\t]\s*([\d,]+\.?\d*)',
            # Pattern: Qty x Description @ Price
            r'(\d+)\s*[xX×]\s*([A-Za-z0-9\s\.,\-]+)\s+@\s+([\d,]+\.?\d*)',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 3:
                    try:
                        item = {
                            'raw_text': line,
                            'description': groups[1] if len(groups) > 1 else groups[0],
                            'quantity': int(re.sub(r'[^\d]', '', groups[0])),
                            'unit_price': Decimal(re.sub(r'[$,]', '', groups[2])),
                        }
                        if len(groups) >= 4:
                            item['total'] = Decimal(re.sub(r'[$,]', '', groups[3]))
                        else:
                            item['total'] = item['quantity'] * item['unit_price']
                        
                        # Clean description
                        item['description'] = re.sub(r'^\d+\s*', '', item['description'])
                        item['description'] = item['description'].strip()
                        
                        return item
                    except:
                        continue
        
        return None
    
    def _validate_fields(self, fields: Dict[str, ExtractedField]) -> Dict[str, ExtractedField]:
        """Validate extracted fields."""
        validated = {}
        
        for name, field in fields.items():
            # Skip None values
            if field.value is None:
                continue
            
            # Validate based on field type
            if name == 'vendor_name':
                if not self._validate_vendor_name(field.value):
                    field.confidence *= 0.5
                    field.validation_errors.append("Invalid vendor name format")
            
            elif name in ['total_amount', 'subtotal', 'tax_total']:
                if not self._validate_amount(field.value):
                    field.confidence *= 0.5
                    field.validation_errors.append("Invalid amount format")
            
            elif name == 'date' or name == 'due_date':
                if not self._validate_date(field.value):
                    field.confidence *= 0.5
                    field.validation_errors.append("Invalid date format")
            
            elif name == 'invoice_number':
                if not self._validate_invoice_number(field.value):
                    field.confidence *= 0.5
                    field.validation_errors.append("Invalid invoice number format")
            
            field.validated = len(field.validation_errors) == 0
            validated[name] = field
        
        return validated
    
    def _validate_vendor_name(self, name: str) -> bool:
        """Validate vendor name."""
        if not name or len(name) < 2:
            return False
        # Should not be all caps or contain too many numbers
        if name.isupper() and len(name) > 20:
            return False
        if len(re.findall(r'\d', name)) > len(name) * 0.3:
            return False
        return True
    
    def _validate_amount(self, amount: Any) -> bool:
        """Validate amount."""
        try:
            if isinstance(amount, (int, float, Decimal)):
                return amount >= 0
            if isinstance(amount, str):
                cleaned = re.sub(r'[$,€£]', '', amount)
                return bool(re.match(r'^\d*\.?\d+$', cleaned))
        except:
            pass
        return False
    
    def _validate_date(self, date_val: Any) -> bool:
        """Validate date."""
        if isinstance(date_val, date):
            return True
        if isinstance(date_val, str):
            return bool(re.match(r'\d{4}-\d{2}-\d{2}', date_val))
        return False
    
    def _validate_invoice_number(self, inv_num: str) -> bool:
        """Validate invoice number format."""
        if not inv_num:
            return False
        # Should be alphanumeric with some dashes
        cleaned = re.sub(r'[^A-Za-z0-9]', '', inv_num)
        return len(cleaned) >= 4 and len(cleaned) <= 25
    
    def _fill_missing_from_ocr(
        self,
        fields: Dict[str, ExtractedField],
        ocr_results: Dict[str, Any]
    ) -> Dict[str, ExtractedField]:
        """Fill missing fields from OCR results."""
        # If vendor_name is missing, try to get from OCR
        if 'vendor_name' not in fields or not fields['vendor_name'].value:
            for key in ['vendor', 'supplier', 'company']:
                if key in ocr_results:
                    fields['vendor_name'] = ExtractedField(
                        name='vendor_name',
                        value=ocr_results[key],
                        confidence=0.3,
                        source="ocr_fallback",
                        raw_text=str(ocr_results[key])
                    )
                    break
        
        # If total_amount is missing, try to calculate from line items
        if 'total_amount' not in fields and 'line_items' in fields:
            line_items = fields['line_items'].value
            if line_items:
                total = sum(item.get('total', 0) for item in line_items if 'total' in item)
                if total > 0:
                    fields['total_amount'] = ExtractedField(
                        name='total_amount',
                        value=total,
                        confidence=0.5,
                        source="calculated_from_line_items"
                    )
        
        return fields

