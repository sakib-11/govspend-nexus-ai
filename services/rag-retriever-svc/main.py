"""RAG Retriever Service — production-grade retrieval-augmented generation.

Features:
  • Hybrid search (dense pgvector + sparse full-text)
  • Query expansion with domain synonyms
  • Cross-encoder reranking
  • Case-contextual retrieval
  • Response caching with TTL
  • Retrieval metrics and feedback loop
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_config
from routes import retrieval as retrieval_routes
from services.context_builder import ContextBuilder
from services.embedding_service import EmbeddingService
from services.hybrid_search import HybridSearch
from services.keyword_search import KeywordSearch
from services.query_processor import QueryProcessor
from services.reranker_service import RerankerService
from services.retriever_service import RAGRetrieverService
from services.vector_search import VectorSearch

config = get_config()

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
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
    logger.info("Starting %s on port %d", config.SERVICE_NAME, config.PORT)

    # Database
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
        logger.exception("DB connection failed — using mock pool")
        db_pool = _MockPool()

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
    embedding_service = EmbeddingService(config)
    query_processor = QueryProcessor(db_pool, config)
    vector_search = VectorSearch(db_pool, embedding_service, config)
    keyword_search = KeywordSearch(db_pool, config)
    hybrid_search = HybridSearch(vector_search, keyword_search, embedding_service, config)
    reranker_service = RerankerService(config)
    await reranker_service.initialize()

    retriever_service = RAGRetrieverService(
        db_pool=db_pool,
        query_processor=query_processor,
        hybrid_search=hybrid_search,
        embedding_service=embedding_service,
        reranker_service=reranker_service,
        config=config,
    )

    # Attach to state
    app.state.db_pool = db_pool
    app.state.redis = redis_client
    app.state.retriever_service = retriever_service
    app.state.embedding_service = embedding_service
    app.state.reranker_service = reranker_service
    app.state.context_builder = ContextBuilder()

    logger.info("%s ready — hybrid retrieval initialised", config.SERVICE_NAME)
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
    title="RAG Retriever Service",
    version="1.0.0",
    description=(
        "GovSpend Nexus AI — production-grade RAG retrieval with "
        "hybrid search, query expansion, and cross-encoder reranking."
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

app.include_router(retrieval_routes.router)


@app.get("/")
async def root() -> dict:
    return {
        "service": config.SERVICE_NAME,
        "status": "running",
        "version": "1.0.0",
        "features": [
            "hybrid_search",
            "query_expansion",
            "cross_encoder_reranking",
            "case_contextual_retrieval",
            "response_caching",
            "feedback_loop",
        ],
    }


@app.get("/health")
async def health() -> dict:
    reranker = getattr(app.state, "reranker_service", None)
    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reranker_loaded": reranker.is_ready if reranker else False,
        "embedding_provider": config.EMBEDDING_PROVIDER,
    }


@app.get("/api/v1/status")
async def service_status() -> dict:
    reranker = getattr(app.state, "reranker_service", None)
    return {
        "service": config.SERVICE_NAME,
        "status": "operational",
        "hybrid_search": True,
        "query_expansion": config.QUERY_EXPANSION_ENABLED,
        "reranking": reranker.is_ready if reranker else False,
        "caching": config.CACHE_ENABLED,
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=config.DEBUG)
