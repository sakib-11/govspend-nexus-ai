"""Base detector interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from ..models.signals import Signal, DetectionType, SignalStatus


class BaseDetector(ABC):
    """Abstract base class for all detectors"""

    def __init__(self, **kwargs):
        self.config = kwargs

    @abstractmethod
    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run detection on a transaction.

        Returns:
            Dict with:
            - signal_value: float (0-1)
            - confidence: float (0-1)
            - raw_deviation: optional float
            - evidence: List[str]
            - recommendations: List[str]
            - metadata: Dict[str, Any]
        """
        pass

    @abstractmethod
    def get_weight(self) -> float:
        """Get detector weight for scoring"""
        pass

    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """Get list of required transaction fields"""
        pass

    def create_signal(
        self,
        transaction_id: str,
        signal_value: float,
        confidence: float,
        detection_type: DetectionType,
        raw_value: Optional[float] = None,
        evidence: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a signal result dict"""
        return {
            "signal_value": signal_value,
            "confidence": confidence,
            "raw_deviation": raw_value,
            "evidence": evidence or [],
            "recommendations": recommendations or [],
            "metadata": metadata or {},
            "detection_type": detection_type.value
        }