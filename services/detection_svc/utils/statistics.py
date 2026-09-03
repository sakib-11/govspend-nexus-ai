"""Advanced statistical utilities for price deviation detection."""

import math
from typing import Dict, List, Tuple, Optional


class StatisticsUtils:
    """Advanced statistical utilities for price deviation detection."""

    @staticmethod
    def calculate_iqr_metrics(prices: List[float]) -> Dict[str, float]:
        """
        Calculate comprehensive IQR metrics.
        Returns: dict with q1, q3, iqr, lower_fence, upper_fence
        """
        if not prices:
            return {}

        sorted_prices = sorted(prices)
        n = len(sorted_prices)

        q1 = StatisticsUtils._percentile(sorted_prices, 25)
        q3 = StatisticsUtils._percentile(sorted_prices, 75)
        iqr = q3 - q1

        # Standard multiplier for outlier detection
        multiplier = 1.5
        lower_fence = q1 - multiplier * iqr
        upper_fence = q3 + multiplier * iqr

        return {
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "lower_fence": lower_fence,
            "upper_fence": upper_fence
        }

    @staticmethod
    def _percentile(sorted_list: List[float], percentile: int) -> float:
        """Calculate exact percentile using linear interpolation."""
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
        else:
            lower = sorted_list[int(index)]
            upper = sorted_list[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

    @staticmethod
    def calculate_robust_metrics(prices: List[float]) -> Dict[str, float]:
        """
        Calculate robust statistical metrics resistant to outliers.
        """
        if not prices:
            return {}

        sorted_prices = sorted(prices)
        n = len(sorted_prices)

        # Trimmed mean (remove 5% from each tail)
        trim_count = int(n * 0.05)
        trimmed_prices = sorted_prices[trim_count:n - trim_count]
        robust_mean = sum(trimmed_prices) / len(trimmed_prices) if trimmed_prices else 0

        # Median absolute deviation (MAD) - robust variance measure
        median = StatisticsUtils._percentile(sorted_prices, 50)
        deviations = [abs(p - median) for p in prices]
        mad = StatisticsUtils._percentile(sorted(deviations), 50) * 1.4826  # Scale factor for normality

        # Coefficient of variation (robust)
        cv_robust = mad / median if median > 0 else 0

        return {
            "robust_mean": robust_mean,
            "median": median,
            "mad": mad,
            "cv_robust": cv_robust,
            "q1": StatisticsUtils._percentile(sorted_prices, 25),
            "q3": StatisticsUtils._percentile(sorted_prices, 75)
        }

    @staticmethod
    def calculate_sample_confidence(count: int, std_dev: float, mean: float) -> float:
        """
        Calculate confidence level based on sample characteristics.
        """
        if count == 0:
            return 0.0

        # Sample size confidence
        if count >= 30:
            size_score = 0.9
        elif count >= 15:
            size_score = 0.7
        elif count >= 10:
            size_score = 0.5
        elif count >= 5:
            size_score = 0.3
        else:
            size_score = 0.1

        # Variance confidence (relative to mean)
        if mean > 0 and std_dev:
            cv = std_dev / mean
            if cv < 0.1:
                variance_score = 0.9
            elif cv < 0.25:
                variance_score = 0.7
            elif cv < 0.5:
                variance_score = 0.5
            elif cv < 1.0:
                variance_score = 0.3
            else:
                variance_score = 0.1
        else:
            variance_score = 0.5

        # Sample representativeness (diminishing returns)
        representativeness_score = min(1.0, math.log10(count + 1) / 2)

        # Weighted combination
        confidence = (
            size_score * 0.5 +
            variance_score * 0.3 +
            representativeness_score * 0.2
        )

        return min(1.0, confidence)

    @staticmethod
    def detect_multimodal(prices: List[float], threshold: float = 0.5) -> bool:
        """
        Detect if price distribution is multimodal (multiple peaks).
        """
        if len(prices) < 10:
            return False

        try:
            # Use kernel density estimation for modality detection
            from sklearn.neighbors import KernelDensity
            import numpy as np

            prices_array = np.array(prices).reshape(-1, 1)
            kde = KernelDensity(bandwidth=1.0).fit(prices_array)

            # Sample density
            x_grid = np.linspace(min(prices), max(prices), 100).reshape(-1, 1)
            density = np.exp(kde.score_samples(x_grid))

            # Find peaks
            peaks = []
            for i in range(1, len(density) - 1):
                if density[i] > density[i-1] and density[i] > density[i+1]:
                    peaks.append(density[i])

            return len(peaks) >= 2
        except Exception:
            return False

    @staticmethod
    def identify_outlier_types(price: float, metrics: Dict[str, float]) -> List[str]:
        """
        Identify types of outlier patterns.
        """
        indicators = []

        if "upper_fence" in metrics and price > metrics["upper_fence"]:
            indicators.append("above_upper_fence")

        if "q3" in metrics and "iqr" in metrics:
            # Extreme outlier (> 3 * IQR)
            if price > metrics["q3"] + 3 * metrics["iqr"]:
                indicators.append("extreme_outlier")
            # Moderate outlier (1.5-3 * IQR)
            elif price > metrics["upper_fence"]:
                indicators.append("moderate_outlier")

        if "robust_mean" in metrics and "mad" in metrics:
            # Deviation from robust center
            if metrics["mad"] > 0:
                deviations = abs(price - metrics["robust_mean"]) / metrics["mad"]
                if deviations > 5:
                    indicators.append("extreme_robust_deviation")
                elif deviations > 2:
                    indicators.append("significant_robust_deviation")

        return indicators