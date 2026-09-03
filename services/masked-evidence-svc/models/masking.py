"""Masking models — entity types, PII fields, and masking rules."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Types of entities that can be masked."""

    VENDOR = "vendor"
    OFFICIAL = "official"
    TRANSACTION = "transaction"
    INVOICE = "invoice"
    DEPARTMENT = "department"
    USER = "user"
    CASE = "case"
    EVIDENCE = "evidence"
    GENERIC = "generic"


class PIIField(str, Enum):
    """PII fields that require masking."""

    PAN = "pan"
    GST = "gst"
    UPI = "upi"
    BANK_ACCOUNT = "bank_account"
    PHONE = "phone"
    EMAIL = "email"
    ADDRESS = "address"
    AADHAAR = "aadhaar"
    NAME = "name"
    VENDOR_NAME = "vendor_name"
    VENDOR_ID = "vendor_id"
    OFFICIAL_NAME = "official_name"
    OFFICIAL_ID = "official_id"
    INVOICE_NUMBER = "invoice_number"
    PO_NUMBER = "po_number"
    ACCOUNT_NUMBER = "account_number"


class MaskingLevel(str, Enum):
    """Masking levels based on user role."""

    FULL = "full"       # Level 3+: everything visible
    PARTIAL = "partial"  # Level 2: PII masked, data visible
    MINIMAL = "minimal"  # Level 1: only aggregate data


class MaskingRule(BaseModel):
    """Rule for masking a specific PII field type."""

    field_type: str
    pattern: Optional[str] = None
    mask_character: str = "*"
    preserve_start: int = 2
    preserve_end: int = 0


class TokenMapping(BaseModel):
    """Mapping between a token and the hash of its raw identifier."""

    token: str
    raw_identifier_hash: str
    entity_type: str
    prefix: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
