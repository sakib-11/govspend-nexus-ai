"""Service for querying historical peer transactions."""

import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import redis.asyncio as redis
from ..models.price_deviation import PeerTransaction
from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PeerQueryService:
    """Service for querying historical peer transactions."""

    def __init__(self):
        self.redis_client = None
        self.db_pool = None
        self._init_connections()

    def _init_connections(self) -> None:
        """Initialize database connections."""
        # Redis for caching
        self.redis_client = redis.from_url(settings.REDIS_URL)

        # PostgreSQL for transaction data
        # Will be initialized lazily

    async def _get_db_pool(self):
        """Get or create database connection pool."""
        if not self.db_pool:
            try:
                import asyncpg
                self.db_pool = await asyncpg.create_pool(
                    settings.DATABASE_URL,
                    min_size=5,
                    max_size=20
                )
            except Exception as e:
                logger.warning(f"Database connection failed, using mock data: {e}")
                self.db_pool = None
        return self.db_pool

    async def query_peers(
        self,
        category: str,
        region: str,
        quantity_band: str,
        lookback_days: int = 90,
        limit: int = 1000
    ) -> List[PeerTransaction]:
        """
        Query historical peer transactions.
        """
        try:
            # Check cache first
            cache_key = f"peer_query:{category}:{region}:{quantity_band}:{lookback_days}"
            cached_result = await self.redis_client.get(cache_key)

            if cached_result:
                data = json.loads(cached_result)
                return [PeerTransaction(**item) for item in data]

            # Query database
            pool = await self._get_db_pool()

            if pool:
                async with pool.acquire() as conn:
                    # Build quantity filter
                    quantity_filter = self._build_quantity_filter(quantity_band)

                    query = f"""
                        SELECT
                            transaction_id,
                            vendor_id,
                            category,
                            subcategory,
                            region,
                            quantity,
                            unit_price,
                            total_amount,
                            transaction_date,
                            document_number
                        FROM transactions
                        WHERE
                            category = $1
                            AND region = $2
                            {quantity_filter}
                            AND transaction_date >= NOW() - INTERVAL '{lookback_days} days'
                            AND unit_price > 0
                            AND status = 'completed'
                            AND is_verified = true
                        ORDER BY transaction_date DESC
                        LIMIT {limit}
                    """

                    rows = await conn.fetch(query, category, region)

                    peers = []
                    for row in rows:
                        peer = PeerTransaction(
                            transaction_id=row['transaction_id'],
                            vendor_id=row['vendor_id'],
                            category=row['category'],
                            subcategory=row.get('subcategory'),
                            region=row['region'],
                            quantity=float(row['quantity']),
                            unit_price=float(row['unit_price']),
                            total_amount=float(row['total_amount']),
                            transaction_date=row['transaction_date'],
                            document_number=row.get('document_number')
                        )
                        # Set derived fields
                        peer.quantity_band = quantity_band
                        peers.append(peer)

                    # Cache result
                    cache_data = json.dumps([p.model_dump() for p in peers])
                    await self.redis_client.setex(
                        cache_key,
                        settings.CACHE_TTL_SECONDS,
                        cache_data
                    )

                    logger.info(f"Found {len(peers)} peer transactions for {category}/{region}")
                    return peers
            else:
                # Return mock data for testing
                logger.info("Database not available, returning mock peer data")
                return self._get_mock_peers(category, region, quantity_band)

        except Exception as e:
            logger.error(f"Peer query failed: {e}", exc_info=True)
            # Return mock data as fallback
            return self._get_mock_peers(category, region, quantity_band)

    def _build_quantity_filter(self, quantity_band: str) -> str:
        """Build SQL filter for quantity band."""
        if quantity_band == "all":
            return ""
        elif quantity_band == "small":
            return "AND quantity <= 10"
        elif quantity_band == "medium":
            return "AND quantity > 10 AND quantity <= 100"
        elif quantity_band == "large":
            return "AND quantity > 100 AND quantity <= 1000"
        elif quantity_band == "bulk":
            return "AND quantity > 1000"
        else:
            return ""

    def _get_mock_peers(self, category: str, region: str, quantity_band: str) -> List[PeerTransaction]:
        """Generate mock peer data for testing."""
        import random
        from datetime import date, timedelta

        peers = []
        base_price = 100.0

        # Adjust base price by category
        category_prices = {
            "IT Hardware": 500.0,
            "Office Supplies": 25.0,
            "Furniture": 200.0,
            "Software": 1000.0,
            "Medical Supplies": 50.0,
            "Construction": 150.0,
        }
        base_price = category_prices.get(category, 100.0)

        # Generate mock peers
        for i in range(random.randint(15, 50)):
            # Add some variance to price
            price_variance = random.uniform(-0.3, 0.3)
            unit_price = base_price * (1 + price_variance)

            peer = PeerTransaction(
                transaction_id=f"mock-txn-{category}-{i}",
                vendor_id=f"VEND-MOCK-{random.randint(1000, 9999)}",
                category=category,
                subcategory=None,
                region=region,
                quantity=random.uniform(1, 1000),
                unit_price=round(unit_price, 2),
                total_amount=round(unit_price * random.uniform(1, 100), 2),
                transaction_date=date.today() - timedelta(days=random.randint(1, 90)),
                document_number=f"DOC-{random.randint(10000, 99999)}",
                quantity_band=quantity_band
            )
            peers.append(peer)

        return peers

    async def get_benchmark_stats(
        self,
        category: str,
        region: str,
        quantity_band: str
    ) -> Optional[Dict[str, Any]]:
        """Get pre-computed benchmark statistics."""
        try:
            pool = await self._get_db_pool()

            if pool:
                async with pool.acquire() as conn:
                    query = """
                        SELECT
                            COUNT(*) as count,
                            AVG(unit_price) as mean,
                            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unit_price) as median,
                            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY unit_price) as q1,
                            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY unit_price) as q3,
                            STDDEV(unit_price) as std_dev
                        FROM transactions
                        WHERE
                            category = $1
                            AND region = $2
                            AND quantity_band = $3
                            AND transaction_date >= NOW() - INTERVAL '90 days'
                            AND unit_price > 0
                    """

                    row = await conn.fetchrow(query, category, region, quantity_band)

                    if row and row['count'] > 0:
                        return {
                            "count": row['count'],
                            "mean": float(row['mean']) if row['mean'] else 0,
                            "median": float(row['median']) if row['median'] else 0,
                            "q1": float(row['q1']) if row['q1'] else 0,
                            "q3": float(row['q3']) if row['q3'] else 0,
                            "std_dev": float(row['std_dev']) if row['std_dev'] else 0
                        }

            return None

        except Exception as e:
            logger.error(f"Failed to get benchmark stats: {e}")
            return None