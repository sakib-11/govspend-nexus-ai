"""Formatting utilities — format signals, evidence, and policies for prompts."""

from __future__ import annotations

from typing import Any, Dict, List


def format_signals(signals: List[Dict[str, Any]], max_items: int = 10) -> str:
    """Format signal dicts into a human-readable list."""
    if not signals:
        return "No signals detected."
    lines: List[str] = []
    for sig in signals[:max_items]:
        dtype = sig.get("detector_type", "unknown")
        val = sig.get("signal_value", 0)
        conf = sig.get("confidence", 0)
        ev = sig.get("evidence_ids", [])
        line = f"- {dtype}: signal {val:.2%}, confidence {conf:.2%}"
        if ev:
            line += f", evidence: {', '.join(ev[:3])}"
        lines.append(line)
    return "\n".join(lines)


def format_evidence(evidence_bundle: Dict[str, Any], max_items: int = 10) -> str:
    """Format evidence bundle into a human-readable list."""
    items = evidence_bundle.get("evidence", [])
    if not items:
        return "No evidence available."
    lines: List[str] = []
    for ev in items[:max_items]:
        eid = ev.get("id", "unknown")
        desc = ev.get("description", "No description")
        etype = ev.get("type", "")
        line = f"- {eid}: {desc}"
        if etype:
            line += f" (type: {etype})"
        lines.append(line)
    return "\n".join(lines)


def format_policies(policies: List[Dict[str, Any]], max_items: int = 5) -> str:
    """Format retrieved policies into a human-readable list."""
    if not policies:
        return "No relevant policies retrieved."
    lines: List[str] = []
    for pol in policies[:max_items]:
        pid = pol.get("policy_id", "unknown")
        title = pol.get("title", "Untitled")
        content = pol.get("content", "")
        if len(content) > 300:
            content = content[:300] + "..."
        lines.append(f"- {pid}: {title}\n  {content}")
    return "\n".join(lines)


def format_signal_summary(signals: List[Dict[str, Any]]) -> str:
    """One-line summary of signals."""
    if not signals:
        return "No signals"
    high = [s for s in signals if s.get("signal_value", 0) > 0.7]
    if high:
        names = [s.get("detector_type", "unknown") for s in high[:3]]
        return f"High-risk signals: {', '.join(names)}"
    return f"{len(signals)} signal(s) detected"
