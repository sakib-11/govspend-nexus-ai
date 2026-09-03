from pydantic_settings import BaseSettings
from typing import Optional, List, Dict
from functools import lru_cache

class LedgerConfig(BaseSettings):
    """Ledger Service configuration"""
    
    # Service
    service_name: str = "ledger-svc"
    port: int = 8011
    debug: bool = False
    
    # Database (Secure DB - separate from main DB)
    db_host: str = "ledger-db.internal"
    db_port: int = 5432
    db_name: str = "govspend_ledger"
    db_user: str = "ledger_user"
    db_password: str = "ledger_secure_pass"
    db_ssl_mode: str = "require"
    db_pool_min: int = 5
    db_pool_max: int = 20
    
    # HSM/KMS Configuration
    hsm_enabled: bool = True
    hsm_type: str = "aws_kms"  # aws_kms, azure_keyvault, hashicorp_vault, local
    hsm_endpoint: Optional[str] = None
    hsm_region: Optional[str] = "us-east-1"
    hsm_key_id: Optional[str] = None
    
    # Key Configuration
    master_key_id: str = "ledger-master-key"
    key_rotation_days: int = 90
    encryption_algorithm: str = "AES-256-GCM"
    key_derivation_iterations: int = 100000
    
    # Local HSM (Development only)
    local_hsm_key: Optional[str] = None
    
    # Service Authentication (mTLS)
    tls_enabled: bool = True
    tls_cert_path: str = "/certs/ledger.crt"
    tls_key_path: str = "/certs/ledger.key"
    tls_ca_path: str = "/certs/ca.crt"
    
    # Allowed Services
    allowed_services: List[str] = ["unmask-svc", "admin-svc"]
    
    # Audit
    audit_enabled: bool = True
    audit_log_path: str = "/var/log/ledger/audit.log"
    
    # Performance
    cache_ttl_seconds: int = 300
    max_batch_size: int = 100
    
    class Config:
        env_prefix = "LEDGER_"
        env_file = ".env.ledger"

@lru_cache()
def get_config() -> LedgerConfig:
    return LedgerConfig()
