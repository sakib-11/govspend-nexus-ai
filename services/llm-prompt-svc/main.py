"""LLM Prompt Engineering Service — structured prompt generation and validation.

Features:
  • Structured system/user prompt templates
  • Few-shot in-context learning examples
  • JSON schema validation for LLM input/output
  • Grounding and citation coverage checks
  • Prompt optimisation with validation feedback
  • Token counting and cost estimation
  • Template management and rendering
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_config
from routes import prompt as prompt_routes
from services.context_builder import ContextBuilder
from services.prompt_optimizer import PromptOptimizer
from services.prompt_service import PromptService
from services.schema_validator import SchemaValidator
from services.template_service import TemplateService

config = get_config()

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s on port %d", config.SERVICE_NAME, config.PORT)

    # Database (optional — for template persistence and audit)
    db_pool = None
    try:
        import asyncpg
        db_pool = await asyncpg.create_pool(
            host=config.DB_HOST, port=config.DB_PORT,
            database=config.DB_NAME, user=config.DB_USER,
            password=config.DB_PASSWORD,
            min_size=config.DB_MIN_POOL_SIZE,
            max_size=config.DB_MAX_POOL_SIZE,
        )
        logger.info("Database pool created")
    except Exception:
        logger.warning("DB unavailable — running without persistence")

    # Redis (optional)
    redis_client = None
    try:
        import redis.asyncio as aioredis
        redis_client = await aioredis.Redis(
            host=config.REDIS_HOST, port=config.REDIS_PORT,
            db=config.REDIS_DB, password=config.REDIS_PASSWORD,
            decode_responses=True,
        )
        logger.info("Redis connected")
    except Exception:
        logger.warning("Redis unavailable")

    # Services
    context_builder = ContextBuilder(config)
    template_service = TemplateService(config)
    schema_validator = SchemaValidator()
    prompt_optimizer = PromptOptimizer(config)
    prompt_service = PromptService(config)

    # Attach to state
    app.state.db_pool = db_pool
    app.state.redis = redis_client
    app.state.context_builder = context_builder
    app.state.template_service = template_service
    app.state.schema_validator = schema_validator
    app.state.prompt_optimizer = prompt_optimizer
    app.state.prompt_service = prompt_service

    logger.info("%s ready — prompt engineering initialised", config.SERVICE_NAME)
    yield

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
# FastAPI app
# ------------------------------------------------------------------

app = FastAPI(
    title="LLM Prompt Engineering Service",
    version="1.0.0",
    description=(
        "GovSpend Nexus AI — structured prompt engineering with "
        "schema validation, grounding checks, and prompt optimisation."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prompt_routes.router)


@app.get("/")
async def root() -> dict:
    return {
        "service": config.SERVICE_NAME,
        "status": "running",
        "version": "1.0.0",
        "features": [
            "structured_prompts",
            "few_shot_learning",
            "schema_validation",
            "grounding_checks",
            "citation_tracking",
            "prompt_optimisation",
            "cost_estimation",
        ],
    }


@app.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "llm_model": config.LLM_MODEL,
        "strict_validation": config.STRICT_VALIDATION,
    }


@app.get("/api/v1/status")
async def service_status() -> dict:
    return {
        "service": config.SERVICE_NAME,
        "status": "operational",
        "llm_provider": config.LLM_PROVIDER,
        "llm_model": config.LLM_MODEL,
        "schema_validation": config.STRICT_VALIDATION,
        "grounding_required": config.REQUIRE_GROUNDING,
        "citations_required": config.REQUIRE_CITATIONS,
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=config.DEBUG)
