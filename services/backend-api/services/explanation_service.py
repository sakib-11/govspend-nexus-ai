"""Explanation service — generate AI explanations for risk scores."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.explanation import CaseExplanation, ExplanationPoint

logger = logging.getLogger(__name__)

_SIGNAL_DESCRIPTIONS: Dict[str, str] = {
    "price_deviation": "The unit price deviates significantly from the market benchmark for this category and region. Historical peer pricing suggests this transaction is above the expected range.",
    "duplicate_fuzzy": "This invoice closely resembles previously processed invoices from the same vendor. Fuzzy matching detected high similarity with a prior transaction.",
    "vendor_graph_risk": "The vendor's relationship network shows concentrated transactions with a small number of approving officials, indicating potential collusion risk.",
    "timing_anomaly": "The approval time is statistically unusual compared to historical patterns for similar transactions.",
    "contract_splitting": "Multiple purchase orders to this vendor within a short window may indicate deliberate splitting to avoid review thresholds.",
    "approval_velocity": "This purchase order was approved faster than typical for similar transactions in this department.",
}

_MOCK_POLICIES = [
    {"policy_id": "GFR-4.3", "title": "Government Financial Rules — Procurement", "content": "All procurements must be at market rates. Price deviations above 20% require justification.", "relevance": 0.95},
    {"policy_id": "GFR-9.1", "title": "Government Financial Rules — Fraud Prevention", "content": "Duplicate invoices within 30 days are subject to fraud investigation.", "relevance": 0.92},
    {"policy_id": "GFR-12.4", "title": "Government Financial Rules — Vendor Relationships", "content": "Concentrated vendor-official relationships require independent verification.", "relevance": 0.88},
]


class ExplanationService:
    """Generate structured AI explanations for risk scores."""

    def __init__(self) -> None:
        self._cache: Dict[str, CaseExplanation] = {}

    def generate(
        self,
        case_id: str,
        *,
        risk_score: float,
        signals: List[Dict[str, Any]],
        evidence: Optional[List[Dict[str, Any]]] = None,
        transaction_id: str = "",
        include_policies: bool = True,
    ) -> CaseExplanation:
        """Generate an explanation for a case."""
        if case_id in self._cache:
            return self._cache[case_id]

        evidence = evidence or []
        policies = _MOCK_POLICIES if include_policies else []

        points: List[ExplanationPoint] = []
        sorted_signals = sorted(signals, key=lambda s: s.get("signal_value", 0), reverse=True)

        for idx, sig in enumerate(sorted_signals):
            sig_type = sig.get("detector_type", "unknown")
            sig_value = sig.get("signal_value", 0)
            confidence = sig.get("confidence", 0)

            desc = _SIGNAL_DESCRIPTIONS.get(sig_type, f"The {sig_type} detector flagged this transaction.")
            severity = "strongly" if sig_value > 0.7 else "moderately" if sig_value > 0.4 else "mildly"

            sentence = f"This transaction was {severity} flagged by {sig_type} analysis (signal: {sig_value:.2f}, confidence: {confidence:.2f}). {desc}"

            policy_refs = self._match_policies(sig_type, policies)

            point = ExplanationPoint(
                point_number=idx + 1,
                detector_name=sig_type,
                sentence=sentence,
                confidence=confidence,
                evidence_ids=[e.get("evidence_id", "") for e in evidence[:2]],
                policy_references=[p["policy_id"] for p in policy_refs],
                citations=[
                    {"source": "signal", "value": sig_value, "confidence": confidence},
                    *[{"source": "policy", "id": p["policy_id"], "title": p["title"]} for p in policy_refs],
                ],
            )
            points.append(point)

        tier = "high" if risk_score >= 0.75 else "borderline" if risk_score >= 0.40 else "low"
        sig_count = len(signals)
        high_count = sum(1 for s in signals if s.get("signal_value", 0) > 0.7)

        summary = (
            f"This transaction has been classified as {tier} risk (score: {risk_score:.2f}) "
            f"based on {sig_count} detector signals ({high_count} high-severity). "
        )
        if points:
            summary += f"The primary concern is: {points[0].sentence}"

        grounded = sum(1 for p in points if p.evidence_ids or p.policy_references)
        grounding = grounded / len(points) if points else 0.0

        sig_confs = [s.get("confidence", 0) for s in signals]
        overall_conf = sum(sig_confs) / len(sig_confs) if sig_confs else 0.5

        explanation = CaseExplanation(
            case_id=case_id,
            transaction_id=transaction_id,
            explanations=points,
            summary=summary,
            overall_confidence=round(overall_conf, 4),
            grounding_score=round(grounding, 4),
            evidence_count=len(evidence),
            policy_count=len(policies),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._cache[case_id] = explanation
        return explanation

    def get_cached(self, case_id: str) -> Optional[CaseExplanation]:
        return self._cache.get(case_id)

    @staticmethod
    def _match_policies(sig_type: str, policies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Match signal type to relevant policies."""
        mapping = {
            "price_deviation": ["GFR-4.3"],
            "duplicate_fuzzy": ["GFR-9.1"],
            "vendor_graph_risk": ["GFR-12.4", "GFR-9.1"],
            "contract_splitting": ["GFR-4.3", "GFR-9.1"],
        }
        relevant_ids = set(mapping.get(sig_type, []))
        return [p for p in policies if p["policy_id"] in relevant_ids]
