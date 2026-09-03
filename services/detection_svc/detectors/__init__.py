"""Detectors package for detection service."""

from .base import BaseDetector
from .price_deviation import PriceDeviationDetector
from .duplicate_fuzzy import DuplicateFuzzyDetector
from .timing_anomaly import TimingAnomalyDetector
from .vendor_graph_risk import VendorGraphRiskDetector
from .contract_splitting import ContractSplittingDetector
from .approval_velocity import ApprovalVelocityDetector
from .registry import DetectorRegistry, registry

__all__ = [
    "BaseDetector",
    "PriceDeviationDetector",
    "DuplicateFuzzyDetector",
    "TimingAnomalyDetector",
    "VendorGraphRiskDetector",
    "ContractSplittingDetector",
    "ApprovalVelocityDetector",
    "DetectorRegistry",
    "registry",
]