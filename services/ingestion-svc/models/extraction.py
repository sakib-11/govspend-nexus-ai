"""Extraction models for OCR pipeline."""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

class ExtractionConfidence(str, Enum):
    HIGH = "high"      # > 0.8
    MEDIUM = "medium"  # 0.5 - 0.8
    LOW = "low"        # < 0.5
    
class FieldMatch(BaseModel):
    """A field match with confidence."""
    value: Any
    confidence: float
    source: str  # Which extractor found it
    raw_text: Optional[str] = None
    
class ExtractedField(BaseModel):
    """An extracted field with metadata."""
    name: str
    value: Any
    confidence: float
    alternatives: List[Any] = []
    source: str
    raw_text: Optional[str] = None
    validated: bool = False
    validation_errors: List[str] = []
    
    @property
    def confidence_level(self) -> ExtractionConfidence:
        if self.confidence >= 0.8:
            return ExtractionConfidence.HIGH
        elif self.confidence >= 0.5:
            return ExtractionConfidence.MEDIUM
        return ExtractionConfidence.LOW

class ExtractionResult(BaseModel):
    """Complete extraction result."""
    upload_id: str
    extracted_fields: Dict[str, ExtractedField]
    confidence_scores: Dict[str, float]
    overall_confidence: float
    extraction_time_ms: float
    warnings: List[str] = []
    errors: List[str] = []
    
    @property
    def is_high_confidence(self) -> bool:
        return self.overall_confidence >= 0.8
    
    @property
    def missing_required_fields(self) -> List[str]:
        required = ["vendor_name", "total_amount", "invoice_number", "date"]
        return [f for f in required if f not in self.extracted_fields]
    
    def get_field_value(self, field_name: str, default: Any = None) -> Any:
        if field_name in self.extracted_fields:
            return self.extracted_fields[field_name].value
        return default

class LineItemExtraction(BaseModel):
    """Extracted line item."""
    description: str
    quantity: Optional[int] = None
    unit_price: Optional[Decimal] = None
    total: Optional[Decimal] = None
    line_number: Optional[int] = None
    confidence: float = 0.0
    raw_text: Optional[str] = None

class VendorInfo(BaseModel):
    """Extracted vendor information."""
    name: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    confidence: float = 0.0

class InvoiceExtraction(BaseModel):
    """Complete invoice extraction with all fields."""
    upload_id: str
    
    # Core fields
    invoice_number: Optional[str] = None
    purchase_order: Optional[str] = None
    date: Optional[date] = None
    due_date: Optional[date] = None
    
    # Vendor info
    vendor: Optional[VendorInfo] = None
    
    # Financials
    subtotal: Optional[Decimal] = None
    tax_total: Optional[Decimal] = None
    shipping_total: Optional[Decimal] = None
    discount_total: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    currency: str = "USD"
    
    # Line items
    line_items: List[LineItemExtraction] = []
    line_item_count: Optional[int] = None
    
    # Metadata
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    
    # Confidence
    overall_confidence: float = 0.0
    field_confidences: Dict[str, float] = {}
    
    # Raw data
    raw_text: Optional[str] = None
    
    @validator('date', 'due_date', pre=True)
    def parse_date(cls, v):
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y%m%d', '%b %d, %Y', '%d %b %Y']:
                try:
                    return datetime.strptime(v, fmt).date()
                except ValueError:
                    continue
        return v
    
    @validator('total_amount', 'subtotal', 'tax_total', pre=True)
    def parse_amount(cls, v):
        if isinstance(v, (int, float, Decimal)):
            return Decimal(str(v))
        if isinstance(v, str):
            # Remove currency symbols and commas
            cleaned = re.sub(r'[$,€£]', '', v).strip()
            try:
                return Decimal(cleaned)
            except:
                return None
        return 
