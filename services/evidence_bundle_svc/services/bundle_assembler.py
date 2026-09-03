"""Bundle assembler — the orchestrator that composes evidence bundles."""

import asyncio
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..models.evidence_bundle import (
    EvidenceBundle,
    BundleStatus,
    BundleFormat,
    TransactionEvidence,
    DetectorEvidence,
    BenchmarkEvidence,
    EvidenceItem,
)
from .signal_collector import SignalCollector
from .transaction_fetcher import TransactionFetcher
from .benchmark_collector import BenchmarkCollector
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BundleAssembler:
    """Orchestrate the complete assembly of an evidence bundle.

    Pipeline::

        1.  Fetch canonical transaction data
        2.  Collect all detector signals + evidence
        3.  Extract benchmark data from each detector's metadata
        4.  Assemble into an EvidenceBundle
        5.  Validate, checksum, tag, and finalise
    """

    def __init__(
        self,
        signal_collector: SignalCollector,
        transaction_fetcher: TransactionFetcher,
        benchmark_collector: BenchmarkCollector,
    ):
        self.signal_collector = signal_collector
        self.transaction_fetcher = transaction_fetcher
        self.benchmark_collector = benchmark_collector

    # ── Single bundle assembly ────────────────────────────────────

    async def assemble_bundle(
        self,
        transaction_id: str,
        scoring_result: Optional[Dict[str, Any]] = None,
        include_benchmarks: bool = True,
        bundle_format: BundleFormat = BundleFormat.JSON_EXTENDED,
    ) -> EvidenceBundle:
        """Assemble a complete evidence bundle for one transaction.

        Parameters
        ----------
        transaction_id:
            The canonical transaction ID.
        scoring_result:
            The full scoring-result dict from the ``scoring.results`` stream.
            Used both to derive detector evidence (when no DB is available)
            and to populate the scoring context (risk_score, risk_tier, etc.).
        """
        scoring_result = scoring_result or {}

        # 1. Fetch transaction data
        raw_tx_data = scoring_result.get("source_event", {})
        transaction_evidence = await self.transaction_fetcher.fetch_transaction_data(
            transaction_id,
            raw_data=raw_tx_data if isinstance(raw_tx_data, dict) else None,
        )

        # 2. Collect detector signals
        detector_evidences = await self.signal_collector.collect_signals_for_transaction(
            transaction_id,
            scoring_result=scoring_result,
        )

        # 3. Collect benchmarks from detector metadata
        benchmark_evidences: List[BenchmarkEvidence] = []
        if include_benchmarks:
            for det in detector_evidences:
                meta = det.metadata or {}
                if det.benchmark_data:
                    meta.setdefault("benchmarks", det.benchmark_data)
                if meta:
                    bm = await self.benchmark_collector.collect_benchmarks_from_signal(
                        det.detector_type, meta,
                    )
                    benchmark_evidences.extend(bm)

        # 4. Create bundle
        bundle = EvidenceBundle(
            transaction_id=transaction_id,
            format=bundle_format,
            transaction_evidence=transaction_evidence,
            detector_evidences=detector_evidences,
            benchmark_evidences=benchmark_evidences,
            weights_version=scoring_result.get("weights_version"),
            risk_score=scoring_result.get("risk_score"),
            risk_tier=scoring_result.get("risk_tier"),
            confidence_factor=scoring_result.get("confidence_factor"),
            tags=self._generate_tags(transaction_evidence, detector_evidences),
        )

        # 5. Finalize — mark assembled FIRST so timestamps are stable
        bundle.mark_assembled()
        bundle.size_bytes = bundle.calculate_size()
        bundle.storage_checksum = bundle.compute_checksum()

        logger.info(
            "Assembled bundle %s for tx %s — detectors=%s, evidence=%d, size=%d bytes",
            bundle.bundle_id,
            transaction_id,
            bundle.get_detector_types(),
            bundle.get_evidence_count(),
            bundle.size_bytes,
        )

        return bundle

    # ── Bulk assembly ─────────────────────────────────────────────

    async def assemble_bundles_bulk(
        self,
        scoring_results: Dict[str, Dict[str, Any]],
        include_benchmarks: bool = True,
        bundle_format: BundleFormat = BundleFormat.JSON_EXTENDED,
    ) -> Dict[str, EvidenceBundle]:
        """Assemble bundles for multiple transactions in parallel."""
        if not scoring_results:
            return {}

        transaction_ids = list(scoring_results.keys())

        # Parallel fetches
        transactions = await self.transaction_fetcher.fetch_transactions_bulk(
            transaction_ids,
            raw_data_map={
                tx_id: sr.get("source_event", {})
                for tx_id, sr in scoring_results.items()
                if isinstance(sr.get("source_event"), dict)
            },
        )
        signals_map = await self.signal_collector.collect_signals_bulk(
            transaction_ids,
            scoring_results=scoring_results,
        )

        bundles: Dict[str, EvidenceBundle] = {}
        for tx_id, scoring_result in scoring_results.items():
            try:
                tx_ev = transactions.get(tx_id)
                if not tx_ev:
                    tx_ev = TransactionEvidence(transaction_id=tx_id)

                det_evidences = signals_map.get(tx_id, [])

                # Benchmarks
                bm_evidences: List[BenchmarkEvidence] = []
                if include_benchmarks:
                    for det in det_evidences:
                        meta = det.metadata or {}
                        if det.benchmark_data:
                            meta.setdefault("benchmarks", det.benchmark_data)
                        if meta:
                            bm = await self.benchmark_collector.collect_benchmarks_from_signal(
                                det.detector_type, meta,
                            )
                            bm_evidences.extend(bm)

                bundle = EvidenceBundle(
                    transaction_id=tx_id,
                    format=bundle_format,
                    transaction_evidence=tx_ev,
                    detector_evidences=det_evidences,
                    benchmark_evidences=bm_evidences,
                    weights_version=scoring_result.get("weights_version"),
                    risk_score=scoring_result.get("risk_score"),
                    risk_tier=scoring_result.get("risk_tier"),
                    confidence_factor=scoring_result.get("confidence_factor"),
                    tags=self._generate_tags(tx_ev, det_evidences),
                )

                bundle.mark_assembled()
                bundle.size_bytes = bundle.calculate_size()
                bundle.storage_checksum = bundle.compute_checksum()

                bundles[tx_id] = bundle

            except Exception as e:
                logger.error("Failed to assemble bundle for %s: %s", tx_id, e)
                error_bundle = self._create_error_bundle(tx_id, str(e), bundle_format)
                bundles[tx_id] = error_bundle

        logger.info(
            "Bulk assembly complete: %d/%d bundles assembled",
            sum(1 for b in bundles.values() if b.status != BundleStatus.ERROR),
            len(scoring_results),
        )

        return bundles

    # ── Tag generation ────────────────────────────────────────────

    @staticmethod
    def _generate_tags(
        transaction: TransactionEvidence,
        detectors: List[DetectorEvidence],
    ) -> List[str]:
        """Derive meaningful tags from the assembled data."""
        tags: List[str] = []

        # Detector tags
        det_types = [d.detector_type for d in detectors]
        if det_types:
            tags.append(f"detectors:{','.join(sorted(set(det_types))[:5])}")

        # High-signal tag
        high_signals = [d for d in detectors if d.signal_value > 0.75]
        if high_signals:
            tags.append("high_signals_present")

        # Department tag
        if transaction.department_data:
            dept = transaction.department_data.get("department_name")
            if dept:
                tags.append(f"dept:{dept[:30]}")

        # Vendor tag
        if transaction.vendor_data:
            vendor = transaction.vendor_data.get("vendor_name")
            if vendor:
                tags.append(f"vendor:{vendor[:30]}")

        # Amount value band
        total = transaction.amounts.get("total", 0)
        if isinstance(total, (int, float)) and total > 0:
            if total > 1_000_000:
                tags.append("value:high")
            elif total > 100_000:
                tags.append("value:medium")
            else:
                tags.append("value:standard")

        return tags

    # ── Error bundle ──────────────────────────────────────────────

    @staticmethod
    def _create_error_bundle(
        transaction_id: str,
        error_msg: str,
        bundle_format: BundleFormat = BundleFormat.JSON_EXTENDED,
    ) -> EvidenceBundle:
        """Create an ERROR-status bundle so the pipeline never silently drops work."""
        bundle = EvidenceBundle(
            transaction_id=transaction_id,
            status=BundleStatus.ERROR,
            format=bundle_format,
            transaction_evidence=TransactionEvidence(transaction_id=transaction_id),
            metadata={"error": error_msg},
        )
        bundle.size_bytes = bundle.calculate_size()
        bundle.storage_checksum = bundle.compute_checksum()
        return bundle
