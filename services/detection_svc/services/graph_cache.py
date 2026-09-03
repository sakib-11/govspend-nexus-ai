"""Stub cache service for vendor graph data."""

from typing import Any, Dict, Optional

from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class GraphCache:
    """Minimal cache for vendor-graph detection results.

    Provides the same interface expected by ``VendorGraphRiskDetector``
    without requiring a full Redis dependency at import time.
    """

    PREFIX = "graph:"
    TTL = 86_400  # 1 day

    def __init__(self) -> None:
        self.redis_client = None
        try:
            import redis.asyncio as _redis

            self.redis_client = _redis.from_url(settings.REDIS_URL)
        except Exception as exc:
            logger.warning("GraphCache: Redis unavailable (%s), cache disabled", exc)

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        if not self.redis_client:
            return None
        try:
            import json

            data = await self.redis_client.get(f"{self.PREFIX}{key}")
            return json.loads(data) if data else None
        except Exception as exc:
            logger.warning("GraphCache GET failed: %s", exc)
            return None

    async def set(self, key: str, value: Dict[str, Any]) -> None:
        if not self.redis_client:
            return
        try:
            import json

            await self.redis_client.setex(
                f"{self.PREFIX}{key}",
                self.TTL,
                json.dumps(value, default=str),
            )
        except Exception as exc:
            logger.warning("GraphCache SET failed: %s", exc)
