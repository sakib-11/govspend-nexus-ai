"""Redis cache for timing statistics and analysis results."""

import json
from typing import Any, Dict, Optional

from ..config import settings
from ..models.timing import TimingStatistics
from ..utils.logging import get_logger

logger = get_logger(__name__)


class TimingCache:
    """Dedicated cache layer for timing-anomaly detection.

    Key-space:
    * ``timing:stats:<dept>:<period>``  – historical statistics (7-day TTL)
    * ``timing:analysis:<tx_id>``       – per-transaction result (7-day TTL)
    """

    STATS_PREFIX = "timing:stats:"
    ANALYSIS_PREFIX = "timing:analysis:"
    TTL = 86_400 * 7  # 7 days

    def __init__(self) -> None:
        import redis.asyncio as _redis

        self.redis_client = _redis.from_url(settings.REDIS_URL)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def cache_statistics(
        self,
        department_id: str,
        fiscal_period: str,
        stats: TimingStatistics,
    ) -> None:
        try:
            key = f"{self.STATS_PREFIX}{department_id}:{fiscal_period}"
            await self.redis_client.setex(
                key, self.TTL, json.dumps(stats.model_dump(mode="json"), default=str)
            )
        except Exception as exc:
            logger.warning("Failed to cache timing stats: %s", exc)

    async def get_statistics(
        self, department_id: str, fiscal_period: str
    ) -> Optional[TimingStatistics]:
        try:
            key = f"{self.STATS_PREFIX}{department_id}:{fiscal_period}"
            data = await self.redis_client.get(key)
            if data:
                return TimingStatistics(**json.loads(data))
            return None
        except Exception as exc:
            logger.warning("Failed to get cached timing stats: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Analysis results
    # ------------------------------------------------------------------

    async def cache_analysis(
        self, transaction_id: str, result: Dict[str, Any]
    ) -> None:
        try:
            key = f"{self.ANALYSIS_PREFIX}{transaction_id}"
            await self.redis_client.setex(
                key, self.TTL, json.dumps(result, default=str)
            )
        except Exception as exc:
            logger.warning("Failed to cache timing analysis: %s", exc)

    async def get_analysis(
        self, transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            key = f"{self.ANALYSIS_PREFIX}{transaction_id}"
            data = await self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as exc:
            logger.warning("Failed to get cached timing analysis: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    async def invalidate_statistics(
        self, department_id: str, fiscal_period: str
    ) -> None:
        try:
            key = f"{self.STATS_PREFIX}{department_id}:{fiscal_period}"
            await self.redis_client.delete(key)
        except Exception as exc:
            logger.warning("Failed to invalidate timing stats: %s", exc)
