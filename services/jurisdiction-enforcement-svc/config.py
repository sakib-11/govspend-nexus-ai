"""Configuration for Jurisdiction Enforcement Service."""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class JurisdictionEnforcementConfig(BaseSettings):
    """Jurisdiction Enforcement configuration with sensible production defaults."""
    
    # Service
    SERVICE_NAME: str = "jurisdiction-enforcement-svc"
    PORT: int = 8006
    HOST: str = "0.0.0.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://user:pass@localhost:5432/govspend"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Cache settings
    JURISDICTION_CACHE_TTL_SECONDS: int = 300  # 5 minutes
    
    # Audit settings
    AUDIT_ENABLED: bool = True
    AUDIT_RETENTION_DAYS: int = 365
    
    # Rate limiting (if needed)
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD_SECONDS: int = 60
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_prefix="JURISDICTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_config() -> JurisdictionEnforcementConfig:
    return JurisdictionEnforcementConfig()