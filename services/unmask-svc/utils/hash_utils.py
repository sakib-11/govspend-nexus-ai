"""Hash utilities — HMAC signatures, SHA-256 hashing, and data integrity."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict


GENESIS_HASH = "0" * 64


def compute_payload_hash(payload: Dict[str, Any]) -> str:
    """SHA-256 hex digest of a JSON-serialised payload.

    Keys are sorted so the same logical data always produces the same hash.
    """
    serialised = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def compute_data_checksum(data: Any) -> str:
    """SHA-256 hex digest of arbitrary JSON-serialisable *data*."""
    serialised = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def compute_chain_hash(
    previous_hash: str,
    action: str,
    user_id: str,
    request_id: str,
    timestamp: str,
    payload_hash: str,
    from_status: str = "",
    to_status: str = "",
) -> str:
    """Compute the hash chain entry from its constituent fields.

    This mirrors the database trigger logic so the chain can be verified
    without a database round-trip.
    """
    data = f"{previous_hash}{action}{user_id}{request_id}{timestamp}{payload_hash}{from_status}{to_status}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_hmac_signature(key: str, payload: Dict[str, Any]) -> str:
    """HMAC-SHA256 signature of a JSON-serialised payload."""
    serialised = json.dumps(payload, sort_keys=True, default=str)
    return hmac.new(
        key.encode("utf-8"),
        serialised.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    """Timing-safe string comparison."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def hash_identifier(raw_identifier: str) -> str:
    """SHA-256 hex digest of a raw identifier (non-reversible)."""
    return hashlib.sha256(raw_identifier.encode("utf-8")).hexdigest()
