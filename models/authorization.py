"""Authorization models for GovSpend Nexus AI."""

from enum import Enum
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid import uuid4


class AuthorizationDecision(str, Enum):
    """Authorization decision result"""

    ALLOW = "allow"
    DENY = "deny"
    PARTIAL = "partial"


class AuthorizationReason(str, Enum):
    """Reason for authorization decision"""

    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    JURISDICTION_ALLOWED = "jurisdiction_allowed"
    JURISDICTION_DENIED = "jurisdiction_denied"
    ROLE_REQUIRED = "role_required"
    RESOURCE_OWNER = "resource_owner"
    RESOURCE_OWNER_DENIED = "resource_owner_denied"
    MFA_REQUIRED = "mfa_required"
    MFA_NOT_VERIFIED = "mfa_not_verified"
    SESSION_EXPIRED = "session_expired"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    POLICY_DENIED = "policy_denied"
    EMERGENCY_OVERRIDE = "emergency_override"


class ResourceType(str, Enum):
    """Resource types for authorization"""

    TRANSACTION = "transaction"
    DETECTION = "detection"
    SCORE = "score"
    CASE = "case"
    EVIDENCE = "evidence"
    USER = "user"
    POLICY = "policy"
    AUDIT = "audit"
    REPORT = "report"
    JURISDICTION = "jurisdiction"
    SYSTEM = "system"


class ActionType(str, Enum):
    """Action types for authorization"""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    EXPORT = "export"
    OVERRIDE = "override"
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    ASSIGN = "assign"
    CLOSE = "close"
    VIEW = "view"
    MANAGE = "manage"


class PermissionTag(BaseModel):
    """Permission tag for authorization"""

    resource: ResourceType
    action: ActionType
    scope: Optional[str] = None
    jurisdiction_required: bool = False

    def to_string(self) -> str:
        """Convert to string representation"""
        tag = f"{self.resource.value}:{self.action.value}"
        if self.scope:
            tag += f":{self.scope}"
        return tag

    @classmethod
    def from_string(cls, tag: str) -> "PermissionTag":
        """Create from string representation"""
        parts = tag.split(":")
        if len(parts) >= 2:
            resource = ResourceType(parts[0])
            action = ActionType(parts[1])
            scope = parts[2] if len(parts) > 2 else None
            return cls(resource=resource, action=action, scope=scope)
        raise ValueError(f"Invalid permission tag: {tag}")


class ToolTag(BaseModel):
    """Tool/Resource tag for authorization"""

    tool_id: str
    resource_type: ResourceType
    required_permissions: List[PermissionTag] = Field(default_factory=list)
    allowed_roles: List[str] = Field(default_factory=list)
    jurisdiction_required: bool = False
    jurisdictions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def requires_permission(self, permission: PermissionTag) -> bool:
        """Check if this permission is required"""
        for required in self.required_permissions:
            if (
                required.resource == permission.resource
                and required.action == permission.action
            ):
                return True
        return False


class AuthorizationRequest(BaseModel):
    """Authorization request"""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    request_id: str = Field(default_factory=lambda: f"auth-{uuid4().hex[:12]}")
    user_id: str
    user_roles: List[str] = Field(default_factory=list)
    user_permissions: List[str] = Field(default_factory=list)
    user_jurisdictions: List[str] = Field(default_factory=list)

    resource_type: ResourceType
    action: ActionType
    resource_id: Optional[str] = None
    resource_jurisdiction: Optional[str] = None
    resource_owner_id: Optional[str] = None

    tool_tags: List[ToolTag] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)

    mfa_verified: bool = False
    session_id: Optional[str] = None
    ip_address: Optional[str] = None

    timestamp: datetime = Field(default_factory=datetime.now)


class AuthorizationResponse(BaseModel):
    """Authorization response"""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    request_id: str
    decision: AuthorizationDecision
    reason: AuthorizationReason
    message: str
    allowed_actions: List[str] = Field(default_factory=list)
    denied_actions: List[str] = Field(default_factory=list)

    permission_checks: List[Dict[str, Any]] = Field(default_factory=list)
    jurisdiction_checks: List[Dict[str, Any]] = Field(default_factory=list)
    role_checks: List[Dict[str, Any]] = Field(default_factory=list)

    audit_id: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=datetime.now)
    evaluated_by: str = "authorization_engine"

    partial_grants: Dict[str, bool] = Field(default_factory=dict)


class AuthorizationPolicy(BaseModel):
    """Authorization policy configuration"""

    policy_id: str = Field(default_factory=lambda: f"pol-{uuid4().hex[:12]}")
    name: str
    description: Optional[str] = None
    version: str = "1.0"

    permission_rules: List[Dict[str, Any]] = Field(default_factory=list)
    jurisdiction_rules: List[Dict[str, Any]] = Field(default_factory=list)
    role_rules: List[Dict[str, Any]] = Field(default_factory=list)

    allow_overrides: List[Dict[str, Any]] = Field(default_factory=list)
    deny_overrides: List[Dict[str, Any]] = Field(default_factory=list)

    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"


class AuthorizationAuditLog(BaseModel):
    """Authorization audit log"""

    audit_id: str = Field(default_factory=lambda: f"aud-{uuid4().hex[:12]}")
    request_id: str
    user_id: str
    decision: AuthorizationDecision
    reason: AuthorizationReason
    resource_type: ResourceType
    action: ActionType
    resource_id: Optional[str] = None
    resource_jurisdiction: Optional[str] = None

    user_roles: List[str] = Field(default_factory=list)
    user_permissions: List[str] = Field(default_factory=list)
    user_jurisdictions: List[str] = Field(default_factory=list)

    permission_checks_passed: int = 0
    permission_checks_failed: int = 0
    jurisdiction_checks_passed: int = 0
    jurisdiction_checks_failed: int = 0

    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None

    allowed: bool
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

    timestamp: datetime = Field(default_factory=datetime.now)
    response_time_ms: Optional[float] = None