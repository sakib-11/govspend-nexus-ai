"""Models for the Detection Service."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class DetectionType(str, Enum):
    """Types of detection algorithms."""
    PRICE_DEVIATION = "price_deviation"
    DUPLICATE = "duplicate_fuzzy"
    VENDOR_RISK = "vendor_graph_risk"
    TIMING_ANOMALY = "timing_anomaly"
    CONTRACT_SPLITTING = "contract_splitting"
    APPROVAL_VELOCITY = "approval_velocity"


class DetectionSeverity(str, Enum):
    """Severity levels for detections."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class DetectionStatus(str, Enum):
    """Status of detection processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class PriceDeviationSignal(BaseModel):
    """Signal output for price deviation detector."""
    signal_value: float = Field(..., ge=0, le=1, description="Normalized signal value")
    raw_deviation: float = Field(..., description="Raw deviation from benchmark")
    benchmark_price: float = Field(..., description="Calculated benchmark price")
    upper_fence: float = Field(..., description="Upper fence from IQR")
    percentile_rank: float = Field(..., ge=0, le=100, description="Percentile rank of transaction")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in detection")
    sample_count: int = Field(..., description="Number of peer samples used")
    sample_std: Optional[float] = Field(None, description="Standard deviation of samples")

    # Peer group information
    peer_category: Optional[str] = None
    peer_region: Optional[str] = None
    peer_quantity_band: Optional[str] = None

    # Metadata
    outlier_indicators: List[str] = Field(default_factory=list)
    detection_method: str = "iqr"
    computed_at: datetime = Field(default_factory=datetime.utcnow)


class DetectionResult(BaseModel):
    """Complete detection result."""
    id: str
    transaction_id: str
    detection_type: DetectionType
    severity: DetectionSeverity
    signal_value: float
    confidence: float
    details: Dict[str, Any]
    evidence: List[str]
    recommendations: List[str]
    status: DetectionStatus
    created_at: datetime
    updated_at: datetime

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }