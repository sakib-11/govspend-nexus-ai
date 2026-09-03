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


def validate_signals(signals: Any) -> List[str]:
    """Validate a list of signal dicts."""
    errors: List[str] = []
    if not isinstance(signals, list):
        return ["Signals must be a list"]
    for i, sig in enumerate(signals):
        if not isinstance(sig, dict):
            errors.append(f"Signal {i} must be a dict")
            continue
        if "detector_type" not in sig:
            errors.append(f"Signal {i} missing 'detector_type'")
        if "signal_value" not in sig:
            errors.append(f"Signal {i} missing 'signal_value'")
        if "confidence" not in sig:
            errors.append(f"Signal {i} missing 'confidence'")
    return errors


def validate_explanations(explanations: Any) -> List[str]:
    """Validate a list of explanation point dicts."""
    errors: List[str] = []
    if not isinstance(explanations, list):
        return ["Explanations must be a list"]
    if len(explanations) == 0:
        return ["At least one explanation is required"]
    for i, exp in enumerate(explanations):
        if not isinstance(exp, dict):
            errors.append(f"Explanation {i} must be a dict")
            continue
        for field in ("point_number", "detector_name", "sentence", "confidence"):
            if field not in exp:
                errors.append(f"Explanation {i} missing '{field}'")
        if "sentence" in exp and isinstance(exp["sentence"], str) and len(exp["sentence"]) < 10:
            errors.append(f"Explanation {i} sentence must be at least 10 characters")
    return errors


def collect_evidence_ids(input_data: Dict[str, Any]) -> Set[str]:
    """Collect all evidence IDs from input signals and evidence bundle."""
    ids: Set[str] = set()

    # From signals
    for sig in input_data.get("signals", []):
        ids.update(sig.get("evidence_ids", []))

    # From evidence bundle
    bundle = input_data.get("evidence_bundle", {})
    for ev in bundle.get("evidence", []):
        if "id" in ev:
            ids.add(ev["id"])

    return ids


def collect_policy_ids(input_data: Dict[str, Any]) -> Set[str]:
    """Collect all policy IDs from input retrieved policies."""
    ids: Set[str] = set()
    for policy in input_data.get("retrieved_policies", []):
        pid = policy.get("policy_id")
        if pid:
            ids.add(pid)
    return ids


def compute_citation_coverage(
    explanations: List[Dict[str, Any]],
    evidence_ids: Set[str],
    policy_ids: Set[str],
) -> float:
    """Compute fraction of explanations that have at least one valid citation."""
    if not explanations:
        return 0.0
    grounded = 0
    for exp in explanations:
        ev = set(exp.get("evidence_ids", []))
        pol = set(exp.get("policy_references", []))
        if ev & evidence_ids or pol & policy_ids:
            grounded += 1
    return grounded / len(explanations)
