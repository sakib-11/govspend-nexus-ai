"""Template service — manage, store, and render prompt templates."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config import LLMPromptConfig
from models.prompt import PromptTemplate, PromptType
from templates.few_shot_examples import format_few_shot_for_prompt, get_few_shot_examples
from templates.system_prompts import get_system_prompt, list_styles as system_styles
from templates.user_prompts import get_user_prompt, list_styles as user_styles
from utils.template_utils import (
    count_tokens_approx,
    extract_variables,
    render_template,
)

logger = logging.getLogger(__name__)


class TemplateService:
    """Manage prompt templates — selection, rendering, and listing."""

    def __init__(self, config: LLMPromptConfig) -> None:
        self.config = config

    def get_system_prompt(
        self,
        risk_tier: str = "LOW",
        custom_instructions: Optional[str] = None,
    ) -> str:
        """Select and optionally augment the system prompt based on risk tier."""
        style_map = {
            "HIGH": "fraud_focus",
            "BORDERLINE": "regulatory_focus",
            "LOW": "default",
        }
        style = style_map.get(risk_tier, "default")
        prompt = get_system_prompt(style)

        if custom_instructions:
            prompt += f"\n\nADDITIONAL INSTRUCTIONS:\n{custom_instructions}"

        return prompt

    def get_user_prompt(
        self,
        context: Dict[str, Any],
        risk_tier: str = "LOW",
    ) -> str:
        """Select and render the user prompt template."""
        style = "case_focused" if risk_tier in ("HIGH", "BORDERLINE") else "default"
        template = get_user_prompt(style)
        return render_template(template, context)

    def get_few_shot_section(self, count: int = 2) -> str:
        """Render few-shot examples for inclusion in the system prompt."""
        examples = get_few_shot_examples(count)
        return format_few_shot_for_prompt(examples)

    def render_template(
        self,
        template_str: str,
        variables: Dict[str, Any],
    ) -> str:
        """Render an arbitrary template string."""
        return render_template(template_str, variables)

    def get_template_variables(self, template_str: str) -> List[str]:
        """List variable names in a template."""
        return extract_variables(template_str)

    def list_available_styles(self) -> Dict[str, List[str]]:
        """Return available system and user prompt styles."""
        return {
            "system": system_styles(),
            "user": user_styles(),
        }

    def build_prompt_metadata(
        self,
        system_prompt: str,
        user_prompt: str,
        template_name: str,
        variables_used: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build metadata dict for a generated prompt."""
        return {
            "system_tokens": count_tokens_approx(system_prompt),
            "user_tokens": count_tokens_approx(user_prompt),
            "total_tokens": count_tokens_approx(system_prompt + user_prompt),
            "template_name": template_name,
            "variables_count": len(variables_used),
        }
