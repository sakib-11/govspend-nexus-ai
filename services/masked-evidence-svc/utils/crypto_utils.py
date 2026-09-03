"""Crypto utilities — HMAC token generation, hashing, and verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Optional


def generate_hmac_token(
    raw_identifier: str,
    hmac_key: str,
    *,
    token_length: int = 10,
) -> str:
    """Generate an HMAC-SHA256 token from a raw identifier.

    The token is deterministic: the same *raw_identifier* + *hmac_key*
    always produces the same token.

    Returns a base32-encoded string of exactly *token_length* characters.
    """
    digest = hmac.new(
        hmac_key.encode("utf-8"),
        raw_identifier.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # Take first 8 hex chars (4 bytes) and base32-encode
    short = digest[:16].encode("utf-8")
    encoded = base64.b32encode(short).decode("utf-8").rstrip("=").upper()

    # Trim or pad to exact length
    if len(encoded) >= token_length:
        return encoded[:token_length]
    # Pad with non-ambiguous chars if needed
    return encoded.ljust(token_length, "A")


def hash_identifier(raw_identifier: str) -> str:
    """Return a SHA-256 hex digest of *raw_identifier*.

    Used for storing verifiable but non-reversible hashes in token_mappings.
    """
    return hashlib.sha256(raw_identifier.encode("utf-8")).hexdigest()


def compute_data_hash(data: bytes) -> str:
    """Return a SHA-256 hex digest of arbitrary *data*."""
    return hashlib.sha256(data).hexdigest()


def generate_evidence_hash(data_dict: dict) -> str:
    """Deterministic hash of a JSON-serialised dictionary.

    Keys are sorted so the same logical data always produces the same hash.
    """
    import json

    serialised = json.dumps(data_dict, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    """Timing-safe string comparison."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def generate_random_token(length: int = 16) -> str:
    """Generate a cryptographically random hex token (not HMAC-based)."""
    return secrets.token_hex(length)
