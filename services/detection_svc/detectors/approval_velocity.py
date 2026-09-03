"""Approval Velocity Detector.

Pipeline:
1. Parse input (``ApprovalVelocityInput``).
2. Fetch / compute historical approval-time statistics.
3. Get contextual median (weekday + month adjustment).
4. Compute velocity metrics: ratio, linear score, percentile rank.
5. Apply context adjustments (emergency, expedited, high-value).
6. Generate evidence & recommendations.
7. Cache result.
"""

import asyncio
import math
import random
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from .base import BaseDetector
from ..config import settings
from ..models.approval_velocity import (
    ApprovalContext,
    ApprovalVelocityInput,
    ApprovalVelocityResult,
    ApprovalVelocitySeverity,
    HistoricalApprovalStats,
)
from ..models.detection import DetectionType
from ..services.approval_analytics import ApprovalAnalyticsService
from ..services.velocity_cache import VelocityCache
from ..utils.logging import get_logger
from ..utils.time_utils import TimeUtils

logger = get_logger(__name__)


class ApprovalVelocityDetector(BaseDetector):
    """Detect unusually fast approvals by comparing to historical norms.

    Uses category × department medians adjusted for weekday and month
    patterns, with context-aware severity for emergency / expedited
    approvals.
    """

    def __init__(
        self,
        analytics_service: Optional[ApprovalAnalyticsService] = None,
        velocity_cache: Optional[VelocityCache] = None,
    ) -> None:
        super().__init__(DetectionType.APPROVAL_VELOCITY)
        self.analytics_service = analytics_service or ApprovalAnalyticsService()
        self.velocity_cache = velocity_cache or VelocityCache()
        self.time_utils = TimeUtils()

        # Tuning knobs
        self.lookback_days: int = 365
        self.min_sample_size: int = 10
        self.fast_threshold: float = 0.50
        self.emergency_threshold: float = 0.25
        self.max_score: float = 1.0

        logger.info("ApprovalVelocityDetector initialised")

    # ------------------------------------------------------------------
    # BaseDetector interface
    # ------------------------------------------------------------------

    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        start_time = asyncio.get_event_loop().time()

        try:
            input_data = self._parse_input(transaction)

            stats = await self._get_historical_stats(input_data)
            if not stats:
                return self._create_insufficient_data_result(input_data)

            median_time = await self.analytics_service.get_contextual_median(
                stats, input_data.approval_date, input_data.category
            )

            approval_time = input_data.get_approval_time()

            result = self._calculate_velocity_metrics(
                input_data, approval_time, median_time, stats
            )
            result = self._apply_context_adjustments(result, input_data)
            result = self._enhance_result(result, input_data, stats)

            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            result["processing_time_ms"] = int(elapsed)
            result["computed_at"] = datetime.utcnow().isoformat()

            await self.velocity_cache.cache_analysis(
                input_data.transaction_id, result
            )

            logger.info(
                "Approval velocity detection completed: signal=%.3f, ratio=%.2f, severity=%s",
                result["signal_value"],
                result["time_ratio"],
                result["severity"],
            )
            return result

        except Exception as exc:
            logger.error("Approval velocity detection failed: %s", exc, exc_info=True)
            return self._create_error_result(transaction, str(exc))

    def get_weight(self) -> float:
        return 0.05

    def get_required_fields(self) -> List[str]:
        return [
            "department_id",
            "category",
            "submission_date",
            "approval_date",
        ]

    # ------------------------------------------------------------------
    # Input parsing
    # ------------------------------------------------------------------

    def _parse_input(self, transaction: Dict[str, Any]) -> ApprovalVelocityInput:
        return ApprovalVelocityInput(
            transaction_id=transaction.get("transaction_id", str(uuid.uuid4())),
            department_id=transaction.get("department_id", ""),
            vendor_id=transaction.get("vendor_id", ""),
            category=transaction.get("category", ""),
            subcategory=transaction.get("subcategory"),
            amount=float(transaction.get("amount", 0)),
            transaction_date=transaction.get("transaction_date", date.today()),
            submission_date=transaction.get("submission_date", date.today()),
            approval_date=transaction.get("approval_date", date.today()),
            approver_id=transaction.get("approver_id"),
            is_expedited=transaction.get("is_expedited", False),
            is_emergency=transaction.get("is_emergency", False),
            approval_context=transaction.get("approval_context"),
        )

    # ------------------------------------------------------------------
    # Historical stats (cache → stub DB → compute)
    # ------------------------------------------------------------------

    async def _get_historical_stats(
        self, input_data: ApprovalVelocityInput
    ) -> Optional[HistoricalApprovalStats]:
        cached = await self.velocity_cache.get_stats(
            input_data.category, input_data.department_id
        )
        if cached:
            return cached

        historical_data = await self._query_historical_data(input_data)
        if not historical_data:
            return None

        stats = await self.analytics_service.calculate_historical_stats(
            input_data.category,
            input_data.department_id,
            historical_data["times"],
            historical_data["timestamps"],
        )
        if stats:
            await self.velocity_cache.cache_stats(
                input_data.category, input_data.department_id, stats
            )
        return stats

    async def _query_historical_data(
        self, input_data: ApprovalVelocityInput
    ) -> Optional[Dict[str, List]]:
        """Simulated historical data — replace with DB query in production."""
        try:
            seed = hash(f"{input_data.category}:{input_data.department_id}") % (2**32)
            rng = random.Random(seed)

            sample_size = 20 + rng.randint(0, 30)
            base_median = 24 + rng.random() * 48  # 24–72 h

            times: List[float] = []
            timestamps: List[datetime] = []
            for _ in range(sample_size):
                t = max(0.5, base_median + rng.gauss(0, base_median * 0.3))
                times.append(t)
                days_ago = rng.randint(0, 365)
                timestamps.append(datetime.utcnow() - timedelta(days=days_ago))

            return {"times": times, "timestamps": timestamps}
        except Exception as exc:
            logger.error("Failed to query historical data: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Velocity metrics
    # ------------------------------------------------------------------

    def _calculate_velocity_metrics(
        self,
        input_data: ApprovalVelocityInput,
        approval_time: float,
        median_time: float,
        stats: HistoricalApprovalStats,
    ) -> Dict[str, Any]:
        time_ratio = self.time_utils.calculate_velocity_ratio(approval_time, median_time)
        linear_score = self.time_utils.calculate_linear_score(
            approval_time, median_time, self.max_score
        )
        acceleration = self.time_utils.calculate_acceleration_factor(
            approval_time, median_time
        )
        percentile_rank = self._calculate_percentile_rank(approval_time, stats)
        velocity_band = self.time_utils.get_velocity_band(approval_time, median_time)
        raw_deviation = approval_time - median_time

        signal_value = linear_score
        confidence = self._calculate_confidence(
            stats, approval_time, median_time, input_data
        )
        severity = self._determine_severity(signal_value, time_ratio, input_data)
        context = self._determine_context(input_data)

        return {
            "signal_value": signal_value,
            "confidence": confidence,
            "approval_time": approval_time,
            "median_time": median_time,
            "time_ratio": time_ratio,
            "velocity_score": linear_score,
            "raw_deviation": raw_deviation,
            "department_id": input_data.department_id,
            "category": input_data.category,
            "sample_count": stats.sample_count,
            "severity": severity,
            "context": context,
            "velocity_indicators": self._generate_indicators(
                time_ratio, signal_value, input_data
            ),
            "historical_stats": stats.model_dump(mode="json"),
            "percentile_rank": percentile_rank,
            "velocity_band": velocity_band,
            "acceleration_factor": acceleration,
            "context_adjustments": {},
        }

    def _calculate_percentile_rank(
        self, approval_time: float, stats: HistoricalApprovalStats
    ) -> float:
        if stats.sample_count < 10:
            return 50.0
        if approval_time <= stats.p10:
            return 10.0
        if approval_time <= stats.p25:
            return 25.0
        if approval_time <= stats.p50:
            return 50.0
        if approval_time <= stats.p75:
            return 75.0
        if approval_time <= stats.p90:
            return 90.0
        return 95.0

    def _calculate_confidence(
        self,
        stats: HistoricalApprovalStats,
        approval_time: float,
        median_time: float,
        input_data: ApprovalVelocityInput,
    ) -> float:
        base = stats.confidence
        sample_factor = min(1.0, stats.sample_count / 50)

        if median_time > 0:
            ratio = approval_time / median_time
            if ratio < 0.25:
                ratio_conf = 0.90
            elif ratio < 0.50:
                ratio_conf = 0.70
            elif ratio < 0.75:
                ratio_conf = 0.50
            else:
                ratio_conf = 0.30
        else:
            ratio_conf = 0.30

        penalty = 0.0
        if input_data.is_emergency:
            penalty = 0.30
        elif input_data.is_expedited:
            penalty = 0.15

        confidence = base * 0.3 + sample_factor * 0.3 + ratio_conf * 0.4 - penalty
        return min(1.0, max(0.0, confidence))

    def _determine_severity(
        self,
        signal_value: float,
        time_ratio: float,
        input_data: ApprovalVelocityInput,
    ) -> ApprovalVelocitySeverity:
        if input_data.is_emergency and time_ratio < 0.30:
            return ApprovalVelocitySeverity.MEDIUM
        if input_data.is_expedited and time_ratio < 0.20:
            return ApprovalVelocitySeverity.MEDIUM

        if signal_value >= 0.90:
            return ApprovalVelocitySeverity.CRITICAL
        if signal_value >= 0.70:
            return ApprovalVelocitySeverity.HIGH
        if signal_value >= 0.40:
            return ApprovalVelocitySeverity.MEDIUM
        if signal_value >= 0.20:
            return ApprovalVelocitySeverity.LOW
        return ApprovalVelocitySeverity.NONE

    @staticmethod
    def _determine_context(input_data: ApprovalVelocityInput) -> ApprovalContext:
        if input_data.is_emergency:
            return ApprovalContext.EMERGENCY
        if input_data.is_expedited:
            return ApprovalContext.EXPEDITED
        if input_data.approval_context:
            return input_data.approval_context
        return ApprovalContext.NORMAL

    # ------------------------------------------------------------------
    # Indicators
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_indicators(
        time_ratio: float,
        signal_value: float,
        input_data: ApprovalVelocityInput,
    ) -> List[str]:
        indicators: List[str] = []

        if time_ratio < 0.25:
            indicators.append("EXTREME_VELOCITY")
        elif time_ratio < 0.50:
            indicators.append("HIGH_VELOCITY")
        elif time_ratio < 0.75:
            indicators.append("MODERATE_VELOCITY")

        if signal_value > 0.80:
            indicators.append("SIGNIFICANT_DEVIATION")

        if input_data.is_emergency:
            indicators.append("EMERGENCY_APPROVAL")
        elif input_data.is_expedited:
            indicators.append("EXPEDITED_APPROVAL")

        if input_data.approval_date.weekday() >= 5:
            indicators.append("WEEKEND_APPROVAL")

        if input_data.amount > 100_000 and time_ratio < 0.50:
            indicators.append("HIGH_VALUE_FAST_APPROVAL")

        return indicators

    # ------------------------------------------------------------------
    # Context adjustments
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_context_adjustments(
        result: Dict[str, Any], input_data: ApprovalVelocityInput
    ) -> Dict[str, Any]:
        signal = result["signal_value"]
        adjustments: List[str] = []

        if input_data.is_emergency:
            if result["time_ratio"] < 0.30:
                signal = min(1.0, signal * 1.2)
            else:
                signal = max(0.0, signal * 0.6)
            adjustments.append("Emergency approval — reduced severity")

        if input_data.is_expedited:
            if result["time_ratio"] < 0.20:
                signal = min(1.0, signal * 1.1)
            else:
                signal = max(0.0, signal * 0.7)
            adjustments.append("Expedited approval — moderate adjustment")

        if input_data.amount > 100_000 and result["time_ratio"] < 0.30:
            signal = min(1.0, signal * 1.15)
            adjustments.append("High value transaction — increased scrutiny")

        result["signal_value"] = min(1.0, max(0.0, signal))
        result["context_adjustments"] = adjustments
        return result

    # ------------------------------------------------------------------
    # Evidence & recommendations
    # ------------------------------------------------------------------

    def _enhance_result(
        self,
        result: Dict[str, Any],
        input_data: ApprovalVelocityInput,
        stats: HistoricalApprovalStats,
    ) -> Dict[str, Any]:
        result["evidence"] = self._generate_evidence(result, input_data, stats)
        result["recommendations"] = self._generate_recommendations(result, input_data)
        return result

    @staticmethod
    def _generate_evidence(
        result: Dict[str, Any],
        input_data: ApprovalVelocityInput,
        stats: HistoricalApprovalStats,
    ) -> List[str]:
        evidence: List[str] = []
        approval_time = result["approval_time"]
        median_time = result["median_time"]
        time_ratio = result["time_ratio"]
        band = result.get("velocity_band", "UNKNOWN")

        evidence.append(
            f"Approval time: {approval_time:.1f} hours "
            f"(historical median: {median_time:.1f} hours)"
        )
        evidence.append(
            f"Approval is {time_ratio:.1%} of historical median "
            f"({band.replace('_', ' ').title()})"
        )

        pct = result.get("percentile_rank", 50)
        if pct <= 25:
            evidence.append(
                f"Approval is in the {pct:.0f}th percentile "
                f"(faster than 75% of approvals)"
            )

        if input_data.is_emergency:
            evidence.append("Emergency approval context — faster approvals may be warranted")
        elif input_data.is_expedited:
            evidence.append("Expedited approval context — faster than normal may be expected")

        n = stats.sample_count
        if n >= 30:
            evidence.append(f"Based on {n} historical approvals (robust dataset)")
        elif n >= 10:
            evidence.append(f"Based on {n} historical approvals (limited dataset)")
        else:
            evidence.append(f"Based on limited data ({n} approvals) — low confidence")

        if result["confidence"] < 0.50:
            evidence.append("Low confidence due to limited data or high variance")

        if input_data.amount > 100_000:
            evidence.append(f"High value transaction: ${input_data.amount:,.2f}")

        if input_data.approval_date.weekday() >= 5:
            evidence.append("Approval occurred on weekend")

        return evidence

    @staticmethod
    def _generate_recommendations(
        result: Dict[str, Any], input_data: ApprovalVelocityInput
    ) -> List[str]:
        recs: List[str] = []
        severity = result["severity"]
        signal = result["signal_value"]

        if severity == ApprovalVelocitySeverity.CRITICAL:
            recs.append("URGENT: Exceptionally fast approval — immediate investigation required")
            recs.append("Verify approval authority and process adherence")
            recs.append("Check for potential collusion or bypass of controls")
        elif severity == ApprovalVelocitySeverity.HIGH:
            recs.append("High-priority: Unusually fast approval — require secondary review")
            recs.append("Review supporting documentation and approval justification")
            recs.append("Verify if expedited approval was properly authorized")
        elif severity == ApprovalVelocitySeverity.MEDIUM:
            recs.append("Medium priority: Faster than normal — recommend review")
            recs.append("Check if this is consistent with historical patterns")
            recs.append("Monitor for similar patterns in future approvals")
        elif severity == ApprovalVelocitySeverity.LOW:
            recs.append("Low priority: Slightly faster than normal — continue monitoring")

        if input_data.is_emergency:
            recs.append("Verify emergency approval protocols were followed")
            recs.append("Ensure all required emergency documentation is complete")

        if input_data.is_expedited:
            recs.append("Verify expedited approval was properly requested and authorized")

        if input_data.amount > 100_000 and signal > 0.50:
            recs.append("High-value transaction with fast approval — escalate to compliance")

        if input_data.approval_date.weekday() >= 5 and signal > 0.50:
            recs.append("Weekend approval with unusual speed — verify authorization")

        if result["confidence"] < 0.50:
            recs.append("Low confidence detection — gather more historical data for validation")

        return recs

    # ------------------------------------------------------------------
    # Fallback results
    # ------------------------------------------------------------------

    def _create_insufficient_data_result(
        self, input_data: ApprovalVelocityInput
    ) -> Dict[str, Any]:
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "approval_time": input_data.get_approval_time(),
            "median_time": 0.0,
            "time_ratio": 0.0,
            "velocity_score": 0.0,
            "raw_deviation": 0.0,
            "department_id": input_data.department_id,
            "category": input_data.category,
            "sample_count": 0,
            "severity": ApprovalVelocitySeverity.NONE,
            "context": ApprovalContext.UNKNOWN,
            "velocity_indicators": ["INSUFFICIENT_DATA"],
            "evidence": [
                f"Insufficient historical data for {input_data.category} in "
                f"{input_data.department_id} (need at least {self.min_sample_size} samples)"
            ],
            "recommendations": [
                "Collect more historical approval data",
                "Use broader category or department benchmarks",
            ],
            "historical_stats": None,
            "percentile_rank": None,
            "velocity_band": "UNKNOWN",
            "acceleration_factor": 0.0,
            "context_adjustments": {},
        }

    def _create_error_result(
        self, transaction: Dict[str, Any], error: str
    ) -> Dict[str, Any]:
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "approval_time": 0.0,
            "median_time": 0.0,
            "time_ratio": 0.0,
            "velocity_score": 0.0,
            "raw_deviation": 0.0,
            "department_id": transaction.get("department_id", ""),
            "category": transaction.get("category", ""),
            "sample_count": 0,
            "severity": ApprovalVelocitySeverity.NONE,
            "context": ApprovalContext.UNKNOWN,
            "velocity_indicators": ["DETECTION_ERROR"],
            "evidence": [f"Detection failed: {error}"],
            "recommendations": ["Retry detection or check input data"],
            "historical_stats": None,
            "percentile_rank": None,
            "velocity_band": "UNKNOWN",
            "acceleration_factor": 0.0,
            "context_adjustments": {},
            "transaction_id": transaction.get("transaction_id", str(uuid.uuid4())),
            "error": error,
        }
