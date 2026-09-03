"""OpenAI API client — fallback LLM provider."""

from __future__ import annotations

import json
import logging
import time

import httpx

from clients.base_client import BaseLLMClient
from config import ExplanationConfig
from models.explanation import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """OpenAI-compatible chat completions client."""

    def __init__(self, config: ExplanationConfig) -> None:
        self.config = config
        self.model = config.OPENAI_MODEL
        self.base_url = "https://api.openai.com/v1"
        self._client = httpx.AsyncClient(
            timeout=config.TIMEOUT_SECONDS,
            headers={
                "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion via the OpenAI API."""
        start = time.monotonic()

        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature or self.config.OPENAI_TEMPERATURE,
            "max_tokens": request.max_tokens or self.config.OPENAI_MAX_TOKENS,
            "top_p": request.top_p or 0.9,
            "response_format": {"type": "json_object"},
        }

        try:
            resp = await self._client.post(f"{self.base_url}/chat/completions", json=payload)
            resp.raise_for_status()
        except httpx.TimeoutException:
            raise TimeoutError("OpenAI API timed out")
        except httpx.HTTPStatusError as exc:
            logger.error("OpenAI API %d: %s", exc.response.status_code, exc.response.text[:200])
            raise RuntimeError(f"OpenAI API error: {exc.response.status_code}") from exc

        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        elapsed_ms = (time.monotonic() - start) * 1000
        return LLMResponse(
            content=content,
            model=self.model,
            provider="openai",
            token_count=data.get("usage", {}).get("total_tokens", 0),
            processing_time_ms=elapsed_ms,
            raw_response=data,
        )

    async def health_check(self) -> bool:
        try:
            resp = await self._client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                },
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()
