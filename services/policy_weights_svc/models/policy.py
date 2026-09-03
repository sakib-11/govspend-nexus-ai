"""Policy Weights models — core data structures for version-controlled weight management."""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict
from uuid import uuid4


# ─── Enums ────────────────────────────────────────────────────────


class PolicyStatus(str, Enum):
    """Lifecycle status of a weight policy version."""

    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class CalibrationType(str, Enum):
    """Type of calibration performed."""

    MANUAL = "manual"
    AUTOMATED = "automated"
    DRIFT_DETECTION = "drift_detection"
    A_B_TESTING = "a_b_testing"
    PERFORMANCE_TUNING = "performance_tuning"
    REGULATORY = "regulatory"
    EMERGENCY = "emergency"


class WeightChangeReason(str, Enum):
    """Reason for weight changes."""

    PERFORMANCE_IMPROVEMENT = "performance_improvement"
    FALSE_POSITIVE_REDUCTION = "false_positive_reduction"
    FALSE_NEGATIVE_REDUCTION = "false_negative_reduction"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    SEASONAL_ADJUSTMENT = "seasonal_adjustment"
    DATA_DRIFT = "data_drift"
    EMERGENCY_ADJUSTMENT = "emergency_adjustment"
    MANUAL_REVIEW = "manual_review"
    A_B_TEST_WINNER = "a_b_test_winner"


# ─── Detector Weights ────────────────────────────────────────────

# Canonical detector names — the order and set match the detection pipeline
DETECTOR_NAMES: tuple[str, ...] = (
    "price_deviation",
    "duplicate_fuzzy",
    "vendor_graph_risk",
    "timing_anomaly",
    "contract_splitting",
    "approval_velocity",
)


class DetectorWeights(BaseModel):
    """Weights for individual detectors — must sum to 1.0."""

    model_config = ConfigDict(frozen=False)

    price_deviation: float = Field(default=0.30, ge=0.0, le=1.0)
    duplicate_fuzzy: float = Field(default=0.20, ge=0.0, le=1.0)
    vendor_graph_risk: float = Field(default=0.20, ge=0.0, le=1.0)
    timing_anomaly: float = Field(default=0.10, ge=0.0, le=1.0)
    contract_splitting: float = Field(default=0.15, ge=0.0, le=1.0)
    approval_velocity: float = Field(default=0.05, ge=0.0, le=1.0)

    def weight_sum(self) -> float:
        """Sum of all weights."""
        return sum(getattr(self, name) for name in DETECTOR_NAMES)

    def validate_sum(self, tolerance: float = 0.001) -> bool:
        """Check that weights sum to ~1.0."""
        return abs(self.weight_sum() - 1.0) < tolerance

    def as_dict(self) -> Dict[str, float]:
        """Ordered dict of all weights."""
        return {name: getattr(self, name) for name in DETECTOR_NAMES}

    def diff(self, other: "DetectorWeights") -> Dict[str, float]:
        """Compute per-detector weight differences (other − self)."""
        return {name: getattr(other, name) - getattr(self, name) for name in DETECTOR_NAMES}

    def max_abs_change(self, other: "DetectorWeights") -> float:
        """Largest absolute change across all detectors."""
        diffs = self.diff(other)
        return max(abs(v) for v in diffs.values()) if diffs else 0.0


# ─── Weight Policy ────────────────────────────────────────────────


class WeightPolicy(BaseModel):
    """Complete weight policy version with lifecycle management."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        populate_by_name=True,
    )

    # ── Identifiers ──────────────────────────────────────────────
    policy_id: str = Field(default_factory=lambda: f"pol-{uuid4().hex[:12]}")
    version: str

    # ── Weights ──────────────────────────────────────────────────
    weights: DetectorWeights
    weights_sum: Optional[float] = None

    # ── Metadata ─────────────────────────────────────────────────
    name: str
    description: Optional[str] = None
    status: PolicyStatus = PolicyStatus.DRAFT

    # ── Calibration ──────────────────────────────────────────────
    calibration_type: Optional[CalibrationType] = None
    calibration_reason: Optional[WeightChangeReason] = None
    calibration_data: Optional[Dict[str, Any]] = None

    # ── Performance ──────────────────────────────────────────────
    performance_metrics: Optional[Dict[str, float]] = None

    # ── Version lineage ──────────────────────────────────────────
    previous_version: Optional[str] = None
    supersedes_version: Optional[str] = None

    # ── Timestamps ───────────────────────────────────────────────
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    activated_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None

    # ── Audit ────────────────────────────────────────────────────
    created_by: str = "system"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    # ── Tags / metadata ──────────────────────────────────────────
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Auto-compute weights_sum after construction."""
        self.weights_sum = self.weights.weight_sum()

    # ── Lifecycle helpers ────────────────────────────────────────

    def is_active(self) -> bool:
        return self.status == PolicyStatus.ACTIVE

    def can_activate(self) -> bool:
        return self.status in {
            PolicyStatus.DRAFT,
            PolicyStatus.PENDING_APPROVAL,
        }

    def can_deactivate(self) -> bool:
        return self.status == PolicyStatus.ACTIVE

    def activate(self, approved_by: str) -> None:
        """Transition to ACTIVE status."""
        if not self.can_activate():
            raise ValueError(
                f"Cannot activate policy in status '{self.status.value}' "
                f"(must be draft or pending_approval)"
            )
        now = datetime.now(timezone.utc)
        self.status = PolicyStatus.ACTIVE
        self.approved_by = approved_by
        self.approved_at = now
        self.activated_at = now
        self.updated_at = now

    def deactivate(self) -> None:
        """Transition to INACTIVE status."""
        if not self.can_deactivate():
            raise ValueError(
                f"Cannot deactivate policy in status '{self.status.value}'"
            )
        now = datetime.now(timezone.utc)
        self.status = PolicyStatus.INACTIVE
        self.deactivated_at = now
        self.updated_at = now

    def supersede(self) -> None:
        """Mark as superseded by a newer version."""
        self.status = PolicyStatus.SUPERSEDED
        self.updated_at = datetime.now(timezone.utc)

    def archive(self) -> None:
        """Transition to ARCHIVED status."""
        self.status = PolicyStatus.ARCHIVED
        self.updated_at = datetime.now(timezone.utc)


# ─── Audit ────────────────────────────────────────────────────────


class PolicyAuditLog(BaseModel):
    """Immutable audit record for every policy change."""

    model_config = ConfigDict(populate_by_name=True)

    audit_id: str = Field(default_factory=lambda: f"aud-{uuid4().hex[:12]}")
    policy_id: str
    version: str
    action: str  # CREATE, UPDATE, ACTIVATE, DEACTIVATE, ARCHIVE, CALIBRATE
    old_state: Optional[Dict[str, Any]] = None
    new_state: Dict[str, Any]
    changed_fields: List[str] = Field(default_factory=list)
    performed_by: str
    performed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    reason: Optional[str] = None


# ─── Calibration ──────────────────────────────────────────────────


class CalibrationRequest(BaseModel):
    """Request to calibrate policy weights."""

    name: str
    description: Optional[str] = None
    weights: DetectorWeights
    calibration_type: CalibrationType
    calibration_reason: WeightChangeReason
    calibration_data: Optional[Dict[str, Any]] = None
    created_by: str = "system"
    test_duration_days: int = Field(default=7, ge=1, le=90)


# ─── Query / comparison ──────────────────────────────────────────


class WeightPolicyQuery(BaseModel):
    """Filter parameters for querying policies."""

    status: Optional[List[PolicyStatus]] = None
    version: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    created_by: Optional[str] = None
    tags: Optional[List[str]] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class PolicyVersionComparison(BaseModel):
    """Structured diff between two policy versions."""

    version_a: str
    version_b: str
    weight_diffs: Dict[str, float]
    sum_diff: float
    status_diff: Dict[str, str]
    performance_diff: Optional[Dict[str, float]] = None
    summary: str


# ─── Create / update requests ────────────────────────────────────


class PolicyCreateRequest(BaseModel):
    """Request to create a new policy."""

    name: str
    description: Optional[str] = None
    weights: DetectorWeights
    created_by: str = "system"
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PolicyUpdateRequest(BaseModel):
    """Request to update a draft policy's weights."""

    weights: Optional[DetectorWeights] = None
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    updated_by: str = "system"
    reason: Optional[str] = None
