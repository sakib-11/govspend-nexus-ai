"""Template utilities — variable interpolation, token counting, and cost estimation."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Set


def extract_variables(template: str) -> List[str]:
    """Extract ``{variable}`` names from a template string."""
    return list(set(re.findall(r"\{(\w+)\}", template)))


def interpolate(template: str, variables: Dict[str, Any]) -> str:
    """Safely interpolate *variables* into *template*.

    Unknown variables are left as-is.  Supports nested dict access with
    dot notation (e.g. ``{meta.department}``).
    """
    def _replace(match: re.Match) -> str:
        key = match.group(1)
        # Support dot notation
        parts = key.split(".")
        value: Any = variables
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return match.group(0)  # leave as-is
            if value is None:
                return match.group(0)
        return str(value)

    return re.sub(r"\{(\w+(?:\.\w+)*)\}", _replace, template)


def render_template(template: str, variables: Dict[str, Any]) -> str:
    """Render a template, then clean up any un-interpolated placeholders."""
    rendered = interpolate(template, variables)
    # Remove orphaned placeholders
    rendered = re.sub(r"\{\w+\}", "", rendered)
    # Collapse multiple blank lines
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip()


def count_tokens_approx(text: str) -> int:
    """Approximate token count (1 token ≈ 4 characters for English)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    cost_per_1k_input: float = 0.01,
    cost_per_1k_output: float = 0.03,
) -> float:
    """Estimate USD cost for an LLM call."""
    input_cost = (input_tokens / 1000) * cost_per_1k_input
    output_cost = (output_tokens / 1000) * cost_per_1k_output
    return round(input_cost + output_cost, 6)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate *text* to approximately *max_tokens* tokens."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def compute_prompt_hash(system_prompt: str, user_prompt: str) -> str:
    """Deterministic hash for cache keying."""
    combined = f"{system_prompt}|||{user_prompt}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]


def extract_template_variables_used(
    template: str, variables: Dict[str, Any],
) -> Dict[str, Any]:
    """Return only the variables that are actually referenced in *template*."""
    required = extract_variables(template)
    return {k: variables[k] for k in required if k in variables}
