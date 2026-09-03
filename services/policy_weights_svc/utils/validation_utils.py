"""Validation utilities for weight policies."""

from typing import Dict, List, Optional

from ..models.policy import DetectorWeights, DETECTOR_NAMES


class ValidationUtils:
    """Static helpers for validating weights and policy data."""

    @staticmethod
    def validate_weights_sum(
        weights: DetectorWeights, tolerance: float = 0.001
    ) -> bool:
        """Check that weights sum to 1.0 within tolerance."""
        return weights.validate_sum(tolerance)

    @staticmethod
    def validate_weight_ranges(weights: DetectorWeights) -> List[str]:
        """Return a list of error strings for out-of-range weights."""
        errors: List[str] = []
        for name in DETECTOR_NAMES:
            val = getattr(weights, name)
            if val < 0.0 or val > 1.0:
                errors.append(f"{name}: {val} must be between 0.0 and 1.0")
        return errors

    @staticmethod
    def validate_version_string(version: str) -> bool:
        """Check version matches v{major}.{minor} pattern."""
        from .version_utils import VersionUtils
        return VersionUtils.validate(version)

    @staticmethod
    def validate_no_zero_weights(weights: DetectorWeights) -> bool:
        """Return True if every detector has a non-zero weight.

        Zero-weight detectors are allowed but flagged — a detector with
        weight 0 effectively disables it in the scoring pipeline.
        """
        return all(getattr(weights, name) > 0 for name in DETECTOR_NAMES)

    @staticmethod
    def detect_drift(
        current: DetectorWeights,
        historical: List[DetectorWeights],
        threshold: float = 0.10,
    ) -> Dict[str, bool]:
        """Check for drift per-detector against historical averages.

        Returns a dict mapping detector name → True if drifted.
        """
        if not historical:
            return {name: False for name in DETECTOR_NAMES}

        averages: Dict[str, float] = {}
        for name in DETECTOR_NAMES:
            avg = sum(getattr(w, name) for w in historical) / len(historical)
            averages[name] = avg

        return {
            name: abs(getattr(current, name) - averages[name]) > threshold
            for name in DETECTOR_NAMES
        }

    @staticmethod
    def classify_change_magnitude(
        old: DetectorWeights, new: DetectorWeights
    ) -> str:
        """Classify the magnitude of a weight change."""
        max_change = old.max_abs_change(new)
        if max_change < 0.01:
            return "negligible"
        if max_change < 0.05:
            return "minor"
        if max_change < 0.15:
            return "moderate"
        return "major"
