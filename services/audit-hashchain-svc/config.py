from pydantic_settings import BaseSettings
from typing import Optional, List, Dict
from functools import lru_cache

class HashChainConfig(BaseSettings):
    """Hash Chain Service configuration"""
    
    # Service
    service_name: str = "audit-hashchain-svc"
    port: int = 8013
    debug: bool = False
    
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "govspend_audit"
    db_user: str = "hashchain_user"
    db_password: str = "hashchain_pass"
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Audit Stream
    audit_stream: str = "audit.events"
    consumer_group: str = "hashchain-group"
    consumer_name: str = "hashchain-consumer-1"
    
    # Hash Chain
    genesis_hash: str = "0000000000000000000000000000000000000000000000000000000000000000"
    hash_algorithm: str = "sha256"
    merkle_tree_enabled: bool = True
    
    # Notary (TUF/External)
    notary_enabled: bool = True
    notary_type: str = "tuf"  # tuf, sigstore, custom
    notary_endpoint: Optional[str] = None
    notary_api_key: Optional[str] = None
    notary_cert_path: Optional[str] = None
    
    # Blockchain
    blockchain_enabled: bool = False
    blockchain_type: str = "ethereum"  # ethereum, hyperledger, custom
    blockchain_rpc_url: Optional[str] = None
    blockchain_contract_address: Optional[str] = None
    blockchain_private_key: Optional[str] = None
    blockchain_gas_limit: int = 200000
    
    # Snapshot
    snapshot_interval_hours: int = 24
    snapshot_retention_days: int = 365
    snapshot_storage_path: str = "/var/lib/audit/snapshots"
    
    # Verification
    auto_verify: bool = True
    verification_interval_hours: int = 6
    alert_on_tamper: bool = True
    alert_webhook_url: Optional[str] = None
    
    # Performance
    batch_size: int = 1000
    flush_interval_seconds: int = 60
    cache_ttl_seconds: int = 3600
    
    class Config:
        env_prefix = "HASHCHAIN_"
        env_file = ".env.hashchain"

@lru_cache()
def get_config() -> HashChainConfig:
    return HashChainConfig()
