"""Benchmark collector — gathers reference benchmark data used by detectors."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..models.evidence_bundle import BenchmarkEvidence, EvidenceItem, EvidenceSource
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BenchmarkCollector:
    """Collect benchmark data produced by detectors.

    When a detector signals results, it may embed benchmark context (e.g.
    price quartiles, peer-group statistics, HHI thresholds).  This service
    extracts and normalises those into ``BenchmarkEvidence`` objects.
    """

    def __init__(self, db_pool=None):
        self.db_pool = db_pool

    # ── Public API ────────────────────────────────────────────────

    async def collect_benchmarks_from_signal(
        self,
        detector_type: str,
        signal_metadata: Dict[str, Any],
    ) -> List[BenchmarkEvidence]:
        """Extract benchmark evidence from a detector's metadata payload.

        Parameters
        ----------
        detector_type:
            e.g. ``"price_deviation"``, ``"timing_anomaly"``, ``"vendor_graph_risk"``
        signal_metadata:
            The ``metadata`` dict from a ``DetectorEvidence``.  Typically
            contains a ``"benchmarks"`` sub-dict.
        """
        benchmarks: List[BenchmarkEvidence] = []

        if not signal_metadata:
            return benchmarks

        # The standard nesting is signal_metadata["benchmarks"]
        bench_data = signal_metadata.get("benchmarks", signal_metadata)

        extractor = _EXTRACTORS.get(detector_type)
        if extractor:
            benchmarks.extend(extractor(bench_data, detector_type))
        else:
            # Generic fallback — export all keys as evidence items
            benchmarks.extend(
                self._extract_generic(bench_data, detector_type)
            )

        return benchmarks

    async def collect_detector_specific_benchmarks(
        self,
        detector_type: str,
        params: Dict[str, Any],
    ) -> List[BenchmarkEvidence]:
        """Collect live benchmarks from the DB for a given detector.

        For example, fetch the latest price benchmark row for a category.
        """
        if not self.db_pool:
            return []

        benchmarks: List[BenchmarkEvidence] = []

        if detector_type == "price_deviation":
            benchmarks.extend(
                await self._fetch_price_benchmarks(params)
            )
        elif detector_type == "timing_anomaly":
            benchmarks.extend(
                await self._fetch_timing_benchmarks(params)
            )

        return benchmarks

    # ── Extractors ────────────────────────────────────────────────

    @staticmethod
    def _extract_price_benchmarks(
        bench_data: Dict[str, Any], detector_type: str
    ) -> List[BenchmarkEvidence]:
        benchmarks: List[BenchmarkEvidence] = []

        # Price quartiles
        quartiles = bench_data.get("quartiles")
        if quartiles and isinstance(quartiles, dict):
            items = []
            for q_name, q_val in quartiles.items():
                items.append(
                    EvidenceItem(
                        source=EvidenceSource.BENCHMARK_DATA,
                        source_type="price_quartile",
                        source_id=f"{detector_type}_{q_name}",
                        data={"quartile": q_name, "value": q_val, "currency": "USD"},
                        confidence=0.9,
                        relevance_score=0.9,
                    )
                )
            benchmarks.append(
                BenchmarkEvidence(
                    benchmark_type="price_quartiles",
                    benchmark_data=quartiles,
                    source=detector_type,
                    evidence_items=items,
                )
            )

        # Peer-group statistics
        peer_stats = bench_data.get("peer_stats")
        if peer_stats and isinstance(peer_stats, dict):
            items = []
            for stat_key, stat_val in peer_stats.items():
                items.append(
                    EvidenceItem(
                        source=EvidenceSource.BENCHMARK_DATA,
                        source_type="peer_statistic",
                        source_id=f"{detector_type}_peer_{stat_key}",
                        data={"statistic": stat_key, "value": stat_val},
                        confidence=0.85,
                        relevance_score=0.8,
                    )
                )
            benchmarks.append(
                BenchmarkEvidence(
                    benchmark_type="peer_statistics",
                    benchmark_data={"peer_stats": peer_stats},
                    source=detector_type,
                    evidence_items=items,
                )
            )

        return benchmarks

    @staticmethod
    def _extract_timing_benchmarks(
        bench_data: Dict[str, Any], detector_type: str
    ) -> List[BenchmarkEvidence]:
        benchmarks: List[BenchmarkEvidence] = []

        hist_stats = bench_data.get("historical_stats")
        if hist_stats and isinstance(hist_stats, dict):
            items = []
            for stat_key, stat_val in hist_stats.items():
                items.append(
                    EvidenceItem(
                        source=EvidenceSource.BENCHMARK_DATA,
                        source_type="historical_statistic",
                        source_id=f"{detector_type}_{stat_key}",
                        data={"statistic": stat_key, "value": stat_val},
                        confidence=0.9,
                        relevance_score=0.8,
                    )
                )
            benchmarks.append(
                BenchmarkEvidence(
                    benchmark_type="historical_statistics",
                    benchmark_data={"historical_stats": hist_stats},
                    source=detector_type,
                    evidence_items=items,
                )
            )

        return benchmarks

    @staticmethod
    def _extract_vendor_graph_benchmarks(
        bench_data: Dict[str, Any], detector_type: str
    ) -> List[BenchmarkEvidence]:
        benchmarks: List[BenchmarkEvidence] = []

        thresholds = bench_data.get("hhi_thresholds")
        if thresholds and isinstance(thresholds, dict):
            items = []
            for key, val in thresholds.items():
                items.append(
                    EvidenceItem(
                        source=EvidenceSource.BENCHMARK_DATA,
                        source_type="hhi_threshold",
                        source_id=f"{detector_type}_{key}",
                        data={"threshold": key, "value": val},
                        confidence=0.85,
                        relevance_score=0.8,
                    )
                )
            benchmarks.append(
                BenchmarkEvidence(
                    benchmark_type="hhi_thresholds",
                    benchmark_data={"hhi_thresholds": thresholds},
                    source=detector_type,
                    evidence_items=items,
                )
            )

        return benchmarks

    @staticmethod
    def _extract_generic(
        bench_data: Dict[str, Any], detector_type: str
    ) -> List[BenchmarkEvidence]:
        """Catch-all: wrap every key/value as a benchmark evidence item."""
        items = []
        for key, val in bench_data.items():
            items.append(
                EvidenceItem(
                    source=EvidenceSource.BENCHMARK_DATA,
                    source_type=f"{detector_type}_{key}",
                    source_id=f"{detector_type}_{key}",
                    data={key: val},
                    confidence=0.7,
                    relevance_score=0.7,
                )
            )

        if items:
            return [
                BenchmarkEvidence(
                    benchmark_type=f"{detector_type}_generic",
                    benchmark_data=bench_data,
                    source=detector_type,
                    evidence_items=items,
                )
            ]
        return []

    # ── DB lookups ────────────────────────────────────────────────

    async def _fetch_price_benchmarks(
        self, params: Dict[str, Any]
    ) -> List[BenchmarkEvidence]:
        category = params.get("category")
        region = params.get("region")
        if not category:
            return []

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    category, percentile_25, percentile_50, percentile_75,
                    mean, std_dev, sample_count, updated_at
                FROM price_benchmarks
                WHERE category = $1
                AND (region = $2 OR region IS NULL)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                category,
                region,
            )

        if not rows:
            return []

        row = rows[0]
        items = []
        for col in ("percentile_25", "percentile_50", "percentile_75", "mean", "std_dev"):
            if row[col] is not None:
                items.append(
                    EvidenceItem(
                        source=EvidenceSource.BENCHMARK_DATA,
                        source_type="price_benchmark",
                        source_id=f"price_{col}",
                        data={
                            "statistic": col,
                            "value": float(row[col]),
                            "category": category,
                            "region": region,
                        },
                        confidence=0.9,
                        relevance_score=0.9,
                    )
                )

        if not items:
            return []

        return [
            BenchmarkEvidence(
                benchmark_type="price_benchmarks",
                benchmark_data={
                    "category": category,
                    "region": region,
                    "statistics": {
                        k: float(v)
                        for k, v in dict(row).items()
                        if v is not None and isinstance(v, (int, float))
                    },
                },
                source="price_deviation_benchmark",
                evidence_items=items,
            )
        ]

    async def _fetch_timing_benchmarks(
        self, params: Dict[str, Any]
    ) -> List[BenchmarkEvidence]:
        department_id = params.get("department_id")
        if not department_id:
            return []

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT department_id, fiscal_period, mean_approval_time,
                       std_approval_time, sample_count
                FROM timing_benchmarks
                WHERE department_id = $1
                ORDER BY computed_at DESC
                LIMIT 1
                """,
                department_id,
            )

        if not rows:
            return []

        row = rows[0]
        items = []
        for col in ("mean_approval_time", "std_approval_time", "sample_count"):
            if row[col] is not None:
                items.append(
                    EvidenceItem(
                        source=EvidenceSource.BENCHMARK_DATA,
                        source_type="timing_benchmark",
                        source_id=f"timing_{col}",
                        data={
                            "statistic": col,
                            "value": float(row[col]) if col != "sample_count" else int(row[col]),
                            "department_id": department_id,
                            "fiscal_period": row["fiscal_period"],
                        },
                        confidence=0.85,
                        relevance_score=0.8,
                    )
                )

        if not items:
            return []

        return [
            BenchmarkEvidence(
                benchmark_type="timing_benchmarks",
                benchmark_data=dict(row),
                source="timing_anomaly_benchmark",
                evidence_items=items,
            )
        ]


# Registry of per-detector extractors
_EXTRACTORS = {
    "price_deviation": BenchmarkCollector._extract_price_benchmarks,
    "timing_anomaly": BenchmarkCollector._extract_timing_benchmarks,
    "vendor_graph_risk": BenchmarkCollector._extract_vendor_graph_benchmarks,
}
