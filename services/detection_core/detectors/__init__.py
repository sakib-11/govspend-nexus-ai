"""Detectors package for Detection Core."""

from .base import BaseDetector
from .price_deviation import PriceDeviationDetector
from .duplicate_fuzzy import DuplicateFuzzyDetector
from .vendor_graph_risk import VendorGraphRiskDetector
from .timing_anomaly import TimingAnomalyDetector
from .contract_splitting import ContractSplittingDetector
from .registry import DetectorRegistry

__all__ = [
    "BaseDetector",
    "PriceDeviationDetector",
    "DuplicateFuzzyDetector",
    "VendorGraphRiskDetector",
    "TimingAnomalyDetector",
    "ContractSplittingDetector",
    "DetectorRegistry",
]