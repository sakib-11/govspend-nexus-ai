"""Unmask models — request, approve, reject, view, and audit unmasking."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class UnmaskStatus(str, Enum):
    """Lifecycle states for an unmask request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNMASKED = "unmasked"
    VIEWED = "viewed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class UnmaskAction(str, Enum):
    """Actions that trigger state transitions."""

    CREATE = "create"
    APPROVE = "approve"
    REJECT = "reject"
    UNMASK = "unmask"
    VIEW = "view"
    EXPIRE = "expire"
    CANCEL = "cancel"


class UnmaskEntityType(str, Enum):
    """Types of entities that can be unmasked."""

    TRANSACTION = "transaction"
    VENDOR = "vendor"
    OFFICIAL = "official"
    INVOICE = "invoice"
    EVIDENCE = "evidence"


class UnmaskRequest(BaseModel):
    """Full unmask request record."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    request_id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    entity_type: UnmaskEntityType
    entity_token: str
    reason: str
    requested_by: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: UnmaskStatus = UnmaskStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    unmasked_by: Optional[str] = None
    unmasked_at: Optional[datetime] = None
    viewed_by: Optional[str] = None
    viewed_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    jurisdiction_id: str = "unknown"
    mfa_verified: bool = False
    mfa_verified_at: Optional[datetime] = None
    unmasked_data: Optional[Dict[str, Any]] = None
    data_checksum: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Request / Response DTOs ────────────────────────────────────────────


class UnmaskCreateRequest(BaseModel):
    """Request body for creating an unmask request."""

    case_id: UUID
    entity_type: UnmaskEntityType = UnmaskEntityType.TRANSACTION
    entity_token: str
    reason: str = Field(..., min_length=10, max_length=1000)
    jurisdiction_id: str = "unknown"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UnmaskApproveRequest(BaseModel):
    """Request body for approving an unmask request."""

    request_id: UUID
    notes: str = ""
    mfa_code: Optional[str] = None


class UnmaskRejectRequest(BaseModel):
    """Request body for rejecting an unmask request."""

    request_id: UUID
    reason: str = Field(..., min_length=5, max_length=1000)


class UnmaskViewRequest(BaseModel):
    """Request body for viewing unmasked data."""

    request_id: UUID
    mfa_code: Optional[str] = None


class UnmaskResponse(BaseModel):
    """Response for unmask operations."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    request_id: UUID
    case_id: UUID
    entity_type: str
    entity_token: str
    status: str
    requested_by: str
    requested_at: datetime
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    unmasked_data: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    can_view: bool = False
    can_approve: bool = False
    can_reject: bool = False
    rejection_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UnmaskDecision(BaseModel):
    """Decision on an unmask request (legacy compatibility)."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    request_id: str
    decision: UnmaskStatus
    decided_by: str
    comment: str = ""
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
