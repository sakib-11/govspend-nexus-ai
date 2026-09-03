"""Canonical data models for standardized transaction representation."""

from pydantic import BaseModel, Field, validator, ValidationError
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from enum import Enum
import re

class TransactionType(str, Enum):
    """Types of transactions."""
    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    PAYMENT = "payment"
    OTHER = "other"

class TransactionStatus(str, Enum):
    """Status of a transaction."""
    DRAFT = "draft"
    VALIDATED = "validated"
    CANONICALIZED = "canonicalized"
    REJECTED = "rejected"
    ERROR = "error"

class CurrencyCode(str, Enum):
    """Supported currency codes."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"
    CNY = "CNY"
    INR = "INR"
    OTHER = "OTHER"

class Vendor(BaseModel):
    """Canonical vendor information."""
    id: Optional[str] = None
    name: str
    tax_id: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    
    @validator('tax_id')
    def validate_tax_id(cls, v):
        if v is not None:
            # Remove spaces and dashes
            cleaned = re.sub(r'[\s\-]', '', v)
            if len(cleaned) < 5:
                raise ValueError(f"Tax ID too short: {v}")
        return v

class Buyer(BaseModel):
    """Canonical buyer information."""
    id: Optional[str] = None
    name: str
    department: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

class LineItem(BaseModel):
    """Canonical line item."""
    line_number: Optional[int] = Field(None, ge=1)
    description: str
    quantity: Decimal = Field(..., ge=0)
    unit_price: Decimal = Field(..., ge=0)
    total: Optional[Decimal] = Field(None, ge=0)
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    tax_amount: Optional[Decimal] = Field(None, ge=0)
    discount_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    discount_amount: Optional[Decimal] = Field(None, ge=0)
    product_code: Optional[str] = None
    unit_of_measure: Optional[str] = None
    
    @validator('total', always=True)
    def calculate_total(cls, v, values):
        """Calculate total if not provided."""
        if v is None and 'quantity' in values and 'unit_price' in values:
            return values['quantity'] * values['unit_price']
        return v
    
    @validator('tax_amount', always=True)
    def calculate_tax(cls, v, values):
        """Calculate tax amount if not provided."""
        if v is None and 'total' in values and 'tax_rate' in values:
            return values['total'] * values['tax_rate']
        return v

class CanonicalTransaction(BaseModel):
    """Canonical transaction model."""
    
    # Metadata
    id: Optional[str] = None
    source_id: str  # Original upload ID
    transaction_type: TransactionType = TransactionType.INVOICE
    status: TransactionStatus = TransactionStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    
    # Document identification
    document_number: str = Field(..., min_length=1, max_length=50)
    purchase_order: Optional[str] = None
    reference_number: Optional[str] = None
    
    # Dates
    document_date: date
    due_date: Optional[date] = None
    delivery_date: Optional[date] = None
    
    # Parties
    vendor: Vendor
    buyer: Buyer
    
    # Financials
    subtotal: Optional[Decimal] = Field(None, ge=0)
    tax_total: Optional[Decimal] = Field(None, ge=0)
    shipping_total: Optional[Decimal] = Field(None, ge=0)
    discount_total: Optional[Decimal] = Field(None, ge=0)
    total_amount: Decimal = Field(..., ge=0)
    currency: CurrencyCode = CurrencyCode.USD
    
    # Line items
    line_items: List[LineItem] = Field(default_factory=list)
    line_item_count: Optional[int] = Field(None, ge=0)
    
    # Payment terms
    payment_terms: Optional[str] = None
    payment_method: Optional[str] = None
    
    # Additional metadata
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Validation tracking
    validation_errors: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    is_valid: bool = True
    
    @validator('line_item_count', always=True)
    def calculate_line_item_count(cls, v, values):
        """Calculate line item count."""
        if v is None and 'line_items' in values:
            return len(values['line_items'])
        return v
    
    @validator('total_amount')
    def validate_total(cls, v, values):
        """Validate total amount consistency."""
        if 'subtotal' in values and values['subtotal']:
            subtotal = values['subtotal']
            tax = values.get('tax_total', 0)
            shipping = values.get('shipping_total', 0)
            discount = values.get('discount_total', 0)
            
            expected_total = subtotal + tax + shipping - discount
            
            # Allow small rounding differences
            if abs(v - expected_total) > Decimal('0.01'):
                raise ValueError(
                    f"Total amount {v} does not match calculated total {expected_total} "
                    f"(subtotal={subtotal}, tax={tax}, shipping={shipping}, discount={discount})"
                )
        return v
    
    @validator('document_number')
    def validate_document_number(cls, v):
        """Validate document number format."""
        if not v or len(v) < 2:
            raise ValueError(f"Document number too short: {v}")
        # Should contain at least one letter or number
        if not re.search(r'[A-Za-z0-9]', v):
            raise ValueError(f"Document number must contain alphanumeric characters: {v}")
        return v.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper formatting."""
        return self.dict(exclude={'validation_errors', 'validation_warnings', 'is_valid'})
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        import json
        return json.dumps(self.to_dict(), default=str, indent=2)
