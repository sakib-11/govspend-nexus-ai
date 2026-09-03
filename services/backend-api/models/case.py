"""Case management models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class CaseTier(str, Enum):
    HIGH = "HIGH"
    BORDERLINE = "BORDERLINE"
    LOW = "LOW"


class CaseStatus(str, Enum):
    NEW = "new"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    CLOSED = "closed"


class CaseSummary(BaseModel):
    """Case summary for queue listing."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    case_id: str
    transaction_id: str
    risk_score: float = Field(ge=0.0, le=1.0)
    tier: CaseTier
    status: CaseStatus
    department: str
    vendor_token: str
    amount: float
    transaction_date: datetime
    top_signals: List[Dict[str, Any]] = Field(default_factory=list)
    signal_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CaseDetail(BaseModel):
    """Full case detail with signals, evidence, and action history."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    case_id: str
    transaction_id: str
    risk_score: float = Field(ge=0.0, le=1.0)
    tier: CaseTier
    status: CaseStatus
    confidence_factor: float = Field(ge=0.0, le=1.0)
    weights_version: str

    # Transaction data
    transaction: Dict[str, Any] = Field(default_factory=dict)
    vendor: Dict[str, Any] = Field(default_factory=dict)
    department: Dict[str, Any] = Field(default_factory=dict)

    # Signals
    signals: List[Dict[str, Any]] = Field(default_factory=list)
    signals_summary: Dict[str, Any] = Field(default_factory=dict)

    # Evidence
    evidence_ids: List[str] = Field(default_factory=list)
    evidence_summary: Dict[str, Any] = Field(default_factory=dict)

    # Metadata
    jurisdiction_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_to: Optional[str] = None

    # Audit
    actions: List[Dict[str, Any]] = Field(default_factory=list)


class CaseFilter(BaseModel):
    """Filters for case listing."""

    tier: Optional[List[CaseTier]] = None
    status: Optional[List[CaseStatus]] = None
    department: Optional[str] = None
    vendor_token: Optional[str] = None
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    search: Optional[str] = None


class CaseAction(BaseModel):
    """Case action request."""

    action: str  # approve, reject, escalate, close
    notes: Optional[str] = None
    reason: Optional[str] = None


class CaseActionResponse(BaseModel):
    """Case action response."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    case_id: str
    action: str
    status: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    performed_by: str
    message: str
