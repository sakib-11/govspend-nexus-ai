"""Configuration for Detection Core Service."""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Service
    SERVICE_NAME: str = "detection-core"
    PORT: int = 8002
    HOST: str = "0.0.0.0"

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    INPUT_STREAM: str = "tx.ingested"
    EVENT_STREAM: str = "detection.events"
    CONSUMER_GROUP: str = "detection_group"

    # PostgreSQL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/govspend")

    # Detector Engine
    MAX_CONCURRENT_TRANSACTIONS: int = 10
    DETECTOR_TIMEOUT_SECONDS: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: int = 5
    PARALLEL_DETECTORS: bool = True
    BATCH_SIZE: int = 100
    PROCESSING_TIMEOUT_SECONDS: int = 60

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()