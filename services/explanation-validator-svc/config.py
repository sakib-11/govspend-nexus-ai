"""Production-ready configuration for Explanation Validator Service."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class ValidatorConfig(BaseSettings):
    """Production-ready Explanation Validator configuration with validation."""

    model_config = SettingsConfigDict(
        env_prefix="VALIDATOR_",
        env_file=".env.validator",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============================================
    # Service Configuration
    # ============================================
    service_name: str = "explanation-validator-svc"
    port: int = Field(default=8018, ge=1, le=65535)
    host: str = "0.0.0.0"
    debug: bool = False
    environment: str = "development"
    log_level: str = "INFO"
    log_format: str = "json"

    # ============================================
    # Database Configuration
    # ============================================
    db_host: str = "localhost"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "govspend"
    db_user: str = "validator_user"
    db_password: str = "validator_pass"
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=200)
    db_ssl: bool = False
    db_timeout: int = Field(default=30, ge=1, le=300)

    # ============================================
    # Redis Configuration
    # ============================================
    redis_host: str = "localhost"
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_db: int = Field(default=0, ge=0, le=15)
    redis_password: Optional[str] = None
    redis_max_connections: int = Field(default=10, ge=1, le=100)
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=3600, ge=0, le=86400)

    # ============================================
    # Validation Settings
    # ============================================
    require_100_percent_grounding: bool = True
    strict_citation_check: bool = True
    validate_schema: bool = True
    validate_evidence_ids: bool = True
    validate_policy_ids: bool = True
    validate_detector_names: bool = True
    min_grounding_score: float = Field(default=1.0, ge=0.0, le=1.0)
    allowed_missing_citations: int = Field(default=0, ge=0)
    max_ungrounded_sentences: int = Field(default=0, ge=0)

    # ============================================
    # Masking Settings
    # ============================================
    mask_ungrounded_claims: bool = True
    mask_marker: str = "[UNCITED]"
    rephrase_ungrounded: bool = True

    # ============================================
    # LLM / AI Configuration
    # ============================================
    groq_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    llm_model: str = "mixtral-8x7b-32768"
    llm_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2048, ge=1, le=4096)
    rephraser_enabled: bool = True
    rephraser_model: str = "mixtral-8x7b-32768"
    rephraser_max_attempts: int = Field(default=2, ge=1, le=5)

    # ============================================
    # Security Configuration
    # ============================================
    jwt_secret: Optional[str] = None
    hmac_key: Optional[str] = None
    secret_key: Optional[str] = None
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )

    # ============================================
    # Rate Limiting
    # ============================================
    rate_limit_max_requests: int = Field(default=100, ge=1, le=1000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)

    # ============================================
    # Monitoring and Observability
    # ============================================
    enable_metrics: bool = True
    enable_tracing: bool = True
    metrics_port: int = Field(default=9090, ge=1, le=65535)

    # ============================================
    # Validators
    # ============================================

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @validator("environment")
    def validate_environment(cls, v):
        valid_envs = ["development", "staging", "production"]
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v_lower

    @property
    def database_url(self) -> str:
        """Construct database URL from components."""
        if self.db_password:
            return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        return f"postgresql://{self.db_user}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


@lru_cache()
def get_config() -> ValidatorConfig:
    """Get cached configuration instance."""
    return ValidatorConfig()


def setup_logging(config: ValidatorConfig) -> None:
    """Configure structured logging based on environment."""
    log_level = getattr(logging, config.log_level)

    if config.log_format == "json" and config.is_production:
        # JSON logging for production
        import json
        from pythonjsonlogger import json as json_logger

        class JsonFormatter(json_logger.JsonFormatter):
            def add_fields(self, log_record, record, message_dict):
                super().add_fields(log_record, record, message_dict)
                log_record["level"] = record.levelname
                log_record["service"] = config.service_name
                log_record["environment"] = config.environment
                log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"

        formatter = JsonFormatter(
            "%(timestamp)s %(level)s %(service)s %(message)s"
        )
    else:
        # Standard logging for development
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add file handler for production
    if config.is_production:
        file_handler = logging.FileHandler("/var/log/explanation-validator/app.log")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

