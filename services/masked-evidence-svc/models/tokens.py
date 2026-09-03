"""Token models — HMAC-based token representations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Token(BaseModel):
    """HMAC-based token replacing a raw PII identifier."""

    token: str
    entity_type: str
    prefix: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TokenVerification(BaseModel):
    """Result of a token verification request."""

    token: str
    exists: bool
    entity_type: Optional[str] = None
