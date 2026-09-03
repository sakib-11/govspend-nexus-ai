"""Duplicate Fuzzy Detector - Fuzzy matching for duplicate detection."""

from typing import Dict, Any, List
from .base import BaseDetector
from ..models.signals import DetectionType


class DuplicateFuzzyDetector(BaseDetector):
    """Duplicate fuzzy detector using similarity matching"""

    def __init__(self, similarity_threshold: float = 0.85, window_days: int = 30):
        super().__init__()
        self.similarity_threshold = similarity_threshold
        self.window_days = window_days

    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Detect duplicate transactions"""
        # In production, this would query recent transactions and compute similarity
        # For now, return a mock result
        vendor_id = transaction.get("vendor_id", "")
        amount = transaction.get("amount", 0)

        # Mock similarity check
        is_duplicate = False
        similarity = 0.0

        if vendor_id == "known_duplicate_vendor":
            is_duplicate = True
            similarity = 0.92

        signal_value = similarity if is_duplicate else 0.0
        confidence = 0.85 if is_duplicate else 0.1

        return self.create_signal(
            transaction_id=transaction.get("transaction_id", "unknown"),
            signal_value=signal_value,
            confidence=confidence,
            detection_type=DetectionType.DUPLICATE,
            raw_value=similarity,
            evidence=[f"Similarity score: {similarity:.2%}"] if is_duplicate else [],
            recommendations=["Flag for manual review"] if is_duplicate else []
        )

    def get_weight(self) -> float:
        return 0.20

    def get_required_fields(self) -> List[str]:
        return ["vendor_id", "amount", "transaction_date"]