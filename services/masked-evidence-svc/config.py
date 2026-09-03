"""Configuration for the Masked Evidence Service."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class MaskedEvidenceConfig(BaseSettings):
    """Masked Evidence Service configuration with production defaults."""

    # Service
    SERVICE_NAME: str = "masked-evidence-svc"
    PORT: int = 8011
    HOST: str = "0.0.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # Database (PostgreSQL via asyncpg)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "govspend_masked"
    DB_USER: str = "masked_user"
    DB_PASSWORD: str = "masked_pass"
    DB_MIN_POOL_SIZE: int = 5
    DB_MAX_POOL_SIZE: int = 20

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # HMAC Key — in production, sourced from KMS
    HMAC_KEY: str = "govspend-hmac-key-change-in-production"

    # Tokenization
    TOKEN_PREFIX: str = "VEND"
    TOKEN_LENGTH: int = 10

    # Masking
    MASK_CHARACTER: str = "*"
    MASK_THRESHOLD: int = 3  # keep first 3 chars visible

    # Cache
    CACHE_TTL_SECONDS: int = 3600
    CACHE_ENABLED: bool = True

    # Rate limiting
    RATE_LIMIT_MAX_REQUESTS: int = 200
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    model_config = SettingsConfigDict(
        env_prefix="MASKED_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_config() -> MaskedEvidenceConfig:
    return MaskedEvidenceConfig()
