"""Configuration for the LLM Prompt Engineering Service."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMPromptConfig(BaseSettings):
    """LLM Prompt Service configuration with production defaults."""

    # Service
    SERVICE_NAME: str = "llm-prompt-svc"
    PORT: int = 8016
    HOST: str = "0.0.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # Database (PostgreSQL via asyncpg)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "govspend_llm"
    DB_USER: str = "llm_user"
    DB_PASSWORD: str = "llm_pass"
    DB_MIN_POOL_SIZE: int = 5
    DB_MAX_POOL_SIZE: int = 20

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # LLM Configuration
    LLM_PROVIDER: str = "openai"  # openai | anthropic | azure
    LLM_MODEL: str = "gpt-4-turbo-preview"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2000
    LLM_TOP_P: float = 0.9
    LLM_FREQUENCY_PENALTY: float = 0.0
    LLM_PRESENCE_PENALTY: float = 0.0
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None

    # Prompt Configuration
    MAX_CONTEXT_LENGTH: int = 8000
    MAX_EVIDENCE_ITEMS: int = 10
    MAX_POLICY_CHUNKS: int = 5
    MAX_EXPLANATION_POINTS: int = 10

    # Validation
    STRICT_VALIDATION: bool = True
    REQUIRE_CITATIONS: bool = True
    REQUIRE_GROUNDING: bool = True
    VALIDATION_RETRY_COUNT: int = 2
    MIN_GROUNDING_SCORE: float = 0.5

    # Cache
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600

    # Rate limiting
    RATE_LIMIT_MAX_REQUESTS: int = 200
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Performance
    TIMEOUT_SECONDS: int = 60
    MAX_RETRIES: int = 3

    # Cost estimation (USD per 1K tokens)
    COST_PER_1K_INPUT_TOKENS: float = 0.01
    COST_PER_1K_OUTPUT_TOKENS: float = 0.03

    model_config = SettingsConfigDict(
        env_prefix="LLM_PROMPT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_config() -> LLMPromptConfig:
    return LLMPromptConfig()
