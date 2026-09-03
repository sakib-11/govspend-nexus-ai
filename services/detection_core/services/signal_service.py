"""Signal Service - Manages signals in database."""

from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from ..models.signals import Signal, SignalGroup, SignalStatus, DetectionType
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SignalService:
    """Service for managing signals in database"""

    def __init__(self):
        # In production, this would use a real database
        self._signals_db: Dict[str, List[Signal]] = {}
        self._signal_groups: Dict[str, SignalGroup] = {}

    async def save_signals(self, signal_group: SignalGroup) -> str:
        """Save signals to database"""
        group_id = str(uuid.uuid4())

        # In production, this would insert into database
        self._signal_groups[group_id] = signal_group

        for signal in signal_group.signals:
            if signal.transaction_id not in self._signals_db:
                self._signals_db[signal.transaction_id] = []
            self._signals_db[signal.transaction_id].append(signal)

        logger.info(f"Saved {len(signal_group.signals)} signals for transaction {signal_group.transaction_id}")
        return group_id

    async def get_signals(
        self,
        transaction_id: str,
        detection_type: Optional[DetectionType] = None
    ) -> List[Signal]:
        """Get signals for a transaction"""
        signals = self._signals_db.get(transaction_id, [])

        if detection_type:
            signals = [s for s in signals if s.detection_type == detection_type]

        return signals

    async def get_signal(self, signal_id: str) -> Optional[Signal]:
        """Get a signal by ID"""
        for signals in self._signals_db.values():
            for signal in signals:
                if signal.signal_id == signal_id:
                    return signal
        return None

    async def update_signal_status(
        self,
        signal_id: str,
        status: SignalStatus,
        processed_at: Optional[datetime] = None
    ) -> bool:
        """Update signal status"""
        signal = await self.get_signal(signal_id)
        if not signal:
            return False

        signal.status = status
        signal.processed_at = processed_at or datetime.utcnow()
        return True

    async def get_signal_group(self, transaction_id: str) -> Optional[SignalGroup]:
        """Get signal group for a transaction"""
        for group in self._signal_groups.values():
            if group.transaction_id == transaction_id:
                return group
        return None

    async def get_high_risk_transactions(
        self,
        threshold: float = 0.7,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get transactions with high risk signals"""
        high_risk = []

        for transaction_id, signals in self._signals_db.items():
            if not signals:
                continue

            # Calculate max signal
            max_signal = max(s.value for s in signals)

            if max_signal >= threshold:
                high_risk.append({
                    "transaction_id": transaction_id,
                    "signals": signals,
                    "max_signal": max_signal,
                    "signal_count": len(signals)
                })

        # Sort by max signal
        high_risk.sort(key=lambda x: x["max_signal"], reverse=True)

        return high_risk[:limit]