"""Audit Logging Service — main application entry point.

Production-grade audit logging with:
  • Cryptographic hash chaining (SHA-256)
  • Tamper detection and verification
  • Buffered async logging with circuit breaker
  • Rate limiting and metrics collection
  • Webhook alerts for critical events
  • Data export (JSON, CSV, NDJSON)
  • Retention and archival management
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_config
from middleware.audit_middleware import AuditMiddleware
from middleware.rate_limiter import RateLimiterMiddleware
from routes import audit as audit_routes
from services.audit_logger import AuditLogger
from services.audit_retriever import AuditRetriever
from services.audit_verifier import AuditVerifier
from services.batch_processor import BatchProcessor
from services.hash_chain_manager import HashChainManager
from services.metrics import MetricsCollector
from services.retention import RetentionManager
from services.tamper_detector import TamperDetector
from services.webhook_alerts import WebhookAlertService

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

    # ── Core services ──────────────────────────────────────────────
    chain_manager = HashChainManager(salt=config.SALT)
    audit_logger = AuditLogger(
        chain_manager,
        async_logging=config.ASYNC_LOGGING,
        buffer_size=config.BUFFER_SIZE,
        flush_interval=config.FLUSH_INTERVAL_SECONDS,
    )
    audit_verifier = AuditVerifier(chain_manager)
    audit_retriever = AuditRetriever(chain_manager)
    tamper_detector = TamperDetector(audit_verifier)

    # ── Production services ────────────────────────────────────────
    metrics = MetricsCollector()
    batch_processor = BatchProcessor(
        chain_manager,
        batch_size=config.BATCH_SIZE,
        flush_interval=config.FLUSH_INTERVAL_SECONDS,
    )
    webhook_alerts = WebhookAlertService()
    retention_manager = RetentionManager(
        chain_manager,
        retention_days=config.RETENTION_DAYS,
        archive_before_days=min(config.RETENTION_DAYS // 2, 365),
    )

    # ── Attach to app.state ────────────────────────────────────────
    app.state.hash_chain_manager = chain_manager
    app.state.audit_logger = audit_logger
    app.state.audit_verifier = audit_verifier
    app.state.audit_retriever = audit_retriever
    app.state.tamper_detector = tamper_detector
    app.state.metrics = metrics
    app.state.batch_processor = batch_processor
    app.state.webhook_alerts = webhook_alerts
    app.state.retention_manager = retention_manager

    # ── Start background tasks ─────────────────────────────────────
    audit_logger.start()
    batch_processor.start()

    logger.info("%s ready — hash chain initialised", config.SERVICE_NAME)

    yield

    # ── Graceful shutdown ───────────────────────────────────────────
    logger.info("Shutting down %s", config.SERVICE_NAME)
    await batch_processor.stop()
    await audit_logger.stop()


# ------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------

app = FastAPI(
    title="Audit Logging Service",
    version="1.0.0",
    description=(
        "GovSpend Nexus AI — production-grade tamper-evident audit logging "
        "with cryptographic hash chaining, metrics, rate limiting, "
        "webhook alerts, data export, and retention management."
    ),
    lifespan=lifespan,
)

# ── Middleware (order matters: outermost = first to execute) ──────
app.add_middleware(RateLimiterMiddleware, max_requests=200, window_seconds=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(audit_routes.router)


@app.get("/")
async def root() -> dict:
    return {
        "service": config.SERVICE_NAME,
        "status": "running",
        "version": "1.0.0",
        "features": [
            "hash_chain",
            "tamper_detection",
            "metrics",
            "rate_limiting",
            "batch_processing",
            "webhook_alerts",
            "data_export",
            "retention_management",
        ],
    }


@app.get("/health")
async def health_check() -> dict:
    chain = getattr(app.state, "hash_chain_manager", None)
    metrics_collector = getattr(app.state, "metrics", None)
    batch = getattr(app.state, "batch_processor", None)

    total = chain.get_chain_state()[2] if chain else 0
    chain_status = chain.get_chain_status() if chain else None

    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "chain": {
            "total_entries": total,
            "is_valid": chain_status.is_valid if chain_status else True,
            "last_hash": chain_status.last_hash if chain_status else None,
        },
        "batch_queue": batch.get_stats()["queue_size"] if batch else 0,
        "metrics_summary": {
            "entries_logged": metrics_collector.get_counter("audit_entries_total") if metrics_collector else 0,
        },
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
