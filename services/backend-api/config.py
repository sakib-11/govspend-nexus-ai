"""Configuration for the Backend API service."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendAPIConfig(BaseSettings):
    """Backend API configuration."""

    SERVICE_NAME: str = "backend-api"
    PORT: int = 8015
    HOST: str = "0.0.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    SEED_DEMO_DATA: bool = True
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="BACKEND_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_config() -> BackendAPIConfig:
    return BackendAPIConfig()
