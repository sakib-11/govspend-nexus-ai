"""Configuration for MCP Gateway."""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPGatewayConfig(BaseSettings):
    """MCP Gateway configuration with sensible production defaults."""

    # Service
    SERVICE_NAME: str = "mcp-gateway"
    PORT: int = 8008
    HOST: str = "0.0.0.0"
    DEBUG: bool = False

    # Security — JWT
    SECRET_KEY: str = os.getenv("MCP_SECRET_KEY", "dev-secret-change-in-production-!!")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SESSION_TIMEOUT_MINUTES: int = 30

    # OIDC (optional — falls back to local auth when disabled)
    OIDC_ENABLED: bool = False
    OIDC_PROVIDER: str = "keycloak"  # keycloak | auth0
    OIDC_ISSUER: str = os.getenv("OIDC_ISSUER", "govspend-nexus")
    OIDC_CLIENT_ID: str = os.getenv("OIDC_CLIENT_ID", "govspend-gateway")
    OIDC_CLIENT_SECRET: str = os.getenv("OIDC_CLIENT_SECRET", "")
    OIDC_AUTHORIZATION_ENDPOINT: str = ""
    OIDC_TOKEN_ENDPOINT: str = ""
    OIDC_USERINFO_ENDPOINT: str = ""
    OIDC_JWKS_ENDPOINT: str = ""

    # Keycloak
    KEYCLOAK_URL: Optional[str] = None
    KEYCLOAK_REALM: str = "govspend"
    KEYCLOAK_CLIENT_ID: str = "govspend-gateway"
    KEYCLOAK_CLIENT_SECRET: str = ""

    # MFA
    MFA_ENABLED: bool = True
    MFA_METHODS: List[str] = ["totp", "sms", "email"]
    MFA_ISSUER: str = "GovSpend-Nexus-AI"
    MFA_CODE_LENGTH: int = 6
    MFA_CODE_EXPIRY_SECONDS: int = 300
    MFA_MAX_ATTEMPTS: int = 5

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://user:pass@localhost:5432/govspend"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD_SECONDS: int = 60
    RATE_LIMIT_BLOCK_DURATION_MINUTES: int = 15

    # Account lockout
    MAX_FAILED_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30

    # Audit
    AUDIT_ENABLED: bool = True
    AUDIT_LOG_LEVEL: str = "INFO"
    AUDIT_RETENTION_DAYS: int = 365

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_config() -> MCPGatewayConfig:
    return MCPGatewayConfig()
