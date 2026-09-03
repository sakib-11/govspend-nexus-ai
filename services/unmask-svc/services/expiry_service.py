"""Expiry service — background job that auto-expires stale unmask requests."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from config import UnmaskConfig
from models.unmask import UnmaskAction, UnmaskStatus

logger = logging.getLogger(__name__)


class ExpiryService:
    """Periodically expires stale unmask requests.

    Runs as a background asyncio task inside the FastAPI lifespan.
    """

    def __init__(self, db_pool, audit_service, config: UnmaskConfig) -> None:
        self.db_pool = db_pool
        self.audit_service = audit_service
        self.config = config
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background expiry loop."""
        if self._is_running:
            return
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Expiry service started (interval=%d min)",
            self.config.EXPIRY_CHECK_INTERVAL_MINUTES,
        )

    async def stop(self) -> None:
        """Stop the background expiry loop."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Expiry service stopped")

    async def _run_loop(self) -> None:
        """Main loop — process expired requests on each interval."""
        while self._is_running:
            try:
                await self._process_expired_requests()
            except Exception:
                logger.exception("Error processing expired requests")
            await asyncio.sleep(self.config.EXPIRY_CHECK_INTERVAL_MINUTES * 60)

    async def _process_expired_requests(self) -> int:
        """Find and expire overdue requests.  Returns count expired."""
        now = datetime.now(timezone.utc)
        expired_count = 0

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT request_id FROM unmask_requests
                WHERE status IN ('pending', 'approved', 'unmasked')
                  AND expired_at IS NOT NULL
                  AND expired_at < $1
                """,
                now,
            )

            for row in rows:
                request_id = row["request_id"]

                # Determine current status for audit
                status_row = await conn.fetchrow(
                    "SELECT status FROM unmask_requests WHERE request_id = $1",
                    request_id,
                )
                current_status = (
                    UnmaskStatus(status_row["status"]) if status_row else UnmaskStatus.PENDING
                )

                await conn.execute(
                    """
                    UPDATE unmask_requests
                    SET status = $1, updated_at = NOW()
                    WHERE request_id = $2
                    """,
                    UnmaskStatus.EXPIRED.value,
                    str(request_id),
                )

                await self.audit_service.log_audit(
                    request_id=request_id,
                    action=UnmaskAction.EXPIRE.value,
                    user_id="system",
                    from_status=current_status,
                    to_status=UnmaskStatus.EXPIRED,
                    details={"reason": "auto_expired", "trigger": "expiry_service"},
                )
                expired_count += 1
                logger.info("Auto-expired request %s", request_id)

        # Clean up stale rate-limit rows
        if expired_count > 0:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    DELETE FROM unmask_rate_limit
                    WHERE window_start < NOW() - INTERVAL '1 day'
                    """
                )

        return expired_count
