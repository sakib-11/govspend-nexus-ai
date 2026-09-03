"""Main application entry point for the Scoring Service."""

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .consumers import DetectionConsumer
from .routes import scoring
from .services import ConfidenceCalculator, ScoringEngine, SignalFetcher, TierClassifier
from .utils.logging import get_logger, setup_logging
from .utils.weights_policy import WeightPolicyManager

# Setup logging
setup_logging(log_level=settings.LOG_LEVEL)
logger = get_logger(__name__)

# Global instances
db_pool: asyncpg.Pool = None
redis_client: redis.Redis = None
signal_fetcher: SignalFetcher = None
scoring_engine: ScoringEngine = None
weight_manager: WeightPolicyManager = None
consumer_task: asyncio.Task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_pool, redis_client, signal_fetcher, scoring_engine
    global weight_manager, consumer_task

    logger.info(f"Starting {settings.SERVICE_NAME} service...")

    # Initialize database pool
    db_pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=5,
        max_size=20,
    )
    logger.info("Database pool initialized")

    # Initialize Redis
    redis_client = redis.from_url(settings.REDIS_URL)
    logger.info("Redis client initialized")

    # Initialize weight manager
    weight_manager = WeightPolicyManager("policies")
    logger.info(f"Weight manager initialized with {len(weight_manager.list_versions())} versions")

    # Initialize services
    signal_fetcher = SignalFetcher(db_pool)
    confidence_calculator = ConfidenceCalculator()
    tier_classifier = TierClassifier(
        high_threshold=settings.HIGH_THRESHOLD,
        borderline_threshold=settings.BORDERLINE_THRESHOLD,
    )
    scoring_engine = ScoringEngine(
        weight_manager=weight_manager,
        confidence_calculator=confidence_calculator,
        tier_classifier=tier_classifier,
    )
    logger.info("Scoring engine initialized")

    # Store in app state for route access
    app.state.signal_fetcher = signal_fetcher
    app.state.scoring_engine = scoring_engine
    app.state.weight_manager = weight_manager

    # Start consumer
    consumer = DetectionConsumer(
        redis_client=redis_client,
        signal_fetcher=signal_fetcher,
        scoring_engine=scoring_engine,
    )
    consumer_task = asyncio.create_task(consumer.consume_loop())
    logger.info("Detection consumer started")

    yield

    # Cleanup
    logger.info(f"Shutting down {settings.SERVICE_NAME} service...")

    if consumer_task:
        consumer_task.cancel()
        with suppress(asyncio.CancelledError):
            await consumer_task

    if redis_client:
        await redis_client.close()
        logger.info("Redis client closed")

    if db_pool:
        await db_pool.close()
        logger.info("Database pool closed")

    logger.info(f"{settings.SERVICE_NAME} service stopped")


# Initialize FastAPI app
app = FastAPI(
    title="GovSpend Nexus AI - Scoring Service",
    version="1.0.0",
    description="Risk scoring service for government procurement transactions",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes (prefix and tags already defined in router)
app.include_router(scoring.router)


@app.get("/")
async def root():
    return {
        "service": "scoring-svc",
        "status": "running",
        "version": "1.0.0",
        "weights_versions": weight_manager.list_versions() if weight_manager else [],
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "weights_versions": weight_manager.list_versions() if weight_manager else [],
        "db_pool": bool(db_pool),
        "redis_client": bool(redis_client),
    }