from enum import Enum
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class EncryptionAlgorithm(str, Enum):
    """Supported encryption algorithms"""
    AES_256_GCM = "AES-256-GCM"
    AES_256_CBC = "AES-256-CBC"

class KeyStatus(str, Enum):
    """Key status"""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ROTATED = "ROTATED"
    COMPROMISED = "COMPROMISED"

class EncryptionContext(BaseModel):
    """Encryption context for operations"""
    algorithm: EncryptionAlgorithm = Field(default=EncryptionAlgorithm.AES_256_GCM)
    key_id: str
    key_version: str = "1"
    iv: Optional[bytes] = None
    auth_tag: Optional[bytes] = None

class DataKey(BaseModel):
    """Data key wrapped by master key"""
    key_id: str
    encrypted_key: bytes  # Encrypted with master key
    key_material_hash: str  # Hash of the plaintext key material for verification
    created_at: datetime = Field(default_factory=datetime.now)
