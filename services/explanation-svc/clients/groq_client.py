"""Groq API client — fast inference via the Groq API."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional

import httpx

from clients.base_client import BaseLLMClient
from config import ExplanationConfig
from models.explanation import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class GroqClient(BaseLLMClient):
    """Groq API client using the OpenAI-compatible chat completions endpoint."""

    def __init__(self, config: ExplanationConfig) -> None:
        self.config = config
        self.model = config.GROQ_MODEL
        self.base_url = "https://api.groq.com/openai/v1"
        self._client = httpx.AsyncClient(
            timeout=config.TIMEOUT_SECONDS,
            headers={
                "Authorization": f"Bearer {config.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion via the Groq API."""
        start = time.monotonic()

        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature or self.config.GROQ_TEMPERATURE,
            "max_tokens": request.max_tokens or self.config.GROQ_MAX_TOKENS,
            "top_p": request.top_p or self.config.GROQ_TOP_P,
            "response_format": {"type": "json_object"},
        }

        try:
            resp = await self._client.post(f"{self.base_url}/chat/completions", json=payload)
            resp.raise_for_status()
        except httpx.TimeoutException:
            raise TimeoutError("Groq API timed out")
        except httpx.HTTPStatusError as exc:
            logger.error("Groq API %d: %s", exc.response.status_code, exc.response.text[:200])
            raise RuntimeError(f"Groq API error: {exc.response.status_code}") from exc

        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Robust JSON extraction
        content = self._ensure_json(content)

        elapsed_ms = (time.monotonic() - start) * 1000
        return LLMResponse(
            content=content,
            model=self.model,
            provider="groq",
            token_count=data.get("usage", {}).get("total_tokens", 0),
            processing_time_ms=elapsed_ms,
            raw_response=data,
        )

    async def health_check(self) -> bool:
        try:
            resp = await self._client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                },
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _ensure_json(text: str) -> str:
        """Try to parse *text* as JSON; if it fails, extract the first JSON object."""
        try:
            json.loads(text)
            return text
        except (json.JSONDecodeError, TypeError):
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    json.loads(match.group())
                    return match.group()
                except json.JSONDecodeError:
                    pass
        return text
