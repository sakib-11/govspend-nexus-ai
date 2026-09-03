"""Detector registry for managing all detectors."""

from typing import Dict, List, Optional

from .base import BaseDetector
from ..models.detection import DetectionType
from .price_deviation import PriceDeviationDetector
from .duplicate_fuzzy import DuplicateFuzzyDetector
from .timing_anomaly import TimingAnomalyDetector
from .contract_splitting import ContractSplittingDetector
from .approval_velocity import ApprovalVelocityDetector
from .vendor_graph_risk import VendorGraphRiskDetector


class DetectorRegistry:
    """Registry for all detectors."""

    def __init__(self):
        self._detectors: Dict[DetectionType, BaseDetector] = {}
        self._register_default_detectors()

    def _register_default_detectors(self) -> None:
        """Register default detectors."""
        self.register(PriceDeviationDetector())
        self.register(DuplicateFuzzyDetector())
        self.register(TimingAnomalyDetector())
        self.register(ContractSplittingDetector())
        self.register(ApprovalVelocityDetector())
        self.register(VendorGraphRiskDetector())

    def register(self, detector: BaseDetector) -> None:
        """Register a detector."""
        self._detectors[detector.detector_type] = detector

    def get(self, detector_type: DetectionType) -> Optional[BaseDetector]:
        """Get a detector by type."""
        return self._detectors.get(detector_type)

    def get_all(self) -> List[BaseDetector]:
        """Get all registered detectors."""
        return list(self._detectors.values())

    def get_by_weight(self) -> List[BaseDetector]:
        """Get detectors sorted by weight (highest first)."""
        return sorted(self._detectors.values(), key=lambda d: d.get_weight(), reverse=True)


# Global registry instance
registry = DetectorRegistry()