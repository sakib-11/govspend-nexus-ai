"""Timing Anomaly Detector - Statistical anomaly detection in approval timing."""

from typing import Dict, Any, List
from .base import BaseDetector
from ..models.signals import DetectionType


class TimingAnomalyDetector(BaseDetector):
    """Timing anomaly detector using statistical analysis"""

    def __init__(self, z_score_threshold: float = 2.0, fiscal_end_window: int = 14):
        super().__init__()
        self.z_score_threshold = z_score_threshold
        self.fiscal_end_window = fiscal_end_window

    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Detect timing anomalies"""
        # In production, this would analyze approval timing patterns
        # For now, return mock results
        approval_days = transaction.get("approval_days", 5)
        is_fiscal_end = transaction.get("is_fiscal_end", False)

        # Mock statistical analysis
        mean_days = 7.0
        std_days = 2.0
        z_score = (approval_days - mean_days) / std_days if std_days > 0 else 0

        # Amplify if near fiscal end
        if is_fiscal_end:
            z_score *= 1.5

        signal_value = min(1.0, abs(z_score) / 3.0) if abs(z_score) > self.z_score_threshold else 0.0
        confidence = 0.7

        return self.create_signal(
            transaction_id=transaction.get("transaction_id", "unknown"),
            signal_value=signal_value,
            confidence=confidence,
            detection_type=DetectionType.TIMING_ANOMALY,
            raw_value=z_score,
            evidence=[
                f"Approval time: {approval_days} days",
                f"Z-score: {z_score:.2f}",
                f"Fiscal end period: {is_fiscal_end}"
            ],
            recommendations=["Review approval workflow"] if signal_value > 0.5 else []
        )

    def get_weight(self) -> float:
        return 0.10

    def get_required_fields(self) -> List[str]:
        return ["approval_days", "transaction_date", "submitted_date"]