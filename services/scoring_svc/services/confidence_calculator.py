"""Confidence calculator for computing confidence factors from detector signals."""

import statistics


class ConfidenceCalculator:
    """Calculates confidence factors from detector signal confidences."""

    @staticmethod
    def compute_factor(
        confidences: list[float],
        floor: float = 0.50,
        method: str = "mean",
    ) -> float:
        """
        Compute confidence factor from detector confidences.

        Methods:
        - mean: Arithmetic mean (default)
        - weighted_mean: Mean weighted by signal strength
        - harmonic: Harmonic mean (penalizes low values)
        - product: Product of confidences (Bayesian-like)
        """
        if not confidences:
            return floor

        if method == "mean":
            factor = statistics.mean(confidences)
        elif method == "weighted_mean":
            # Weight by confidence values themselves
            total = sum(confidences)
            if total > 0:
                factor = sum(c * c for c in confidences) / total
            else:
                factor = statistics.mean(confidences)
        elif method == "harmonic":
            # Harmonic mean penalizes low confidence values
            if min(confidences) <= 0:
                factor = 0.0
            else:
                factor = len(confidences) / sum(1.0 / c for c in confidences)
        elif method == "product":
            # Product (Bayesian-like combination)
            factor = 1.0
            for c in confidences:
                factor *= c
        else:
            factor = statistics.mean(confidences)

        # Apply floor and clamp
        factor = max(floor, factor)
        factor = min(1.0, factor)

        return factor

    @staticmethod
    def compute_confidence_decay(
        confidences: list[float],
        number_of_signals: int,
        floor: float = 0.50,
    ) -> float:
        """
        Compute confidence factor with decay based on signal count.
        Fewer signals = lower confidence.
        """
        if not confidences:
            return floor

        base = statistics.mean(confidences)

        # Penalize for having fewer than 3 signals
        if number_of_signals < 3:
            decay_factor = number_of_signals / 3.0
            factor = base * decay_factor
        else:
            factor = base

        return max(floor, min(1.0, factor))

    @staticmethod
    def compute_bayesian_factor(
        confidences: list[float],
        prior: float = 0.50,
        floor: float = 0.50,
    ) -> float:
        """
        Bayesian confidence update from prior belief.
        """
        if not confidences:
            return floor

        # Convert to log-odds
        prior_odds = prior / (1 - prior) if prior < 1 else float("inf")

        current_odds = prior_odds
        for c in confidences:
            if c >= 1.0:
                return 1.0
            if c <= 0.0:
                return floor
            # Likelihood ratio
            lr = c / (1 - c)
            current_odds *= lr

        # Convert back to probability
        factor = 1.0 if current_odds == float("inf") else current_odds / (1 + current_odds)

        return max(floor, min(1.0, factor))