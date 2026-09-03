"""Price Deviation Detector - IQR-based anomaly detection."""

from typing import Dict, Any, List
from .base import BaseDetector
from ..models.signals import DetectionType


class PriceDeviationDetector(BaseDetector):
    """Price deviation detector using IQR-based anomaly detection"""

    def __init__(self, lookback_days: int = 90, min_samples: int = 10):
        super().__init__()
        self.lookback_days = lookback_days
        self.min_samples = min_samples

    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Detect price deviation"""
        # Extract required fields
        amount = transaction.get("amount", 0)
        quantity = transaction.get("quantity", 1)
        unit_price = amount / quantity if quantity > 0 else amount

        # In production, this would query historical peer prices
        # For now, use mock benchmark
        benchmark_price = 100.0
        iqr = 15.0
        upper_fence = benchmark_price + 1.5 * iqr

        # Calculate signal
        if unit_price > upper_fence:
            deviation = unit_price - upper_fence
            signal_value = min(1.0, deviation / (benchmark_price * 0.5))
        else:
            signal_value = 0.0

        confidence = 0.8

        return self.create_signal(
            transaction_id=transaction.get("transaction_id", "unknown"),
            signal_value=signal_value,
            confidence=confidence,
            detection_type=DetectionType.PRICE_DEVIATION,
            raw_value=unit_price,
            evidence=[f"Unit price ${unit_price:.2f} vs benchmark ${benchmark_price:.2f}"],
            recommendations=["Review pricing against peer benchmarks"] if signal_value > 0.5 else []
        )

    def get_weight(self) -> float:
        return 0.30

    def get_required_fields(self) -> List[str]:
        return ["amount", "quantity", "category", "region"]