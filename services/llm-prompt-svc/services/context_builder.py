"""Context builder — format LLM input into prompt-ready sections."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from config import LLMPromptConfig
from models.prompt import LLMInput


class ContextBuilder:
    """Build structured context sections from LLM input data."""

    def __init__(self, config: LLMPromptConfig) -> None:
        self.config = config

    def build_context(self, llm_input: LLMInput) -> Dict[str, Any]:
        """Build a dict of prompt-ready context sections."""
        ctx: Dict[str, Any] = {
            "case_id": llm_input.case_id,
            "transaction_id": llm_input.transaction_id,
            "risk_score": f"{llm_input.risk_score:.2%}",
            "risk_tier": llm_input.risk_tier.value,
            "signals": self._format_signals(llm_input.signals),
            "evidence_bundle": self._format_evidence(llm_input.evidence_bundle),
            "retrieved_policies": self._format_policies(llm_input.retrieved_policies),
            "context": self._build_metadata_context(llm_input.metadata),
        }

        # Optional metadata-derived fields
        meta = llm_input.metadata
        ctx["department_line"] = (
            f"- Department: {meta['department']}" if "department" in meta else ""
        )
        ctx["amount_line"] = (
            f"- Amount: ${meta['amount']:,.2f}" if "amount" in meta else ""
        )
        ctx["vendor_line"] = (
            f"- Vendor: {meta['vendor_token']}" if "vendor_token" in meta else ""
        )
        ctx["date_line"] = (
            f"- Date: {meta['transaction_date']}" if "transaction_date" in meta else ""
        )

        return ctx

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _format_signals(self, signals: List[Dict[str, Any]]) -> str:
        if not signals:
            return "No signals detected."

        lines: List[str] = []
        for sig in signals[: self.config.MAX_EXPLANATION_POINTS]:
            dtype = sig.get("detector_type", "unknown")
            val = sig.get("signal_value", 0)
            conf = sig.get("confidence", 0)
            ev_ids = sig.get("evidence_ids", [])

            line = f"- {dtype}: Signal {val:.2%}, Confidence {conf:.2%}"
            if ev_ids:
                line += f", Evidence: {', '.join(ev_ids[:3])}"
            lines.append(line)

        return "\n".join(lines)

    def _format_evidence(self, evidence_bundle: Dict[str, Any]) -> str:
        items = evidence_bundle.get("evidence", [])
        if not items:
            return "No evidence available."

        lines: List[str] = []
        for ev in items[: self.config.MAX_EVIDENCE_ITEMS]:
            eid = ev.get("id", "unknown")
            desc = ev.get("description", "No description")
            etype = ev.get("type", "")
            conf = ev.get("confidence")

            line = f"- {eid}: {desc}"
            if etype:
                line += f" (Type: {etype})"
            if conf is not None:
                line += f", Confidence: {conf:.2%}"
            lines.append(line)

        return "\n".join(lines)

    def _format_policies(self, policies: List[Dict[str, Any]]) -> str:
        if not policies:
            return "No relevant policies retrieved."

        lines: List[str] = []
        for pol in policies[: self.config.MAX_POLICY_CHUNKS]:
            pid = pol.get("policy_id", "unknown")
            title = pol.get("title", "Untitled")
            relevance = pol.get("relevance", 0)
            content = pol.get("content", "")

            if len(content) > 300:
                content = content[:300] + "..."

            line = f"- {pid}: {title}"
            line += f"\n  Relevance: {relevance:.2%}"
            line += f"\n  Content: {content}"
            lines.append(line)

        return "\n".join(lines)

    def _build_metadata_context(self, metadata: Dict[str, Any]) -> str:
        parts: List[str] = []
        for key in ("case_history", "department", "amount", "vendor_info", "jurisdiction"):
            if key in metadata:
                label = key.replace("_", " ").title()
                value = metadata[key]
                if key == "amount":
                    value = f"${value:,.2f}"
                parts.append(f"{label}: {value}")
        return "\n".join(parts) if parts else "No additional context available."
