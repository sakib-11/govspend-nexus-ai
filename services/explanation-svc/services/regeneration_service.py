"""Regeneration service — retry explanation generation with improved prompts."""

from __future__ import annotations

import logging
from typing import Optional

from config import ExplanationConfig
from models.explanation import (
    ExplanationRequest,
    ExplanationResponse,
    ExplanationValidationResult,
)
from services.llm_client import LLMClientService
from services.validation_service import ValidationService

logger = logging.getLogger(__name__)


class RegenerationService:
    """Retry explanation generation, feeding validation errors back into the prompt."""

    def __init__(
        self,
        llm_client: LLMClientService,
        validation_service: ValidationService,
        config: ExplanationConfig,
    ) -> None:
        self.llm = llm_client
        self.validator = validation_service
        self.config = config
        self.max_attempts = config.MAX_REGENERATION_ATTEMPTS

    async def regenerate(
        self,
        request: ExplanationRequest,
        previous_response: Optional[ExplanationResponse] = None,
        previous_validation: Optional[ExplanationValidationResult] = None,
    ) -> Optional[ExplanationResponse]:
        """Attempt to regenerate a valid explanation.

        Returns the first valid result, or ``None`` after exhausting retries.
        """
        attempt = 0
        last_resp = previous_response
        last_val = previous_validation

        while attempt < self.max_attempts:
            attempt += 1
            logger.info("Regeneration attempt %d/%d", attempt, self.max_attempts)

            try:
                instructions = self._build_instructions(last_val)
                response = await self.llm.generate_explanation(
                    request, custom_instructions=instructions,
                )

                val = await self.validator.validate(response, request.model_dump())
                if val.is_valid:
                    logger.info("Regeneration succeeded on attempt %d", attempt)
                    return response

                # Permissive mode: accept if no hard errors
                if self.config.VALIDATION_STRICTNESS == "permissive" and not val.errors:
                    return response

                last_resp = response
                last_val = val

            except Exception as exc:
                logger.warning("Regeneration attempt %d failed: %s", attempt, exc)

        logger.warning("Regeneration exhausted after %d attempts", self.max_attempts)
        return None

    def _build_instructions(self, val: Optional[ExplanationValidationResult]) -> Optional[str]:
        if val is None:
            return None
        parts: list[str] = ["CORRECTION INSTRUCTIONS:"]

        if val.errors:
            parts.append("ERRORS TO FIX:")
            for e in val.errors[:5]:
                parts.append(f"  - {e}")

        if val.missing_evidence:
            parts.append(f"CITE these evidence IDs: {', '.join(val.missing_evidence[:5])}")

        if val.missing_policies:
            parts.append(f"REFERENCE these policies: {', '.join(val.missing_policies[:5])}")

        if val.uncited_sentences:
            nums = ", ".join(str(n) for n in val.uncited_sentences[:5])
            parts.append(f"ADD CITATIONS to points: {nums}")

        if val.suggestions:
            parts.append("SUGGESTIONS:")
            for s in val.suggestions[:3]:
                parts.append(f"  - {s}")

        parts.append("")
        parts.append("Regenerate the full JSON response addressing all issues above.")

        return "\n".join(parts)
