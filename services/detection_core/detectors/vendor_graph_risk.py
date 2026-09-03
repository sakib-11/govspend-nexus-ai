"""Vendor Graph Risk Detector - HHI and repeat official analysis."""

from typing import Dict, Any, List
from .base import BaseDetector
from ..models.signals import DetectionType


class VendorGraphRiskDetector(BaseDetector):
    """Vendor graph risk detector using HHI and repeat official analysis"""

    def __init__(self, lookback_days: int = 365, hhi_weight: float = 0.6, repeat_weight: float = 0.4):
        super().__init__()
        self.lookback_days = lookback_days
        self.hhi_weight = hhi_weight
        self.repeat_weight = repeat_weight

    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Detect vendor graph risk"""
        # In production, this would query the vendor graph
        # For now, return mock results
        department_id = transaction.get("department_id", "")
        vendor_id = transaction.get("vendor_id", "")

        # Mock HHI calculation
        hhi_normalized = 0.35  # Moderate concentration

        # Mock repeat official score
        repeat_score = 0.25

        # Combined signal
        signal_value = hhi_normalized * self.hhi_weight + repeat_score * self.repeat_weight
        confidence = 0.75

        return self.create_signal(
            transaction_id=transaction.get("transaction_id", "unknown"),
            signal_value=signal_value,
            confidence=confidence,
            detection_type=DetectionType.VENDOR_RISK,
            raw_value=signal_value,
            evidence=[
                f"HHI: {hhi_normalized:.2f}",
                f"Repeat official score: {repeat_score:.2f}"
            ],
            recommendations=["Monitor vendor concentration"] if signal_value > 0.5 else []
        )

    def get_weight(self) -> float:
        return 0.20

    def get_required_fields(self) -> List[str]:
        return ["department_id", "vendor_id", "amount"]