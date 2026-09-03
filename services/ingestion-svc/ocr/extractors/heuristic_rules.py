"""Heuristic rules for intelligent field extraction."""

import re
from typing import Dict, Any, Optional, List, Tuple, Pattern
from decimal import Decimal
from datetime import datetime, date
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class ExtractionRule:
    """A single extraction rule with confidence."""
    pattern: Pattern
    field_name: str
    confidence: float = 0.7
    post_process: Optional[callable] = None
    priority: int = 1  # Higher = higher priority
    context_required: Optional[List[str]] = None

class HeuristicRulesEngine:
    """Heuristic rules engine for extracting fields from OCR text."""
    
    def __init__(self):
        self.rules: Dict[str, List[ExtractionRule]] = {}
        self._initialize_rules()
        
    def _initialize_rules(self):
        """Initialize all heuristic extraction rules."""
        
        # ===== Invoice Number Rules =====
        self.rules['invoice_number'] = [
            ExtractionRule(
                pattern=re.compile(r'(?:INVOICE|INV|DOCUMENT|BILL)[\s#:]+([A-Z0-9\-]{6,20})', re.IGNORECASE),
                field_name='invoice_number',
                confidence=0.9,
                priority=3
            ),
            ExtractionRule(
                pattern=re.compile(r'(?:INV|DOC)[\s#:]*([A-Z0-9\-]{6,15})', re.IGNORECASE),
                field_name='invoice_number',
                confidence=0.8,
                priority=2
            ),
            ExtractionRule(
                pattern=re.compile(r'#\s*([A-Z0-9\-]{6,20})', re.IGNORECASE),
                field_name='invoice_number',
                confidence=0.6,
                priority=1
            ),
        ]
        
        # ===== Purchase Order Rules =====
        self.rules['purchase_order'] = [
            ExtractionRule(
                pattern=re.compile(r'(?:PURCHASE ORDER|P\.?O\.?|ORDER)[\s#:]+([A-Z0-9\-]{5,20})', re.IGNORECASE),
                field_name='purchase_order',
                confidence=0.9,
                priority=3
            ),
            ExtractionRule(
                pattern=re.compile(r'PO\s*[:#]*\s*([A-Z0-9\-]{5,20})', re.IGNORECASE),
                field_name='purchase_order',
                confidence=0.85,
                priority=2
            ),
        ]
        
        # ===== Date Rules =====
        date_patterns = [
            r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b',  # MM/DD/YYYY or DD/MM/YYYY
            r'\b(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\b',  # YYYY-MM-DD
            r'\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b',  # Month DD, YYYY
            r'\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b',  # DD Month YYYY
            r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})\b',  # MM/DD/YY or DD/MM/YY
        ]
        
        # Date rules with post-processing
        self.rules['date'] = [
            ExtractionRule(
                pattern=re.compile(r'(?:DATE|INVOICE DATE|BILL DATE)[\s:]+(.*?)(?:\n|$)', re.IGNORECASE),
                field_name='date',
                confidence=0.9,
                priority=3,
                post_process=self._parse_date_from_text
            ),
            ExtractionRule(
                pattern=re.compile(r'(?:DATE|DATED|DT)[\s:]+(.*?)(?:\n|$)', re.IGNORECASE),
                field_name='date',
                confidence=0.75,
                priority=2,
                post_process=self._parse_date_from_text
            ),
        ]
        
        self.rules['due_date'] = [
            ExtractionRule(
                pattern=re.compile(r'(?:DUE DATE|PAYMENT DUE|DUE ON)[\s:]+(.*?)(?:\n|$)', re.IGNORECASE),
                field_name='due_date',
                confidence=0.85,
                priority=2,
                post_process=self._parse_date_from_text
            ),
            ExtractionRule(
                pattern=re.compile(r'DUE[\s:]+(.*?)(?:\n|$)', re.IGNORECASE),
                field_name='due_date',
                confidence=0.6,
                priority=1,
                post_process=self._parse_date_from_text
            ),
        ]
        
        # ===== Vendor Name Rules =====
        self.rules['vendor_name'] = [
            ExtractionRule(
                pattern=re.compile(r'(?:VENDOR|SUPPLIER|FROM|SELLER)[\s:]+([A-Za-z\s\.&\',\-]{2,40})', re.IGNORECASE),
                field_name='vendor_name',
                confidence=0.9,
                priority=3
            ),
            ExtractionRule(
                pattern=re.compile(r'^(?:[A-Z][a-z]*\s+){2,5}(?:Inc|LLC|Corp|Ltd|Co|Company|Corporation)\.?$', re.MULTILINE),
                field_name='vendor_name',
                confidence=0.7,
                priority=2
            ),
        ]
        
        # ===== Vendor Tax ID Rules =====
        self.rules['vendor_tax_id'] = [
            ExtractionRule(
                pattern=re.compile(r'(?:TAX ID|EIN|VAT|GST|TIN)[\s:]+([A-Z0-9\-]{5,15})', re.IGNORECASE),
                field_name='vendor_tax_id',
                confidence=0.85,
                priority=2
            ),
            ExtractionRule(
                pattern=re.compile(r'\b(\d{2}-\d{7})\b'),  # US EIN
                field_name='vendor_tax_id',
                confidence=0.6,
                priority=1
            ),
        ]
        
        # ===== Amount Rules =====
        amount_patterns = [
            r'(?:TOTAL|TOTAL AMOUNT|GRAND TOTAL|AMOUNT DUE)[\s$:]+([\d,]+\.?\d*)',
            r'(?:SUBTOTAL|SUB TOTAL)[\s$:]+([\d,]+\.?\d*)',
            r'(?:TAX|VAT|GST)[\s$:]+([\d,]+\.?\d*)',
            r'(?:SHIPPING|DELIVERY)[\s$:]+([\d,]+\.?\d*)',
            r'(?:DISCOUNT)[\s$:]+([\d,]+\.?\d*)',
        ]
        
        self.rules['total_amount'] = [
            ExtractionRule(
                pattern=re.compile(r'(?:GRAND TOTAL|TOTAL AMOUNT)[\s$:]+([\d,]+\.?\d*)', re.IGNORECASE),
                field_name='total_amount',
                confidence=0.95,
                priority=3,
                post_process=self._parse_currency_amount
            ),
            ExtractionRule(
                pattern=re.compile(r'(?:TOTAL|AMOUNT DUE)[\s$:]+([\d,]+\.?\d*)', re.IGNORECASE),
                field_name='total_amount',
                confidence=0.85,
                priority=2,
                post_process=self._parse_currency_amount
            ),
            ExtractionRule(
                pattern=re.compile(r'TOTAL[\s$:]*([\d,]+\.?\d*)', re.IGNORECASE),
                field_name='total_amount',
                confidence=0.7,
                priority=1,
                post_process=self._parse_currency_amount
            ),
        ]
        
        self.rules['subtotal'] = [
            ExtractionRule(
                pattern=re.compile(r'SUBTOTAL[\s$:]+([\d,]+\.?\d*)', re.IGNORECASE),
                field_name='subtotal',
                confidence=0.85,
                priority=2,
                post_process=self._parse_currency_amount
            ),
        ]
        
        self.rules['tax_total'] = [
            ExtractionRule(
                pattern=re.compile(r'(?:TAX|VAT|GST)[\s$:]+([\d,]+\.?\d*)', re.IGNORECASE),
                field_name='tax_total',
                confidence=0.8,
                priority=2,
                post_process=self._parse_currency_amount
            ),
        ]
        
        # ===== Payment Terms Rules =====
        self.rules['payment_terms'] = [
            ExtractionRule(
                pattern=re.compile(r'PAYMENT\s*TERMS?[\s:]+([A-Za-z\s\d]+)(?:\n|$)', re.IGNORECASE),
                field_name='payment_terms',
                confidence=0.8,
                priority=2
            ),
            ExtractionRule(
                pattern=re.compile(r'TERMS:?\s*([A-Za-z\s\d]+)(?:\n|$)', re.IGNORECASE),
                field_name='payment_terms',
                confidence=0.6,
                priority=1
            ),
        ]
        
        # ===== Currency Rules =====
        self.rules['currency'] = [
            ExtractionRule(
                pattern=re.compile(r'(USD|EUR|GBP|JPY|CAD|AUD|CNY)'),
                field_name='currency',
                confidence=0.9,
                priority=2
            ),
        ]
    
    def extract_with_rules(self, text: str, field_name: str) -> List[Tuple[Any, float, str]]:
        """
        Extract a specific field using all matching rules.
        
        Returns:
            List of (value, confidence, matched_text) tuples
        """
        results = []
        
        if field_name not in self.rules:
            return results
        
        for rule in self.rules[field_name]:
            try:
                matches = rule.pattern.finditer(text)
                for match in matches:
                    if match.groups():
                        value = match.group(1)
                        
                        # Apply post-processing if available
                        if rule.post_process:
                            try:
                                value = rule.post_process(value)
                            except Exception as e:
                                logger.debug(f"Post-processing failed for {field_name}: {e}")
                                continue
                        
                        if value is not None:
                            results.append((
                                value,
                                rule.confidence,
                                match.group(0)
                            ))
            except Exception as e:
                logger.warning(f"Rule execution failed for {field_name}: {e}")
                continue
        
        # Sort by confidence (highest first)
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def _parse_date_from_text(self, date_str: str) -> Optional[date]:
        """Parse date from various text formats."""
        date_str = date_str.strip()
        
        # Try common date formats
        formats = [
            '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d',
            '%b %d, %Y', '%d %b %Y', '%B %d, %Y', '%d %B %Y',
            '%m-%d-%Y', '%d-%m-%Y',
            '%m/%d/%y', '%d/%m/%y', '%m-%d-%y', '%d-%m-%y',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        return None
    
    def _parse_currency_amount(self, amount_str: str) -> Optional[Decimal]:
        """Parse currency amount from string."""
        # Remove currency symbols and whitespace
        cleaned = re.sub(r'[$,€£\s]', '', amount_str)
        
        # Handle negative amounts
        negative = False
        if cleaned.startswith('-'):
            negative = True
            cleaned = cleaned[1:]
        
        try:
            amount = Decimal(cleaned)
            if negative:
                amount = -amount
            return amount
        except:
            return None
    
    def _is_valid_vendor_name(self, name: str) -> bool:
        """Validate vendor name format."""
        if not name or len(name) < 2 or len(name) > 40:
            return False
        # Check if it has at least two words
        words = name.strip().split()
        return len(words) >= 2

