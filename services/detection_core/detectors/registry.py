"""Detector Registry for managing all detectors."""

from typing import Dict, Type, Optional, List, Any
from ..models.signals import DetectionType
from .base import BaseDetector
from ..models.signals import DetectionType as DT
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DetectorRegistry:
    """Registry for managing detector instances"""

    def __init__(self):
        self._detectors: Dict[str, Type[BaseDetector]] = {}
        self._detector_weights: Dict[str, float] = {}
        self._detector_instances: Dict[str, BaseDetector] = {}
        self._detector_configs: Dict[str, Dict[str, Any]] = {}

        # Register built-in detectors
        self.register_detectors()

    def register_detectors(self):
        """Register all built-in detectors"""
        # Import here to avoid circular imports
        from .price_deviation import PriceDeviationDetector
        from .duplicate_fuzzy import DuplicateFuzzyDetector
        from .vendor_graph_risk import VendorGraphRiskDetector
        from .timing_anomaly import TimingAnomalyDetector
        from .contract_splitting import ContractSplittingDetector

        self.register(
            "price_deviation",
            PriceDeviationDetector,
            weight=0.30,
            config={"lookback_days": 90, "min_samples": 10}
        )
        self.register(
            "duplicate_fuzzy",
            DuplicateFuzzyDetector,
            weight=0.20,
            config={"similarity_threshold": 0.85, "window_days": 30}
        )
        self.register(
            "vendor_graph_risk",
            VendorGraphRiskDetector,
            weight=0.20,
            config={"lookback_days": 365, "hhi_weight": 0.6, "repeat_weight": 0.4}
        )
        self.register(
            "timing_anomaly",
            TimingAnomalyDetector,
            weight=0.10,
            config={"z_score_threshold": 2.0, "fiscal_end_window": 14}
        )
        self.register(
            "contract_splitting",
            ContractSplittingDetector,
            weight=0.15,
            config={"window_days": 14, "min_pos": 3}
        )
        # Approval velocity detector (placeholder)
        self.register(
            "approval_velocity",
            None,
            weight=0.05,
            config={}
        )

        logger.info(f"Registered {len(self._detectors)} detectors")

    def register(
        self,
        detector_id: str,
        detector_class: Optional[Type[BaseDetector]],
        weight: float = 0.0,
        config: Optional[Dict[str, Any]] = None
    ):
        """Register a detector"""
        self._detectors[detector_id] = detector_class
        self._detector_weights[detector_id] = weight
        self._detector_configs[detector_id] = config or {}

    def get_detector(self, detector_id: str) -> Optional[BaseDetector]:
        """Get or create detector instance"""
        if detector_id in self._detector_instances:
            return self._detector_instances[detector_id]

        detector_class = self._detectors.get(detector_id)
        if not detector_class:
            logger.error(f"Detector {detector_id} not registered")
            return None

        try:
            config = self._detector_configs.get(detector_id, {})
            instance = detector_class(**config)
            self._detector_instances[detector_id] = instance
            return instance
        except Exception as e:
            logger.error(f"Failed to create detector {detector_id}: {e}")
            return None

    def get_all_detectors(self) -> List[str]:
        """Get all registered detector IDs"""
        return list(self._detectors.keys())

    def get_weight(self, detector_id: str) -> float:
        """Get detector weight"""
        return self._detector_weights.get(detector_id, 0.0)

    def get_required_fields(self, detector_id: str) -> List[str]:
        """Get required fields for a detector"""
        instance = self.get_detector(detector_id)
        if instance:
            return instance.get_required_fields()
        return []

    def get_detector_metadata(self, detector_id: str) -> Dict[str, Any]:
        """Get detector metadata"""
        return {
            "detector_id": detector_id,
            "weight": self.get_weight(detector_id),
            "required_fields": self.get_required_fields(detector_id),
            "config": self._detector_configs.get(detector_id, {})
        }

    def get_all_detectors_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all detectors"""
        return {
            detector_id: self.get_detector_metadata(detector_id)
            for detector_id in self.get_all_detectors()
        }