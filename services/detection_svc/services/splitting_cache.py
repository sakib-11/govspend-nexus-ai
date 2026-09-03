"""Redis cache for contract-splitting analysis results and PO data."""

import json
from typing import Any, Dict, List, Optional

from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SplittingCache:
    """Cache layer for contract-splitting detection.

    Key-space
    ---------
    * ``splitting:<vendor>:<dept>``  – full analysis result (7-day TTL)
    * ``pos:<vendor>:<dept>``       – purchase-order list (1-hour TTL)
    """

    ANALYSIS_PREFIX = "splitting:"
    PO_PREFIX = "pos:"
    LONG_TTL = 86_400 * 7  # 7 days
    SHORT_TTL = 3600  # 1 hour

    def __init__(self) -> None:
        import redis.asyncio as _redis

        self.redis_client = _redis.from_url(settings.REDIS_URL)

    # ------------------------------------------------------------------
    # Analysis results
    # ------------------------------------------------------------------

    async def cache_analysis(
        self, vendor_id: str, department_id: str, result: Dict[str, Any]
    ) -> None:
        try:
            key = f"{self.ANALYSIS_PREFIX}{vendor_id}:{department_id}"
            await self.redis_client.setex(
                key, self.LONG_TTL, json.dumps(result, default=str)
            )
        except Exception as exc:
            logger.warning("Failed to cache splitting analysis: %s", exc)

    async def get_analysis(
        self, vendor_id: str, department_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            key = f"{self.ANALYSIS_PREFIX}{vendor_id}:{department_id}"
            data = await self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as exc:
            logger.warning("Failed to get cached splitting analysis: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Purchase orders
    # ------------------------------------------------------------------

    async def cache_purchase_orders(
        self, vendor_id: str, department_id: str, purchase_orders: List[Dict[str, Any]]
    ) -> None:
        try:
            key = f"{self.PO_PREFIX}{vendor_id}:{department_id}"
            await self.redis_client.setex(
                key, self.SHORT_TTL, json.dumps(purchase_orders, default=str)
            )
        except Exception as exc:
            logger.warning("Failed to cache purchase orders: %s", exc)

    async def get_purchase_orders(
        self, vendor_id: str, department_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        try:
            key = f"{self.PO_PREFIX}{vendor_id}:{department_id}"
            data = await self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as exc:
            logger.warning("Failed to get cached purchase orders: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    async def invalidate(self, vendor_id: str, department_id: str) -> None:
        try:
            keys = [
                f"{self.ANALYSIS_PREFIX}{vendor_id}:{department_id}",
                f"{self.PO_PREFIX}{vendor_id}:{department_id}",
            ]
            await self.redis_client.delete(*keys)
        except Exception as exc:
            logger.warning("Failed to invalidate cache: %s", exc)
