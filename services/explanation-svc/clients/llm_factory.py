"""LLM factory — create and manage LLM client instances."""

from __future__ import annotations

import logging
from typing import Optional

from clients.base_client import BaseLLMClient
from clients.groq_client import GroqClient
from clients.openai_client import OpenAIClient
from config import ExplanationConfig

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM clients based on provider configuration."""

    @staticmethod
    def create_client(provider: str, config: ExplanationConfig) -> Optional[BaseLLMClient]:
        """Create an LLM client for *provider*."""
        if provider == "groq":
            if not config.GROQ_API_KEY:
                logger.warning("Groq API key not configured")
                return None
            return GroqClient(config)
        if provider == "openai":
            if not config.OPENAI_API_KEY:
                logger.warning("OpenAI API key not configured")
                return None
            return OpenAIClient(config)
        logger.error("Unsupported LLM provider: %s", provider)
        return None

    @staticmethod
    def get_primary_client(config: ExplanationConfig) -> Optional[BaseLLMClient]:
        """Return the primary LLM client."""
        return LLMFactory.create_client(config.LLM_PROVIDER, config)

    @staticmethod
    def get_fallback_client(config: ExplanationConfig) -> Optional[BaseLLMClient]:
        """Return the fallback LLM client (the *other* provider)."""
        fallback = "openai" if config.LLM_PROVIDER != "openai" else "groq"
        return LLMFactory.create_client(fallback, config)
