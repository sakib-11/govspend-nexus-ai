"""Models for timing anomaly detection."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class TimingAnomalyType(str, Enum):
    """Classification of timing anomalies."""

    APPROVAL_TIME = "approval_time"
    PROCESSING_TIME = "processing_time"
    PAYMENT_TIME = "payment_time"
    FISCAL_END = "fiscal_end"
    HOLIDAY = "holiday"
    WEEKEND = "weekend"
    NORMAL = "normal"


class AnomalySeverity(str, Enum):
    """Severity levels for timing anomalies."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class TimingStatistics(BaseModel):
    """Historical timing statistics for a department."""

    department_id: str
    fiscal_period: str
    mean_approval_time: float  # hours
    std_approval_time: float  # hours
    min_time: float
    max_time: float
    median_time: float
    sample_count: int
    confidence: float
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    # Quartile / IQR metrics
    q1: Optional[float] = None
    q3: Optional[float] = None
    iqr: Optional[float] = None
    outlier_count: int = 0

    # Time-of-day patterns
    weekend_avg: Optional[float] = None
    weekday_avg: Optional[float] = None
    holiday_avg: Optional[float] = None


class TimingAnomalyResult(BaseModel):
    """Complete timing anomaly detection result."""

    signal_value: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)

    # Z-score information
    z_score: float
    raw_deviation: float  # hours
    normalized_deviation: float

    # Context
    department_id: str
    approval_time: float  # hours
    historical_mean: float
    historical_std: float
    fiscal_amplification: float = 1.0
    is_fiscal_end: bool = False
    days_to_fiscal_end: Optional[int] = None

    # Anomaly classification
    anomaly_type: TimingAnomalyType
    severity: AnomalySeverity
    anomaly_indicators: List[str]

    # Evidence
    evidence: List[str]
    recommendations: List[str]

    # Details
    fiscal_period: Optional[str] = None
    statistics: Optional[Dict[str, Any]] = None
    outlier_analysis: Dict[str, Any] = Field(default_factory=dict)

    # Metadata
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[int] = None

    @field_validator("signal_value")
    @classmethod
    def validate_signal(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


class ApprovalTimeInput(BaseModel):
    """Input for approval-time anomaly detection."""

    transaction_id: str
    department_id: str
    vendor_id: str
    amount: float
    transaction_date: date
    approval_date: date
    submission_date: date
    fiscal_period: Optional[str] = None
    fiscal_year_end: Optional[date] = None

    @field_validator("approval_date")
    @classmethod
    def validate_approval_date(cls, v: date, info) -> date:
        submission_date = info.data.get("submission_date")
        if submission_date and v < submission_date:
            raise ValueError("Approval date cannot be before submission date")
        return v

    @field_validator("transaction_date")
    @classmethod
    def validate_transaction_date(cls, v: date, info) -> date:
        approval_date = info.data.get("approval_date")
        if approval_date and v > approval_date:
            raise ValueError("Transaction date cannot be after approval date")
        return v

    def get_approval_time(self) -> float:
        """Approval time in hours (calendar days × 24)."""
        delta = self.approval_date - self.submission_date
        return delta.total_seconds() / 3600
