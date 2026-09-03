"""Signal Collector - Collects and manages signals from detectors."""

from typing import List, Dict, Any, Optional
from datetime import datetime

from ..models.signals import Signal, SignalGroup
from ..models.engine import TransactionContext
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SignalCollector:
    """Collect and manage signals from detectors"""

    def __init__(self):
        self.signals: Dict[str, List[Signal]] = {}  # transaction_id -> signals

    def add_signal(self, transaction_id: str, signal: Signal) -> None:
        """Add a signal to the collector"""
        if transaction_id not in self.signals:
            self.signals[transaction_id] = []
        self.signals[transaction_id].append(signal)

        logger.debug(f"Added signal {signal.signal_id} for transaction {transaction_id}")

    def get_signals(self, transaction_id: str) -> List[Signal]:
        """Get all signals for a transaction"""
        return self.signals.get(transaction_id, [])

    def get_signal_group(self, transaction_id: str) -> Optional[SignalGroup]:
        """Get signal group for a transaction"""
        signals = self.get_signals(transaction_id)
        if not signals:
            return None

        group = SignalGroup(
            transaction_id=transaction_id,
            signals=signals
        )
        group.calculate_metrics()
        return group

    def get_signals_by_type(
        self,
        transaction_id: str,
        detection_type: str
    ) -> List[Signal]:
        """Get signals of a specific type"""
        signals = self.get_signals(transaction_id)
        return [s for s in signals if s.detection_type == detection_type]

    def get_high_signals(
        self,
        transaction_id: str,
        threshold: float = 0.5
    ) -> List[Signal]:
        """Get signals above a threshold"""
        signals = self.get_signals(transaction_id)
        return [s for s in signals if s.value >= threshold]

    def calculate_risk_score(self, transaction_id: str) -> float:
        """
        Calculate overall risk score from all signals
        Weighted sum of signal values
        """
        signals = self.get_signals(transaction_id)
        if not signals:
            return 0.0

        total_weight = sum(s.weight for s in signals)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(s.value * s.weight * s.confidence for s in signals)
        return weighted_sum / total_weight

    def clear(self, transaction_id: str) -> None:
        """Clear signals for a transaction"""
        if transaction_id in self.signals:
            del self.signals[transaction_id]
            logger.debug(f"Cleared signals for transaction {transaction_id}")