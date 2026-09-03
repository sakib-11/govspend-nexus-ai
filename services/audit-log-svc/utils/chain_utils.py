"""Chain utilities — helpers for building and validating chain payloads."""

from __future__ import annotations

from typing import Any, Dict, Optional

from utils.hash_utils import compute_chain_hash, compute_data_hash


# The genesis hash (64 zeroes) marks the start of the chain.
GENESIS_HASH = "0" * 64


def build_chain_payload(
    previous_hash: str,
    data_payload: Dict[str, Any],
    salt: str,
    sequence: int,
) -> Dict[str, str]:
    """Build a chain payload dict from the components.

    Returns a dict with ``data_hash`` and ``current_hash`` suitable for
    storing alongside the audit entry.
    """
    data_hash = compute_data_hash(data_payload)
    current_hash = compute_chain_hash(previous_hash, data_hash, salt, sequence)
    return {
        "previous_hash": previous_hash,
        "data_hash": data_hash,
        "current_hash": current_hash,
    }


def validate_chain_payload(
    previous_hash: str,
    data_payload: Dict[str, Any],
    salt: str,
    sequence: int,
    expected_current_hash: str,
) -> bool:
    """Recompute the chain hash and compare it against the expected value."""
    data_hash = compute_data_hash(data_payload)
    computed = compute_chain_hash(previous_hash, data_hash, salt, sequence)
    return computed == expected_current_hash
