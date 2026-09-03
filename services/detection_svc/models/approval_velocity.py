"""Models for approval velocity detection."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ApprovalVelocitySeverity(str, Enum):
    """Severity levels for velocity detections."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ApprovalContext(str, Enum):
    """Classification of approval context."""

    NORMAL = "normal"
    EXPEDITED = "expedited"
    EMERGENCY = "emergency"
    RUSH = "rush"
    UNKNOWN = "unknown"


class HistoricalApprovalStats(BaseModel):
    """Historical approval velocity statistics for a category × department."""

    category: str
    department_id: str
    median_approval_time: float  # hours
    mean_approval_time: float
    std_approval_time: float
    min_time: float
    max_time: float
    q1: float
    q3: float
    sample_count: int
    confidence: float

    # Percentiles
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float

    # Time-based patterns (optional)
    weekday_median: Optional[Dict[int, float]] = None
    month_median: Optional[Dict[int, float]] = None
    hour_median: Optional[Dict[int, float]] = None

    computed_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalVelocityInput(BaseModel):
    """Input for approval velocity detection."""

    transaction_id: str
    department_id: str
    vendor_id: str
    category: str
    subcategory: Optional[str] = None
    amount: float
    transaction_date: date
    submission_date: date
    approval_date: date
    approver_id: Optional[str] = None

    # Optional context flags
    is_expedited: bool = False
    is_emergency: bool = False
    approval_context: Optional[ApprovalContext] = None

    @field_validator("approval_date")
    @classmethod
    def validate_approval_date(cls, v: date, info) -> date:
        submission_date = info.data.get("submission_date")
        if submission_date and v < submission_date:
            raise ValueError("Approval date cannot be before submission date")
        return v

    def get_approval_time(self) -> float:
        """Approval time in hours (calendar days × 24)."""
        delta = self.approval_date - self.submission_date
        return delta.total_seconds() / 3600


class ApprovalVelocityResult(BaseModel):
    """Complete approval velocity detection result."""

    signal_value: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)

    # Core metrics
    approval_time: float  # hours
    median_time: float  # historical median
    time_ratio: float  # actual / median
    velocity_score: float  # linear score
    raw_deviation: float

    # Context
    department_id: str
    category: str
    sample_count: int

    # Classification
    severity: ApprovalVelocitySeverity
    context: ApprovalContext
    velocity_indicators: List[str]

    # Evidence
    evidence: List[str]
    recommendations: List[str]

    # Detailed analysis
    historical_stats: Optional[HistoricalApprovalStats] = None
    percentile_rank: Optional[float] = None
    pattern_analysis: Dict[str, Any] = Field(default_factory=dict)

    # Metadata
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[int] = None

    @field_validator("signal_value")
    @classmethod
    def validate_signal(cls, v: float) -> float:
        return min(1.0, max(0.0, v))
