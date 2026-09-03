from pydantic_settings import BaseSettings
from typing import Optional, List, Dict
from functools import lru_cache

class PolicyIngestionConfig(BaseSettings):
    """Policy Document Ingestion configuration"""
    
    # Service
    service_name: str = "policy-ingestion-svc"
    port: int = 8014
    debug: bool = False
    
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "govspend_policies"
    db_user: str = "policy_user"
    db_password: str = "policy_pass"
    
    # Vector Settings
    vector_dimension: int = 1536  # OpenAI ada-002
    vector_distance: str = "cosine"
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    # Embedding
    embedding_model: str = "text-embedding-ada-002"
    embedding_provider: str = "openai"
    embedding_batch_size: int = 20
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None
    
    # Document Processing
    max_file_size_mb: int = 100
    supported_formats: List[str] = ["pdf", "docx", "txt", "html", "md"]
    ocr_enabled: bool = True
    language_detection: bool = True
    
    # Metadata
    policy_categories: List[str] = ["gfr", "procurement", "privacy", "audit", "financial"]
    
    # Performance
    batch_size: int = 50
    parallel_workers: int = 4
    cache_ttl_seconds: int = 3600
    
    # Storage
    storage_path: str = "/var/lib/policies"
    temp_path: str = "/tmp/policy_ingestion"
    
    class Config:
        env_prefix = "POLICY_"
        env_file = ".env.policy"

@lru_cache()
def get_config() -> PolicyIngestionConfig:
    return PolicyIngestionConfig()
