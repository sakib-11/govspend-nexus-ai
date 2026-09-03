"""Few-shot examples — input/output pairs for in-context learning."""

from __future__ import annotations

from typing import Any, Dict, List

FEW_SHOT_EXAMPLES: List[Dict[str, Any]] = [
    {
        "input": {
            "case_id": "CASE-001",
            "transaction_id": "TX-001",
            "risk_score": 0.85,
            "risk_tier": "HIGH",
            "signals": [
                {"detector_type": "price_deviation", "signal_value": 0.92, "confidence": 0.95,
                 "evidence_ids": ["EV-1001"]},
                {"detector_type": "duplicate_fuzzy", "signal_value": 0.80, "confidence": 0.90,
                 "evidence_ids": ["EV-1002"]},
            ],
            "evidence_bundle": {
                "evidence": [
                    {"id": "EV-1001", "type": "invoice",
                     "description": "Invoice shows unit price 50% above market average for identical items"},
                    {"id": "EV-1002", "type": "comparison",
                     "description": "Near-identical transaction found in vendor history within 90 days"},
                ],
            },
            "retrieved_policies": [
                {"policy_id": "GFR-4.3", "title": "Government Financial Rules",
                 "content": "All procurement must be at prevailing market rates. "
                             "Departures exceeding 10% require written justification.",
                 "relevance": 0.92},
            ],
        },
        "output": {
            "summary": (
                "This case exhibits HIGH risk with two significant fraud indicators: "
                "a 50% price deviation above market benchmarks and a near-duplicate "
                "transaction within 90 days. Both signals are strongly supported by "
                "evidence and violate GFR-4.3 procurement pricing rules."
            ),
            "confidence": 0.92,
            "grounding_score": 1.0,
            "citations_used": 2,
            "total_evidence": 2,
            "total_policies": 1,
            "explanations": [
                {
                    "point_number": 1,
                    "detector_name": "price_deviation",
                    "sentence": (
                        "The invoice unit price exceeds the historical market benchmark "
                        "by 50%, indicating potential price manipulation or vendor collusion."
                    ),
                    "confidence": 0.95,
                    "evidence_ids": ["EV-1001"],
                    "policy_references": ["GFR-4.3"],
                    "citations": [
                        {
                            "citation_type": "evidence",
                            "reference_id": "EV-1001",
                            "reference_text": "Invoice shows unit price 50% above market average",
                            "relevance_score": 0.95,
                        },
                    ],
                },
                {
                    "point_number": 2,
                    "detector_name": "duplicate_fuzzy",
                    "sentence": (
                        "A near-identical transaction was found in the same vendor's "
                        "history within 90 days, suggesting potential duplicate invoicing "
                        "or contract splitting."
                    ),
                    "confidence": 0.90,
                    "evidence_ids": ["EV-1002"],
                    "policy_references": ["GFR-4.3"],
                    "citations": [
                        {
                            "citation_type": "evidence",
                            "reference_id": "EV-1002",
                            "reference_text": "Near-identical transaction found in vendor history",
                            "relevance_score": 0.90,
                        },
                    ],
                },
            ],
        },
    },
    {
        "input": {
            "case_id": "CASE-002",
            "transaction_id": "TX-002",
            "risk_score": 0.65,
            "risk_tier": "BORDERLINE",
            "signals": [
                {"detector_type": "timing_anomaly", "signal_value": 0.75, "confidence": 0.80,
                 "evidence_ids": ["EV-2001"]},
            ],
            "evidence_bundle": {
                "evidence": [
                    {"id": "EV-2001", "type": "timing",
                     "description": "Transaction approved in 15 minutes, median is 60 minutes"},
                ],
            },
            "retrieved_policies": [
                {"policy_id": "GFR-9.1", "title": "Government Financial Rules",
                 "content": "Approvals must allow adequate review time per transaction value.",
                 "relevance": 0.85},
            ],
        },
        "output": {
            "summary": (
                "The transaction shows a BORDERLINE timing anomaly with unusually "
                "fast approval. The 15-minute approval is well below the 60-minute "
                "median, potentially indicating inadequate review."
            ),
            "confidence": 0.80,
            "grounding_score": 1.0,
            "citations_used": 1,
            "total_evidence": 1,
            "total_policies": 1,
            "explanations": [
                {
                    "point_number": 1,
                    "detector_name": "timing_anomaly",
                    "sentence": (
                        "This transaction was approved in 15 minutes, significantly "
                        "below the median approval time of 60 minutes, suggesting "
                        "the review process may have been bypassed or abbreviated."
                    ),
                    "confidence": 0.80,
                    "evidence_ids": ["EV-2001"],
                    "policy_references": ["GFR-9.1"],
                    "citations": [
                        {
                            "citation_type": "evidence",
                            "reference_id": "EV-2001",
                            "reference_text": "Transaction approved in 15 minutes",
                            "relevance_score": 0.80,
                        },
                    ],
                },
            ],
        },
    },
]


def get_few_shot_examples(limit: int = 2) -> List[Dict[str, Any]]:
    """Return the first *limit* few-shot examples."""
    return FEW_SHOT_EXAMPLES[:limit]


def format_few_shot_for_prompt(examples: List[Dict[str, Any]]) -> str:
    """Format few-shot examples as a prompt section."""
    import json

    parts: List[str] = []
    for i, ex in enumerate(examples, 1):
        parts.append(f"Example {i}:")
        parts.append(f"Input:\n{json.dumps(ex['input'], indent=2)}")
        parts.append(f"Expected Output:\n{json.dumps(ex['output'], indent=2)}")
        parts.append("")
    return "\n".join(parts)
