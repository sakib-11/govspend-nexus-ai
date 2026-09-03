"""Core scoring engine combining weighted sum and confidence factor."""

from datetime import datetime, timezone

from ..models.scoring import (
    RiskTier,
    ScoringResult,
)
from ..models.signals import DetectorSignal
from ..utils.validators import Validators
from ..utils.weights_policy import WeightPolicyManager
from .confidence_calculator import ConfidenceCalculator
from .tier_classifier import TierClassifier


class ScoringEngine:
    """
    Core scoring engine implementing:
    RiskScore = Σ(weight_i × signal_i) × confidence_factor

    Where:
    - weight_i: Weight for detector i from versioned policy
    - signal_i: Signal value from detector i (in [0, 1])
    - confidence_factor: Aggregated confidence from used signals
    """

    def __init__(
        self,
        weight_manager: WeightPolicyManager,
        confidence_calculator: ConfidenceCalculator,
        tier_classifier: TierClassifier,
    ):
        self.weight_manager = weight_manager
        self.confidence_calculator = confidence_calculator
        self.tier_classifier = tier_classifier

    async def score_transaction(
        self,
        signals: list[DetectorSignal],
        weights_version: str | None = None,
        min_confidence: float = 0.30,
        confidence_floor: float = 0.50,
    ) -> ScoringResult:
        """
        Score a transaction using weighted sum and confidence factor.

        Formula: RiskScore = Σ(weight_i × signal_i) × confidence_factor

        Args:
            signals: List of detector signals for the transaction
            weights_version: Optional specific weight version to use
            min_confidence: Minimum confidence threshold for signals
            confidence_floor: Minimum confidence factor floor

        Returns:
            ScoringResult with risk score, tier, and components
        """
        if not signals:
            raise ValueError("No signals provided for transaction")

        # Validate signals
        for signal in signals:
            errors = Validators.validate_detector_signal(signal)
            if errors:
                raise ValueError(f"Invalid signal: {', '.join(errors)}")

        # Get weights configuration
        weights_config = self.weight_manager.get_weights(weights_version)

        # Filter signals by minimum confidence
        valid_signals = [s for s in signals if s.confidence >= min_confidence]

        if not valid_signals:
            # Use signals without confidence filter if all below threshold
            valid_signals = signals
            confidence_factor = confidence_floor
        else:
            # Calculate confidence factor from valid signals
            confidences = [s.confidence for s in valid_signals]
            confidence_factor = self.confidence_calculator.compute_factor(
                confidences,
                floor=confidence_floor,
                method="harmonic",  # Harmonic mean penalizes low confidence
            )

        # Calculate weighted sum
        weighted_sum = 0.0
        total_weight_used = 0.0
        components = {}
        used_signals = []

        for signal in valid_signals:
            detector_type = signal.detector_type
            weight = weights_config.weights.get(detector_type, 0.0)

            if weight > 0:
                weighted_component = weight * signal.signal_value
                weighted_sum += weighted_component
                total_weight_used += weight
                components[detector_type] = weighted_component
                used_signals.append(signal)

        # Normalize by total weight of detectors that fired, so that
        # maximum signal values produce a weighted_sum near 1.0 regardless
        # of how many detectors are active.
        weighted_sum = weighted_sum / total_weight_used if total_weight_used > 0 else 0.0

        # Clamp weighted sum to [0, 1]
        weighted_sum = max(0.0, min(1.0, weighted_sum))

        # Calculate final risk score
        risk_score = weighted_sum * confidence_factor

        # Clamp final score to [0, 1]
        risk_score = max(0.0, min(1.0, risk_score))

        # Determine risk tier
        risk_tier = self.tier_classifier.classify(risk_score)

        # Build result
        result = ScoringResult(
            transaction_id=valid_signals[0].transaction_id,
            risk_score=risk_score,
            risk_tier=risk_tier,
            weighted_sum=weighted_sum,
            confidence_factor=confidence_factor,
            signals_used=len(used_signals),
            weights_version=weights_config.version,
            calculated_at=datetime.now(timezone.utc),
            components=components,
            metadata={
                "total_signals_received": len(signals),
                "signals_used_count": len(used_signals),
                "signals_filtered": len(signals) - len(used_signals),
                "min_confidence_used": min_confidence,
                "confidence_floor_used": confidence_floor,
                "total_weight_used": total_weight_used,
                "normalized_weighted_sum": weighted_sum,
            },
        )

        return result

    async def score_transactions_bulk(
        self,
        signals_map: dict[str, list[DetectorSignal]],
        weights_version: str | None = None,
        min_confidence: float = 0.30,
        confidence_floor: float = 0.50,
    ) -> dict[str, ScoringResult]:
        """Score multiple transactions in bulk."""
        results = {}
        for tx_id, signals in signals_map.items():
            try:
                result = await self.score_transaction(
                    signals,
                    weights_version,
                    min_confidence,
                    confidence_floor,
                )
                results[tx_id] = result
            except Exception as e:
                # Return error result but continue with others
                results[tx_id] = ScoringResult(
                    transaction_id=tx_id,
                    risk_score=0.0,
                    risk_tier=RiskTier.LOW,
                    weighted_sum=0.0,
                    confidence_factor=0.0,
                    signals_used=0,
                    weights_version="error",
                    calculated_at=datetime.now(timezone.utc),
                    components={},
                    metadata={"error": str(e)},
                )
        return results