"""Configuration for the Unmask Service."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class UnmaskConfig(BaseSettings):
    """Unmask Service configuration with production defaults."""

    # Service
    SERVICE_NAME: str = "unmask-svc"
    PORT: int = 8012
    HOST: str = "0.0.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # Database (PostgreSQL via asyncpg)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "govspend_unmask"
    DB_USER: str = "unmask_user"
    DB_PASSWORD: str = "unmask_pass"
    DB_MIN_POOL_SIZE: int = 5
    DB_MAX_POOL_SIZE: int = 20

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Ledger Service
    LEDGER_SERVICE_URL: str = "http://ledger-svc:8011"
    LEDGER_SERVICE_TOKEN: str = "ledger-service-token"
    LEDGER_TIMEOUT_SECONDS: int = 30

    # MFA Configuration
    MFA_ENABLED: bool = True
    MFA_ISSUER: str = "GovSpend-Unmask"
    MFA_CODE_LENGTH: int = 6
    MFA_CODE_EXPIRY_SECONDS: int = 300
    MFA_MAX_ATTEMPTS: int = 3
    MFA_LOCKOUT_MINUTES: int = 15

    # State Machine
    REQUEST_TTL_HOURS: int = 72
    VIEW_TTL_HOURS: int = 24
    MAX_PENDING_REQUESTS: int = 10
    EXPIRY_CHECK_INTERVAL_MINUTES: int = 5

    # Audit
    AUDIT_ENABLED: bool = True
    AUDIT_HASH_SALT: str = "govspend-unmask-salt-2024"
    AUDIT_RETENTION_DAYS: int = 365

    # Security
    SELF_APPROVAL_DISALLOWED: bool = True
    REQUIRE_DIFFERENT_CHECKER: bool = True
    MAX_REQUESTS_PER_DAY: int = 50
    RATE_LIMIT_WINDOW_MINUTES: int = 60

    # Rate limiting (HTTP)
    RATE_LIMIT_MAX_REQUESTS: int = 200
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Cache
    CACHE_TTL_SECONDS: int = 3600

    # Notification (optional)
    NOTIFICATION_ENABLED: bool = False
    NOTIFICATION_SERVICE_URL: Optional[str] = None

    model_config = SettingsConfigDict(
        env_prefix="UNMASK_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_config() -> UnmaskConfig:
    return UnmaskConfig()
