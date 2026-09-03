"""Evidence models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    """Evidence item for case listing."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    evidence_id: str
    evidence_type: str  # invoice, document, signal, benchmark
    description: str
    data: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # detector name or system
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceDetail(BaseModel):
    """Detailed evidence with full data and verification."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    evidence_id: str
    case_id: str
    transaction_id: str
    evidence_type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    verified: bool = False
    hash: str = ""
