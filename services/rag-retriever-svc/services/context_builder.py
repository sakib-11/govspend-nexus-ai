"""Context builder — construct retrieval context from case signals and evidence."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from models.retrieval import QueryContext

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Build QueryContext and search metadata from case data."""

    @staticmethod
    def from_case_data(
        case_signals: List[Dict[str, Any]],
        case_evidence: List[Dict[str, Any]],
        risk_score: Optional[float] = None,
        risk_tier: Optional[str] = None,
    ) -> QueryContext:
        """Build a QueryContext from case signals and evidence."""

        focus_areas: List[str] = []

        # Derive focus areas from signals
        if case_signals:
            signal_types = {s.get("detector_type", "") for s in case_signals}
            if "price_anomaly" in signal_types or "duplicate_invoice" in signal_types:
                focus_areas.extend(["fraud_detection", "procurement"])
            if "statutory_violation" in signal_types:
                focus_areas.append("compliance")
            if not focus_areas:
                focus_areas.append("general_investigation")

        # Derive from evidence types
        if case_evidence:
            evidence_types = {e.get("evidence_type", "") for e in case_evidence}
            if "invoice" in evidence_types:
                focus_areas.append("financial_review")
            if "graph" in evidence_types:
                focus_areas.append("network_analysis")

        # Risk-based focus
        if risk_tier == "HIGH":
            focus_areas.append("high_priority_fraud")
        elif risk_tier == "BORDERLINE":
            focus_areas.append("potential_fraud_review")

        return QueryContext(
            domain="government_procurement",
            focus_areas=list(set(focus_areas)),
            case_id=None,
        )

    @staticmethod
    def build_category_filter(
        focus_areas: List[str],
        include_policies: bool = True,
    ) -> Optional[List[str]]:
        """Map focus areas to document category filters."""

        category_map: Dict[str, List[str]] = {
            "fraud_detection": ["fraud", "investigation", "enforcement"],
            "compliance": ["compliance", "regulation", "policy"],
            "procurement": ["procurement", "contract", "gfr"],
            "financial_review": ["financial", "accounting", "audit"],
            "network_analysis": ["network", "relationship", "graph"],
            "high_priority_fraud": ["fraud", "enforcement", "criminal"],
            "potential_fraud_review": ["fraud", "investigation", "review"],
            "general_investigation": ["investigation", "enforcement"],
        }

        if not include_policies:
            return None

        categories: List[str] = []
        for area in focus_areas:
            categories.extend(category_map.get(area, []))

        return list(set(categories)) if categories else None

    @staticmethod
    def enrich_query_with_signals(
        base_query: str,
        case_signals: List[Dict[str, Any]],
    ) -> str:
        """Append signal-derived terms to the query."""
        if not case_signals:
            return base_query

        extra_terms: List[str] = []
        for signal in case_signals[:5]:
            dtype = signal.get("detector_type", "")
            value = signal.get("signal_value", 0)
            if value > 0.5 and dtype:
                extra_terms.append(dtype.replace("_", " "))

        if extra_terms:
            return f"{base_query} {' '.join(extra_terms)}"
        return base_query
