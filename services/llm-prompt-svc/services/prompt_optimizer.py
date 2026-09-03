"""Prompt optimizer — improve prompts based on validation feedback."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config import LLMPromptConfig
from models.prompt import ValidationResult

logger = logging.getLogger(__name__)


class PromptOptimizer:
    """Optimise prompts by appending validation-derived instructions."""

    def __init__(self, config: LLMPromptConfig) -> None:
        self.config = config

    def enhance_system_prompt(
        self,
        base_prompt: str,
        validation_result: Optional[ValidationResult] = None,
    ) -> str:
        """Append corrective instructions based on *validation_result*."""
        if validation_result is None or validation_result.is_valid:
            return base_prompt

        additions: List[str] = []

        # Low grounding
        if validation_result.grounding_score < self.config.MIN_GROUNDING_SCORE:
            additions.append(
                "IMPORTANT: Your previous output had a low grounding score. "
                "Ensure EVERY explanation point is directly supported by the "
                "provided evidence. Do not speculate."
            )

        # Missing citations
        if validation_result.missing_evidence:
            ids = ", ".join(validation_result.missing_evidence[:5])
            additions.append(
                f"NOTE: The following evidence IDs were cited but not found in the "
                f"input: {ids}. Only cite evidence that is actually provided."
            )

        # Missing policy references
        if validation_result.missing_policies:
            ids = ", ".join(validation_result.missing_policies[:5])
            additions.append(
                f"NOTE: The following policy references were cited but not found: "
                f"{ids}. Only reference policies that are actually provided."
            )

        # Low citation coverage
        if validation_result.citation_coverage < 0.5:
            additions.append(
                "REMINDER: Each explanation MUST include at least one evidence "
                "citation and one policy reference where applicable."
            )

        # Warnings
        for warning in validation_result.warnings[:3]:
            additions.append(f"WARNING: {warning}")

        if additions:
            base_prompt += "\n\n--- CORRECTION INSTRUCTIONS ---\n" + "\n".join(additions)

        return base_prompt

    def enhance_user_prompt(
        self,
        base_prompt: str,
        max_retries: int = 0,
    ) -> str:
        """Add retry-specific instructions for subsequent attempts."""
        if max_retries == 0:
            return base_prompt

        retry_note = (
            f"\n\n[RETRY ATTEMPT {max_retries}: Please ensure all explanations "
            "are properly grounded in evidence and include valid citations.]"
        )
        return base_prompt + retry_note

    def build_optimized_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        validation_result: Optional[ValidationResult] = None,
        retry_count: int = 0,
    ) -> tuple[str, str]:
        """Return optimised (system, user) prompt pair."""
        optimized_system = self.enhance_system_prompt(system_prompt, validation_result)
        optimized_user = self.enhance_user_prompt(user_prompt, retry_count)
        return optimized_system, optimized_user
