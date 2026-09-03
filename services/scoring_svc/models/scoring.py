"""Models for the Scoring Service."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskTier(str, Enum):
    """Risk tier classification."""
    HIGH = "HIGH"
    BORDERLINE = "BORDERLINE"
    LOW = "LOW"


class WeightConfig(BaseModel):
    """Versioned weight configuration."""
    model_config = ConfigDict(frozen=True)

    version: str
    weights: dict[str, float]
    effective_from: datetime
    effective_to: datetime | None = None
    description: str | None = None

    @property
    def total_weight(self) -> float:
        """Total weight sum (should be 1.0)."""
        return sum(self.weights.values())


class ScoringResult(BaseModel):
    """Complete scoring result."""
    transaction_id: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_tier: RiskTier
    weighted_sum: float = Field(..., ge=0.0, le=1.0)
    confidence_factor: float = Field(..., ge=0.0, le=1.0)
    signals_used: int
    weights_version: str
    calculated_at: datetime
    components: dict[str, float]
    metadata: dict[str, Any] | None = None


class ScoringRequest(BaseModel):
    """API request for scoring."""
    transaction_id: str
    weights_version: str | None = None
    include_details: bool = False


class BulkScoringRequest(BaseModel):
    """Bulk scoring request."""
    transaction_ids: list[str]
    weights_version: str | None = None
    include_details: bool = False