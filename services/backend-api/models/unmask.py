"""Unmask workflow models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class UnmaskEntityType(str, Enum):
    VENDOR = "vendor"
    OFFICIAL = "official"
    TRANSACTION = "transaction"
    INVOICE = "invoice"


class UnmaskStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNMASKED = "unmasked"
    VIEWED = "viewed"
    EXPIRED = "expired"


class UnmaskRequestCreate(BaseModel):
    """Create an unmask request."""

    case_id: str
    entity_type: UnmaskEntityType
    entity_token: str
    reason: str
    jurisdiction_id: str


class UnmaskResponse(BaseModel):
    """Unmask request/response."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    request_id: str
    case_id: str
    entity_type: str
    entity_token: str
    status: UnmaskStatus
    requested_by: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    unmasked_data: Optional[Dict[str, Any]] = None


class UnmaskApproval(BaseModel):
    """Unmask approval decision."""

    decision: str  # approve | reject
    reason: Optional[str] = None
