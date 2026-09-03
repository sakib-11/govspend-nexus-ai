"""Validation utilities — input sanitisation and PII detection helpers."""

from __future__ import annotations

import re
from typing import List, Optional, Set

# Precompiled PII-detection patterns ------------------------------------------
_PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
_GST_RE = re.compile(
    r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z0-9][0-9]\b"
)
_UPI_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z]{2,}\b")
_PHONE_RE = re.compile(r"\b[6-9][0-9]{9}\b")
_EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
)
_AADHAAR_RE = re.compile(r"\b[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\b")
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")


def contains_pii(value: str) -> List[str]:
    """Detect PII patterns in a string value.

    Returns a list of detected PII type labels (e.g. ``["pan", "phone"]``).
    """
    detected: List[str] = []
    if _PAN_RE.search(value):
        detected.append("pan")
    if _GST_RE.search(value):
        detected.append("gst")
    if _UPI_RE.search(value):
        detected.append("upi")
    if _PHONE_RE.search(value):
        detected.append("phone")
    if _EMAIL_RE.search(value):
        detected.append("email")
    if _AADHAAR_RE.search(value):
        detected.append("aadhaar")
    if _IFSC_RE.search(value):
        detected.append("ifsc")
    return detected


# Well-known PII field name patterns -----------------------------------------

_PII_FIELD_KEYWORDS: Set[str] = frozenset({
    "pan", "gst", "upi", "bank_account", "account_number",
    "phone", "email", "address", "aadhaar", "ifsc",
    "vendor_name", "vendor_id", "official_name", "official_id",
    "invoice_number", "po_number", "name", "mobile",
})


def field_looks_like_pii(field_name: str) -> bool:
    """Return ``True`` if *field_name* is likely a PII-carrying field."""
    lower = field_name.lower()
    for kw in _PII_FIELD_KEYWORDS:
        if kw in lower:
            return True
    return False


def sanitise_identifier(value: str) -> str:
    """Strip whitespace and control characters from an identifier."""
    return re.sub(r"[\x00-\x1f\x7f]", "", value).strip()


def validate_entity_type(entity_type: str) -> Optional[str]:
    """Return normalised entity type or ``None`` if invalid."""
    allowed = {
        "vendor", "official", "transaction", "invoice",
        "department", "user", "case", "evidence", "generic",
    }
    normalised = entity_type.lower().strip()
    return normalised if normalised in allowed else None
