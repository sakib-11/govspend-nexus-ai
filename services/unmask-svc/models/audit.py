"""Audit models — tamper-evident audit log entries and chain verification."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditEntry(BaseModel):
    """A single audit log entry with hash chain links."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    audit_id: UUID
    request_id: UUID
    action: str
    user_id: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    previous_hash: str = ""
    current_hash: str = ""
    payload_hash: str = ""
    signature: Optional[str] = None


class AuditChainVerification(BaseModel):
    """Result of verifying the audit hash chain."""

    is_valid: bool
    entries_checked: int = 0
    tampered_entries: List[UUID] = Field(default_factory=list)
    missing_entries: List[UUID] = Field(default_factory=list)
    error_message: Optional[str] = None
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditChainStatus(BaseModel):
    """Summary of the hash chain state."""

    total_entries: int = 0
    last_entry_id: Optional[UUID] = None
    last_hash: Optional[str] = None
    chain_start_hash: str = "0" * 64
    chain_end_hash: Optional[str] = None
    is_valid: bool = True
    tampered_count: int = 0
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditQuery(BaseModel):
    """Query parameters for filtering audit entries."""

    request_id: Optional[UUID] = None
    user_id: Optional[str] = None
    action: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)
