"""Validation service — validates weights, policies, and calibration data."""

from typing import Dict, List, Optional

from ..models.policy import DetectorWeights, WeightPolicy, DETECTOR_NAMES
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ValidationService:
    """Validates weight policies and calibration requests."""

    def validate_weights_sum(
        self, weights: DetectorWeights, tolerance: float = 0.001
    ) -> bool:
        """Validate that weights sum to 1.0."""
        total = weights.weight_sum()
        ok = abs(total - 1.0) < tolerance
        if not ok:
            logger.warning("Weights sum to %.4f, expected 1.0 (±%.4f)", total, tolerance)
        return ok

    def validate_weight_ranges(self, weights: DetectorWeights) -> List[str]:
        """Return error strings for any out-of-range weights."""
        errors: List[str] = []
        for name in DETECTOR_NAMES:
            val = getattr(weights, name)
            if val < 0.0 or val > 1.0:
                errors.append(f"{name}: {val} is not in [0.0, 1.0]")
        return errors

    def validate_policy_for_activation(self, policy: WeightPolicy) -> List[str]:
        """Run all checks needed before activating a policy."""
        errors: List[str] = []

        if not policy.can_activate():
            errors.append(
                f"Policy status '{policy.status.value}' does not allow activation"
            )

        if not self.validate_weights_sum(policy.weights):
            errors.append(
                f"Weights sum to {policy.weights.weight_sum():.4f}, expected ~1.0"
            )

        range_errors = self.validate_weight_ranges(policy.weights)
        errors.extend(range_errors)

        if not policy.name:
            errors.append("Policy must have a name")

        return errors

    def validate_performance_improvement(
        self,
        old_metrics: Optional[Dict[str, float]],
        new_metrics: Optional[Dict[str, float]],
    ) -> bool:
        """Check whether new metrics show improvement over old.

        Returns True if at least one core metric (precision, recall, f1, accuracy)
        improved and none degraded by more than 5pp.
        """
        if not old_metrics or not new_metrics:
            return True  # Cannot validate — assume OK

        core_metrics = ("precision", "recall", "f1_score", "accuracy")
        improvements = 0
        regressions = 0

        for key in core_metrics:
            old_val = old_metrics.get(key)
            new_val = new_metrics.get(key)
            if old_val is None or new_val is None:
                continue
            delta = new_val - old_val
            if delta > 0:
                improvements += 1
            elif delta < -0.05:
                regressions += 1

        # Need at least one improvement and no major regressions
        return improvements > 0 and regressions == 0

    def validate_calibration_request(self, request: dict) -> List[str]:
        """Validate a calibration request payload."""
        errors: List[str] = []

        if "weights" not in request:
            errors.append("Missing required field: weights")
            return errors

        weights_data = request["weights"]
        if isinstance(weights_data, dict):
            weights = DetectorWeights(**weights_data)
        else:
            weights = weights_data

        if not self.validate_weights_sum(weights):
            errors.append(f"Weights sum to {weights.weight_sum():.4f}, expected 1.0")

        errors.extend(self.validate_weight_ranges(weights))

        return errors
