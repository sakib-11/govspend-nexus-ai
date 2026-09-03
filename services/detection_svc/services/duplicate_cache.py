"""Redis cache for duplicate detection hash checks and result storage."""

import json
from typing import Any, Dict, Optional

from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DuplicateCache:
    """Dedicated cache layer for duplicate/fuzzy detection.

    Uses the same Redis instance as the rest of the detection service but
    manages its own key-space and TTLs:

    * ``dup:hash:<hash>`` – boolean hash-duplicate existence (7-day TTL)
    * ``dup:result:<tx_id>`` – full detection result (1-hour TTL)
    * ``dup:cand:<key>`` – candidate look-ups (1-hour TTL)
    """

    HASH_KEY_PREFIX = "dup:hash:"
    RESULT_KEY_PREFIX = "dup:result:"
    CANDIDATE_KEY_PREFIX = "dup:cand:"

    DEFAULT_TTL = 3600  # 1 hour
    HASH_TTL = 86_400 * 7  # 7 days

    def __init__(self) -> None:
        import redis.asyncio as _redis

        self.redis_client = _redis.from_url(settings.REDIS_URL)

    # ------------------------------------------------------------------
    # Hash-duplicate cache
    # ------------------------------------------------------------------

    async def get_hash_duplicate(self, invoice_hash: str) -> Optional[bool]:
        """Return ``True/False`` if cached, ``None`` if absent."""
        try:
            key = f"{self.HASH_KEY_PREFIX}{invoice_hash}"
            value = await self.redis_client.get(key)
            if value is not None:
                return json.loads(value) == "true"
            return None
        except Exception as exc:
            logger.warning("Cache hash-duplicate GET failed: %s", exc)
            return None

    async def cache_hash_duplicate(self, invoice_hash: str, exists: bool) -> None:
        """Persist the existence check result."""
        try:
            key = f"{self.HASH_KEY_PREFIX}{invoice_hash}"
            await self.redis_client.setex(
                key, self.HASH_TTL, "true" if exists else "false"
            )
        except Exception as exc:
            logger.warning("Cache hash-duplicate SET failed: %s", exc)

    # ------------------------------------------------------------------
    # Detection-result cache
    # ------------------------------------------------------------------

    async def cache_result(
        self, transaction_id: str, result: Dict[str, Any]
    ) -> None:
        """Cache a complete detection result keyed by transaction id."""
        try:
            key = f"{self.RESULT_KEY_PREFIX}{transaction_id}"
            await self.redis_client.setex(
                key, self.DEFAULT_TTL, json.dumps(result, default=str)
            )
        except Exception as exc:
            logger.warning("Cache result SET failed: %s", exc)

    async def get_result(
        self, transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a cached detection result."""
        try:
            key = f"{self.RESULT_KEY_PREFIX}{transaction_id}"
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as exc:
            logger.warning("Cache result GET failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Candidate cache
    # ------------------------------------------------------------------

    async def cache_candidate(
        self,
        key: str,
        candidate_data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> None:
        """Cache a fuzzy-match candidate."""
        try:
            ttl = ttl or self.DEFAULT_TTL
            await self.redis_client.setex(
                f"{self.CANDIDATE_KEY_PREFIX}{key}",
                ttl,
                json.dumps(candidate_data, default=str),
            )
        except Exception as exc:
            logger.warning("Cache candidate SET failed: %s", exc)

    async def get_candidate(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached candidate."""
        try:
            value = await self.redis_client.get(f"{self.CANDIDATE_KEY_PREFIX}{key}")
            if value:
                return json.loads(value)
            return None
        except Exception as exc:
            logger.warning("Cache candidate GET failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    async def invalidate_for_transaction(self, transaction_id: str) -> None:
        """Remove all cache entries associated with *transaction_id*."""
        try:
            await self.redis_client.delete(
                f"{self.RESULT_KEY_PREFIX}{transaction_id}"
            )
            logger.info("Invalidated cache for %s", transaction_id)
        except Exception as exc:
            logger.warning("Cache invalidation failed: %s", exc)
