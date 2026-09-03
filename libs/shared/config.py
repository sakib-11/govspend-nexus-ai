"""Configuration management for GovSpend Nexus AI"""
import os
from typing import Optional, List
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "GovSpend Nexus AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    APP_VERSION: str = "1.0.0"
    SECRET_KEY: str
    
    # Database
    DATABASE_URL: str
    DATABASE_TEST_URL: Optional[str] = None
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Redis
    REDIS_URL: str
    REDIS_TEST_URL: Optional[str] = None
    REDIS_MAX_CONNECTIONS: int = 10
    CACHE_TTL_SECONDS: int = 3600
    
    # Security
    HMAC_KEY: str
    KMS_KEY_ID: str = "dev-kms-key"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60
    MFA_ENABLED: bool = False
    
    # LLM
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL_HIGH: str = "gpt-4o-mini"
    LLM_MODEL_MEDIUM: str = "gpt-4o-mini"
    LLM_MODEL_LOW: Optional[str] = None
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2048
    RAG_TOP_K: int = 3
    
    # Thresholds
    HIGH_RISK_THRESHOLD: float = 0.75
    BORDERLINE_THRESHOLD: float = 0.40
    REVIEW_THRESHOLD: float = 100000
    MIN_PEER_SAMPLE: int = 5
    CONFIDENCE_SAMPLE_SIZE: int = 10
    
    # Detector Weights
    WEIGHT_PRICE_DEVIATION: float = 0.30
    WEIGHT_DUPLICATE_FUZZY: float = 0.20
    WEIGHT_VENDOR_GRAPH: float = 0.20
    WEIGHT_CONTRACT_SPLITTING: float = 0.15
    WEIGHT_TIMING_ANOMALY: float = 0.10
    WEIGHT_APPROVAL_VELOCITY: float = 0.05
    
    @property
    def detector_weights(self) -> dict:
        """Get all detector weights as a dictionary"""
        return {
            "price_deviation": self.WEIGHT_PRICE_DEVIATION,
            "duplicate_fuzzy": self.WEIGHT_DUPLICATE_FUZZY,
            "vendor_graph_risk": self.WEIGHT_VENDOR_GRAPH,
            "contract_splitting": self.WEIGHT_CONTRACT_SPLITTING,
            "timing_anomaly": self.WEIGHT_TIMING_ANOMALY,
            "approval_velocity": self.WEIGHT_APPROVAL_VELOCITY,
        }
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RATE_LIMIT: int = 100
    API_RATE_PERIOD: int = 60
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Service Ports
    PORT_INGESTION: int = 8001
    PORT_DETECTION: int = 8002
    PORT_SCORING: int = 8003
    PORT_GATEWAY: int = 8004
    PORT_EXPLANATION: int = 8005
    PORT_MASKED_EVIDENCE: int = 8006
    PORT_LEDGER: int = 8007
    PORT_UNMASK: int = 8008
    PORT_AUDIT_LOG: int = 8009
    PORT_DIGITAL_TWIN: int = 8010
    
    # Docker
    DOCKER_REGISTRY: str = "localhost:5000"
    DOCKER_NAMESPACE: str = "govspend"
    
    # Testing
    TEST_TIMEOUT: int = 30
    TEST_RETRIES: int = 3
    TEST_COVERAGE_THRESHOLD: int = 80
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
