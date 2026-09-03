"""State utilities — helpers for working with unmask request state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from models.unmask import UnmaskStatus


# Fields that are safe to show at each status level
_SAFE_FIELDS: frozenset[str] = frozenset({
    "request_id", "case_id", "entity_type", "status",
    "requested_by", "requested_at", "jurisdiction_id", "metadata",
})


def is_terminal(status: UnmaskStatus) -> bool:
    """Return True if *status* is a terminal (non-actionable) state."""
    return status in (
        UnmaskStatus.REJECTED,
        UnmaskStatus.EXPIRED,
        UnmaskStatus.CANCELLED,
    )


def is_active(status: UnmaskStatus) -> bool:
    """Return True if *status* represents an active request."""
    return status in (
        UnmaskStatus.PENDING,
        UnmaskStatus.APPROVED,
        UnmaskStatus.UNMASKED,
        UnmaskStatus.VIEWED,
    )


def compute_expiry(ttl_hours: int) -> datetime:
    """Compute an expiry datetime *ttl_hours* from now (UTC)."""
    return datetime.now(timezone.utc) + timedelta(hours=ttl_hours)


def safe_summary(status: UnmaskStatus) -> List[str]:
    """Return the list of fields safe to include in a public summary."""
    fields = list(_SAFE_FIELDS)
    if status == UnmaskStatus.UNMASKED or status == UnmaskStatus.VIEWED:
        fields.append("unmasked_data")
    return fields
