"""Prompt service — main orchestrator for prompt generation and validation."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import LLMPromptConfig
from models.prompt import (
    LLMInput,
    LLMOutput,
    PromptRequest,
    PromptResponse,
    ValidationResult,
)
from services.context_builder import ContextBuilder
from services.prompt_optimizer import PromptOptimizer
from services.schema_validator import SchemaValidator
from services.template_service import TemplateService
from utils.template_utils import count_tokens_approx, estimate_cost

logger = logging.getLogger(__name__)


class PromptService:
    """Orchestrate prompt generation, validation, and optimisation."""

    def __init__(self, config: LLMPromptConfig) -> None:
        self.config = config
        self.context_builder = ContextBuilder(config)
        self.template_service = TemplateService(config)
        self.schema_validator = SchemaValidator()
        self.optimizer = PromptOptimizer(config)

    # ------------------------------------------------------------------
    # Generate prompt
    # ------------------------------------------------------------------

    async def generate_prompt(self, request: PromptRequest) -> PromptResponse:
        """Generate system + user prompts from structured input."""

        # 1. Build context from LLM input
        context = self.context_builder.build_context(request.llm_input)

        # 2. Select and render system prompt
        system_prompt = self.template_service.get_system_prompt(
            risk_tier=request.llm_input.risk_tier.value,
            custom_instructions=request.custom_instructions,
        )

        # 3. Select and render user prompt
        user_prompt = self.template_service.get_user_prompt(
            context=context,
            risk_tier=request.llm_input.risk_tier.value,
        )

        # 4. Optionally prepend few-shot examples
        if request.include_few_shot:
            few_shot = self.template_service.get_few_shot_section(2)
            system_prompt = f"{system_prompt}\n\nFEW-SHOT EXAMPLES:\n{few_shot}"

        # 5. Token counting and cost estimation
        total_text = f"{system_prompt}\n\n{user_prompt}"
        token_count = count_tokens_approx(total_text)
        estimated_cost = estimate_cost(
            token_count,
            self.config.LLM_MAX_TOKENS,
            self.config.COST_PER_1K_INPUT_TOKENS,
            self.config.COST_PER_1K_OUTPUT_TOKENS,
        )

        template_name = request.template_name or (
            "fraud_focus" if request.llm_input.risk_tier.value == "HIGH" else "default"
        )

        return PromptResponse(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            token_count=token_count,
            estimated_cost=estimated_cost,
            template_used=template_name,
            variables_used=context,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate_input(self, input_data: Dict[str, Any]) -> ValidationResult:
        """Validate LLM input data."""
        return self.schema_validator.validate_input(input_data)

    async def validate_output(
        self,
        output_data: Dict[str, Any],
        input_data: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Validate LLM output data with optional grounding check."""
        return self.schema_validator.validate_output(output_data, input_data)

    # ------------------------------------------------------------------
    # Format output
    # ------------------------------------------------------------------

    async def format_output(self, llm_response: Dict[str, Any]) -> LLMOutput:
        """Parse raw LLM JSON into a validated LLMOutput."""
        return LLMOutput(**llm_response)

    # ------------------------------------------------------------------
    # Optimisation loop
    # ------------------------------------------------------------------

    async def generate_with_validation(
        self,
        request: PromptRequest,
        llm_output_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a prompt, optionally validate an output, and optimise.

        Returns a dict with prompt, validation, and optimised prompt info.
        """
        prompt_response = await self.generate_prompt(request)

        validation: Optional[ValidationResult] = None
        if llm_output_data is not None:
            input_dict = request.llm_input.model_dump(mode="json")
            validation = await self.validate_output(llm_output_data, input_dict)

        # Optimise if validation failed
        optimized_system = prompt_response.system_prompt
        optimized_user = prompt_response.user_prompt
        retry_count = 0

        if validation and not validation.is_valid and retry_count < self.config.VALIDATION_RETRY_COUNT:
            optimized_system, optimized_user = self.optimizer.build_optimized_prompt(
                prompt_response.system_prompt,
                prompt_response.user_prompt,
                validation,
                retry_count,
            )
            retry_count += 1

        return {
            "prompt": prompt_response.model_dump(mode="json"),
            "validation": validation.model_dump(mode="json") if validation else None,
            "optimized": {
                "system_prompt": optimized_system,
                "user_prompt": optimized_user,
                "retries_applied": retry_count,
            },
        }

    # ------------------------------------------------------------------
    # Template listing
    # ------------------------------------------------------------------

    def get_available_templates(self) -> Dict[str, Any]:
        """Return metadata about available templates."""
        styles = self.template_service.list_available_styles()
        return {
            "system_styles": styles.get("system", []),
            "user_styles": styles.get("user", []),
            "few_shot_count": 2,
        }
