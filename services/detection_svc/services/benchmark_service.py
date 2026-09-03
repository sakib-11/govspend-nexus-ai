"""Service for managing price benchmarks."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

import asyncpg
from ..models.benchmarks import BenchmarkPrice
from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BenchmarkService:
    """Service for managing price benchmarks."""

    def __init__(self):
        self.db_pool = None
        self.cache_ttl = settings.CACHE_TTL_SECONDS

    async def _get_db_pool(self):
        if not self.db_pool:
            try:
                self.db_pool = await asyncpg.create_pool(
                    settings.DATABASE_URL,
                    min_size=5,
                    max_size=20
                )
            except Exception as e:
                logger.warning(f"Database connection failed: {e}")
                self.db_pool = None
        return self.db_pool

    async def save_benchmark(
        self,
        category: str,
        region: str,
        quantity_band: str,
        benchmark_price: float,
        upper_fence: float,
        lower_fence: float,
        sample_count: int,
        sample_std: Optional[float],
        confidence: float
    ) -> BenchmarkPrice:
        """Save or update benchmark price."""
        try:
            pool = await self._get_db_pool()

            if pool:
                async with pool.acquire() as conn:
                    # Check if benchmark exists
                    existing = await conn.fetchrow(
                        """
                        SELECT id FROM benchmarks
                        WHERE category = $1 AND region = $2 AND quantity_band = $3
                        """,
                        category, region, quantity_band
                    )

                    benchmark_id = existing['id'] if existing else str(uuid.uuid4())

                    # Upsert benchmark
                    await conn.execute(
                        """
                        INSERT INTO benchmarks (
                            id, category, region, quantity_band,
                            benchmark_price, upper_fence, lower_fence,
                            sample_count, sample_std, confidence,
                            computed_at, last_updated, is_active
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT (id) DO UPDATE SET
                            benchmark_price = EXCLUDED.benchmark_price,
                            upper_fence = EXCLUDED.upper_fence,
                            lower_fence = EXCLUDED.lower_fence,
                            sample_count = EXCLUDED.sample_count,
                            sample_std = EXCLUDED.sample_std,
                            confidence = EXCLUDED.confidence,
                            last_updated = EXCLUDED.last_updated
                        """,
                        benchmark_id,
                        category,
                        region,
                        quantity_band,
                        benchmark_price,
                        upper_fence,
                        lower_fence,
                        sample_count,
                        sample_std,
                        confidence,
                        datetime.utcnow(),
                        datetime.utcnow(),
                        True
                    )

                    # Return benchmark object
                    return BenchmarkPrice(
                        id=benchmark_id,
                        category=category,
                        region=region,
                        quantity_band=quantity_band,
                        benchmark_price=benchmark_price,
                        upper_fence=upper_fence,
                        lower_fence=lower_fence,
                        sample_count=sample_count,
                        sample_std=sample_std,
                        confidence=confidence,
                        computed_at=datetime.utcnow(),
                        expires_at=datetime.utcnow() + timedelta(seconds=self.cache_ttl)
                    )
            else:
                # Return mock benchmark if DB not available
                return BenchmarkPrice(
                    id=str(uuid.uuid4()),
                    category=category,
                    region=region,
                    quantity_band=quantity_band,
                    benchmark_price=benchmark_price,
                    upper_fence=upper_fence,
                    lower_fence=lower_fence,
                    sample_count=sample_count,
                    sample_std=sample_std,
                    confidence=confidence,
                    computed_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(seconds=self.cache_ttl)
                )

        except Exception as e:
            logger.error(f"Failed to save benchmark: {e}")
            raise

    async def get_benchmark(
        self,
        category: str,
        region: str,
        quantity_band: str
    ) -> Optional[BenchmarkPrice]:
        """Get benchmark from database."""
        try:
            pool = await self._get_db_pool()

            if pool:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        SELECT * FROM benchmarks
                        WHERE
                            category = $1
                            AND region = $2
                            AND quantity_band = $3
                            AND is_active = true
                        """,
                        category, region, quantity_band
                    )

                    if row:
                        return BenchmarkPrice(
                            id=row['id'],
                            category=row['category'],
                            region=row['region'],
                            quantity_band=row['quantity_band'],
                            benchmark_price=float(row['benchmark_price']),
                            upper_fence=float(row['upper_fence']),
                            lower_fence=float(row['lower_fence']),
                            sample_count=row['sample_count'],
                            sample_std=float(row['sample_std']) if row['sample_std'] else None,
                            confidence=float(row['confidence']),
                            computed_at=row['computed_at'],
                            expires_at=row['computed_at'] + timedelta(seconds=self.cache_ttl),
                            last_updated=row['last_updated'],
                            is_active=row['is_active']
                        )

            return None

        except Exception as e:
            logger.error(f"Failed to get benchmark: {e}")
            return None

    async def update_benchmark_stats(self) -> None:
        """Update all benchmarks with latest data (scheduled job)."""
        try:
            pool = await self._get_db_pool()

            if pool:
                async with pool.acquire() as conn:
                    # Update benchmarks for all categories/regions/bands
                    # This would be a complex query to recalculate statistics
                    # Implementation depends on your database schema
                    logger.info("Updating benchmark statistics...")
                    # TODO: Implement bulk update

        except Exception as e:
            logger.error(f"Failed to update benchmark stats: {e}")