"""Base LLM client — abstract interface for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from models.explanation import LLMRequest, LLMResponse


class BaseLLMClient(ABC):
    """Abstract base class for LLM API clients."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion from the LLM."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable."""
        ...

    async def close(self) -> None:
        """Release resources (optional override)."""
        pass
