"""Evidence Bundle Service — Main Application Entry Point.

Consumes scoring results from Redis Streams, assembles complete evidence
bundles (transaction data + detector signals + benchmarks), and stores
them for downstream audit, explanation, and reporting.
"""

import asyncio
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .utils.logging import setup_logging, get_logger
from .services.signal_collector import SignalCollector
from .services.transaction_fetcher import TransactionFetcher
from .services.benchmark_collector import BenchmarkCollector
from .services.bundle_assembler import BundleAssembler
from .services.bundle_storage import BundleStorage
from .consumers.scoring_consumer import ScoringConsumer
from .routes import bundle as bundle_routes

# ── Logging ───────────────────────────────────────────────────────
setup_logging(log_level=settings.LOG_LEVEL)
logger = get_logger(__name__)

# ── Globals ───────────────────────────────────────────────────────
db_pool: asyncpg.Pool = None
redis_client: aioredis.Redis = None
consumer_task: asyncio.Task = None


# ── Lifespan ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — init DB, Redis, services, and consumer."""
    global db_pool, redis_client, consumer_task

    logger.info("Starting %s (port %d) ...", settings.SERVICE_NAME, settings.PORT)

    # Database
    try:
        db_pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=5,
            max_size=20,
        )
        logger.info("Database pool initialised")
    except Exception as e:
        logger.warning("Database unavailable (%s) — running in memory-only mode", e)
        db_pool = None

    # Redis
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning("Redis unavailable (%s) — consumer disabled", e)
        redis_client = None

    # Services
    signal_collector = SignalCollector(db_pool)
    transaction_fetcher = TransactionFetcher(db_pool)
    benchmark_collector = BenchmarkCollector(db_pool)
    bundle_assembler = BundleAssembler(
        signal_collector, transaction_fetcher, benchmark_collector
    )
    bundle_storage = BundleStorage(db_pool, settings)

    # Inject into routes
    bundle_routes.init_routes(bundle_assembler, bundle_storage)

    # Store in app.state for dependency injection
    app.state.bundle_assembler = bundle_assembler
    app.state.bundle_storage = bundle_storage

    # Start Redis consumer if available
    if redis_client:
        consumer = ScoringConsumer(
            redis_client, bundle_assembler, bundle_storage, settings
        )
        consumer_task = asyncio.create_task(consumer.consume_loop())
        logger.info("Scoring consumer started")

    logger.info("%s ready", settings.SERVICE_NAME)

    yield  # ── App is running ─────────────────────────────────────

    # Shutdown
    logger.info("Shutting down %s ...", settings.SERVICE_NAME)

    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")

    if db_pool:
        await db_pool.close()
        logger.info("Database pool closed")


# ── App ───────────────────────────────────────────────────────────
app = FastAPI(
    title="GovSpend Nexus AI — Evidence Bundle Service",
    version="1.0.0",
    description="Assembles evidence bundles for audit, explanation, and reporting",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(bundle_routes.router, prefix="/api/v1", tags=["Evidence Bundles"])


@app.get("/")
async def root():
    return {
        "service": settings.SERVICE_NAME,
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": "1.0.0",
        "components": {
            "database": "connected" if db_pool else "memory-only",
            "redis": "connected" if redis_client else "unavailable",
            "consumer": "running" if consumer_task and not consumer_task.done() else "stopped",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
