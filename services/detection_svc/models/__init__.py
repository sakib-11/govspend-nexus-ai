"""Models package for detection service."""

from .detection import (
    DetectionType,
    DetectionSeverity,
    DetectionStatus,
    PriceDeviationSignal,
    DetectionResult,
)
from .price_deviation import (
    PeerTransaction,
    PeerGroup,
    PriceDeviationInput,
)
from .benchmarks import (
    BenchmarkPrice,
    BenchmarkCacheEntry,
)
from .duplicate import (
    DuplicateMatchType,
    SimilarityMatch,
    DuplicateDetectionResult,
    DuplicateSearchParams,
    FuzzyMatchCandidate,
)
from .timing import (
    TimingAnomalyType,
    AnomalySeverity,
    TimingStatistics,
    TimingAnomalyResult,
    ApprovalTimeInput,
)
from .contract_splitting import (
    SplittingPattern,
    SplittingSeverity,
    PurchaseOrder,
    ContractSplittingGroup,
    ContractSplittingResult,
    SplittingDetectionInput,
)
from .approval_velocity import (
    ApprovalVelocitySeverity,
    ApprovalContext,
    HistoricalApprovalStats,
    ApprovalVelocityInput,
    ApprovalVelocityResult,
)
from .vendor_graph import (
    NodeType,
    EdgeType,
    GraphNode,
    GraphEdge,
    VendorGraph,
    HHIResult,
    RepeatOfficialResult,
    VendorGraphRiskResult,
    DepartmentSpend,
    OfficialVendorRelationship,
)

__all__ = [
    "DetectionType",
    "DetectionSeverity",
    "DetectionStatus",
    "PriceDeviationSignal",
    "DetectionResult",
    "PeerTransaction",
    "PeerGroup",
    "PriceDeviationInput",
    "BenchmarkPrice",
    "BenchmarkCacheEntry",
    "DuplicateMatchType",
    "SimilarityMatch",
    "DuplicateDetectionResult",
    "DuplicateSearchParams",
    "FuzzyMatchCandidate",
    "TimingAnomalyType",
    "AnomalySeverity",
    "TimingStatistics",
    "TimingAnomalyResult",
    "ApprovalTimeInput",
    "SplittingPattern",
    "SplittingSeverity",
    "PurchaseOrder",
    "ContractSplittingGroup",
    "ContractSplittingResult",
    "SplittingDetectionInput",
    "ApprovalVelocitySeverity",
    "ApprovalContext",
    "HistoricalApprovalStats",
    "ApprovalVelocityInput",
    "ApprovalVelocityResult",
    "NodeType",
    "EdgeType",
    "GraphNode",
    "GraphEdge",
    "VendorGraph",
    "HHIResult",
    "RepeatOfficialResult",
    "VendorGraphRiskResult",
    "DepartmentSpend",
    "OfficialVendorRelationship",
]