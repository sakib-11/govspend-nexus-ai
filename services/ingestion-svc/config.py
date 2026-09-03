"""Configuration for the GovSpend Nexus Ingestion Service."""

from enum import Enum
from pathlib import Path
from typing import List, Optional, Set

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Supported application environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env."""

    # ------------------------------------------------------------------
    # General / Application
    # ------------------------------------------------------------------
    app_name: str = "GovSpend Nexus - Ingestion Service"
    app_version: str = "1.0.0"

    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True

    host: str = "0.0.0.0"
    port: int = 8001

    allowed_origins: List[str] = ["*"]

    # ------------------------------------------------------------------
    # File Upload
    # ------------------------------------------------------------------
    max_file_size: int = 10 * 1024 * 1024  # 10 MB

    allowed_extensions: Set[str] = {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".bmp",
    }

    allowed_mime_types: Set[str] = {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/bmp",
    }

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------
    ocr_default_engine: str = "tesseract"
    ocr_engine: str = "tesseract"

    ocr_cache_ttl: int = 86400
    ocr_max_file_size: int = 50 * 1024 * 1024

    # ------------------------------------------------------------------
    # Tesseract
    # ------------------------------------------------------------------
    tesseract_path: Optional[str] = "/usr/bin/tesseract"
    tesseract_language: str = "eng"
    tesseract_lang: str = "eng"
    tesseract_psm: int = 6

    # ------------------------------------------------------------------
    # AWS Textract
    # ------------------------------------------------------------------
    aws_region: str = "us-east-1"
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    storage_type: str = "local"

    upload_dir: str = "./uploads"
    processed_dir: str = "./processed"
    temp_dir: str = "./temp"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    min_total_amount: float = 0.01
    max_total_amount: float = 10_000_000_000.0

    vendor_name_min_length: int = 2
    vendor_name_max_length: int = 200

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379"

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = "INFO"

    # ------------------------------------------------------------------
    # Pydantic configuration
    # ------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Compatibility properties
    #
    # These allow code written using either naming style to continue
    # working without duplicating the underlying configuration.
    # ------------------------------------------------------------------

    @property
    def HOST(self) -> str:
        """Compatibility alias for host."""
        return self.host

    @property
    def PORT(self) -> int:
        """Compatibility alias for port."""
        return self.port

    @property
    def MAX_FILE_SIZE(self) -> int:
        """Compatibility alias for max_file_size."""
        return self.max_file_size

    @property
    def ALLOWED_EXTENSIONS(self) -> Set[str]:
        """Compatibility alias for allowed_extensions."""
        return self.allowed_extensions

    @property
    def ALLOWED_MIME_TYPES(self) -> Set[str]:
        """Compatibility alias for allowed_mime_types."""
        return self.allowed_mime_types

    @property
    def OCR_ENGINE(self) -> str:
        """Compatibility alias for ocr_engine."""
        return self.ocr_engine

    @property
    def TESSERACT_PATH(self) -> Optional[str]:
        """Compatibility alias for tesseract_path."""
        return self.tesseract_path

    @property
    def TESSERACT_LANG(self) -> str:
        """Compatibility alias for tesseract_lang."""
        return self.tesseract_lang

    @property
    def TESSERACT_PSM(self) -> int:
        """Compatibility alias for tesseract_psm."""
        return self.tesseract_psm

    @property
    def AWS_REGION(self) -> str:
        """Compatibility alias for aws_region."""
        return self.aws_region

    @property
    def AWS_ACCESS_KEY(self) -> Optional[str]:
        """Compatibility alias for aws_access_key."""
        return self.aws_access_key

    @property
    def AWS_SECRET_KEY(self) -> Optional[str]:
        """Compatibility alias for aws_secret_key."""
        return self.aws_secret_key

    @property
    def STORAGE_TYPE(self) -> str:
        """Compatibility alias for storage_type."""
        return self.storage_type

    @property
    def UPLOAD_DIR(self) -> str:
        """Compatibility alias for upload_dir."""
        return self.upload_dir

    @property
    def TEMP_DIR(self) -> str:
        """Compatibility alias for temp_dir."""
        return self.temp_dir

    @property
    def MIN_TOTAL_AMOUNT(self) -> float:
        """Compatibility alias for min_total_amount."""
        return self.min_total_amount

    @property
    def MAX_TOTAL_AMOUNT(self) -> float:
        """Compatibility alias for max_total_amount."""
        return self.max_total_amount

    @property
    def VENDOR_NAME_MIN_LENGTH(self) -> int:
        """Compatibility alias for vendor_name_min_length."""
        return self.vendor_name_min_length

    @property
    def VENDOR_NAME_MAX_LENGTH(self) -> int:
        """Compatibility alias for vendor_name_max_length."""
        return self.vendor_name_max_length

    @property
    def REDIS_URL(self) -> str:
        """Compatibility alias for redis_url."""
        return self.redis_url

    @property
    def LOG_LEVEL(self) -> str:
        """Compatibility alias for log_level."""
        return self.log_level

    # ------------------------------------------------------------------
    # Compatibility with your previous main.py
    # ------------------------------------------------------------------

    @property
    def app_env(self) -> str:
        """Return environment as a string."""
        return self.environment.value

    @property
    def port_ingestion(self) -> int:
        """Return ingestion service port."""
        return self.port


settings = Settings()
