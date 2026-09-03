"""Signal collector — gathers detector signals and their evidence."""

import hashlib
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from ..models.evidence_bundle import DetectorEvidence, EvidenceItem, EvidenceSource
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SignalCollector:
    """Collect and organize detector signals with their evidence.

    In production this queries ``detection_signals`` / ``signal_evidence``
    tables.  For standalone use, it falls back to in-memory stubs derived
    from the scoring result payload.
    """

    def __init__(self, db_pool=None):
        self.db_pool = db_pool

    # ── Public API ────────────────────────────────────────────────

    async def collect_signals_for_transaction(
        self,
        transaction_id: str,
        scoring_result: Optional[Dict[str, Any]] = None,
    ) -> List[DetectorEvidence]:
        """Return all detector signals for one transaction.

        If a ``db_pool`` is available we query the database; otherwise we
        derive detector evidence from the ``scoring_result`` dict that was
        published on the ``scoring.results`` stream.
        """
        if self.db_pool:
            return await self._collect_from_db(transaction_id)

        if scoring_result:
            return self._collect_from_scoring_result(transaction_id, scoring_result)

        logger.debug("No DB pool and no scoring result — returning empty signals")
        return []

    async def collect_signals_bulk(
        self,
        transaction_ids: List[str],
        scoring_results: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, List[DetectorEvidence]]:
        """Collect signals for multiple transactions in one pass."""
        if self.db_pool:
            return await self._collect_bulk_from_db(transaction_ids)

        results: Dict[str, List[DetectorEvidence]] = {}
        scoring_map = scoring_results or {}

        for tx_id in transaction_ids:
            scoring = scoring_map.get(tx_id)
            results[tx_id] = self._collect_from_scoring_result(tx_id, scoring)

        return results

    # ── Database path ─────────────────────────────────────────────

    async def _collect_from_db(
        self, transaction_id: str
    ) -> List[DetectorEvidence]:
        """Query detection_signals + signal_evidence from PostgreSQL."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    detector_type, signal_value, confidence,
                    evidence_ids, transaction_id, timestamp,
                    metadata, raw_data
                FROM detection_signals
                WHERE transaction_id = $1
                ORDER BY detector_type
                """,
                transaction_id,
            )
            return [await self._row_to_detector_evidence(conn, row) for row in rows]

    async def _collect_bulk_from_db(
        self, transaction_ids: List[str]
    ) -> Dict[str, List[DetectorEvidence]]:
        if not transaction_ids:
            return {}

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    detector_type, signal_value, confidence,
                    evidence_ids, transaction_id, timestamp,
                    metadata, raw_data
                FROM detection_signals
                WHERE transaction_id = ANY($1)
                ORDER BY transaction_id, detector_type
                """,
                transaction_ids,
            )

            grouped: Dict[str, list] = {}
            for row in rows:
                tx_id = row["transaction_id"]
                grouped.setdefault(tx_id, []).append(row)

            result: Dict[str, List[DetectorEvidence]] = {}
            for tx_id, tx_rows in grouped.items():
                result[tx_id] = [
                    await self._row_to_detector_evidence(conn, r) for r in tx_rows
                ]
            return result

    async def _row_to_detector_evidence(self, conn, row) -> DetectorEvidence:
        """Convert a DB row into a DetectorEvidence, fetching child evidence."""
        evidence_items: List[EvidenceItem] = []
        evidence_ids = row["evidence_ids"] or []

        if evidence_ids:
            evidence_rows = await conn.fetch(
                """
                SELECT evidence_id, evidence_type, evidence_data, source, confidence
                FROM signal_evidence
                WHERE evidence_id = ANY($1)
                """,
                evidence_ids,
            )
            ev_map = {e["evidence_id"]: e for e in evidence_rows}
            for eid in evidence_ids:
                erow = ev_map.get(eid)
                if erow:
                    evidence_items.append(
                        EvidenceItem(
                            evidence_id=erow["evidence_id"],
                            source=EvidenceSource.DETECTOR_SIGNAL,
                            source_type=erow["evidence_type"],
                            source_id=row["detector_type"],
                            data=erow["evidence_data"] or {},
                            confidence=erow["confidence"] or row["confidence"],
                            timestamp=row["timestamp"],
                        )
                    )

        meta = row["metadata"] or {}
        return DetectorEvidence(
            detector_type=row["detector_type"],
            signal_value=float(row["signal_value"]),
            confidence=float(row["confidence"]),
            raw_data=row["raw_data"] or {},
            benchmark_data=meta.get("benchmarks"),
            evidence_items=evidence_items,
            metadata=meta,
        )

    # ── In-memory / stub path ─────────────────────────────────────

    def _collect_from_scoring_result(
        self,
        transaction_id: str,
        scoring_result: Optional[Dict[str, Any]],
    ) -> List[DetectorEvidence]:
        """Derive DetectorEvidence entries from a scoring-result dict.

        The scoring service publishes:
        {
            "transaction_id": ...,
            "risk_score": ...,
            "detectors_used": ["price_deviation", ...],
            "source_event": { ... detector-specific payloads ... },
            ...
        }
        """
        if not scoring_result:
            return []

        detectors_used = scoring_result.get("detectors_used", [])
        source_event = scoring_result.get("source_event", {})
        components = source_event.get("components", {}) if isinstance(source_event, dict) else {}

        evidences: List[DetectorEvidence] = []

        for det_type in detectors_used:
            # Pull component data if available
            comp = components.get(det_type, {}) if isinstance(components, dict) else {}

            signal_val = float(comp.get("signal_value", scoring_result.get("risk_score", 0.0)))
            conf = float(comp.get("confidence", scoring_result.get("confidence_factor", 0.5)))

            # Build an evidence item from the component payload
            evidence_items: List[EvidenceItem] = []
            if comp:
                evidence_items.append(
                    EvidenceItem(
                        source=EvidenceSource.DETECTOR_SIGNAL,
                        source_type=det_type,
                        source_id=f"{transaction_id}_{det_type}",
                        data=comp,
                        confidence=conf,
                    )
                )

            evidences.append(
                DetectorEvidence(
                    detector_type=det_type,
                    signal_value=min(1.0, max(0.0, signal_val)),
                    confidence=min(1.0, max(0.0, conf)),
                    raw_data=comp,
                    benchmark_data=comp.get("benchmark_data"),
                    evidence_items=evidence_items,
                )
            )

        return evidences
