"""Hash utilities — SHA-256 computation helpers for the audit chain."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_sha256(data: str) -> str:
    """Compute the SHA-256 hex-digest of a string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_chain_hash(previous_hash: str, data_hash: str, salt: str, sequence: int) -> str:
    """Compute the deterministic chain hash for a single entry.

    ``chain_hash = SHA-256(previous_hash || data_hash || salt || sequence)``
    """
    payload = f"{previous_hash}{data_hash}{salt}{sequence}"
    return compute_sha256(payload)


def verify_hash(data: str, expected: str) -> bool:
    """Constant-time comparison of a recomputed hash against an expected value."""
    computed = compute_sha256(data)
    return computed == expected


def compute_data_hash(payload: dict[str, Any]) -> str:
    """Compute a deterministic data hash from a JSON-serialisable dict.

    Keys are sorted and non-serialisable values are converted via ``default=str``
    so that the same logical payload always produces the same hash.
    """
    serialised = json.dumps(payload, sort_keys=True, default=str)
    return compute_sha256(serialised)
