"""Cache service — Redis-backed explanation cache with in-memory fallback."""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from config import ExplanationConfig
from models.explanation import ExplanationResponse

logger = logging.getLogger(__name__)


class CacheService:
    """Cache explanation responses. Uses Redis when available, otherwise in-memory."""

    def __init__(self, redis_client=None, config: Optional[ExplanationConfig] = None) -> None:
        self._redis = redis_client
        self.config = config or ExplanationConfig()
        self._memory: dict[str, tuple[str, float]] = {}
        self._redis_ok = redis_client is not None

    async def get(self, case_id: str) -> Optional[ExplanationResponse]:
        key = f"explanation:{case_id}"

        # Try Redis
        if self._redis_ok:
            try:
                raw = await self._redis.get(key)
                if raw is not None:
                    return ExplanationResponse(**json.loads(raw))
            except Exception:
                logger.debug("Redis GET failed for %s", key)
                self._redis_ok = False

        # In-memory fallback
        entry = self._memory.get(key)
        if entry is not None:
            data, expires = entry
            if expires > time.time():
                return ExplanationResponse(**json.loads(data))
            del self._memory[key]
        return None

    async def set(self, case_id: str, response: ExplanationResponse) -> None:
        key = f"explanation:{case_id}"
        serialised = json.dumps(response.model_dump(mode="json"), default=str)

        if self._redis_ok:
            try:
                await self._redis.setex(key, self.config.CACHE_TTL_SECONDS, serialised)
                return
            except Exception:
                logger.debug("Redis SET failed for %s", key)
                self._redis_ok = False

        self._memory[key] = (serialised, time.time() + self.config.CACHE_TTL_SECONDS)

    async def delete(self, case_id: str) -> None:
        key = f"explanation:{case_id}"
        if self._redis_ok:
            try:
                await self._redis.delete(key)
            except Exception:
                self._redis_ok = False
        self._memory.pop(key, None)

    def get_stats(self) -> dict:
        return {
            "backend": "redis" if self._redis_ok else "memory",
            "memory_keys": len(self._memory),
        }
