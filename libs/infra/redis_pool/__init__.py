"""Redis connection pool and stream helpers."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_pool: Any = None


class RedisPool:
    """Thin async wrapper around redis-py."""

    def __init__(self) -> None:
        self._client: Any = None

    async def initialise(
        self,
        *,
        url: Optional[str] = None,
        decode_responses: bool = True,
    ) -> None:
        if self._client is not None:
            return
        import redis.asyncio as aioredis  # type: ignore[import-untyped]

        url = url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._client = aioredis.from_url(url, decode_responses=decode_responses)
        logger.info("Redis pool initialised (%s)", url)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Redis pool closed")

    @property
    def client(self) -> Any:
        if self._client is None:
            raise RuntimeError("RedisPool not initialised")
        return self._client

    # ------------------------------------------------------------------
    # Stream helpers
    # ------------------------------------------------------------------

    async def xadd(self, stream: str, data: Dict[str, Any], **kwargs: Any) -> Any:
        serialised = {k: json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v) for k, v in data.items()}
        return await self.client.xadd(stream, serialised, **kwargs)

    async def xread(
        self,
        streams: Dict[str, str],
        count: int = 100,
        block: int = 0,
    ) -> List:
        return await self.client.xread(streams, count=count, block=block)

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        return await self.client.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        await self.client.set(key, value, ex=ex)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    async def publish(self, channel: str, message: str) -> None:
        await self.client.publish(channel, message)


_redis: Optional[RedisPool] = None


async def get_redis_pool() -> RedisPool:
    global _redis
    if _redis is None:
        _redis = RedisPool()
        await _redis.initialise()
    return _redis


async def close_redis_pool() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
