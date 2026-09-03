"""Contract Splitting Detector - Detects potential contract splitting."""

from typing import Dict, Any, List
from .base import BaseDetector
from ..models.signals import DetectionType


class ContractSplittingDetector(BaseDetector):
    """Contract splitting detector"""

    def __init__(self, window_days: int = 14, min_pos: int = 3):
        super().__init__()
        self.window_days = window_days
        self.min_pos = min_pos

    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Detect contract splitting"""
        # In production, this would query recent POs/Contracts for same vendor/category
        # For now, return mock results
        vendor_id = transaction.get("vendor_id", "")
        category = transaction.get("category", "")
        amount = transaction.get("amount", 0)

        # Mock check for recent similar transactions
        recent_count = 0
        if vendor_id == "split_vendor":
            recent_count = 4

        signal_value = min(1.0, recent_count / 5.0) if recent_count >= self.min_pos else 0.0
        confidence = 0.8 if recent_count >= self.min_pos else 0.2

        return self.create_signal(
            transaction_id=transaction.get("transaction_id", "unknown"),
            signal_value=signal_value,
            confidence=confidence,
            detection_type=DetectionType.CONTRACT_SPLITTING,
            raw_value=recent_count,
            evidence=[
                f"Recent similar POs: {recent_count}",
                f"Window: {self.window_days} days",
                f"Threshold: {self.min_pos} POs"
            ],
            recommendations=["Consolidate procurement"] if signal_value > 0.5 else []
        )

    def get_weight(self) -> float:
        return 0.15

    def get_required_fields(self) -> List[str]:
        return ["vendor_id", "category", "amount", "transaction_date"]