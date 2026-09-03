"""Evidence models — masked transaction, case, and evidence records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MaskedTransaction(BaseModel):
    """Masked transaction data stored in the masked DB."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    transaction_id: UUID
    masked_data: Dict[str, Any] = Field(default_factory=dict)
    tokens: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MaskedCase(BaseModel):
    """Masked case data stored in the masked DB."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    case_id: UUID
    transaction_id: UUID
    masked_case_data: Dict[str, Any] = Field(default_factory=dict)
    tokens: Dict[str, str] = Field(default_factory=dict)
    risk_score: float = Field(ge=0.0, le=1.0, default=0.0)
    tier: str = "unknown"
    jurisdiction_id: str = "unknown"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MaskedEvidenceRecord(BaseModel):
    """Individual masked evidence entry stored in the masked DB."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    evidence_id: UUID
    case_id: UUID
    evidence_type: str
    masked_data: Dict[str, Any] = Field(default_factory=dict)
    tokens: Dict[str, str] = Field(default_factory=dict)
    evidence_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MaskingRequest(BaseModel):
    """Request body for the masking endpoint."""

    raw_data: Dict[str, Any]
    entity_type: str = "generic"
    fields_to_mask: List[str] = Field(default_factory=list)
    preserve_fields: List[str] = Field(default_factory=list)


class MaskingResponse(BaseModel):
    """Response from the masking endpoint."""

    masked_data: Dict[str, Any]
    tokens: Dict[str, str]
    field_count: int
    token_count: int


class EvidenceQuery(BaseModel):
    """Query parameters for listing masked evidence."""

    case_id: Optional[UUID] = None
    transaction_id: Optional[UUID] = None
    evidence_type: Optional[str] = None
    jurisdiction_id: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)
