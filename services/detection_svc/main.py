"""Detection Service - Main Application Entry Point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import detection
from .routes import duplicate as duplicate_routes
from .routes import timing as timing_routes
from .routes import vendor_graph as vendor_graph_routes
from .routes import contract_splitting as contract_splitting_routes
from .routes import approval_velocity as approval_velocity_routes
from .utils.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting %s service...", app.title)
    yield
    logger.info("Shutting down %s service...", app.title)


# Initialize FastAPI app
app = FastAPI(
    title="GovSpend Nexus AI - Detection Service",
    version="1.0.0",
    description="Detection pipeline for fraud risk analysis",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(detection.router, prefix="/api/v1", tags=["Detection"])
app.include_router(duplicate_routes.router, prefix="/api/v1", tags=["Duplicate Detection"])
app.include_router(timing_routes.router, prefix="/api/v1", tags=["Timing Anomaly"])
app.include_router(vendor_graph_routes.router, prefix="/api/v1", tags=["Vendor Graph Risk"])
app.include_router(contract_splitting_routes.router, prefix="/api/v1", tags=["Contract Splitting"])
app.include_router(approval_velocity_routes.router, prefix="/api/v1", tags=["Approval Velocity"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "service": "detection-svc",
        "status": "running",
        "version": "1.0.0"
    }