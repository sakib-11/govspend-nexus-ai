"""Case models for Explanation Service."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CaseTier(str, Enum):
    """Risk tier for a case."""

    LOW = "LOW"
    BORDERLINE = "BORDERLINE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseStatus(str, Enum):
    """Workflow status for a case."""

    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    ESCALATED = "ESCALATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class CaseFilter(BaseModel):
    """Filters for case list queries."""

    tier: Optional[CaseTier] = None
    status: Optional[CaseStatus] = None
    jurisdiction: Optional[str] = None
    department: Optional[str] = None
    assigned_to: Optional[str] = None
    search: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_risk_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_risk_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class RiskFactor(BaseModel):
    """Individual risk factor in a case."""

    type: str
    value: float = Field(ge=0.0, le=1.0)
    severity: str
    description: str


class WorkflowState(BaseModel):
    """Workflow state for a case."""

    stage: str
    stage_order: int = Field(ge=1)
    current_step: str
    next_steps: List[str] = Field(default_factory=list)
    deadline: Optional[datetime] = None
    time_remaining_hours: Optional[float] = None


class CasePermissions(BaseModel):
    """Permissions for current user on a case."""

    can_approve: bool = False
    can_reject: bool = False
    can_escalate: bool = False
    can_request_unmask: bool = False
    can_view_full_data: bool = False
    can_view_audit_trail: bool = False


class CaseDetail(BaseModel):
    """Detailed case information."""

    model_config = ConfigDict(extra="ignore")

    id: str
    transaction_id: str
    risk_score: float = Field(ge=0.0, le=1.0)
    tier: CaseTier
    status: CaseStatus
    department: str
    vendor_token: str
    vendor_name: Optional[str] = None
    amount: float = Field(ge=0.0)
    transaction_date: datetime
    risk_factors: List[RiskFactor] = Field(default_factory=list)
    jurisdiction: str
    assigned_to: Optional[str] = None
    assigned_role: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    explanations: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    unmask_requests: List[Dict[str, Any]] = Field(default_factory=list)
    permissions: CasePermissions
    workflow_state: WorkflowState


class CaseListResponse(BaseModel):
    """Paginated case list response."""

    cases: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int
    filters_applied: Dict[str, Any]
