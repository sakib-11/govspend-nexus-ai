"""Ingestion Service - Main Application Entry Point."""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import logging
import sys
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Project path
# ---------------------------------------------------------------------------

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Application imports
# ---------------------------------------------------------------------------

from services.ingestion_svc.config import Settings
from services.ingestion_svc.routes import ingest
from services.ingestion_svc.routes import crypto
from services.ingestion_svc.routes import stream

# Canonical route is optional during early development.
# The service will still start if it has not been created yet.
try:
    from services.ingestion_svc.routes import canonical
except ImportError:
    canonical = None

from services.ingestion_svc.services.storage import StorageService
from services.ingestion_svc.ocr.core import OCRService
from services.ingestion_svc.ocr.engines.tesseract import TesseractEngine


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = PROJECT_ROOT / "services" / "ingestion-svc" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "ingestion.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)

logger = logging.getLogger("ingestion-service")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

settings = Settings()


def get_setting(name: str, default: Any = None) -> Any:
    """
    Safely read a setting.

    Supports different Settings implementations without breaking startup.
    """
    return getattr(settings, name, default)


APP_NAME = get_setting(
    "app_name",
    "GovSpend Nexus - Ingestion Service",
)

APP_VERSION = get_setting(
    "app_version",
    "1.0.0",
)

APP_ENV = get_setting(
    "app_env",
    get_setting("environment", "development"),
)

DEBUG = bool(
    get_setting(
        "debug",
        False,
    )
)

PORT = int(
    get_setting(
        "port_ingestion",
        8000,
    )
)

UPLOAD_DIR = get_setting(
    "upload_dir",
    "uploads",
)

OCR_DEFAULT_ENGINE = get_setting(
    "ocr_default_engine",
    "tesseract",
)

ALLOWED_ORIGINS = get_setting(
    "allowed_origins",
    ["*"],
)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI application lifespan manager.

    Initializes storage and OCR services during startup and
    cleans them up during shutdown.
    """
    logger.info(
        "🚀 Starting %s...",
        APP_NAME,
    )

    logger.info(
        "Environment: %s",
        APP_ENV,
    )

    logger.info(
        "Version: %s",
        APP_VERSION,
    )

    logger.info(
        "OCR Engine: %s",
        OCR_DEFAULT_ENGINE,
    )

    storage = None
    ocr_service = None

    try:
        # ---------------------------------------------------------------
        # Initialize storage
        # ---------------------------------------------------------------

        storage = StorageService(settings)

        if hasattr(storage, "initialize"):
            result = storage.initialize()

            if hasattr(result, "__await__"):
                await result

        app.state.storage = storage

        logger.info("✅ Storage service initialized")

        # ---------------------------------------------------------------
        # Initialize Tesseract
        # ---------------------------------------------------------------

        tesseract_path = get_setting(
            "tesseract_path",
            None,
        )

        tesseract_language = get_setting(
            "tesseract_language",
            "eng",
        )

        tesseract_psm = get_setting(
            "tesseract_psm",
            6,
        )

        primary_engine = TesseractEngine(
            tesseract_path=tesseract_path,
            language=tesseract_language,
            psm=tesseract_psm,
        )

        # ---------------------------------------------------------------
        # Initialize OCR service
        # ---------------------------------------------------------------

        ocr_service = OCRService(
            primary_engine=primary_engine,
            fallback_engine=None,
            cache_enabled=True,
        )

        app.state.ocr_service = ocr_service

        logger.info("✅ OCR service initialized")

        logger.info(
            "✅ All ingestion services initialized successfully"
        )

    except Exception as exc:
        logger.exception(
            "❌ Failed to initialize ingestion services: %s",
            exc,
        )

        # Store error so readiness endpoint can report it.
        app.state.startup_error = str(exc)

        # Re-raise so deployment/orchestrator knows startup failed.
        raise

    else:
        app.state.startup_error = None

    yield

    # -------------------------------------------------------------------
    # Shutdown
    # -------------------------------------------------------------------

    logger.info(
        "🛑 Shutting down Ingestion Service..."
    )

    # Shutdown OCR service if supported.
    try:
        if ocr_service is not None:
            shutdown_method = getattr(
                ocr_service,
                "shutdown",
                None,
            )

            if shutdown_method:
                result = shutdown_method()

                if hasattr(result, "__await__"):
                    await result

                logger.info(
                    "✅ OCR service shut down"
                )
    except Exception:
        logger.exception(
            "Error while shutting down OCR service"
        )

    # Shutdown storage if supported.
    try:
        if storage is not None:
            shutdown_method = getattr(
                storage,
                "close",
                None,
            )

            if shutdown_method is None:
                shutdown_method = getattr(
                    storage,
                    "shutdown",
                    None,
                )

            if shutdown_method:
                result = shutdown_method()

                if hasattr(result, "__await__"):
                    await result

                logger.info(
                    "✅ Storage service shut down"
                )
    except Exception:
        logger.exception(
            "Error while shutting down storage service"
        )

    logger.info(
        "✅ Ingestion Service stopped"
    )


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=APP_NAME,
    description="Ingest and process procurement documents.",
    version=APP_VERSION,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(stream.router)
app.include_router(
    ingest.router
)

if canonical is not None:
    try:
        app.include_router(
            canonical.router
        )
        logger.info(
            "✅ Canonical router registered"
        )
    except AttributeError:
        logger.warning(
            "Canonical module found, but router is missing"
        )

try:
    app.include_router(
        crypto.router
    )
    logger.info(
        "✅ Crypto router registered"
    )
except AttributeError:
    logger.warning(
        "Crypto module found, but router is missing"
    )

# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
):
    """
    Handle unexpected application errors.
    """
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": (
                str(exc)
                if DEBUG
                else "An unexpected error occurred"
            ),
            "timestamp": datetime.now().isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """
    Basic health check.

    This endpoint verifies that the application process is running.
    """
    return {
        "status": "healthy",
        "service": "ingestion-svc",
        "version": APP_VERSION,
        "environment": APP_ENV,
        "timestamp": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Readiness endpoint
# ---------------------------------------------------------------------------

@app.get("/ready")
async def readiness_check():
    """
    Check whether required services are ready.
    """
    startup_error = getattr(
        app.state,
        "startup_error",
        None,
    )

    if startup_error:
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "components": {
                    "ocr": False,
                    "storage": False,
                },
                "error": startup_error,
                "timestamp": datetime.now().isoformat(),
            },
        )

    ocr_service = getattr(
        app.state,
        "ocr_service",
        None,
    )

    storage = getattr(
        app.state,
        "storage",
        None,
    )

    if ocr_service is None or storage is None:
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "components": {
                    "ocr": ocr_service is not None,
                    "storage": storage is not None,
                },
                "error": "Required services are not initialized",
                "timestamp": datetime.now().isoformat(),
            },
        )

    ocr_ready = True
    storage_ready = True

    # ---------------------------------------------------------------
    # OCR health check
    # ---------------------------------------------------------------

    try:
        health_check_method = getattr(
            ocr_service,
            "health_check",
            None,
        )

        if health_check_method:
            result = health_check_method()

            if hasattr(result, "__await__"):
                result = await result

            ocr_ready = bool(result)

    except Exception as exc:
        logger.error(
            "OCR readiness check failed: %s",
            exc,
        )
        ocr_ready = False

    # ---------------------------------------------------------------
    # Storage health check
    # ---------------------------------------------------------------

    try:
        health_check_method = getattr(
            storage,
            "health_check",
            None,
        )

        if health_check_method:
            result = health_check_method()

            if hasattr(result, "__await__"):
                result = await result

            storage_ready = bool(result)

    except Exception as exc:
        logger.error(
            "Storage readiness check failed: %s",
            exc,
        )
        storage_ready = False

    ready = ocr_ready and storage_ready

    response = {
        "ready": ready,
        "components": {
            "ocr": ocr_ready,
            "storage": storage_ready,
        },
        "timestamp": datetime.now().isoformat(),
    }

    if ready:
        return response

    return JSONResponse(
        status_code=503,
        content=response,
    )


# ---------------------------------------------------------------------------
# Configuration endpoint
# ---------------------------------------------------------------------------

@app.get("/config")
async def get_config():
    """
    Return non-sensitive configuration information.

    Configuration is only exposed in debug mode.
    """
    if not DEBUG:
        return {
            "message": "Config not available in production"
        }

    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "app_env": APP_ENV,
        "debug": DEBUG,
        "port": PORT,
        "upload_dir": UPLOAD_DIR,
        "ocr_default_engine": OCR_DEFAULT_ENGINE,
    }


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """
    Root service information endpoint.
    """
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Local development entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.ingestion_svc.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=DEBUG,
    )
