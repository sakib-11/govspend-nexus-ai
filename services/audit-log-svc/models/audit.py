"""Audit core models — the canonical data structures for the audit log."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AuditEventType(str, Enum):
    """Types of audit events."""

    MCP_TOOL_CALL = "mcp_tool_call"
    MCP_TOOL_RESULT = "mcp_tool_result"
    MCP_TOOL_ERROR = "mcp_tool_error"
    AUTH_LOGIN = "auth_login"
    AUTH_LOGOUT = "auth_logout"
    AUTH_MFA = "auth_mfa"
    JURISDICTION_CHECK = "jurisdiction_check"
    JURISDICTION_CROSS = "jurisdiction_cross"
    CASE_ACTION = "case_action"
    UNMASK_REQUEST = "unmask_request"
    UNMASK_APPROVAL = "unmask_approval"
    POLICY_CHANGE = "policy_change"
    SYSTEM_EVENT = "system_event"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_EXPORT = "data_export"
    ADMIN_ACTION = "admin_action"


class AuditSeverity(str, Enum):
    """Audit severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    ALERT = "alert"


class AuditStatus(str, Enum):
    """Audit entry status."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    TAMPERED = "tampered"


# ---------------------------------------------------------------------------
# Hash chain entry (embedded in AuditEntry)
# ---------------------------------------------------------------------------

class HashChainEntry(BaseModel):
    """Hash chain entry for tamper-evident logging."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    entry_id: str = Field(default_factory=lambda: f"entry-{uuid4().hex[:16]}")
    previous_hash: str
    current_hash: str
    data_hash: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sequence_number: int
    blockchain_hash: Optional[str] = None  # For cross-chain verification


# ---------------------------------------------------------------------------
# Audit entry
# ---------------------------------------------------------------------------

class AuditEntry(BaseModel):
    """Complete audit entry with hash chaining."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        validate_assignment=True,
    )

    # Core identifiers
    audit_id: str = Field(default_factory=lambda: f"aud-{uuid4().hex[:16]}")
    event_type: AuditEventType
    event_version: str = "1.0"

    # User context
    user_id: str
    user_roles: List[str] = Field(default_factory=list)
    user_jurisdictions: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Resource context
    resource_type: str
    resource_id: Optional[str] = None
    resource_token: Optional[str] = None  # Tokenized resource identifier
    jurisdiction_id: Optional[str] = None

    # Action context
    action: str
    action_details: Dict[str, Any] = Field(default_factory=dict)

    # Request / Response
    request_id: str = ""
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    response_status: Optional[int] = None
    error_message: Optional[str] = None
    error_stack: Optional[str] = None

    # Performance
    duration_ms: Optional[float] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Hash chain
    hash_chain: Optional[HashChainEntry] = None

    # Audit metadata
    severity: AuditSeverity = AuditSeverity.INFO
    status: AuditStatus = AuditStatus.COMPLETED
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)

    # Verification
    verified: bool = False
    verified_at: Optional[datetime] = None
    verification_hash: Optional[str] = None

    def compute_data_hash(self) -> str:
        """Deterministic SHA-256 of the core audit fields.

        The hash covers the fields that identify *what happened* and *to
        whom* — intentionally excluding volatile fields like ``hash_chain``
        and ``verified`` so that re-computation always matches.
        """
        payload = {
            "audit_id": self.audit_id,
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()


# ---------------------------------------------------------------------------
# Query model
# ---------------------------------------------------------------------------

class AuditQuery(BaseModel):
    """Structured query for searching audit entries."""

    user_id: Optional[str] = None
    event_type: Optional[List[AuditEventType]] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    jurisdiction_id: Optional[str] = None
    action: Optional[str] = None
    severity: Optional[List[AuditSeverity]] = None
    status: Optional[List[AuditStatus]] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    verified: Optional[bool] = None
    tampered: Optional[bool] = None
    limit: int = Field(default=100, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)
    order_by: str = "timestamp"
    order_direction: str = "desc"


# ---------------------------------------------------------------------------
# Verification result
# ---------------------------------------------------------------------------

class AuditVerificationResult(BaseModel):
    """Result of verifying a single audit entry."""

    audit_id: str
    verified: bool
    chain_valid: bool
    tampered: bool
    previous_hash_valid: bool
    data_hash_valid: bool
    chain_sequence_valid: bool
    verification_details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditChainStatus(BaseModel):
    """Snapshot of the audit hash chain state."""

    total_entries: int
    last_entry_id: Optional[str] = None
    last_hash: Optional[str] = None
    chain_start_hash: Optional[str] = None
    chain_end_hash: Optional[str] = None
    is_valid: bool = True
    last_verification: Optional[datetime] = None
    tampered_entries: int = 0
    verified_entries: int = 0
