"""Service for computing historical approval velocity statistics."""

import math
import statistics
from datetime import date, datetime
from typing import Dict, List, Optional

from ..models.approval_velocity import HistoricalApprovalStats
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ApprovalAnalyticsService:
    """Compute and query historical approval-time statistics."""

    def __init__(self) -> None:
        self.min_sample_size: int = 10

    # ------------------------------------------------------------------
    # Statistics computation
    # ------------------------------------------------------------------

    async def calculate_historical_stats(
        self,
        category: str,
        department_id: str,
        approval_times: List[float],
        timestamps: List[datetime],
    ) -> Optional[HistoricalApprovalStats]:
        """Build a ``HistoricalApprovalStats`` from raw data.

        Returns ``None`` when the sample is too small.
        """
        if len(approval_times) < self.min_sample_size:
            logger.warning("Insufficient samples for %s/%s", category, department_id)
            return None

        sorted_times = sorted(approval_times)
        n = len(sorted_times)

        mean = statistics.mean(approval_times)
        median = statistics.median(approval_times)
        std = statistics.stdev(approval_times) if n > 1 else 0.0

        p10 = self._percentile(sorted_times, 10)
        p25 = self._percentile(sorted_times, 25)
        p50 = median
        p75 = self._percentile(sorted_times, 75)
        p90 = self._percentile(sorted_times, 90)

        weekday_median = self._calculate_weekday_pattern(approval_times, timestamps)
        month_median = self._calculate_month_pattern(approval_times, timestamps)
        hour_median = self._calculate_hour_pattern(approval_times, timestamps)

        confidence = self._calculate_confidence(n, std, mean)

        return HistoricalApprovalStats(
            category=category,
            department_id=department_id,
            median_approval_time=median,
            mean_approval_time=mean,
            std_approval_time=std,
            min_time=min(approval_times),
            max_time=max(approval_times),
            q1=p25,
            q3=p75,
            sample_count=n,
            confidence=confidence,
            p10=p10,
            p25=p25,
            p50=p50,
            p75=p75,
            p90=p90,
            weekday_median=weekday_median,
            month_median=month_median,
            hour_median=hour_median,
        )

    # ------------------------------------------------------------------
    # Percentile
    # ------------------------------------------------------------------

    @staticmethod
    def _percentile(sorted_list: List[float], percentile: int) -> float:
        n = len(sorted_list)
        if n == 0:
            return 0.0
        if percentile == 0:
            return sorted_list[0]
        if percentile == 100:
            return sorted_list[-1]
        index = (n - 1) * percentile / 100
        if index.is_integer():
            return sorted_list[int(index)]
        lower = sorted_list[int(index)]
        upper = sorted_list[int(index) + 1]
        return lower + (upper - lower) * (index - int(index))

    # ------------------------------------------------------------------
    # Time-based patterns
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_weekday_pattern(
        times: List[float], timestamps: List[datetime]
    ) -> Dict[int, float]:
        groups: Dict[int, List[float]] = {i: [] for i in range(7)}
        for t, ts in zip(times, timestamps):
            groups[ts.weekday()].append(t)
        return {
            wd: statistics.median(vals)
            for wd, vals in groups.items()
            if len(vals) >= 3
        }

    @staticmethod
    def _calculate_month_pattern(
        times: List[float], timestamps: List[datetime]
    ) -> Dict[int, float]:
        groups: Dict[int, List[float]] = {i: [] for i in range(1, 13)}
        for t, ts in zip(times, timestamps):
            groups[ts.month].append(t)
        return {
            m: statistics.median(vals)
            for m, vals in groups.items()
            if len(vals) >= 3
        }

    @staticmethod
    def _calculate_hour_pattern(
        times: List[float], timestamps: List[datetime]
    ) -> Dict[int, float]:
        groups: Dict[int, List[float]] = {i: [] for i in range(24)}
        for t, ts in zip(times, timestamps):
            groups[ts.hour].append(t)
        return {
            h: statistics.median(vals)
            for h, vals in groups.items()
            if len(vals) >= 3
        }

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_confidence(sample_size: int, std: float, mean: float) -> float:
        if sample_size < 10:
            return 0.0

        if sample_size >= 50:
            size_score = 0.90
        elif sample_size >= 30:
            size_score = 0.70
        elif sample_size >= 20:
            size_score = 0.50
        else:
            size_score = 0.30

        if mean > 0 and std > 0:
            cv = std / mean
            if cv < 0.3:
                var_score = 0.90
            elif cv < 0.6:
                var_score = 0.70
            elif cv < 1.0:
                var_score = 0.50
            else:
                var_score = 0.30
        else:
            var_score = 0.50

        return min(1.0, size_score * 0.5 + var_score * 0.5)

    # ------------------------------------------------------------------
    # Contextual median
    # ------------------------------------------------------------------

    async def get_contextual_median(
        self,
        stats: HistoricalApprovalStats,
        approval_date: date,
        category: str,
    ) -> float:
        """Adjust the median with weekday and month patterns.

        The idea: if approvals on Mondays are historically slower, use
        that pattern to avoid flagging a Monday approval as suspicious
        just because the overall median includes fast Friday approvals.
        """
        median = stats.median_approval_time

        # Weekday adjustment
        if stats.weekday_median:
            wd = approval_date.weekday()
            if wd in stats.weekday_median:
                wd_median = stats.weekday_median[wd]
                median = wd_median * 0.7 + median * 0.3

        # Month adjustment
        if stats.month_median:
            m = approval_date.month
            if m in stats.month_median:
                m_median = stats.month_median[m]
                median = m_median * 0.6 + median * 0.4

        return median
