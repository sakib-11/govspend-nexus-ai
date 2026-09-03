"""Verification models — extended results for chain and tamper checks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class VerificationResult(BaseModel):
    """Result of verifying a single audit entry."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    verification_id: str = Field(default_factory=lambda: f"ver-{uuid4().hex[:12]}")
    audit_id: str
    verified: bool
    chain_valid: bool
    tampered: bool
    previous_hash_valid: bool
    data_hash_valid: bool
    chain_sequence_valid: bool
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VerificationReport(BaseModel):
    """Aggregate verification report for a batch / full-chain check."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    report_id: str = Field(default_factory=lambda: f"rpt-{uuid4().hex[:12]}")
    total_entries: int = 0
    verified_count: int = 0
    tampered_count: int = 0
    chain_valid: bool = True
    start_sequence: Optional[int] = None
    end_sequence: Optional[int] = None
    tampered_entries: List[Dict[str, Any]] = Field(default_factory=list)
    verified_entries: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
