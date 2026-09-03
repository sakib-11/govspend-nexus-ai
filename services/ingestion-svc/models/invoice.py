"""Invoice data models for the Ingestion Service."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ============================================================================
# ENUMS
# ============================================================================

class InvoiceStatus(str, Enum):
    """Invoice processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    FAILED = "failed"
    REJECTED = "rejected"


# ============================================================================
# VENDOR
# ============================================================================

class Vendor(BaseModel):
    """Vendor information."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="ignore",
    )

    id: Optional[str] = None

    name: str = Field(
        ...,
        min_length=2,
        max_length=200,
    )

    tax_id: Optional[str] = None
    registration_number: Optional[str] = None
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_vendor_name(cls, value: str) -> str:
        """Validate vendor name."""
        value = value.strip()

        if len(value) < 2:
            raise ValueError(
                "Vendor name must be at least 2 characters."
            )

        return value


# ============================================================================
# BUYER
# ============================================================================

class Buyer(BaseModel):
    """Buyer information."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="ignore",
    )

    id: Optional[str] = None
    name: str = Field(
        ...,
        min_length=2,
        max_length=200,
    )

    department: Optional[str] = None
    cost_center: Optional[str] = None
    purchase_order: Optional[str] = None


# ============================================================================
# LINE ITEM
# ============================================================================

class LineItem(BaseModel):
    """Invoice line item."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="ignore",
    )

    id: Optional[str] = None

    description: str = ""

    quantity: float = Field(
        default=1.0,
        gt=0,
    )

    unit_price: float = Field(
        default=0.0,
        ge=0,
    )

    total: Optional[float] = None

    # Alias used by some downstream systems.
    total_price: Optional[float] = None

    tax: float = Field(
        default=0.0,
        ge=0,
    )

    discount: float = Field(
        default=0.0,
        ge=0,
    )

    tax_rate: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )

    tax_amount: Optional[float] = Field(
        default=None,
        ge=0,
    )

    product_code: Optional[str] = None
    uom: Optional[str] = None

    @model_validator(mode="after")
    def calculate_and_validate_total(self):
        """
        Ensure total and total_price remain consistent.

        Allows small rounding differences in OCR-derived values.
        """
        expected_total = self.quantity * self.unit_price

        # If neither value was supplied, calculate it.
        if self.total is None and self.total_price is None:
            self.total = round(expected_total, 2)
            self.total_price = self.total
            return self

        # If only total_price exists, use it as total.
        if self.total is None and self.total_price is not None:
            self.total = self.total_price

        # If only total exists, use it as total_price.
        if self.total_price is None and self.total is not None:
            self.total_price = self.total

        actual_total = (
            self.total
            if self.total is not None
            else self.total_price
        )

        if actual_total is None:
            return self

        # Avoid rejecting zero-priced OCR items.
        if expected_total > 0:
            lower_bound = expected_total * 0.99
            upper_bound = expected_total * 1.01

            if not (
                lower_bound
                <= actual_total
                <= upper_bound
            ):
                raise ValueError(
                    "Line item total mismatch: "
                    f"expected approximately {expected_total:.2f}, "
                    f"got {actual_total:.2f}"
                )

        return self


# ============================================================================
# INVOICE DATA
# ============================================================================

class InvoiceData(BaseModel):
    """Structured invoice data extracted from OCR."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------------
    # Invoice identification
    # ------------------------------------------------------------------------

    invoice_number: Optional[str] = None
    purchase_order: Optional[str] = None

    # ------------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------------

    invoice_date: Optional[date] = None
    due_date: Optional[date] = None

    # ------------------------------------------------------------------------
    # Vendor
    # ------------------------------------------------------------------------

    vendor_name: Optional[str] = None
    vendor_tax_id: Optional[str] = None
    vendor_address: Optional[str] = None
    vendor: Optional[Vendor] = None

    # ------------------------------------------------------------------------
    # Buyer
    # ------------------------------------------------------------------------

    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None
    buyer: Optional[Buyer] = None

    # ------------------------------------------------------------------------
    # Financial information
    # ------------------------------------------------------------------------

    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    discount_amount: Optional[float] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None

    # ------------------------------------------------------------------------
    # Line items
    # ------------------------------------------------------------------------

    line_items: Optional[List[LineItem]] = None

    # ------------------------------------------------------------------------
    # Additional invoice information
    # ------------------------------------------------------------------------

    payment_terms: Optional[str] = None
    notes: Optional[str] = None

    @field_validator(
        "invoice_date",
        "due_date",
        mode="before",
    )
    @classmethod
    def parse_date(
        cls,
        value: Any,
    ) -> Any:
        """Parse common invoice date formats."""

        if value is None:
            return None

        if isinstance(value, date):
            return value

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

            formats = (
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%Y%m%d",
                "%Y/%m/%d",
                "%d-%m-%Y",
                "%d.%m.%Y",
            )

            for fmt in formats:
                try:
                    return datetime.strptime(
                        value,
                        fmt,
                    ).date()
                except ValueError:
                    continue

        return value

    @field_validator(
        "total_amount",
        "subtotal",
        "tax_amount",
        "discount_amount",
        mode="before",
    )
    @classmethod
    def parse_amount(
        cls,
        value: Any,
    ) -> Optional[float]:
        """Parse monetary values safely."""

        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

            # Remove common currency symbols and separators.
            import re

            cleaned = re.sub(
                r"[^\d.\-]",
                "",
                value,
            )

            if not cleaned:
                return None

            try:
                return float(cleaned)
            except ValueError:
                return None

        return value


# ============================================================================
# UPLOAD REQUEST
# ============================================================================

class InvoiceUploadRequest(BaseModel):
    """Request model for invoice upload."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="ignore",
    )

    source_id: str = Field(
        ...,
        description="Source system identifier",
    )

    document_number: Optional[str] = None
    document_date: Optional[date] = None

    expected_vendor: Optional[str] = None

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )

    @field_validator(
        "document_date",
        mode="before",
    )
    @classmethod
    def parse_document_date(
        cls,
        value: Any,
    ) -> Any:
        """Parse document date."""

        if value is None:
            return None

        if isinstance(value, date):
            return value

        if isinstance(value, str):
            value = value.strip()

            for fmt in (
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%Y%m%d",
            ):
                try:
                    return datetime.strptime(
                        value,
                        fmt,
                    ).date()
                except ValueError:
                    continue

        return value


# ============================================================================
# RESPONSE MODEL
# ============================================================================

class InvoiceResponse(BaseModel):
    """Unified invoice processing response."""

    model_config = ConfigDict(
        use_enum_values=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------------

    id: Optional[str] = None
    upload_id: Optional[str] = None

    source_id: Optional[str] = None

    filename: str

    # ------------------------------------------------------------------------
    # Processing state
    # ------------------------------------------------------------------------

    status: InvoiceStatus = InvoiceStatus.PROCESSING

    # ------------------------------------------------------------------------
    # Extracted invoice
    # ------------------------------------------------------------------------

    invoice_data: Optional[InvoiceData] = None

    # Newer structured representation.
    vendor: Optional[Vendor] = None
    buyer: Optional[Buyer] = None

    total_amount: Optional[float] = None
    document_date: Optional[date] = None

    # ------------------------------------------------------------------------
    # OCR / extraction
    # ------------------------------------------------------------------------

    extracted_data: Optional[Dict[str, Any]] = None
    extracted_fields: Optional[Dict[str, Any]] = None

    ocr_confidence: float = Field(
        default=0.0,
        ge=0,
        le=1,
    )

    confidence_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
    )

    ocr_engine: str = "tesseract"

    page_count: int = Field(
        default=0,
        ge=0,
    )

    # ------------------------------------------------------------------------
    # Processing metadata
    # ------------------------------------------------------------------------

    processing_time_seconds: float = Field(
        default=0.0,
        ge=0,
    )

    processing_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
    )

    # ------------------------------------------------------------------------
    # Validation / errors
    # ------------------------------------------------------------------------

    warnings: List[str] = Field(
        default_factory=list
    )

    validation_errors: List[str] = Field(
        default_factory=list
    )

    error_message: Optional[str] = None

    # ------------------------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------------------------

    created_at: datetime = Field(
        default_factory=datetime.now
    )

    timestamp: Optional[datetime] = None

    @model_validator(mode="after")
    def normalize_response(self):
        """Synchronize compatible fields from both response formats."""

        # upload_id <-> id
        if self.upload_id is None and self.id is not None:
            self.upload_id = self.id

        if self.id is None and self.upload_id is not None:
            self.id = self.upload_id

        # processing time conversion
        if (
            self.processing_time_ms is None
            and self.processing_time_seconds > 0
        ):
            self.processing_time_ms = int(
                self.processing_time_seconds * 1000
            )

        if (
            self.processing_time_seconds == 0
            and self.processing_time_ms is not None
        ):
            self.processing_time_seconds = (
                self.processing_time_ms / 1000.0
            )

        # Confidence synchronization
        if (
            self.confidence_score is None
            and self.ocr_confidence is not None
        ):
            self.confidence_score = self.ocr_confidence

        if (
            self.ocr_confidence == 0
            and self.confidence_score is not None
        ):
            self.ocr_confidence = self.confidence_score

        # Timestamp synchronization
        if self.timestamp is None:
            self.timestamp = self.created_at

        return self


# ============================================================================
# SIMPLE UPLOAD RESPONSE
# ============================================================================

class UploadResponse(BaseModel):
    """Response returned by the upload endpoint."""

    model_config = ConfigDict(
        use_enum_values=True,
        extra="ignore",
    )

    upload_id: str
    filename: str

    status: InvoiceStatus = InvoiceStatus.PROCESSING

    processing_time_seconds: float = Field(
        default=0.0,
        ge=0,
    )

    invoice_data: Optional[InvoiceData] = None

    ocr_confidence: float = Field(
        default=0.0,
        ge=0,
        le=1,
    )

    ocr_engine: str = "tesseract"

    page_count: int = Field(
        default=0,
        ge=0,
    )

    warnings: List[str] = Field(
        default_factory=list
    )

    extracted_fields: Optional[Dict[str, Any]] = None

    timestamp: datetime = Field(
        default_factory=datetime.now
    )
