"""Digital Twin Service — vendor/official relationship network analysis."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_config
from services.cache_service import CacheService
from services.graph_service import GraphService
from services.twin_service import TwinService
from routes import twin as twin_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = get_config()
twin_service = TwinService()
cache_service = CacheService(enabled=config.enable_caching, ttl_seconds=config.cache_ttl_seconds)
graph_service = GraphService(cache_service=cache_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.twin_service = twin_service
    app.state.graph_service = graph_service
    app.state.cache_service = cache_service
    logger.info(f"Digital Twin service started on port {config.port}")
    yield
    logger.info("Digital Twin service shutting down")


app = FastAPI(
    title="Digital Twin Service",
    version="1.0.0",
    description="GovSpend Nexus AI — vendor/official relationship network",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(twin_routes.router)


@app.get("/")
async def root() -> dict:
    return {"service": "digital-twin-svc", "status": "running", "version": "1.0.0"}


@app.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "service": "digital-twin-svc",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=config.port)
