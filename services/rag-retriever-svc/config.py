"""Configuration for the RAG Retriever Service."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGRetrieverConfig(BaseSettings):
    """RAG Retriever Service configuration with production defaults."""

    # Service
    SERVICE_NAME: str = "rag-retriever-svc"
    PORT: int = 8015
    HOST: str = "0.0.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # Database (PostgreSQL via asyncpg + pgvector)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "govspend_policies"
    DB_USER: str = "retriever_user"
    DB_PASSWORD: str = "retriever_pass"
    DB_MIN_POOL_SIZE: int = 5
    DB_MAX_POOL_SIZE: int = 20

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Search defaults
    DEFAULT_MATCH_COUNT: int = 10
    DEFAULT_MATCH_THRESHOLD: float = 0.65
    MAX_MATCH_COUNT: int = 50

    # Hybrid search weights
    DENSE_WEIGHT: float = 0.7
    SPARSE_WEIGHT: float = 0.3

    # Reranking
    RERANK_ENABLED: bool = True
    RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANK_TOP_K: int = 20

    # Query processing
    QUERY_EXPANSION_ENABLED: bool = True
    QUERY_EXPANSION_COUNT: int = 3
    USE_SYNONYMS: bool = True

    # Embedding
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_DIMENSION: int = 1536
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None

    # Cache
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600

    # Performance
    BATCH_SIZE: int = 50
    PARALLEL_WORKERS: int = 4
    TIMEOUT_SECONDS: int = 30

    # Rate limiting
    RATE_LIMIT_MAX_REQUESTS: int = 200
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_config() -> RAGRetrieverConfig:
    return RAGRetrieverConfig()
