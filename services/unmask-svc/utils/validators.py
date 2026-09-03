"""Validators — input validation helpers for the unmask service."""

from __future__ import annotations

import re
from typing import List, Optional

from models.unmask import UnmaskEntityType, UnmaskStatus


# Allowed entity types for validation
_VALID_ENTITY_TYPES: frozenset[str] = frozenset(t.value for t in UnmaskEntityType)

# Allowed status values
_VALID_STATUSES: frozenset[str] = frozenset(s.value for s in UnmaskStatus)

# Token format: alphanumeric with hyphens/underscores, max 256 chars
_TOKEN_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,256}$")


def validate_entity_token(token: str) -> bool:
    """Return True if *token* looks like a valid entity token."""
    return bool(_TOKEN_RE.match(token))


def validate_entity_type(entity_type: str) -> Optional[UnmaskEntityType]:
    """Return normalised EntityType or ``None`` if invalid."""
    normalised = entity_type.lower().strip()
    if normalised in _VALID_ENTITY_TYPES:
        return UnmaskEntityType(normalised)
    return None


def validate_status(status: str) -> Optional[UnmaskStatus]:
    """Return normalised Status or ``None`` if invalid."""
    normalised = status.lower().strip()
    if normalised in _VALID_STATUSES:
        return UnmaskStatus(normalised)
    return None


def validate_jurisdiction(jurisdiction_id: str) -> bool:
    """Return True if *jurisdiction_id* is non-empty and reasonable."""
    return bool(jurisdiction_id and len(jurisdiction_id) <= 128)


def validate_reason(reason: str) -> List[str]:
    """Return a list of validation errors for *reason* (empty = valid)."""
    errors: List[str] = []
    if not reason or not reason.strip():
        errors.append("Reason is required")
    elif len(reason) < 10:
        errors.append("Reason must be at least 10 characters")
    elif len(reason) > 1000:
        errors.append("Reason must be at most 1000 characters")
    return errors


def validate_mfa_code(code: Optional[str], *, required: bool = False) -> List[str]:
    """Validate an MFA code format."""
    if code is None:
        if required:
            return ["MFA code is required"]
        return []
    if not code.isdigit():
        return ["MFA code must be numeric"]
    if len(code) != 6:
        return ["MFA code must be 6 digits"]
    return []
