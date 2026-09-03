"""Evidence Bundle models — core data structures for the evidence pipeline."""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict, model_validator
from uuid import uuid4
import json
import hashlib
import sys


class BundleStatus(str, Enum):
    """Lifecycle status of an evidence bundle."""

    PENDING = "PENDING"
    ASSEMBLED = "ASSEMBLED"
    STORED = "STORED"
    RETRIEVED = "RETRIEVED"
    ARCHIVED = "ARCHIVED"
    ERROR = "ERROR"


class BundleFormat(str, Enum):
    """Bundle serialization format."""

    JSON = "JSON"
    JSON_COMPACT = "JSON_COMPACT"
    JSON_EXTENDED = "JSON_EXTENDED"


class EvidenceSource(str, Enum):
    """Origin of an evidence item."""

    DETECTOR_SIGNAL = "DETECTOR_SIGNAL"
    TRANSACTION_DATA = "TRANSACTION_DATA"
    VENDOR_DATA = "VENDOR_DATA"
    BENCHMARK_DATA = "BENCHMARK_DATA"
    DERIVED = "DERIVED"


class EvidenceItem(BaseModel):
    """A single, atomic piece of evidence."""

    model_config = ConfigDict(populate_by_name=True)

    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    source: EvidenceSource
    source_type: str  # e.g. "price_deviation", "amount", "vendor_metadata"
    source_id: str  # Reference ID from source system
    data: Dict[str, Any]
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None

    def to_compact(self) -> Dict[str, Any]:
        """Compact representation for storage / indexing."""
        return {
            "id": self.evidence_id,
            "source": self.source.value,
            "type": self.source_type,
            "confidence": self.confidence,
            "ts": self.timestamp.isoformat(),
        }


class DetectorEvidence(BaseModel):
    """Aggregated evidence from a single detector run."""

    detector_type: str
    signal_value: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    benchmark_data: Optional[Dict[str, Any]] = None
    evidence_items: List[EvidenceItem] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class TransactionEvidence(BaseModel):
    """Evidence derived from the canonical transaction record."""

    transaction_id: str
    canonical_data: Dict[str, Any] = Field(default_factory=dict)
    vendor_data: Dict[str, Any] = Field(default_factory=dict)
    department_data: Optional[Dict[str, Any]] = None
    timestamps: Dict[str, Any] = Field(default_factory=dict)
    amounts: Dict[str, Any] = Field(default_factory=dict)
    evidence_items: List[EvidenceItem] = Field(default_factory=list)


class BenchmarkEvidence(BaseModel):
    """Reference benchmark data used by detectors."""

    benchmark_type: str  # e.g. "price_quartiles", "historical_statistics"
    benchmark_data: Dict[str, Any] = Field(default_factory=dict)
    source: str  # Detector or system that produced this benchmark
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_items: List[EvidenceItem] = Field(default_factory=list)


# ---------- Main bundle ----------


class EvidenceBundle(BaseModel):
    """Complete evidence bundle for one transaction.

    Immutable once assembled — all mutations go through the assembler.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        populate_by_name=True,
    )

    # ── Core identifiers ──────────────────────────────────────────
    bundle_id: str = Field(
        default_factory=lambda: f"bundle-{uuid4().hex[:12]}"
    )
    transaction_id: str
    version: str = "1.0"

    # ── Lifecycle ─────────────────────────────────────────────────
    status: BundleStatus = BundleStatus.PENDING
    format: BundleFormat = BundleFormat.JSON_EXTENDED

    # ── Evidence containers ───────────────────────────────────────
    transaction_evidence: Optional[TransactionEvidence] = None
    detector_evidences: List[DetectorEvidence] = Field(default_factory=list)
    benchmark_evidences: List[BenchmarkEvidence] = Field(default_factory=list)

    # ── Scoring context ───────────────────────────────────────────
    weights_version: Optional[str] = None
    risk_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    risk_tier: Optional[str] = None
    confidence_factor: Optional[float] = Field(None, ge=0.0, le=1.0)

    # ── Audit / metadata ──────────────────────────────────────────
    assembled_at: Optional[datetime] = None
    assembled_by: str = "evidence-bundle-svc"
    size_bytes: int = 0
    storage_location: Optional[str] = None
    storage_checksum: Optional[str] = None

    # ── Lifecycle timestamps ──────────────────────────────────────
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    retrieved_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None

    # ── Tags / metadata ───────────────────────────────────────────
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # ── Serialization helpers ─────────────────────────────────────

    def to_dict(self, compact: bool = False) -> Dict[str, Any]:
        """Convert to plain dict.  ``compact=True`` strips heavy fields."""
        if compact:
            return {
                "bundle_id": self.bundle_id,
                "transaction_id": self.transaction_id,
                "status": self.status.value,
                "weights_version": self.weights_version,
                "risk_score": self.risk_score,
                "risk_tier": self.risk_tier,
                "detector_count": len(self.detector_evidences),
                "evidence_count": self.get_evidence_count(),
                "size_bytes": self.size_bytes,
                "assembled_at": self.assembled_at.isoformat()
                if self.assembled_at
                else None,
            }
        return self.model_dump(mode="json")

    def to_json(self, compact: bool = False, indent: int = 2) -> str:
        """Serialize to JSON string."""
        if compact:
            return json.dumps(
                self.to_dict(compact=True), separators=(",", ":"), default=str
            )
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def _canonical_dict(self) -> Dict[str, Any]:
        """Snapshot of the bundle excluding mutable size/checksum fields.

        This avoids self-referential issues where ``calculate_size``
        includes the ``size_bytes`` value in the serialized output,
        causing the byte count to change depending on the number's
        digit length.
        """
        d = self.to_dict()
        d.pop("size_bytes", None)
        d.pop("storage_checksum", None)
        d.pop("storage_location", None)
        return d

    def calculate_size(self) -> int:
        """Estimate serialized byte size (self-referential fields excluded)."""
        return len(json.dumps(self._canonical_dict(), default=str).encode("utf-8"))

    def compute_checksum(self) -> str:
        """SHA-256 of the canonical JSON for integrity verification."""
        payload = json.dumps(self._canonical_dict(), default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    # ── Introspection ─────────────────────────────────────────────

    def get_detector_types(self) -> List[str]:
        return [d.detector_type for d in self.detector_evidences]

    def get_evidence_count(self) -> int:
        count = 0
        if self.transaction_evidence:
            count += len(self.transaction_evidence.evidence_items)
        for det in self.detector_evidences:
            count += len(det.evidence_items)
        for bm in self.benchmark_evidences:
            count += len(bm.evidence_items)
        return count

    def get_all_evidence_items(self) -> List[EvidenceItem]:
        """Flatten all evidence items across every container."""
        items: List[EvidenceItem] = []
        if self.transaction_evidence:
            items.extend(self.transaction_evidence.evidence_items)
        for det in self.detector_evidences:
            items.extend(det.evidence_items)
        for bm in self.benchmark_evidences:
            items.extend(bm.evidence_items)
        return items

    def has_detector(self, detector_type: str) -> bool:
        return any(d.detector_type == detector_type for d in self.detector_evidences)

    def get_detector(self, detector_type: str) -> Optional[DetectorEvidence]:
        for d in self.detector_evidences:
            if d.detector_type == detector_type:
                return d
        return None

    def mark_assembled(self):
        """Transition status → ASSEMBLED and update timestamp."""
        self.status = BundleStatus.ASSEMBLED
        self.assembled_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def mark_stored(self, location: str):
        """Transition status → STORED after persistence."""
        self.status = BundleStatus.STORED
        self.storage_location = location
        self.updated_at = datetime.now(timezone.utc)

    def mark_archived(self):
        """Transition status → ARCHIVED for soft-delete."""
        self.status = BundleStatus.ARCHIVED
        self.archived_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)


# ---------- Request / response models ----------


class BundleReference(BaseModel):
    """Lightweight pointer to a stored bundle (avoids full deserialization)."""

    bundle_id: str
    transaction_id: str
    storage_location: str
    storage_checksum: str
    size_bytes: int
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BundleQueryRequest(BaseModel):
    """Filter parameters for querying stored bundles."""

    transaction_id: Optional[str] = None
    bundle_id: Optional[str] = None
    status: Optional[BundleStatus] = None
    risk_tier: Optional[str] = None
    detector_types: Optional[List[str]] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class BundleAssembleRequest(BaseModel):
    """Explicit request to assemble a bundle."""

    transaction_id: str
    scoring_result: Dict[str, Any] = Field(default_factory=dict)
    include_benchmarks: bool = True
    bundle_format: BundleFormat = BundleFormat.JSON_EXTENDED


class BundleBulkAssembleRequest(BaseModel):
    """Bulk assembly request."""

    items: List[BundleAssembleRequest] = Field(..., min_length=1, max_length=100)
