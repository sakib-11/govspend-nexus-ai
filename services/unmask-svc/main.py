"""Unmask Service — maker-checker workflow with audit and MFA.

Features:
  • Maker-Checker separation (self-approval prevention)
  • TOTP-based MFA with backup codes and lockout
  • Tamper-evident hash-chain audit logging
  • Data integrity checksums
  • Rate limiting and request expiry
  • Role-based jurisdiction enforcement
  • Ledger integration with retry
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_config
from middleware.audit_middleware import AuditMiddleware
from middleware.auth_middleware import AuthMiddleware
from middleware.mfa_middleware import MFAMiddleware
from routes import unmask as unmask_routes
from services.audit_service import AuditService
from services.expiry_service import ExpiryService
from services.ledger_client import LedgerClient
from services.mfa_service import MFAService
from services.unmask_service import UnmaskService

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
        logger.warning("Redis unavailable — some features may be limited")

    # ── Services ─────────────────────────────────────────────────
    if db_pool is None:
        db_pool = _MockPool()

    mfa_service = MFAService(config, db_pool)
    ledger_client = LedgerClient(config)
    audit_service = AuditService(db_pool, config)
    unmask_service = UnmaskService(
        db_pool=db_pool,
        mfa_service=mfa_service,
        ledger_client=ledger_client,
        audit_service=audit_service,
        config=config,
    )

    # Start expiry background job
    expiry_service = ExpiryService(db_pool, audit_service, config)
    await expiry_service.start()

    # ── Attach to app.state ──────────────────────────────────────
    app.state.db_pool = db_pool
    app.state.redis = redis_client
    app.state.mfa_service = mfa_service
    app.state.ledger_client = ledger_client
    app.state.audit_service = audit_service
    app.state.unmask_service = unmask_service
    app.state.expiry_service = expiry_service

    logger.info("%s ready — maker-checker workflow initialised", config.SERVICE_NAME)

    yield

    # ── Graceful shutdown ────────────────────────────────────────
    logger.info("Shutting down %s", config.SERVICE_NAME)
    await expiry_service.stop()
    await ledger_client.close()
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
# In-memory DB mock (for standalone mode without PostgreSQL)
# ------------------------------------------------------------------

class _MockConn:
    """Minimal async connection mock."""

    async def execute(self, *args, **kwargs):
        return "MOCK"

    async def fetchrow(self, *args, **kwargs):
        return None

    async def fetchval(self, *args, **kwargs):
        return 0

    async def fetch(self, *args, **kwargs):
        return []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class _MockTransaction:
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass


class _MockConnCtx:
    def __init__(self, conn):
        self._conn = conn
    async def __aenter__(self):
        return self._conn
    async def __aexit__(self, *args):
        pass


class _MockPool:
    """Context-manager pool for standalone mode."""

    def acquire(self):
        return _MockConnCtx(_MockConn())

    def transaction(self):
        return _MockTransaction()

    async def close(self):
        pass


# ------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------

app = FastAPI(
    title="Unmask Service",
    version="1.0.0",
    description=(
        "GovSpend Nexus AI — maker-checker unmask service with "
        "tamper-evident audit, MFA, and jurisdiction enforcement."
    ),
    lifespan=lifespan,
)

# ── Middleware (order matters: outermost = first to execute) ──────
app.add_middleware(AuditMiddleware)
app.add_middleware(
    MFAMiddleware, mfa_enabled=config.MFA_ENABLED,
)
app.add_middleware(
    AuthMiddleware,
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
app.include_router(unmask_routes.router)


@app.get("/")
async def root() -> dict:
    return {
        "service": config.SERVICE_NAME,
        "status": "running",
        "version": "1.0.0",
        "features": [
            "maker_checker",
            "mfa_verification",
            "hash_chain_audit",
            "rate_limiting",
            "jurisdiction_enforcement",
            "auto_expiry",
        ],
    }


@app.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mfa_enabled": config.MFA_ENABLED,
        "audit_enabled": config.AUDIT_ENABLED,
    }


@app.get("/api/v1/status")
async def service_status() -> dict:
    return {
        "service": config.SERVICE_NAME,
        "status": "operational",
        "maker_checker_enabled": True,
        "mfa_enabled": config.MFA_ENABLED,
        "audit_enabled": config.AUDIT_ENABLED,
        "self_approval_disallowed": config.SELF_APPROVAL_DISALLOWED,
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
