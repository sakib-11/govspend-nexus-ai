"""Configuration for the Policy Weights Management Service."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Service settings
    SERVICE_NAME: str = "policy-weights-svc"
    PORT: int = 8007
    HOST: str = "0.0.0.0"
    DEBUG: bool = False

    # Database (PostgreSQL)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://user:pass@localhost:5432/govspend"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Cache
    CACHE_TTL_SECONDS: int = 300
    ACTIVE_POLICY_CACHE_KEY: str = "active_policy"

    # Streams
    INPUT_STREAM: str = "calibration.events"
    OUTPUT_STREAM: str = "policy.events"
    ERROR_STREAM: str = "policy.errors"
    CONSUMER_GROUP: str = "policy-group"
    CONSUMER_NAME: str = "policy-consumer-1"

    # Default weights (initial policy)
    DEFAULT_WEIGHTS: dict = {
        "price_deviation": 0.30,
        "duplicate_fuzzy": 0.20,
        "vendor_graph_risk": 0.20,
        "timing_anomaly": 0.10,
        "contract_splitting": 0.15,
        "approval_velocity": 0.05,
    }

    # Policy settings
    MAX_POLICY_HISTORY: int = 100
    REQUIRE_APPROVAL: bool = True
    AUTO_ARCHIVE_AFTER_DAYS: int = 365
    WEIGHT_SUM_TOLERANCE: float = 0.001

    # Performance
    BATCH_SIZE: int = 50
    EVALUATION_WINDOW_DAYS: int = 30
    MIN_EVALUATION_SAMPLES: int = 1000

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
