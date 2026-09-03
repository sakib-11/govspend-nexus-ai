"""Transaction fetcher — retrieves canonical transaction data for bundles."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from ..models.evidence_bundle import (
    TransactionEvidence,
    EvidenceItem,
    EvidenceSource,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class TransactionFetcher:
    """Fetch and normalize transaction data for evidence bundles.

    Queries the ``canonical_transactions`` table when a DB pool is
    available; otherwise, accepts a pre-built dict.
    """

    def __init__(self, db_pool=None):
        self.db_pool = db_pool

    # ── Public API ────────────────────────────────────────────────

    async def fetch_transaction_data(
        self,
        transaction_id: str,
        raw_data: Optional[Dict[str, Any]] = None,
    ) -> TransactionEvidence:
        """Fetch complete transaction data for one transaction."""
        if self.db_pool:
            return await self._fetch_from_db(transaction_id)

        if raw_data:
            return self._build_from_dict(transaction_id, raw_data)

        logger.warning(
            "No DB pool and no raw_data for %s — returning empty evidence",
            transaction_id,
        )
        return self._empty_evidence(transaction_id)

    async def fetch_transactions_bulk(
        self,
        transaction_ids: List[str],
        raw_data_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, TransactionEvidence]:
        """Fetch transaction data for multiple IDs in one pass."""
        if self.db_pool:
            return await self._fetch_bulk_from_db(transaction_ids)

        raw_map = raw_data_map or {}
        return {
            tx_id: self._build_from_dict(tx_id, raw_map.get(tx_id, {}))
            for tx_id in transaction_ids
        }

    # ── Database path ─────────────────────────────────────────────

    async def _fetch_from_db(self, transaction_id: str) -> TransactionEvidence:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    transaction_id, canonical_data, vendor_data,
                    department_data, amounts, timestamps,
                    validated_at, metadata
                FROM canonical_transactions
                WHERE transaction_id = $1
                """,
                transaction_id,
            )

            if not row:
                raise ValueError(f"Transaction {transaction_id} not found in DB")

            return self._row_to_evidence(row)

    async def _fetch_bulk_from_db(
        self, transaction_ids: List[str]
    ) -> Dict[str, TransactionEvidence]:
        if not transaction_ids:
            return {}

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    transaction_id, canonical_data, vendor_data,
                    department_data, amounts, timestamps,
                    validated_at, metadata
                FROM canonical_transactions
                WHERE transaction_id = ANY($1)
                """,
                transaction_ids,
            )
            return {
                row["transaction_id"]: self._row_to_evidence(row) for row in rows
            }

    def _row_to_evidence(self, row) -> TransactionEvidence:
        """Convert a database row to TransactionEvidence."""
        tx_id = row["transaction_id"]
        amounts = dict(row["amounts"]) if row["amounts"] else {}
        timestamps = dict(row["timestamps"]) if row["timestamps"] else {}
        vendor_data = dict(row["vendor_data"]) if row["vendor_data"] else {}
        dept_data = dict(row["department_data"]) if row["department_data"] else {}

        evidence_items = self._build_evidence_items(
            tx_id, amounts, timestamps, vendor_data
        )

        return TransactionEvidence(
            transaction_id=tx_id,
            canonical_data=dict(row["canonical_data"]) if row["canonical_data"] else {},
            vendor_data=vendor_data,
            department_data=dept_data,
            timestamps=timestamps,
            amounts=amounts,
            evidence_items=evidence_items,
        )

    # ── Dict-based path (no DB) ───────────────────────────────────

    def _build_from_dict(
        self, transaction_id: str, data: Dict[str, Any]
    ) -> TransactionEvidence:
        """Construct TransactionEvidence from a plain dict."""
        if not data:
            return self._empty_evidence(transaction_id)

        amounts = data.get("amounts", {})
        timestamps = data.get("timestamps", {})
        vendor_data = data.get("vendor_data", {})
        dept_data = data.get("department_data")

        evidence_items = self._build_evidence_items(
            transaction_id, amounts, timestamps, vendor_data
        )

        return TransactionEvidence(
            transaction_id=transaction_id,
            canonical_data=data.get("canonical_data", data),
            vendor_data=vendor_data,
            department_data=dept_data,
            timestamps=timestamps,
            amounts=amounts,
            evidence_items=evidence_items,
        )

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _build_evidence_items(
        transaction_id: str,
        amounts: Dict[str, Any],
        timestamps: Dict[str, Any],
        vendor_data: Dict[str, Any],
    ) -> List[EvidenceItem]:
        """Derive EvidenceItems from the raw fields."""
        items: List[EvidenceItem] = []

        # Amount evidence
        for amount_type, amount_value in amounts.items():
            items.append(
                EvidenceItem(
                    source=EvidenceSource.TRANSACTION_DATA,
                    source_type="amount",
                    source_id=f"{transaction_id}_{amount_type}",
                    data={"type": amount_type, "value": amount_value, "currency": "USD"},
                    relevance_score=1.0,
                )
            )

        # Timestamp evidence
        for ts_type, ts_value in timestamps.items():
            ts_iso = (
                ts_value.isoformat()
                if isinstance(ts_value, datetime)
                else str(ts_value)
            )
            items.append(
                EvidenceItem(
                    source=EvidenceSource.TRANSACTION_DATA,
                    source_type="timestamp",
                    source_id=f"{transaction_id}_{ts_type}",
                    data={"type": ts_type, "value": ts_iso},
                    relevance_score=1.0,
                )
            )

        # Vendor metadata evidence (skip identifiers)
        skip_keys = {"vendor_id", "vendor_token"}
        for key, value in vendor_data.items():
            if value and key not in skip_keys:
                items.append(
                    EvidenceItem(
                        source=EvidenceSource.VENDOR_DATA,
                        source_type="vendor_metadata",
                        source_id=f"{transaction_id}_vendor_{key}",
                        data={key: value},
                        relevance_score=0.8,
                    )
                )

        return items

    @staticmethod
    def _empty_evidence(transaction_id: str) -> TransactionEvidence:
        """Return a minimal TransactionEvidence when no data is available."""
        return TransactionEvidence(
            transaction_id=transaction_id,
            canonical_data={},
            vendor_data={},
            timestamps={},
            amounts={},
        )
