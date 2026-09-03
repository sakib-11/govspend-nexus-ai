"""Configuration for the Audit Logging Service."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuditLoggingConfig(BaseSettings):
    """Audit logging configuration with production defaults."""

    # Service
    SERVICE_NAME: str = "audit-logging-svc"
    PORT: int = 8010
    HOST: str = "0.0.0.0"
    DEBUG: bool = False

    # Hash chain
    CHAIN_START_HASH: str = "0" * 64
    SALT: str = "govspend-audit-salt-2024"
    HASH_ALGORITHM: str = "sha256"

    # Verification
    AUTO_VERIFY: bool = True
    VERIFICATION_INTERVAL_SECONDS: int = 300
    ALERT_ON_TAMPER: bool = True

    # Retention
    RETENTION_DAYS: int = 3650  # 10 years
    ARCHIVE_ENABLED: bool = True

    # Performance
    BATCH_SIZE: int = 100
    ASYNC_LOGGING: bool = True
    BUFFER_SIZE: int = 1000
    FLUSH_INTERVAL_SECONDS: float = 5.0

    # Security (optional — works without them)
    ENCRYPTION_ENABLED: bool = False
    ENCRYPTION_KEY: Optional[str] = None
    SIGNATURE_ENABLED: bool = False
    SIGNATURE_KEY: Optional[str] = None

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="AUDIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_config() -> AuditLoggingConfig:
    return AuditLoggingConfig()
