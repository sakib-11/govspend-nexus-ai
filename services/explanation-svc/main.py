"""Explanation Service — AI-powered risk explanations with Groq/OpenAI.

Features:
  • Groq API for fast inference with automatic OpenAI fallback
  • Structured explanation generation with citations
  • Multi-level validation (structure, grounding, citations)
  • Automatic regeneration with improved prompts
  • Template-based fallback when LLMs are unavailable
  • Redis/in-memory explanation caching
  • Full audit trail in PostgreSQL
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_config, setup_logging
from routes import (
    admin as admin_routes,
    auth as auth_routes,
    cases as cases_routes,
    explanation as explanation_routes,
    graph as graph_routes,
    unmask as unmask_routes,
)
from services.cache_service import CacheService
from services.explanation_service import ExplanationService
from services.fallback_service import FallbackService
from services.llm_client import LLMClientService
from services.regeneration_service import RegenerationService
from services.validation_service import ValidationService

config = get_config()

setup_logging(config)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# In-memory DB mock (standalone mode)
# ------------------------------------------------------------------

class _MockConn:
    async def execute(self, *a, **kw):
        return "MOCK"
    async def fetchrow(self, *a, **kw):
        return None
    async def fetchval(self, *a, **kw):
        return 0
    async def fetch(self, *a, **kw):
        return []
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass


class _MockPool:
    def acquire(self):
        class _Ctx:
            async def __aenter__(self_):
                return _MockConn()
            async def __aexit__(self_, *args):
                pass
        return _Ctx()
    async def close(self):
        pass


# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s on port %d", config.service_name, config.port)

    # Database
    db_pool = None
    try:
        import asyncpg
        db_pool = await asyncpg.create_pool(
            host=config.db_host, port=config.db_port,
            database=config.db_name, user=config.db_user,
            password=config.db_password,
            min_size=config.db_min_pool_size,
            max_size=config.db_max_pool_size,
        )
        logger.info("Database pool created")
    except Exception:
        logger.warning("DB unavailable — using mock pool")
        db_pool = _MockPool()

    # Redis
    redis_client = None
    try:
        import redis.asyncio as aioredis
        redis_client = await aioredis.Redis(
            host=config.redis_host, port=config.redis_port,
            db=config.redis_db, password=config.redis_password,
            decode_responses=True,
        )
        logger.info("Redis connected")
    except Exception:
        logger.warning("Redis unavailable — using in-memory cache")

    # Services
    cache_service = CacheService(redis_client, config)
    validation_service = ValidationService(config)
    fallback_service = FallbackService(config)
    llm_client = LLMClientService(config)
    regeneration_service = RegenerationService(llm_client, validation_service, config)
    explanation_service = ExplanationService(
        db_pool=db_pool,
        llm_client=llm_client,
        validation_service=validation_service,
        regeneration_service=regeneration_service,
        fallback_service=fallback_service,
        cache_service=cache_service,
        config=config,
    )

    # Attach to state
    app.state.db_pool = db_pool
    app.state.redis = redis_client
    app.state.cache_service = cache_service
    app.state.validation_service = validation_service
    app.state.fallback_service = fallback_service
    app.state.llm_client = llm_client
    app.state.regeneration_service = regeneration_service
    app.state.explanation_service = explanation_service
    app.state.config = config

    logger.info("%s ready — explanation pipeline initialised", config.service_name)
    yield

    logger.info("Shutting down %s", config.service_name)
    await llm_client.close()
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
# FastAPI app
# ------------------------------------------------------------------

app = FastAPI(
    title="Explanation Service",
    version="1.0.0",
    description=(
        "GovSpend Nexus AI — AI-powered risk explanations with "
        "Groq/OpenAI, validation, regeneration, and fallback."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(explanation_routes.router)
app.include_router(cases_routes.router)
app.include_router(graph_routes.router)
app.include_router(unmask_routes.router)
app.include_router(admin_routes.router)


@app.get("/")
async def root() -> dict:
    return {
        "service": config.service_name,
        "status": "running",
        "version": "1.0.0",
        "features": [
            "groq_inference",
            "openai_fallback",
            "citation_validation",
            "auto_regeneration",
            "template_fallback",
            "explanation_caching",
            "admin_console",
        ],
    }


@app.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "service": config.service_name,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "llm_provider": config.llm_provider,
        "llm_model": config.llm_model,
        "fallback_enabled": config.fallback_enabled,
    }


@app.get("/api/v1/status")
async def service_status() -> dict:
    return {
        "service": config.service_name,
        "status": "operational",
        "llm_provider": config.llm_provider,
        "validation_strictness": config.validation_strictness,
        "regeneration_enabled": config.max_regeneration_attempts > 0,
        "fallback_enabled": config.fallback_enabled,
        "caching_enabled": config.cache_enabled,
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.host, port=config.port, reload=config.debug)
