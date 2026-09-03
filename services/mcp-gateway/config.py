"""Configuration for the MCP Gateway & Tools API."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPGatewayConfig(BaseSettings):
    """MCP Gateway configuration with production defaults."""

    # Service
    SERVICE_NAME: str = "mcp-gateway-tools"
    PORT: int = 8009
    HOST: str = "0.0.0.0"
    DEBUG: bool = False

    # Database (optional — tools work in-memory without it)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://user:pass@localhost:5432/govspend"
    )

    # Redis (optional)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Security
    SECRET_KEY: str = os.getenv("MCP_SECRET_KEY", "dev-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Tool execution
    DEFAULT_TIMEOUT_SECONDS: int = 30
    MAX_TIMEOUT_SECONDS: int = 300
    DEFAULT_RETRY_COUNT: int = 3

    # Audit
    AUDIT_ENABLED: bool = True
    AUDIT_MAX_ENTRIES: int = 10_000

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="MCP_GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_config() -> MCPGatewayConfig:
    return MCPGatewayConfig()
