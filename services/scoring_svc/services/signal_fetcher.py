"""Signal fetcher service for retrieving detector signals from database."""

from datetime import datetime

import asyncpg

from ..models.signals import DetectorSignal


class SignalFetcher:
    """Fetches detector signals from the database."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def fetch_signals_for_transaction(
        self,
        transaction_id: str,
        min_confidence: float = 0.30,
    ) -> list[DetectorSignal]:
        """Fetch all signals for a transaction with minimum confidence filter."""
        query = """
            SELECT 
                detector_type,
                signal_value,
                confidence,
                evidence_ids,
                transaction_id,
                timestamp,
                metadata
            FROM detection_signals
            WHERE transaction_id = $1
                AND confidence >= $2
            ORDER BY timestamp DESC
        """

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, transaction_id, min_confidence)

            signals = []
            for row in rows:
                signal = DetectorSignal(
                    detector_type=row["detector_type"],
                    signal_value=float(row["signal_value"]),
                    confidence=float(row["confidence"]),
                    evidence_ids=row["evidence_ids"] or [],
                    transaction_id=row["transaction_id"],
                    timestamp=row["timestamp"],
                    metadata=row["metadata"] or {},
                )
                signals.append(signal)

            return signals

    async def fetch_signals_bulk(
        self,
        transaction_ids: list[str],
        min_confidence: float = 0.30,
    ) -> dict[str, list[DetectorSignal]]:
        """Fetch signals for multiple transactions in bulk."""
        if not transaction_ids:
            return {}

        query = """
            SELECT 
                detector_type,
                signal_value,
                confidence,
                evidence_ids,
                transaction_id,
                timestamp,
                metadata
            FROM detection_signals
            WHERE transaction_id = ANY($1)
                AND confidence >= $2
            ORDER BY transaction_id, timestamp DESC
        """

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, transaction_ids, min_confidence)

            signals_map: dict[str, list[DetectorSignal]] = {}
            for row in rows:
                signal = DetectorSignal(
                    detector_type=row["detector_type"],
                    signal_value=float(row["signal_value"]),
                    confidence=float(row["confidence"]),
                    evidence_ids=row["evidence_ids"] or [],
                    transaction_id=row["transaction_id"],
                    timestamp=row["timestamp"],
                    metadata=row["metadata"] or {},
                )

                tx_id = row["transaction_id"]
                if tx_id not in signals_map:
                    signals_map[tx_id] = []
                signals_map[tx_id].append(signal)

            # Ensure all requested transaction IDs are in the map (even if no signals)
            for tx_id in transaction_ids:
                if tx_id not in signals_map:
                    signals_map[tx_id] = []

            return signals_map

    async def get_latest_signal_timestamp(self, transaction_id: str) -> datetime | None:
        """Get the latest signal timestamp for a transaction."""
        query = """
            SELECT MAX(timestamp) as latest
            FROM detection_signals
            WHERE transaction_id = $1
        """

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(query, transaction_id)
            return row["latest"] if row and row["latest"] else None