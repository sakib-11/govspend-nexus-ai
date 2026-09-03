"""Redis cache for approval-velocity statistics and analysis results."""

import json
from typing import Any, Dict, Optional

from ..config import settings
from ..models.approval_velocity import HistoricalApprovalStats
from ..utils.logging import get_logger

logger = get_logger(__name__)


class VelocityCache:
    """Cache layer for approval-velocity detection.

    Key-space
    ---------
    * ``velocity:stats:<cat>:<dept>``   – historical statistics (7-day TTL)
    * ``velocity:analysis:<tx_id>``     – per-transaction result (24-hour TTL)
    """

    STATS_PREFIX = "velocity:stats:"
    ANALYSIS_PREFIX = "velocity:analysis:"
    STATS_TTL = 86_400 * 7  # 7 days
    ANALYSIS_TTL = 86_400  # 24 hours

    def __init__(self) -> None:
        import redis.asyncio as _redis

        self.redis_client = _redis.from_url(settings.REDIS_URL)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def cache_stats(
        self,
        category: str,
        department_id: str,
        stats: HistoricalApprovalStats,
    ) -> None:
        try:
            key = f"{self.STATS_PREFIX}{category}:{department_id}"
            await self.redis_client.setex(
                key, self.STATS_TTL, json.dumps(stats.model_dump(mode="json"), default=str)
            )
        except Exception as exc:
            logger.warning("Failed to cache velocity stats: %s", exc)

    async def get_stats(
        self, category: str, department_id: str
    ) -> Optional[HistoricalApprovalStats]:
        try:
            key = f"{self.STATS_PREFIX}{category}:{department_id}"
            data = await self.redis_client.get(key)
            if data:
                return HistoricalApprovalStats(**json.loads(data))
            return None
        except Exception as exc:
            logger.warning("Failed to get velocity stats: %s", exc)
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
                key, self.ANALYSIS_TTL, json.dumps(result, default=str)
            )
        except Exception as exc:
            logger.warning("Failed to cache velocity analysis: %s", exc)

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
            logger.warning("Failed to get cached velocity analysis: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    async def invalidate_stats(self, category: str, department_id: str) -> None:
        try:
            key = f"{self.STATS_PREFIX}{category}:{department_id}"
            await self.redis_client.delete(key)
        except Exception as exc:
            logger.warning("Failed to invalidate velocity stats: %s", exc)
