"""Models for contract splitting detection."""

import math
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class SplittingPattern(str, Enum):
    """Recognised contract-splitting patterns."""

    TEMPORAL_CLUSTERING = "temporal_clustering"
    AMOUNT_ALIGNMENT = "amount_alignment"
    FREQUENCY_SPIKE = "frequency_spike"
    SEQUENTIAL_SPLITTING = "sequential_splitting"
    ROUNDING_PATTERN = "rounding_pattern"


class SplittingSeverity(str, Enum):
    """Severity levels for splitting detections."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class PurchaseOrder(BaseModel):
    """Single purchase order."""

    po_id: str
    vendor_id: str
    vendor_name: str
    department_id: str
    department_name: str
    amount: float
    po_date: date
    description: Optional[str] = None
    category: Optional[str] = None
    approver_id: Optional[str] = None
    approver_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Metadata
    is_manual_review: bool = False
    review_threshold: Optional[float] = None
    days_since_previous_po: Optional[int] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class ContractSplittingGroup(BaseModel):
    """A group of POs that may represent contract splitting."""

    group_id: str
    vendor_id: str
    vendor_name: str
    department_id: str
    department_name: str
    window_start: date
    window_end: date
    purchase_orders: List[PurchaseOrder]

    # Aggregated metrics
    po_count: int
    total_amount: float
    average_amount: float
    min_amount: float
    max_amount: float
    std_amount: float
    review_threshold: float
    threshold_exceeded: bool = False
    amount_exceeded_by: float = 0.0

    # Splitting indicators
    splitting_patterns: List[SplittingPattern] = Field(default_factory=list)
    is_high_risk: bool = False
    risk_score: float = 0.0

    # Temporal metrics
    average_days_between: Optional[float] = None
    max_days_between: Optional[int] = None
    min_days_between: Optional[int] = None
    is_sequential: bool = False

    # Amount distribution
    amount_skewness: Optional[float] = None
    amount_entropy: Optional[float] = None

    def calculate_metrics(self) -> None:
        """Compute aggregated metrics from the PO list."""
        if not self.purchase_orders:
            return

        amounts = [po.amount for po in self.purchase_orders]
        self.po_count = len(amounts)
        self.total_amount = sum(amounts)
        self.average_amount = self.total_amount / self.po_count
        self.min_amount = min(amounts)
        self.max_amount = max(amounts)

        if self.po_count > 1:
            variance = (
                sum((x - self.average_amount) ** 2 for x in amounts) / self.po_count
            )
            self.std_amount = math.sqrt(variance)
        else:
            self.std_amount = 0.0

        # Days between consecutive POs
        sorted_pos = sorted(self.purchase_orders, key=lambda p: p.po_date)
        if len(sorted_pos) > 1:
            days_between: List[int] = []
            for i in range(len(sorted_pos) - 1):
                days = (sorted_pos[i + 1].po_date - sorted_pos[i].po_date).days
                days_between.append(days)

            self.average_days_between = sum(days_between) / len(days_between)
            self.min_days_between = min(days_between)
            self.max_days_between = max(days_between)
            self.is_sequential = all(d <= 1 for d in days_between)

        # Threshold check
        if self.review_threshold > 0:
            self.threshold_exceeded = self.total_amount > self.review_threshold
            if self.threshold_exceeded:
                self.amount_exceeded_by = self.total_amount - self.review_threshold


class ContractSplittingResult(BaseModel):
    """Complete contract splitting detection result."""

    signal_value: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)

    # Detection context
    vendor_id: str
    vendor_name: str
    department_id: str
    department_name: str
    review_threshold: float

    # Splitting groups
    splitting_groups: List[ContractSplittingGroup]
    high_risk_groups: List[ContractSplittingGroup]

    # Aggregated metrics
    total_split_amount: float
    total_splitting_groups: int
    total_purchase_orders: int
    total_po_count: int

    # Patterns
    detected_patterns: List[SplittingPattern]
    severity: SplittingSeverity

    # Evidence & recommendations
    evidence: List[str]
    recommendations: List[str]

    # Detailed analysis
    window_analysis: Dict[str, Any] = Field(default_factory=dict)
    pattern_analysis: Dict[str, Any] = Field(default_factory=dict)

    # Metadata
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[int] = None

    @field_validator("signal_value")
    @classmethod
    def validate_signal(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


class SplittingDetectionInput(BaseModel):
    """Input for contract splitting detection."""

    transaction_id: str
    vendor_id: str
    vendor_name: str
    department_id: str
    department_name: str
    amount: float
    po_date: date
    po_id: str
    description: Optional[str] = None
    category: Optional[str] = None
    approver_id: Optional[str] = None
    approver_name: Optional[str] = None
    review_threshold: Optional[float] = None
    window_days: int = 14

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

    def to_purchase_order(self) -> PurchaseOrder:
        """Convert to a ``PurchaseOrder``."""
        return PurchaseOrder(
            po_id=self.po_id,
            vendor_id=self.vendor_id,
            vendor_name=self.vendor_name,
            department_id=self.department_id,
            department_name=self.department_name,
            amount=self.amount,
            po_date=self.po_date,
            description=self.description,
            category=self.category,
            approver_id=self.approver_id,
            approver_name=self.approver_name,
            review_threshold=self.review_threshold,
        )
