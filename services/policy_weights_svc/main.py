"""Policy Weights Management Service — Main Application Entry Point.

Manages version-controlled weight policies for the scoring pipeline with
full audit trails, calibration support, and Redis caching.
"""

import asyncio
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .utils.logging import setup_logging, get_logger
from .services.policy_manager import PolicyManager
from .services.calibration_service import CalibrationService
from .services.audit_service import AuditService
from .consumers.calibration_consumer import CalibrationConsumer
from .routes import policies as policies_routes
from .admin import dashboard as admin_routes

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
            settings.DATABASE_URL, min_size=5, max_size=20
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
        logger.warning("Redis unavailable (%s) — cache and consumer disabled", e)
        redis_client = None

    # Services
    policy_manager = PolicyManager(db_pool, settings, redis_client)
    audit_service = AuditService(db_pool)
    calibration_service = CalibrationService(policy_manager, audit_service, db_pool)

    # Inject into routes
    policies_routes.init_routes(policy_manager, calibration_service, audit_service)
    admin_routes.init_admin_routes(policy_manager, calibration_service)

    # Store in app.state
    app.state.policy_manager = policy_manager
    app.state.calibration_service = calibration_service
    app.state.audit_service = audit_service

    # Start consumer if Redis available
    if redis_client:
        consumer = CalibrationConsumer(redis_client, calibration_service, settings)
        consumer_task = asyncio.create_task(consumer.consume_loop())
        logger.info("Calibration consumer started")

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
    title="GovSpend Nexus AI — Policy Weights Management Service",
    version="1.0.0",
    description="Version-controlled weight policy management for the scoring pipeline",
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
app.include_router(policies_routes.router)
app.include_router(admin_routes.router)


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
            "consumer": (
                "running"
                if consumer_task and not consumer_task.done()
                else "stopped"
            ),
        },
    }


@app.post("/initialize-default")
async def initialize_default_policy():
    """Initialize the default policy if none exists."""
    pm = app.state.policy_manager

    try:
        policies, count = await pm.get_all_policies()
        if count > 0:
            return {"status": "already_initialized", "policy_count": count}

        from .models.policy import DetectorWeights

        weights = DetectorWeights(**settings.DEFAULT_WEIGHTS)
        policy = await pm.create_policy(
            name="Default Policy",
            weights=weights,
            created_by="system",
            description="Initial default policy weights",
        )
        await pm.activate_policy(policy.policy_id, activated_by="system")

        return {"status": "initialized", "policy": policy.model_dump(mode="json")}

    except Exception as e:
        logger.error("Failed to initialize default policy: %s", e)
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
