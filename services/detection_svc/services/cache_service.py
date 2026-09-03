"""Redis cache service for detection data."""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import redis.asyncio as redis
from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class CacheService:
    """Redis cache service for detection data."""

    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.default_ttl = settings.CACHE_TTL_SECONDS

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache with TTL."""
        try:
            serialized = json.dumps(value, default=str)
            ttl = ttl or self.default_ttl
            await self.redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Cache exists check failed for {key}: {e}")
            return False

    def generate_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_parts = []
        for arg in args:
            key_parts.append(str(arg))
        for k, v in kwargs.items():
            key_parts.append(f"{k}:{v}")

        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    async def get_or_compute(
        self,
        key: str,
        compute_func,
        ttl: Optional[int] = None
    ) -> Any:
        """Get from cache or compute if not found."""
        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Compute value
        value = await compute_func()

        # Cache the result
        if value is not None:
            await self.set(key, value, ttl)

        return value

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern."""
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache pattern invalidation failed for {pattern}: {e}")
            return 0

    async def health_check(self) -> bool:
        """Check if cache is operational."""
        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return False