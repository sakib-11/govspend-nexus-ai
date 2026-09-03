"""Validation utilities — input/output validation helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


def validate_risk_score(score: Any) -> Optional[str]:
    """Return an error message if *score* is not in [0, 1]."""
    if not isinstance(score, (int, float)):
        return f"Risk score must be a number, got {type(score).__name__}"
    if not 0.0 <= score <= 1.0:
        return f"Risk score must be between 0 and 1, got {score}"
    return None


def validate_confidence(score: Any) -> Optional[str]:
    """Return an error message if *confidence* is not in [0, 1]."""
    if not isinstance(score, (int, float)):
        return f"Confidence must be a number, got {type(score).__name__}"
    if not 0.0 <= score <= 1.0:
        return f"Confidence must be between 0 and 1, got {score}"
    return None


def validate_explanation_points(points: Any) -> List[str]:
    """Validate a list of explanation point dicts."""
    errors: List[str] = []
    if not isinstance(points, list):
        return ["Explanations must be a list"]
    if len(points) == 0:
        return ["At least one explanation is required"]
    for i, pt in enumerate(points):
        if not isinstance(pt, dict):
            errors.append(f"Explanation {i} must be a dict")
            continue
        for field in ("point_number", "detector_name", "sentence", "confidence"):
            if field not in pt:
                errors.append(f"Explanation {i} missing '{field}'")
        if "sentence" in pt and isinstance(pt["sentence"], str) and len(pt["sentence"]) < 10:
            errors.append(f"Explanation {i} sentence must be at least 10 characters")
    return errors


def collect_evidence_ids(input_data: Dict[str, Any]) -> Set[str]:
    """Collect all evidence IDs from signals and evidence bundle."""
    ids: Set[str] = set()
    for sig in input_data.get("signals", []):
        ids.update(sig.get("evidence_ids", []))
    bundle = input_data.get("evidence_bundle", {})
    for ev in bundle.get("evidence", []):
        if "id" in ev:
            ids.add(ev["id"])
    return ids


def collect_policy_ids(input_data: Dict[str, Any]) -> Set[str]:
    """Collect all policy IDs from retrieved policies."""
    ids: Set[str] = set()
    for pol in input_data.get("retrieved_policies", []):
        pid = pol.get("policy_id")
        if pid:
            ids.add(pid)
    return ids
