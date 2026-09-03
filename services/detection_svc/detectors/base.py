"""Base detector interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List
import uuid

from ..models.detection import DetectionResult, DetectionType, DetectionStatus


class BaseDetector(ABC):
    """Abstract base class for all detectors."""

    def __init__(self, detector_type: DetectionType):
        self.detector_type = detector_type
        self.name = detector_type.value

    @abstractmethod
    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run detection on a transaction.
        Returns: Detection result with signal and metadata.
        """
        pass

    @abstractmethod
    def get_weight(self) -> float:
        """Get detector weight for scoring."""
        pass

    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """Get list of required transaction fields."""
        pass

    def create_detection_result(
        self,
        transaction_id: str,
        signal_value: float,
        confidence: float,
        details: Dict[str, Any],
        severity: str,
        evidence: List[str],
        recommendations: List[str]
    ) -> DetectionResult:
        """Create a standardized detection result."""
        return DetectionResult(
            id=str(uuid.uuid4()),
            transaction_id=transaction_id,
            detection_type=self.detector_type,
            severity=severity,
            signal_value=signal_value,
            confidence=confidence,
            details=details,
            evidence=evidence,
            recommendations=recommendations,
            status=DetectionStatus.COMPLETED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    def calculate_severity(self, signal_value: float, confidence: float) -> str:
        """Calculate severity level from signal and confidence."""
        if confidence < 0.3:
            return "low"

        effective_signal = signal_value * confidence

        if effective_signal >= 0.9:
            return "critical"
        elif effective_signal >= 0.75:
            return "high"
        elif effective_signal >= 0.5:
            return "medium"
        else:
            return "low"