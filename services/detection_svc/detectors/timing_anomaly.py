"""Timing Anomaly Detector.

Pipeline:
1. Parse & validate input (``ApprovalTimeInput``).
2. Fetch / compute historical timing statistics.
3. Compute fiscal-year-end amplification factor.
4. Z-score → sigmoid → amplified signal.
5. Classify anomaly type & severity, build evidence & recommendations.
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from .base import BaseDetector
from ..config import settings
from ..models.detection import DetectionType
from ..models.timing import ApprovalTimeInput, TimingStatistics
from ..services.fiscal_service import FiscalService
from ..services.timing_cache import TimingCache
from ..services.timing_service import TimingService
from ..utils.date_utils import DateUtils
from ..utils.logging import get_logger

logger = get_logger(__name__)


class TimingAnomalyDetector(BaseDetector):
    """Detect abnormal approval / processing / payment timing.

    Uses Z-score analysis backed by per-department historical data,
    amplified during the fiscal year-end rush window.
    """

    def __init__(
        self,
        timing_service: Optional[TimingService] = None,
        fiscal_service: Optional[FiscalService] = None,
        timing_cache: Optional[TimingCache] = None,
    ) -> None:
        super().__init__(DetectionType.TIMING_ANOMALY)
        self.timing_service = timing_service or TimingService()
        self.fiscal_service = fiscal_service or FiscalService()
        self.timing_cache = timing_cache or TimingCache()

        # Tuning knobs
        self.z_score_threshold: float = 2.0
        self.fiscal_end_window: int = 14  # days
        self.min_sample_size: int = 5
        self.default_mean: float = 24.0
        self.default_std: float = 8.0

        logger.info("TimingAnomalyDetector initialised")

    # ------------------------------------------------------------------
    # BaseDetector interface
    # ------------------------------------------------------------------

    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        start_time = asyncio.get_event_loop().time()

        try:
            input_data = await self._parse_input(transaction)
            stats = await self._get_historical_stats(input_data)
            amplification, _is_fiscal_end = await self._get_fiscal_amplification(
                input_data.approval_date
            )

            result = await self.timing_service.analyze_timing_anomaly(
                input_data, stats, amplification
            )

            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            result["processing_time_ms"] = int(elapsed)
            result["computed_at"] = datetime.utcnow().isoformat()

            await self.timing_cache.cache_analysis(input_data.transaction_id, result)

            logger.info(
                "Timing anomaly detection completed: signal=%.3f, z=%.2f, severity=%s",
                result["signal_value"],
                result["z_score"],
                result["severity"],
            )
            return result

        except Exception as exc:
            logger.error("Timing anomaly detection failed: %s", exc, exc_info=True)
            return self._create_error_result(transaction, str(exc))

    def get_weight(self) -> float:
        return 0.10

    def get_required_fields(self) -> List[str]:
        return [
            "department_id",
            "vendor_id",
            "amount",
            "transaction_date",
            "submission_date",
            "approval_date",
        ]

    # ------------------------------------------------------------------
    # Input parsing
    # ------------------------------------------------------------------

    async def _parse_input(
        self, transaction: Dict[str, Any]
    ) -> ApprovalTimeInput:
        return ApprovalTimeInput(
            transaction_id=transaction.get("transaction_id", str(uuid.uuid4())),
            department_id=transaction.get("department_id", ""),
            vendor_id=transaction.get("vendor_id", ""),
            amount=float(transaction.get("amount", 0)),
            transaction_date=transaction.get("transaction_date", date.today()),
            approval_date=transaction.get("approval_date", date.today()),
            submission_date=transaction.get("submission_date", date.today()),
            fiscal_period=transaction.get("fiscal_period"),
            fiscal_year_end=transaction.get("fiscal_year_end"),
        )

    # ------------------------------------------------------------------
    # Historical statistics (cache → DB → defaults)
    # ------------------------------------------------------------------

    async def _get_historical_stats(
        self, input_data: ApprovalTimeInput
    ) -> TimingStatistics:
        fiscal_period = input_data.fiscal_period or await self._get_fiscal_period(
            input_data.approval_date
        )

        # Cache hit
        cached = await self.timing_cache.get_statistics(
            input_data.department_id, fiscal_period
        )
        if cached and cached.sample_count >= self.min_sample_size:
            return cached

        # Simulated DB query (stub)
        historical_data = await self._query_historical_data(
            input_data.department_id, fiscal_period
        )

        stats = await self.timing_service.get_timing_statistics(
            input_data.department_id, fiscal_period, historical_data
        )

        if stats.sample_count >= self.min_sample_size:
            await self.timing_cache.cache_statistics(
                input_data.department_id, fiscal_period, stats
            )

        return stats

    async def _get_fiscal_period(self, date_obj: date) -> str:
        ctx = await self.fiscal_service.get_fiscal_context(date_obj)
        return ctx["fiscal_period"]

    async def _query_historical_data(
        self, department_id: str, fiscal_period: str
    ) -> List[Dict[str, Any]]:
        """Simulated historical data — replace with DB query in production."""
        import random

        seed = hash(f"{department_id}:{fiscal_period}") % (2**32)
        rng = random.Random(seed)

        sample_count = 20 + rng.randint(0, 30)
        base_hours = 24 + rng.random() * 48

        data: List[Dict[str, Any]] = []
        for _ in range(sample_count):
            hours = max(0.5, base_hours + rng.gauss(0, 8))
            data.append(
                {
                    "approval_time": hours,
                    "amount": rng.uniform(1000, 50_000),
                    "submission_date": date.today() - timedelta(days=rng.randint(1, 90)),
                    "approval_date": date.today() - timedelta(days=rng.randint(1, 90)),
                }
            )
        return data

    # ------------------------------------------------------------------
    # Fiscal amplification
    # ------------------------------------------------------------------

    async def _get_fiscal_amplification(
        self, date_obj: date
    ) -> tuple[float, bool]:
        return await self.fiscal_service.get_fiscal_amplification_factor(
            date_obj, days_window=self.fiscal_end_window
        )

    # ------------------------------------------------------------------
    # Error fallback
    # ------------------------------------------------------------------

    def _create_error_result(
        self, transaction: Dict[str, Any], error: str
    ) -> Dict[str, Any]:
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "z_score": 0.0,
            "raw_deviation": 0.0,
            "normalized_deviation": 0.0,
            "department_id": transaction.get("department_id"),
            "approval_time": 0.0,
            "historical_mean": self.default_mean,
            "historical_std": self.default_std,
            "fiscal_amplification": 1.0,
            "is_fiscal_end": False,
            "days_to_fiscal_end": None,
            "anomaly_type": "error",
            "severity": "low",
            "anomaly_indicators": ["DETECTION_ERROR"],
            "evidence": [f"Detection failed: {error}"],
            "recommendations": ["Retry detection or check input data"],
            "fiscal_period": None,
            "statistics": None,
            "outlier_analysis": {},
            "transaction_id": transaction.get("transaction_id", str(uuid.uuid4())),
            "error": error,
        }
