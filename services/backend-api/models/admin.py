"""Admin dashboard models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PolicyWeight(BaseModel):
    """Policy weight configuration."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    version: str
    weights: Dict[str, float]
    is_active: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str
    description: Optional[str] = None


class PolicyWeightCreate(BaseModel):
    """Create a new policy weight version."""

    weights: Dict[str, float]
    description: Optional[str] = None
    activate: bool = False


class AuditLogEntry(BaseModel):
    """Audit log entry for admin view."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    entry_id: str
    timestamp: datetime
    user_id: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    hash_chain: Dict[str, Any] = Field(default_factory=dict)


class UserRoleUpdate(BaseModel):
    """Update user roles and jurisdictions."""

    user_id: str
    roles: List[str]
    jurisdictions: List[str]
