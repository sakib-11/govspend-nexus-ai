"""Tier classifier for risk tier determination."""


from ..models.scoring import RiskTier


class TierClassifier:
    """Classifies risk scores into tiers."""

    def __init__(
        self,
        high_threshold: float = 0.75,
        borderline_threshold: float = 0.40,
    ):
        if not (0.0 <= borderline_threshold < high_threshold <= 1.0):
            raise ValueError(
                "Thresholds must satisfy: 0 <= borderline < high <= 1"
            )
        self.high_threshold = high_threshold
        self.borderline_threshold = borderline_threshold

    def classify(self, risk_score: float) -> RiskTier:
        """Classify risk score into tier."""
        if risk_score >= self.high_threshold:
            return RiskTier.HIGH
        elif risk_score >= self.borderline_threshold:
            return RiskTier.BORDERLINE
        else:
            return RiskTier.LOW

    def get_thresholds(self) -> dict:
        """Get current threshold values."""
        return {
            "high_threshold": self.high_threshold,
            "borderline_threshold": self.borderline_threshold,
        }

    def update_thresholds(
        self,
        high_threshold: float | None = None,
        borderline_threshold: float | None = None,
    ):
        """Update threshold values."""
        if high_threshold is not None:
            if not (0.0 <= high_threshold <= 1.0):
                raise ValueError("high_threshold must be in [0, 1]")
            self.high_threshold = high_threshold

        if borderline_threshold is not None:
            if not (0.0 <= borderline_threshold < self.high_threshold):
                raise ValueError(
                    "borderline_threshold must be in [0, high_threshold)"
                )
            self.borderline_threshold = borderline_threshold