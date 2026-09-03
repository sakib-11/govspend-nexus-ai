"""Backend API — unified API for Cases, Evidence, Explanation, Graph, Unmask, Admin."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import BackendAPIConfig, get_config
from services import (
    CaseService,
    EvidenceService,
    ExplanationService,
    GraphService,
    UnmaskService,
    AdminService,
)
from routes import (
    admin_router,
    cases_router,
    evidence_router,
    explanation_router,
    graph_router,
    unmask_router,
)
from routes.v1 import router as v1_router
from services.nexus_service import NexusService

try:
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
except ImportError:
    TrustedHostMiddleware = None

try:
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
except ImportError:
    ProxyHeadersMiddleware = None

config = get_config()

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise all services, seed demo data, yield, cleanup."""

    logger.info("Starting %s on port %d", config.SERVICE_NAME, config.PORT)

    # Build services
    case_service = CaseService()
    evidence_service = EvidenceService()
    explanation_service = ExplanationService()
    graph_service = GraphService()
    unmask_service = UnmaskService()
    admin_service = AdminService()

    # Seed demo data
    if config.SEED_DEMO_DATA:
        case_service.seed_demo_data()
        evidence_service.seed_demo_data()
        graph_service.seed_demo_data()
        admin_service.seed_demo_data()
        logger.info("Demo data seeded")

    # Attach to app.state
    app.state.case_service = case_service
    app.state.evidence_service = evidence_service
    app.state.explanation_service = explanation_service
    app.state.graph_service = graph_service
    app.state.unmask_service = unmask_service
    app.state.admin_service = admin_service
    app.state.nexus_service = NexusService()
    app.state.production = config.ENVIRONMENT.lower() == "production"

    logger.info("%s ready — %d demo cases loaded", config.SERVICE_NAME, case_service.get_case_count())

    yield

    logger.info("Shutting down %s", config.SERVICE_NAME)


# ------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------

app = FastAPI(
    title="GovSpend Nexus AI — Backend API",
    version="1.0.0",
    description=(
        "Unified backend API for case management, evidence retrieval, "
        "AI explanations, vendor graph analysis, unmask workflows, and "
        "admin dashboard."
    ),
    lifespan=lifespan,
)

cors_origins = [o.strip() for o in os.getenv("BACKEND_API_CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",") if o.strip()]

if TrustedHostMiddleware is not None:
    allowed_hosts = [h.strip() for h in os.getenv("BACKEND_API_ALLOWED_HOSTS","*").split(",") if h.strip()] or ["*"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

if ProxyHeadersMiddleware is not None and os.getenv("BACKEND_API_BEHIND_PROXY", "").lower() == "true":
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

logger.info("CORS origins resolved: %s", ", ".join(cors_origins))

# Mount all route modules
app.include_router(cases_router)
app.include_router(evidence_router)
app.include_router(explanation_router)
app.include_router(graph_router)
app.include_router(unmask_router)
app.include_router(admin_router)
app.include_router(v1_router)


@app.get("/")
async def root() -> dict:
    return {"service": config.SERVICE_NAME, "status": "running", "version": "1.0.0"}


@app.get("/health")
async def health() -> dict:
    case_svc = getattr(app.state, "case_service", None)
    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cases_loaded": case_svc.get_case_count() if case_svc else 0,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=config.DEBUG)
