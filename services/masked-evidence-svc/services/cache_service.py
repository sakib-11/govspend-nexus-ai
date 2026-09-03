"""Cache service — Redis-backed caching with fallback to in-memory store."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CacheService:
    """Redis-backed cache with an in-memory fallback.

    When Redis is unavailable the service degrades gracefully to an in-memory
    dictionary so masking operations remain functional.
    """

    def __init__(self, redis_client=None, *, default_ttl: int = 3600) -> None:
        self._redis = redis_client
        self._default_ttl = default_ttl
        # Fallback in-memory store
        self._memory: dict[str, tuple[str, float]] = {}
        self._redis_available = redis_client is not None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value by *key*."""
        # Try Redis first
        if self._redis_available:
            try:
                raw = await self._redis.get(key)
                if raw is not None:
                    return json.loads(raw)
            except Exception:
                logger.warning("Redis GET failed for key %s — falling back", key)
                self._redis_available = False

        # Fallback to in-memory
        import time

        entry = self._memory.get(key)
        if entry is not None:
            value, expires = entry
            if expires > time.time():
                return json.loads(value)
            # Expired
            del self._memory[key]
        return None

    async def set(self, key: str, value: Any, *, ttl: Optional[int] = None) -> None:
        """Store *value* under *key* with an optional TTL override."""
        ttl = ttl or self._default_ttl
        serialised = json.dumps(value, default=str)

        # Try Redis
        if self._redis_available:
            try:
                await self._redis.setex(key, ttl, serialised)
                return
            except Exception:
                logger.warning("Redis SET failed for key %s — falling back", key)
                self._redis_available = False

        # Fallback to in-memory
        import time

        self._memory[key] = (serialised, time.time() + ttl)

    async def delete(self, key: str) -> None:
        """Remove *key* from the cache."""
        if self._redis_available:
            try:
                await self._redis.delete(key)
            except Exception:
                self._redis_available = False
        self._memory.pop(key, None)

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching *pattern* (prefix match).

        Returns the number of keys removed.
        """
        count = 0
        if self._redis_available:
            try:
                keys = []
                async for k in self._redis.scan_iter(match=pattern):
                    keys.append(k)
                if keys:
                    count = await self._redis.delete(*keys)
                return count
            except Exception:
                self._redis_available = False

        # Fallback: prefix match on in-memory keys
        to_delete = [k for k in self._memory if k.startswith(pattern.replace("*", ""))]
        for k in to_delete:
            del self._memory[k]
            count += 1
        return count

    def get_stats(self) -> dict:
        """Return cache statistics."""
        return {
            "backend": "redis" if self._redis_available else "memory",
            "memory_keys": len(self._memory),
            "redis_available": self._redis_available,
        }
