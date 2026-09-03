"""Crypto utilities — salt generation and HMAC signing."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Union


def generate_salt(length: int = 32) -> str:
    """Generate a cryptographically secure random hex salt."""
    return os.urandom(length).hex()


def hmac_sign(data: Union[str, bytes], key: str, algorithm: str = "sha256") -> str:
    """Sign *data* with HMAC using *key*.  Returns a hex digest."""
    msg = data.encode("utf-8") if isinstance(data, str) else data
    key_bytes = key.encode("utf-8")
    return hmac.new(key_bytes, msg, getattr(hashlib, algorithm)).hexdigest()


def hmac_verify(data: Union[str, bytes], signature: str, key: str, algorithm: str = "sha256") -> bool:
    """Constant-time verify that *signature* matches HMAC of *data*."""
    expected = hmac_sign(data, key, algorithm)
    return hmac.compare_digest(expected, signature)
