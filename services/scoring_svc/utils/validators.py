"""Validators for the Scoring Service."""


from ..models.scoring import WeightConfig
from ..models.signals import DetectorSignal


class Validators:
    """Validation utilities for scoring service."""

    @staticmethod
    def validate_weights_sum_to_one(weights: dict) -> bool:
        """Validate that weights sum to 1.0."""
        total = sum(weights.values())
        return 0.999 <= total <= 1.001

    @staticmethod
    def validate_signal_value(value: float) -> bool:
        """Validate signal value is in [0, 1]."""
        return 0.0 <= value <= 1.0

    @staticmethod
    def validate_confidence(value: float) -> bool:
        """Validate confidence is in [0, 1]."""
        return 0.0 <= value <= 1.0

    @staticmethod
    def validate_detector_signal(signal: DetectorSignal) -> list[str]:
        """Validate a detector signal. Returns list of errors."""
        errors = []

        if not Validators.validate_signal_value(signal.signal_value):
            errors.append(f"Invalid signal_value: {signal.signal_value}")

        if not Validators.validate_confidence(signal.confidence):
            errors.append(f"Invalid confidence: {signal.confidence}")

        if not signal.detector_type:
            errors.append("detector_type is required")

        if not signal.transaction_id:
            errors.append("transaction_id is required")

        return errors

    @staticmethod
    def validate_weight_config(config: WeightConfig) -> list[str]:
        """Validate weight configuration."""
        errors = []

        total = sum(config.weights.values())
        if not (0.999 <= total <= 1.001):
            errors.append(f"Weights sum to {total:.4f}, must be 1.0")

        # Check all expected detector types have weights
        expected_detectors = [
            "price_deviation",
            "duplicate_fuzzy",
            "vendor_graph_risk",
            "timing_anomaly",
            "contract_splitting",
            "approval_velocity",
        ]
        for detector in expected_detectors:
            if detector not in config.weights:
                errors.append(f"Missing weight for detector: {detector}")

        # Check all weights are non-negative
        for name, weight in config.weights.items():
            if weight < 0:
                errors.append(f"Negative weight for {name}: {weight}")

        return errors

    @staticmethod
    def validate_transaction_id(transaction_id: str) -> bool:
        """Validate transaction ID format."""
        return bool(transaction_id and len(transaction_id) > 0 and len(transaction_id) <= 255)