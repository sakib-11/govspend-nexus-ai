"""Database connection pool — thin wrapper around asyncpg with retry."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Lazy import so the module can be imported without asyncpg at module-load time.
_pool: Any = None


class DatabasePool:
    """Singleton async PostgreSQL connection pool."""

    def __init__(self) -> None:
        self._pool: Any = None

    async def initialise(
        self,
        *,
        dsn: Optional[str] = None,
        min_size: int = 5,
        max_size: int = 20,
    ) -> None:
        if self._pool is not None:
            return
        import asyncpg  # type: ignore[import-untyped]

        dsn = dsn or os.getenv(
            "DATABASE_URL", "postgresql://govspend:govspend@localhost:5432/govspend"
        )
        self._pool = await asyncpg.create_pool(
            dsn, min_size=min_size, max_size=max_size
        )
        logger.info("Database pool initialised (%s)", dsn.split("@")[-1])

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("Database pool closed")

    @property
    def pool(self) -> Any:
        if self._pool is None:
            raise RuntimeError("DatabasePool not initialised — call initialise() first")
        return self._pool

    async def execute(self, query: str, *args: Any) -> str:
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list:
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any):  # type: ignore[no-untyped-def]
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any):  # type: ignore[no-untyped-def]
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)


# Module-level singleton
_db_pool: Optional[DatabasePool] = None


async def get_db_pool() -> DatabasePool:
    """Get or create the global database pool."""
    global _db_pool
    if _db_pool is None:
        _db_pool = DatabasePool()
        await _db_pool.initialise()
    return _db_pool


async def close_db_pool() -> None:
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None
