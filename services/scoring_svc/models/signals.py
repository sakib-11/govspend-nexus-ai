"""Signal models for the Scoring Service."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DetectorSignal(BaseModel):
    """Signal from detection pipeline."""
    model_config = ConfigDict(from_attributes=True)

    detector_type: str
    signal_value: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    transaction_id: str
    timestamp: datetime
    metadata: dict[str, Any] | None = None