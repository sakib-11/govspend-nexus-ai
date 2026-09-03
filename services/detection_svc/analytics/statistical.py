"""Statistical analysis utilities — no external scientific dependencies.

All functions are pure-Python (``math`` only) so the detector can run
without numpy or scipy.  Swap in vectorised implementations if the
data volume ever demands it.
"""

import math
from datetime import datetime
from typing import Any, Dict, List, Optional


class StatisticalAnalyzer:
    """Stateless statistical helpers for timing anomaly detection."""

    # ------------------------------------------------------------------
    # Descriptive statistics
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_statistics(values: List[float]) -> Dict[str, float]:
        """Comprehensive descriptive statistics for a list of values.

        Returns a dict with keys: count, mean, median, std, q1, q3,
        iqr, lower_fence, upper_fence, outlier_count, min, max,
        ci_lower, ci_upper.
        """
        if not values:
            return {}

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        mean = sum(values) / n
        median = (
            sorted_vals[n // 2]
            if n % 2
            else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
        )

        # Population standard deviation
        variance = sum((x - mean) ** 2 for x in values) / n
        std = math.sqrt(variance)

        q1 = StatisticalAnalyzer._percentile(sorted_vals, 25)
        q3 = StatisticalAnalyzer._percentile(sorted_vals, 75)
        iqr = q3 - q1

        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr
        outlier_count = sum(1 for x in values if x < lower_fence or x > upper_fence)

        # 95 % confidence interval
        se = std / math.sqrt(n) if n > 0 else 0
        ci_lower = mean - 1.96 * se
        ci_upper = mean + 1.96 * se

        return {
            "count": n,
            "mean": mean,
            "median": median,
            "std": std,
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "lower_fence": lower_fence,
            "upper_fence": upper_fence,
            "outlier_count": outlier_count,
            "min": min(values),
            "max": max(values),
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
        }

    # ------------------------------------------------------------------
    # Percentile
    # ------------------------------------------------------------------

    @staticmethod
    def _percentile(sorted_list: List[float], percentile: int) -> float:
        """Linear-interpolation percentile (0–100)."""
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
    # Z-score & signal transforms
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_z_score(value: float, mean: float, std: float) -> float:
        """Standard Z-score: ``(value − mean) / std``."""
        if std == 0:
            return 0.0
        return (value - mean) / std

    @staticmethod
    def apply_sigmoid(z_score: float, k: float = 1.0) -> float:
        """Logistic sigmoid: ``1 / (1 + e^(−k·z))``.

        Maps any real Z to (0, 1) with the midpoint at z=0 → 0.5.
        """
        return 1.0 / (1.0 + math.exp(-k * z_score))

    # ------------------------------------------------------------------
    # Outlier detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_outliers_robust(
        values: List[float], method: str = "iqr"
    ) -> List[int]:
        """Return *indices* of outliers using *method*.

        Supported: ``"iqr"`` (default), ``"zscore"``.
        """
        if len(values) < 4:
            return []

        stats = StatisticalAnalyzer.calculate_statistics(values)
        mean = stats.get("mean", 0)
        std = stats.get("std", 0)

        if method == "iqr":
            lf = stats.get("lower_fence", 0)
            uf = stats.get("upper_fence", 0)
            return [i for i, v in enumerate(values) if v < lf or v > uf]

        if method == "zscore":
            threshold = 2.5
            return [
                i
                for i, v in enumerate(values)
                if abs(StatisticalAnalyzer.calculate_z_score(v, mean, std)) > threshold
            ]

        return []

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_confidence(
        sample_size: int, std: float, mean: float
    ) -> float:
        """Confidence score ∈ [0, 1] from sample characteristics."""
        if sample_size == 0:
            return 0.0

        # Sample-size component
        if sample_size >= 50:
            size_score = 0.95
        elif sample_size >= 30:
            size_score = 0.85
        elif sample_size >= 20:
            size_score = 0.70
        elif sample_size >= 10:
            size_score = 0.50
        elif sample_size >= 5:
            size_score = 0.30
        else:
            size_score = 0.10

        # Variance component (low CV → high score)
        if mean > 0 and std > 0:
            cv = std / mean
            if cv < 0.2:
                var_score = 0.90
            elif cv < 0.5:
                var_score = 0.70
            elif cv < 1.0:
                var_score = 0.50
            else:
                var_score = 0.30
        else:
            var_score = 0.50

        return min(1.0, size_score * 0.6 + var_score * 0.4)

    # ------------------------------------------------------------------
    # Seasonal / weekly pattern detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_seasonal_pattern(
        values: List[float],
        timestamps: List[datetime],
        period: str = "weekly",
    ) -> Dict[str, Any]:
        """Detect weekly or monthly seasonal patterns.

        Returns ``{averages, patterns, period}``.
        """
        if len(values) < 10:
            return {}

        if period == "weekly":
            groups: Dict[int, List[float]] = {i: [] for i in range(7)}
            for val, ts in zip(values, timestamps):
                groups[ts.weekday()].append(val)
        else:
            groups = {i: [] for i in range(1, 13)}
            for val, ts in zip(values, timestamps):
                groups[ts.month].append(val)

        averages = {
            k: (sum(g) / len(g) if g else 0) for k, g in groups.items()
        }

        patterns: List[str] = []
        if period == "weekly":
            weekend_vals = [averages.get(5, 0), averages.get(6, 0)]
            weekday_vals = [averages.get(i, 0) for i in range(5)]
            weekend_avg = sum(weekend_vals) / 2 if weekend_vals else 0
            weekday_avg = sum(weekday_vals) / 5 if weekday_vals else 0
            if weekend_avg > 0 and weekday_avg > 0:
                if weekend_avg > weekday_avg * 1.5:
                    patterns.append("WEEKEND_HIGHER")
                elif weekday_avg > weekend_avg * 1.5:
                    patterns.append("WEEKDAY_HIGHER")

        return {"averages": averages, "patterns": patterns, "period": period}
