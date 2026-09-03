"""Authentication and authorization models for Explanation Service."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRole(str, Enum):
    """Available user roles."""

    AUDITOR_LEVEL_1 = "auditor_level_1"
    AUDITOR_LEVEL_2 = "auditor_level_2"
    AUDITOR_LEVEL_3 = "auditor_level_3"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class AuthRequest(BaseModel):
    """Authentication request."""

    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)
    mfa_code: Optional[str] = Field(default=None, min_length=6, max_length=6)


class AuthResponse(BaseModel):
    """Authentication response."""

    token: str
    user: Dict[str, Any]
    requires_mfa: bool = False
    mfa_secret: Optional[str] = None
    qr_code_url: Optional[str] = None


class MFASetupRequest(BaseModel):
    """MFA setup request."""

    username: str = Field(min_length=1, max_length=255)


class MFARequest(BaseModel):
    """MFA verification request."""

    code: str = Field(min_length=6, max_length=6)


class UserSession(BaseModel):
    """Active user session."""

    model_config = ConfigDict(extra="ignore")

    user_id: str
    username: str
    email: str
    full_name: str
    roles: List[str]
    jurisdictions: List[str]
    permissions: List[str]
    mfa_enabled: bool = False
    last_login: Optional[datetime] = None
    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None


class Permission(str, Enum):
    """Granular permissions."""

    READ_CASES = "read_cases"
    APPROVE_CASES = "approve_cases"
    REJECT_CASES = "reject_cases"
    ESCALATE_CASES = "escalate_cases"
    APPROVE_UNMASK = "approve_unmask"
    REJECT_UNMASK = "reject_unmask"
    VIEW_FULL_DATA = "view_full_data"
    VIEW_AUDIT_TRAIL = "view_audit_trail"
    MANAGE_USERS = "manage_users"
    VIEW_ADMIN = "view_admin"
    MANAGE_CONFIG = "manage_config"
