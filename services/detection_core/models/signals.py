"""Signal models for Detection Engine."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DetectionType(str, Enum):
    PRICE_DEVIATION = "price_deviation"
    DUPLICATE = "duplicate_fuzzy"
    VENDOR_RISK = "vendor_graph_risk"
    TIMING_ANOMALY = "timing_anomaly"
    CONTRACT_SPLITTING = "contract_splitting"
    APPROVAL_VELOCITY = "approval_velocity"


class SignalStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    ESCALATED = "escalated"
    IGNORED = "ignored"


class Evidence(BaseModel):
    """Evidence supporting a signal"""
    evidence_id: str
    signal_id: str
    evidence_type: str
    description: str
    data: Dict[str, Any]
    source_type: str  # detector, transaction, historical, etc.
    source_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Evidence scoring
    relevance_score: float = 1.0
    credibility_score: float = 1.0


class Signal(BaseModel):
    """Detection signal model"""
    signal_id: str
    transaction_id: str
    detector_id: str
    detection_type: DetectionType
    value: float = Field(..., ge=0, le=1, description="Signal value [0,1]")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score [0,1]")
    raw_value: Optional[float] = None
    weight: float = Field(..., ge=0, le=1, description="Detector weight")

    # Context
    department_id: Optional[str] = None
    vendor_id: Optional[str] = None
    jurisdiction: Optional[str] = None

    # Evidence
    evidence_ids: List[str] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)

    # Processing
    status: SignalStatus = SignalStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: Optional[float] = None


class SignalGroup(BaseModel):
    """Group of signals for a transaction"""
    transaction_id: str
    signals: List[Signal]
    total_signals: int = 0
    max_signal_value: Optional[float] = None
    average_signal_value: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def calculate_metrics(self):
        """Calculate aggregate metrics"""
        self.total_signals = len(self.signals)

        if self.signals:
            self.max_signal_value = max(s.value for s in self.signals)
            self.average_signal_value = sum(s.value for s in self.signals) / len(self.signals)