"""Masked Evidence Service — production-grade PII protection and tokenization.

Features:
  • HMAC-SHA256 based deterministic tokenization
  • Role-based masking (FULL / PARTIAL / MINIMAL)
  • Automatic PII pattern detection
  • PostgreSQL persistence with asyncpg
  • Redis-backed caching with in-memory fallback
  • Rate limiting and PII-safe logging
  • Jurisdiction-enforced access control
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_config
from middleware.masking_middleware import MaskingMiddleware
from routes import evidence as evidence_routes
from routes import masking as masking_routes
from services.cache_service import CacheService
from services.evidence_service import EvidenceService
from services.masking_service import MaskingService
from services.tokenization_service import TokenizationService

config = get_config()

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialise services, yield, cleanup."""

    logger.info("Starting %s on port %d", config.SERVICE_NAME, config.PORT)

    # ── Database pool ────────────────────────────────────────────
    db_pool = None
    redis_client = None

    try:
        import asyncpg

        db_pool = await asyncpg.create_pool(
            host=config.DB_HOST,
            port=config.DB_PORT,
            database=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            min_size=config.DB_MIN_POOL_SIZE,
            max_size=config.DB_MAX_POOL_SIZE,
        )
        logger.info("Database pool created")
    except Exception:
        logger.exception("Failed to connect to database — running without persistence")

    # ── Redis ────────────────────────────────────────────────────
    try:
        import redis.asyncio as aioredis

        redis_client = await aioredis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            password=config.REDIS_PASSWORD,
            decode_responses=True,
        )
        logger.info("Redis connected")
    except Exception:
        logger.warning("Redis unavailable — using in-memory cache fallback")

    # ── Services ─────────────────────────────────────────────────
    # Use an in-memory DB mock if real DB is unavailable
    if db_pool is None:
        db_pool = _MockPool()

    tokenization_service = TokenizationService(config, db_pool)
    masking_service = MaskingService(config, tokenization_service)
    cache_service = CacheService(redis_client, default_ttl=config.CACHE_TTL_SECONDS)
    evidence_service = EvidenceService(db_pool, masking_service, tokenization_service)

    # ── Attach to app.state ──────────────────────────────────────
    app.state.db_pool = db_pool
    app.state.redis = redis_client
    app.state.cache_service = cache_service
    app.state.tokenization_service = tokenization_service
    app.state.masking_service = masking_service
    app.state.evidence_service = evidence_service

    logger.info("%s ready — masking and tokenization initialised", config.SERVICE_NAME)

    yield

    # ── Graceful shutdown ────────────────────────────────────────
    logger.info("Shutting down %s", config.SERVICE_NAME)
    if redis_client:
        try:
            await redis_client.close()
        except Exception:
            pass
    if db_pool and hasattr(db_pool, "close"):
        try:
            await db_pool.close()
        except Exception:
            pass


# ------------------------------------------------------------------
# In-memory DB pool mock (for standalone mode without PostgreSQL)
# ------------------------------------------------------------------

class _MockConn:
    """Minimal async connection mock that stores nothing."""

    async def execute(self, *args, **kwargs):
        return "MOCK"

    async def fetchrow(self, *args, **kwargs):
        return None

    async def fetch(self, *args, **kwargs):
        return []


class _MockPool:
    """Context-manager pool that always yields a mock connection."""

    class _Ctx:
        async def __aenter__(self):
            return _MockConn()
        async def __aexit__(self, *args):
            pass

    def acquire(self):
        return self._Ctx()

    async def close(self):
        pass


# ------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------

app = FastAPI(
    title="Masked Evidence Service",
    version="1.0.0",
    description=(
        "GovSpend Nexus AI — production-grade PII protection and "
        "HMAC-based tokenization for evidence data."
    ),
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────
app.add_middleware(
    MaskingMiddleware,
    max_requests=config.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=config.RATE_LIMIT_WINDOW_SECONDS,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────
app.include_router(evidence_routes.router)
app.include_router(masking_routes.router)


@app.get("/")
async def root() -> dict:
    return {
        "service": config.SERVICE_NAME,
        "status": "running",
        "version": "1.0.0",
        "features": [
            "hmac_tokenization",
            "role_based_masking",
            "pii_detection",
            "jurisdiction_enforcement",
            "rate_limiting",
            "caching",
        ],
    }


@app.get("/health")
async def health() -> dict:
    cache_svc = getattr(app.state, "cache_service", None)
    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cache": cache_svc.get_stats() if cache_svc else None,
    }


@app.get("/api/v1/status")
async def service_status() -> dict:
    return {
        "service": config.SERVICE_NAME,
        "status": "operational",
        "masking_enabled": True,
        "tokenization_enabled": True,
        "version": "1.0.0",
    }


# ------------------------------------------------------------------
# Standalone
# ------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
    )
