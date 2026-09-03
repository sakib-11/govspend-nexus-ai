"""Configuration for the Evidence Bundle Service."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class BundleSettings(BaseSettings):
    # Service settings
    SERVICE_NAME: str = "evidence-bundle-svc"
    PORT: int = 8005
    HOST: str = "0.0.0.0"
    DEBUG: bool = False

    # Database (PostgreSQL)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://user:pass@localhost:5432/govspend"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Streams
    INPUT_STREAM: str = "scoring.results"
    OUTPUT_STREAM: str = "bundle.events"
    ERROR_STREAM: str = "bundle.errors"
    CONSUMER_GROUP: str = "bundle-group"
    CONSUMER_NAME: str = "bundle-consumer-1"

    # Bundle settings
    MAX_BUNDLE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10MB
    DEFAULT_FORMAT: str = "JSON_EXTENDED"
    INCLUDE_BENCHMARKS: bool = True
    COMPRESS_BUNDLES: bool = False

    # Performance
    BATCH_SIZE: int = 50
    FETCH_TIMEOUT_SECONDS: int = 30
    CACHE_TTL_SECONDS: int = 600

    # Evidence retention
    RETENTION_DAYS: int = 365
    ARCHIVAL_ENABLED: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = BundleSettings()
