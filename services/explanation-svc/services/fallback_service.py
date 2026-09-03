"""Fallback service — generate template-based explanations when the LLM fails."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config import ExplanationConfig
from models.explanation import (
    Citation,
    ExplanationPoint,
    ExplanationResponse,
    ExplanationRequest,
    ExplanationStatus,
)

logger = logging.getLogger(__name__)

# Per-detector sentence templates
_SENTENCE_TEMPLATES: Dict[str, str] = {
    "price_deviation": "The unit price deviates from market benchmarks, indicating potential pricing irregularities.",
    "duplicate_fuzzy": "This transaction closely resembles previously processed invoices from the same vendor.",
    "vendor_graph_risk": "The vendor's relationship network shows concentrated transactions with a small number of officials.",
    "timing_anomaly": "The approval time is statistically unusual compared to historical patterns.",
    "contract_splitting": "Multiple purchase orders to this vendor in a short window may indicate deliberate splitting.",
    "approval_velocity": "This purchase order was approved faster than typical for similar transactions.",
}


class FallbackService:
    """Generate fallback explanations when the LLM is unavailable."""

    def __init__(self, config: ExplanationConfig) -> None:
        self.config = config

    async def generate(
        self,
        request: ExplanationRequest,
        error_message: Optional[str] = None,
    ) -> ExplanationResponse:
        """Build a deterministic fallback explanation from the signals."""
        tier = request.risk_tier.upper()

        # Build summary
        sig_summary = self._signal_summary(request.signals)
        if tier == "HIGH":
            summary = (
                f"⚠️ HIGH RISK — This transaction (risk score {request.risk_score:.2%}) "
                f"requires immediate review. {sig_summary}"
            )
        elif tier == "BORDERLINE":
            summary = (
                f"⚠️ BORDERLINE RISK — This transaction (risk score {request.risk_score:.2%}) "
                f"needs secondary verification. {sig_summary}"
            )
        else:
            summary = (
                f"✅ LOW RISK — This transaction (risk score {request.risk_score:.2%}) "
                f"appears within normal parameters. {sig_summary}"
            )

        # Build explanation points
        explanations: List[ExplanationPoint] = []
        for idx, sig in enumerate(request.signals[:5]):
            dtype = sig.get("detector_type", "unknown")
            val = sig.get("signal_value", 0)
            conf = sig.get("confidence", 0.5)
            ev_ids = sig.get("evidence_ids", [])

            sentence = _SENTENCE_TEMPLATES.get(
                dtype,
                f"The {dtype} signal (value: {val:.2%}) requires investigation.",
            )

            explanations.append(ExplanationPoint(
                point_number=idx + 1,
                detector_name=dtype,
                sentence=sentence,
                confidence=conf,
                evidence_ids=ev_ids,
            ))

        # Compute grounding from evidence coverage
        grounded = sum(1 for e in explanations if e.evidence_ids)
        grounding = grounded / len(explanations) if explanations else 0.0

        return ExplanationResponse(
            case_id=request.case_id,
            transaction_id=request.transaction_id,
            summary=summary,
            confidence=0.7,
            explanations=explanations,
            grounding_score=round(grounding, 4),
            citations_used=grounded,
            total_evidence=len(request.evidence_bundle.get("evidence", [])),
            total_policies=len(request.retrieved_policies),
            status=ExplanationStatus.FALLBACK,
            llm_model="fallback",
            llm_provider="fallback",
            generation_time_ms=0.0,
            token_count=0,
            is_fallback=True,
            fallback_reason=error_message or "LLM generation failed",
        )

    def _signal_summary(self, signals: List[Dict[str, Any]]) -> str:
        if not signals:
            return "No signals detected."
        high = [s for s in signals if s.get("signal_value", 0) > 0.7]
        if high:
            names = [s.get("detector_type", "unknown") for s in high[:3]]
            return f"High-risk signals: {', '.join(names)}."
        return f"{len(signals)} signal(s) detected."
