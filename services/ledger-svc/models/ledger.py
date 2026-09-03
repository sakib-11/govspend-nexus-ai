from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4

class EntityType(str, Enum):
    """Types of entities stored in ledger"""
    VENDOR = "vendor"
    OFFICIAL = "official"
    TRANSACTION = "transaction"
    INVOICE = "invoice"
    USER = "user"
    DEPARTMENT = "department"

class AccessLevel(str, Enum):
    """Access levels for ledger"""
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"
    ADMIN = "ADMIN"

class LedgerEntry(BaseModel):
    """Ledger entry with encrypted data"""
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
    
    entry_id: UUID = Field(default_factory=uuid4)
    entity_type: EntityType
    entity_token: str
    encrypted_data: bytes
    encryption_key_id: str
    encryption_algorithm: str
    iv: bytes
    auth_tag: bytes
    data_hash: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None
    is_active: bool = True

class LedgerCreateRequest(BaseModel):
    """Request to create ledger entry"""
    entity_type: EntityType
    entity_token: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

class LedgerReadRequest(BaseModel):
    """Request to read ledger entry"""
    entity_type: EntityType
    entity_token: str
    decrypt: bool = True

class LedgerUpdateRequest(BaseModel):
    """Request to update ledger entry"""
    entity_type: EntityType
    entity_token: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

class LedgerResponse(BaseModel):
    """Ledger response"""
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
    
    entry_id: UUID
    entity_type: str
    entity_token: str
    data: Optional[Dict[str, Any]] = None
    encrypted: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    access_count: int
    last_accessed_at: Optional[datetime] = None

class LedgerAuditLog(BaseModel):
    """Audit log entry"""
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
    
    audit_id: UUID = Field(default_factory=uuid4)
    entry_id: UUID
    action: str
    user_id: str
    service_name: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    previous_hash: Optional[str] = None
    current_hash: Optional[str] = None
    payload_hash: Optional[str] = None

class KeyMetadata(BaseModel):
    """Key metadata for encryption"""
    key_id: str
    key_version: str
    key_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    activated_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    is_active: bool = True
    rotated_from: Optional[str] = None
    created_by: str
