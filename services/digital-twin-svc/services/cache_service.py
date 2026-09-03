"""Cache service — Redis-backed with in-memory fallback for graph query caching."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CacheService:
    """Two-tier cache: Redis primary, in-memory fallback."""

    def __init__(
        self,
        redis_client: Any = None,
        ttl_seconds: int = 300,
        enabled: bool = True,
    ):
        self.redis = redis_client
        self.ttl = ttl_seconds
        self.enabled = enabled
        self._local_cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _make_key(*parts: str) -> str:
        """Build a deterministic cache key from string parts."""
        raw = ":".join(parts)
        return f"graph:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

    @staticmethod
    def _serialize(data: Any) -> str:
        """Serialize to JSON string."""
        if isinstance(data, str):
            return data
        return json.dumps(data, default=str)

    @staticmethod
    def _deserialize(raw: str) -> Any:
        """Deserialize from JSON string."""
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve from cache (Redis → in-memory)."""
        if not self.enabled:
            return None

        # Try Redis first
        if self.redis is not None:
            try:
                raw = await self.redis.get(key)
                if raw is not None:
                    return self._deserialize(raw)
            except Exception as e:
                logger.warning(f"Redis GET failed for {key}: {e}")

        # Fall back to in-memory
        entry = self._local_cache.get(key)
        if entry and entry["expires"] > time.time():
            return entry["data"]
        elif entry:
            del self._local_cache[key]

        return None

    async def set(self, key: str, data: Dict[str, Any]) -> None:
        """Store in cache (both tiers)."""
        if not self.enabled:
            return

        serialized = self._serialize(data)

        # Store in Redis
        if self.redis is not None:
            try:
                await self.redis.setex(key, self.ttl, serialized)
            except Exception as e:
                logger.warning(f"Redis SET failed for {key}: {e}")

        # Store in-memory
        self._local_cache[key] = {
            "data": data,
            "expires": time.time() + self.ttl,
        }

    async def invalidate(self, key: str) -> None:
        """Remove from both cache tiers."""
        if self.redis is not None:
            try:
                await self.redis.delete(key)
            except Exception as e:
                logger.warning(f"Redis DELETE failed for {key}: {e}")

        self._local_cache.pop(key, None)

    async def clear_all(self) -> int:
        """Clear all local cache entries. Returns count cleared."""
        count = len(self._local_cache)
        self._local_cache.clear()

        if self.redis is not None:
            try:
                keys = await self.redis.keys("graph:*")
                if keys:
                    await self.redis.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis CLEAR failed: {e}")

        return count

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        now = time.time()
        active = sum(1 for v in self._local_cache.values() if v["expires"] > now)
        expired = sum(1 for v in self._local_cache.values() if v["expires"] <= now)

        return {
            "total_entries": len(self._local_cache),
            "active_entries": active,
            "expired_entries": expired,
            "redis_connected": self.redis is not None,
            "enabled": self.enabled,
        }
