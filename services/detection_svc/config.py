"""Configuration for the Detection Service."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os


class DetectionSettings(BaseSettings):
    # Service settings
    SERVICE_NAME: str = "detection-svc"
    PORT: int = 8002
    HOST: str = "0.0.0.0"

    # Price deviation detector settings
    PRICE_DEVIATION_LOOKBACK_DAYS: int = 90
    PRICE_DEVIATION_MIN_SAMPLES: int = 10
    PRICE_DEVIATION_IQR_MULTIPLIER: float = 1.5
    PRICE_DEVIATION_MAX_DEVIATION: float = 10.0  # Cap signal at 10x

    # Peer grouping dimensions
    PEER_GROUP_CATEGORIES: List[str] = ["category", "subcategory", "region", "quantity_band"]
    PEER_QUANTITY_BANDS: List[dict] = [
        {"name": "small", "max": 10},
        {"name": "medium", "max": 100},
        {"name": "large", "max": 1000},
        {"name": "bulk", "max": float("inf")}
    ]

    # Confidence thresholds
    CONFIDENCE_HIGH_THRESHOLD: int = 30  # Samples
    CONFIDENCE_MEDIUM_THRESHOLD: int = 15  # Samples
    CONFIDENCE_LOW_THRESHOLD: int = 5  # Samples

    # Cache settings
    CACHE_TTL_SECONDS: int = 3600  # 1 hour
    CACHE_MAX_SIZE: int = 10000

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Database (PostgreSQL for benchmark data)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/govspend")

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = DetectionSettings()