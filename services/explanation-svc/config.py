"""Production-ready configuration for Explanation Service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class ExplanationConfig(BaseSettings):
    """Production-ready Explanation Service configuration with validation."""

    model_config = SettingsConfigDict(
        env_prefix="EXPLANATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============================================
    # Service Configuration
    # ============================================
    service_name: str = "explanation-svc"
    port: int = Field(default=8017, ge=1, le=65535)
    host: str = "0.0.0.0"
    debug: bool = False
    log_level: str = "INFO"
    log_format: str = "json"

    # ============================================
    # CORS Configuration
    # ============================================
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )

    # ============================================
    # Database Configuration
    # ============================================
    db_host: str = "localhost"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "govspend_explanations"
    db_user: str = "explanation_user"
    db_password: str = "explanation_pass"
    db_min_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_pool_size: int = Field(default=20, ge=1, le=100)
    db_timeout: int = Field(default=30, ge=1, le=300)

    # ============================================
    # Redis Configuration
    # ============================================
    redis_host: str = "localhost"
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_db: int = Field(default=0, ge=0, le=15)
    redis_password: Optional[str] = None
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=3600, ge=0, le=86400)

    # ============================================
    # LLM Configuration
    # ============================================
    llm_provider: str = "groq"
    llm_model: str = "mixtral-8x7b-32768"
    groq_api_key: Optional[str] = None
    groq_model: str = "mixtral-8x7b-32768"
    groq_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    groq_max_tokens: int = Field(default=2048, ge=1, le=4096)
    groq_top_p: float = Field(default=0.9, ge=0.0, le=1.0)

    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"
    openai_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    openai_max_tokens: int = Field(default=2000, ge=1, le=4096)

    # ============================================
    # Validation Configuration
    # ============================================
    max_regeneration_attempts: int = Field(default=2, ge=0, le=10)
    validation_strictness: str = "strict"
    require_citations: bool = True
    min_grounding_score: float = Field(default=0.7, ge=0.0, le=1.0)
    min_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    # ============================================
    # Fallback Configuration
    # ============================================
    fallback_enabled: bool = True

    # ============================================
    # Cache Configuration
    # ============================================
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=3600, ge=0, le=86400)

    # ============================================
    # Rate Limiting
    # ============================================
    rate_limit_max_requests: int = Field(default=200, ge=1, le=1000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)

    # ============================================
    # Performance Configuration
    # ============================================
    timeout_seconds: int = Field(default=60, ge=1, le=600)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: float = Field(default=2.0, ge=0.1, le=60.0)

    # ============================================
    # Security Configuration
    # ============================================
    jwt_secret: Optional[str] = None
    hmac_key: Optional[str] = None

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

    @validator("validation_strictness")
    def validate_validation_strictness(cls, v):
        valid_strictness = ["strict", "lenient", "permissive"]
        v_lower = v.lower()
        if v_lower not in valid_strictness:
            raise ValueError(f"Invalid validation strictness: {v}. Must be one of {valid_strictness}")
        return v_lower

    @validator("llm_provider")
    def validate_llm_provider(cls, v):
        valid_providers = ["groq", "openai"]
        v_lower = v.lower()
        if v_lower not in valid_providers:
            raise ValueError(f"Invalid LLM provider: {v}. Must be one of {valid_providers}")
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
    def CACHE_ENABLED(self) -> bool:
        return self.cache_enabled

    @property
    def CACHE_TTL_SECONDS(self) -> int:
        return self.cache_ttl_seconds

    @property
    def GROQ_TEMPERATURE(self) -> float:
        return self.groq_temperature

    @property
    def GROQ_MAX_TOKENS(self) -> int:
        return self.groq_max_tokens

    @property
    def GROQ_TOP_P(self) -> float:
        return self.groq_top_p

    @property
    def MAX_REGENERATION_ATTEMPTS(self) -> int:
        return self.max_regeneration_attempts

    @property
    def MIN_GROUNDING_SCORE(self) -> float:
        return self.min_grounding_score

    @property
    def MIN_CONFIDENCE_THRESHOLD(self) -> float:
        return self.min_confidence_threshold

    @property
    def REQUIRE_CITATIONS(self) -> bool:
        return self.require_citations

    @property
    def VALIDATION_STRICTNESS(self) -> str:
        return self.validation_strictness


    @property
    def FALLBACK_ENABLED(self) -> bool:
        return self.fallback_enabled

@lru_cache()
def get_config() -> ExplanationConfig:
    """Get cached configuration instance."""
    return ExplanationConfig()


def setup_logging(config: ExplanationConfig) -> None:
    """Configure structured logging based on environment."""
    log_level = getattr(logging, config.log_level)

    if config.log_format == "json":
        # JSON logging for production
        from pythonjsonlogger import json as json_logger

        class JsonFormatter(json_logger.JsonFormatter):
            def add_fields(self, log_record, record, message_dict):
                super().add_fields(log_record, record, message_dict)
                log_record["level"] = record.levelname
                log_record["service"] = config.service_name
                log_record["timestamp"] = datetime.now(timezone.utc).isoformat() + "Z"

        formatter = JsonFormatter("%(timestamp)s %(level)s %(service)s %(message)s")
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
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

