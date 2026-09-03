"""Production-ready main application with comprehensive middleware and error handling."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app
import asyncpg
import redis.asyncio as redis

from config import get_config, setup_logging
from utils.error_handling import (
    BaseValidatorException,
    ValidationError,
    GroundingError,
    CitationError,
    global_exception_handler,
    validation_exception_handler,
    grounding_error_handler,
    citation_error_handler,
    AuditLogger,
)
from services.validator_service import ValidatorService
from services.schema_validator import SchemaValidator
from services.citation_validator import CitationValidator
from services.grounding_service import GroundingService
from services.masking_service import MaskingService
from services.rephraser_service import RephraserService
from routes import validator as validator_routes

# ============================================
# Configuration and Logging
# ============================================

config = get_config()
setup_logging(config)
logger = logging.getLogger(__name__)
audit_logger = AuditLogger()

# ============================================
# Prometheus Metrics
# ============================================

REQUEST_COUNT = Counter(
    "validator_requests_total",
    "Total requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_DURATION = Histogram(
    "validator_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
)
ACTIVE_CONNECTIONS = Gauge(
    "validator_active_connections",
    "Active database connections",
)
VALIDATION_SCORE = Histogram(
    "validator_grounding_score",
    "Grounding score distribution",
    buckets=[0.1, 0.3, 0.5, 0.7, 0.9, 1.0],
)

# ============================================
# Middleware
# ============================================

class MetricsMiddleware:
    """Prometheus metrics middleware."""

    async def __call__(self, request: Request, call_next):
        start_time = time.time()
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            status_code = response.status_code
            REQUEST_COUNT.labels(method=method, endpoint=path, status_code=status_code).inc()
            REQUEST_DURATION.labels(method=method, endpoint=path).observe(
                time.time() - start_time
            )
            return response
        except Exception as e:
            REQUEST_COUNT.labels(method=method, endpoint=path, status_code=500).inc()
            raise


class TimingMiddleware:
    """Request timing middleware."""

    async def __call__(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


# ============================================
# Application Lifecycle
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with proper resource management."""

    logger.info(
        "Starting Explanation Validator Service",
        extra={"service": config.service_name, "port": config.port},
    )

    # Initialize database pool with connection retry
    db_pool = None
    for attempt in range(3):
        try:
            db_pool = await asyncpg.create_pool(
                host=config.db_host,
                port=config.db_port,
                database=config.db_name,
                user=config.db_user,
                password=config.db_password,
                min_size=config.db_pool_size // 2,
                max_size=config.db_max_overflow,
                timeout=config.db_timeout,
                command_timeout=config.db_timeout,
            )
            logger.info("Database pool initialized")
            break
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt == 2:
                raise
            time.sleep(2**attempt)

    # Initialize Redis with connection retry
    redis_client = None
    for attempt in range(3):
        try:
            redis_client = redis.Redis(
                host=config.redis_host,
                port=config.redis_port,
                db=config.redis_db,
                password=config.redis_password,
                decode_responses=True,
                max_connections=config.redis_max_connections,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            # Test connection
            await redis_client.ping()
            logger.info("Redis connection established")
            break
        except Exception as e:
            logger.warning(f"Redis connection attempt {attempt + 1} failed: {e}")
            if attempt == 2:
                logger.warning("Redis unavailable - running without cache")
                redis_client = None
            time.sleep(2**attempt)

    # Initialize services
    try:
        schema_validator = SchemaValidator()
        citation_validator = CitationValidator()
        grounding_service = GroundingService()
        masking_service = MaskingService(config)
        rephraser_service = RephraserService(config)

        validator_service = ValidatorService(
            db_pool=db_pool,
            schema_validator=schema_validator,
            citation_validator=citation_validator,
            grounding_service=grounding_service,
            masking_service=masking_service,
            rephraser_service=rephraser_service,
            config=config,
        )

        # Store in app state
        app.state.db_pool = db_pool
        app.state.redis = redis_client
        app.state.validator_service = validator_service
        app.state.schema_validator = schema_validator
        app.state.citation_validator = citation_validator
        app.state.grounding_service = grounding_service
        app.state.masking_service = masking_service
        app.state.rephraser_service = rephraser_service
        app.state.audit_logger = audit_logger

        logger.info("All services initialized successfully")

    except Exception as e:
        logger.error(f"Service initialization failed: {e}")
        raise

    yield

    # Cleanup
    logger.info("Shutting down services")
    try:
        if redis_client:
            await redis_client.close()
        if db_pool:
            await db_pool.close()
        if 'rephraser_service' in locals():
            await rephraser_service.close()
        logger.info("Services shut down successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# ============================================
# Application Factory
# ============================================

def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="Explanation Validator Service",
        description="GovSpend Nexus AI - 100% Grounding Validator",
        version="1.0.0",
        docs_url="/docs" if not config.is_production else None,
        redoc_url="/redoc" if not config.is_production else None,
        openapi_url="/openapi.json" if not config.is_production else None,
        lifespan=lifespan,
    )

    # ============================================
    # Middleware Registration
    # ============================================

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    # GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Custom middleware
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(TimingMiddleware)

    # ============================================
    # Exception Handlers
    # ============================================

    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(GroundingError, grounding_error_handler)
    app.add_exception_handler(CitationError, citation_error_handler)

    # ============================================
    # Routes
    # ============================================

    app.include_router(validator_routes.router, prefix="/api/v1")

    # Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # ============================================
    # Health Checks
    # ============================================

    @app.get("/health")
    async def health_check():
        """Basic health check."""
        return {
            "status": "healthy",
            "service": config.service_name,
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/health/detailed")
    async def detailed_health_check(request: Request):
        """Detailed health check with dependency status."""

        db_healthy = False
        redis_healthy = False

        # Check database
        try:
            db_pool = request.app.state.db_pool
            if db_pool:
                async with db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                db_healthy = True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")

        # Check Redis
        try:
            redis_client = request.app.state.redis
            if redis_client:
                await redis_client.ping()
                redis_healthy = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")

        is_healthy = db_healthy and redis_healthy
        status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "healthy" if is_healthy else "degraded",
                "service": config.service_name,
                "version": "1.0.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dependencies": {
                    "database": "healthy" if db_healthy else "unhealthy",
                    "redis": "healthy" if redis_healthy else "unhealthy",
                },
            },
        )

    # ============================================
    # Startup and Shutdown Events
    # ============================================

    @app.on_event("startup")
    async def startup_event():
        """Application startup tasks."""
        logger.info("Application startup completed")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown tasks."""
        logger.info("Application shutdown initiated")

    return app


# ============================================
# Application Instance
# ============================================

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.log_level.lower(),
        access_log=True,
    )