"""Service for timing analysis and anomaly classification."""

import math
from typing import Any, Dict, List, Optional, Tuple

from ..analytics.statistical import StatisticalAnalyzer
from ..models.timing import ApprovalTimeInput, TimingStatistics
from ..utils.date_utils import DateUtils
from ..utils.logging import get_logger

logger = get_logger(__name__)


class TimingService:
    """Core timing-analysis logic: statistics, Z-score → signal, evidence."""

    def __init__(self) -> None:
        self.analyzer = StatisticalAnalyzer()
        self.min_sample_size: int = 5
        self.z_score_threshold: float = 2.0

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def get_timing_statistics(
        self,
        department_id: str,
        fiscal_period: str,
        historical_data: List[Dict[str, Any]],
    ) -> TimingStatistics:
        """Build a ``TimingStatistics`` from raw historical rows."""
        if not historical_data:
            return TimingStatistics(
                department_id=department_id,
                fiscal_period=fiscal_period,
                mean_approval_time=24.0,
                std_approval_time=8.0,
                min_time=1.0,
                max_time=72.0,
                median_time=22.0,
                sample_count=0,
                confidence=0.0,
            )

        approval_times = [d.get("approval_time", 0) for d in historical_data]
        stats = self.analyzer.calculate_statistics(approval_times)
        confidence = self.analyzer.calculate_confidence(
            len(approval_times),
            stats.get("std", 0),
            stats.get("mean", 24),
        )

        return TimingStatistics(
            department_id=department_id,
            fiscal_period=fiscal_period,
            mean_approval_time=stats.get("mean", 24),
            std_approval_time=stats.get("std", 8),
            min_time=stats.get("min", 0),
            max_time=stats.get("max", 72),
            median_time=stats.get("median", 22),
            sample_count=len(approval_times),
            confidence=confidence,
            q1=stats.get("q1", 0),
            q3=stats.get("q3", 0),
            iqr=stats.get("iqr", 0),
            outlier_count=stats.get("outlier_count", 0),
        )

    # ------------------------------------------------------------------
    # Anomaly analysis
    # ------------------------------------------------------------------

    async def analyze_timing_anomaly(
        self,
        input_data: ApprovalTimeInput,
        historical_stats: TimingStatistics,
        fiscal_amplification: float = 1.0,
    ) -> Dict[str, Any]:
        """Full timing-anomaly analysis → result dict."""
        approval_time = input_data.get_approval_time()

        # Z-score
        z_score = self.analyzer.calculate_z_score(
            approval_time,
            historical_stats.mean_approval_time,
            historical_stats.std_approval_time,
        )

        # Sigmoid → raw signal → fiscal amplification
        raw_signal = self.analyzer.apply_sigmoid(z_score, k=1.0)
        amplified = raw_signal * fiscal_amplification
        signal_value = min(1.0, amplified)

        confidence = self._calculate_confidence(historical_stats, z_score, input_data)
        anomaly_type, severity = self._classify_anomaly(z_score, signal_value, input_data)
        indicators = self._generate_indicators(
            z_score, signal_value, input_data, fiscal_amplification
        )
        evidence = self._generate_evidence(
            input_data, historical_stats, z_score, signal_value
        )
        recommendations = self._generate_recommendations(
            signal_value, severity, input_data
        )

        return {
            "signal_value": signal_value,
            "confidence": confidence,
            "z_score": z_score,
            "raw_deviation": approval_time - historical_stats.mean_approval_time,
            "normalized_deviation": z_score,
            "department_id": input_data.department_id,
            "approval_time": approval_time,
            "historical_mean": historical_stats.mean_approval_time,
            "historical_std": historical_stats.std_approval_time,
            "fiscal_amplification": fiscal_amplification,
            "is_fiscal_end": fiscal_amplification > 1.0,
            "days_to_fiscal_end": self._get_days_to_fiscal_end(input_data),
            "anomaly_type": anomaly_type,
            "severity": severity,
            "anomaly_indicators": indicators,
            "evidence": evidence,
            "recommendations": recommendations,
            "fiscal_period": historical_stats.fiscal_period,
            "statistics": historical_stats.model_dump(mode="json"),
            "outlier_analysis": self._analyze_outlier_context(
                input_data, historical_stats
            ),
        }

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        stats: TimingStatistics,
        z_score: float,
        input_data: ApprovalTimeInput,
    ) -> float:
        base = stats.confidence

        abs_z = abs(z_score)
        if abs_z > 3.0:
            z_conf = 0.9
        elif abs_z > 2.0:
            z_conf = 0.7
        elif abs_z > 1.0:
            z_conf = 0.5
        else:
            z_conf = 0.3

        sample_factor = min(1.0, stats.sample_count / 30)

        confidence = base * 0.4 + z_conf * 0.4 + sample_factor * 0.2
        return min(1.0, max(0.0, confidence))

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_anomaly(
        self,
        z_score: float,
        signal_value: float,
        input_data: ApprovalTimeInput,
    ) -> Tuple[str, str]:
        if z_score > 2.0:
            anomaly_type = "approval_time_delay"
        elif z_score < -2.0:
            anomaly_type = "approval_time_short"
        else:
            anomaly_type = "normal"

        if signal_value >= 0.9:
            severity = "critical"
        elif signal_value >= 0.7:
            severity = "high"
        elif signal_value >= 0.4:
            severity = "medium"
        else:
            severity = "low"

        return anomaly_type, severity

    # ------------------------------------------------------------------
    # Indicators
    # ------------------------------------------------------------------

    def _generate_indicators(
        self,
        z_score: float,
        signal_value: float,
        input_data: ApprovalTimeInput,
        fiscal_amplification: float,
    ) -> List[str]:
        indicators: List[str] = []

        abs_z = abs(z_score)
        if abs_z > 3.0:
            indicators.append("EXTREME_Z_SCORE")
        elif abs_z > 2.0:
            indicators.append("HIGH_Z_SCORE")

        if fiscal_amplification > 1.0:
            indicators.append("FISCAL_END_AMPLIFICATION")
            if fiscal_amplification > 1.5:
                indicators.append("HIGH_FISCAL_AMPLIFICATION")

        if input_data.approval_date.weekday() >= 5:
            indicators.append("WEEKEND_APPROVAL")

        if DateUtils.is_holiday(input_data.approval_date):
            indicators.append("HOLIDAY_APPROVAL")

        days_to_end = DateUtils.days_to_fiscal_end(input_data.approval_date)
        if 0 <= days_to_end <= 14:
            indicators.append("FISCAL_YEAR_END")
            if days_to_end <= 3:
                indicators.append("IMMINENT_FISCAL_END")

        if input_data.amount > 100_000:
            indicators.append("HIGH_VALUE_TRANSACTION")

        if input_data.approval_date.month == 12:
            indicators.append("YEAR_END")

        return indicators

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def _generate_evidence(
        self,
        input_data: ApprovalTimeInput,
        stats: TimingStatistics,
        z_score: float,
        signal_value: float,
    ) -> List[str]:
        evidence: List[str] = []
        approval_time = input_data.get_approval_time()

        evidence.append(
            f"Approval time: {approval_time:.1f} hours "
            f"(historical mean: {stats.mean_approval_time:.1f} hours, "
            f"std: {stats.std_approval_time:.1f} hours)"
        )

        abs_z = abs(z_score)
        if abs_z > 2.0:
            direction = "longer" if z_score > 0 else "shorter"
            evidence.append(
                f"Approval takes {abs_z:.1f} standard deviations {direction} "
                f"than average (Z-score: {z_score:.2f})"
            )

        days_to_end = DateUtils.days_to_fiscal_end(input_data.approval_date)
        if 0 <= days_to_end <= 14:
            evidence.append(
                f"Transaction is near fiscal year end ({days_to_end} days remaining)"
            )
            if signal_value > 0.5:
                evidence.append("Amplified signal due to fiscal year end proximity")

        evidence.append(
            f"Based on {stats.sample_count} historical transactions "
            f"(confidence: {stats.confidence:.2f})"
        )

        if input_data.amount > 100_000:
            evidence.append(f"High value transaction: ${input_data.amount:,.2f}")

        if DateUtils.is_weekend(input_data.approval_date):
            evidence.append("Approval occurred on weekend")

        if DateUtils.is_holiday(input_data.approval_date):
            evidence.append("Approval occurred on holiday")

        return evidence

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self,
        signal_value: float,
        severity: str,
        input_data: ApprovalTimeInput,
    ) -> List[str]:
        recs: List[str] = []

        if signal_value >= 0.9:
            recs.append(
                "URGENT: Significant approval delay detected — "
                "immediate investigation required"
            )
            recs.append("Review approval process for bottlenecks or exceptions")
            recs.append(
                "Check if this is a legitimate delay or potential fraud indicator"
            )
        elif signal_value >= 0.7:
            recs.append("Significant approval anomaly — recommend priority review")
            recs.append("Investigate approval process for this vendor/department")
            recs.append("Verify supporting documentation for transaction")
        elif signal_value >= 0.4:
            recs.append("Moderate timing anomaly — recommend secondary review")
            recs.append("Monitor for patterns in approval times")
            recs.append(
                "Consider process improvement if delays are consistent"
            )

        is_fiscal_end = DateUtils.is_fiscal_year_end_period(
            input_data.approval_date
        )[0]
        if signal_value > 0.3 and is_fiscal_end:
            recs.append("Review for potential year-end rushing or fraud")
            recs.append("Verify if expedited approvals were properly authorized")

        if input_data.amount > 100_000 and signal_value > 0.5:
            recs.append(
                "High-value transaction with timing anomaly — escalate review"
            )

        return recs

    # ------------------------------------------------------------------
    # Outlier context
    # ------------------------------------------------------------------

    def _analyze_outlier_context(
        self,
        input_data: ApprovalTimeInput,
        stats: TimingStatistics,
    ) -> Dict[str, Any]:
        approval_time = input_data.get_approval_time()
        is_outlier = False
        above_upper = False
        below_lower = False

        if stats.iqr and stats.q1 is not None and stats.q3 is not None:
            lower_fence = stats.q1 - 1.5 * stats.iqr
            upper_fence = stats.q3 + 1.5 * stats.iqr
            is_outlier = approval_time < lower_fence or approval_time > upper_fence
            above_upper = approval_time > upper_fence
            below_lower = approval_time < lower_fence

        return {
            "is_outlier": is_outlier,
            "above_upper_fence": above_upper,
            "below_lower_fence": below_lower,
            "outlier_factor": (
                approval_time / stats.mean_approval_time
                if stats.mean_approval_time > 0
                else 0
            ),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_days_to_fiscal_end(input_data: ApprovalTimeInput) -> Optional[int]:
        if input_data.fiscal_year_end:
            return (input_data.fiscal_year_end - input_data.approval_date).days
        return None
