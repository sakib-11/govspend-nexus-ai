"""Configuration for the Scoring Service."""

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Service settings
    SERVICE_NAME: str = "scoring-svc"
    PORT: int = 8004
    HOST: str = "0.0.0.0"
    DEBUG: bool = False

    # Database (PostgreSQL)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/govspend")

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Streams
    INPUT_STREAM: str = "detection.events"
    OUTPUT_STREAM: str = "scoring.results"
    ERROR_STREAM: str = "scoring.errors"
    CONSUMER_GROUP: str = "scoring-group"
    CONSUMER_NAME: str = "scoring-consumer-1"

    # Scoring parameters
    DEFAULT_WEIGHTS_VERSION: str = "v1.0"
    HIGH_THRESHOLD: float = 0.75
    BORDERLINE_THRESHOLD: float = 0.40
    MIN_CONFIDENCE: float = 0.30
    CONFIDENCE_FLOOR: float = 0.50

    # Performance
    BATCH_SIZE: int = 100
    FETCH_TIMEOUT_SECONDS: int = 30
    CACHE_TTL_SECONDS: int = 300

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()