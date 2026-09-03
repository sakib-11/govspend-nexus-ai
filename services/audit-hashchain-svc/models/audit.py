from typing import List, Optional, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4

class HashChainEntry(BaseModel):
    """Hash chain entry"""
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
    
    entry_id: UUID = Field(default_factory=uuid4)
    audit_id: UUID
    sequence_number: int
    previous_hash: str
    current_hash: str
    payload_hash: str
    actor: str
    action: str
    resource: str
    resource_token: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    merkle_root: Optional[str] = None
    merkle_path: Optional[List[str]] = None
    signature: Optional[str] = None
    verified: bool = False
    verified_at: Optional[datetime] = None

class DailySnapshot(BaseModel):
    """Daily snapshot of hash chain"""
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
    
    snapshot_id: UUID = Field(default_factory=uuid4)
    snapshot_date: date
    start_sequence: int
    end_sequence: int
    merkle_root: str
    root_hash: str
    total_entries: int
    snapshot_hash: str
    external_reference: Optional[str] = None
    blockchain_tx_hash: Optional[str] = None
    notary_signature: Optional[str] = None
    notary_timestamp: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    verified: bool = False
    verified_at: Optional[datetime] = None

class MerkleTree(BaseModel):
    """Merkle tree for snapshot"""
    root_hash: str
    leaf_hashes: List[str]
    tree_levels: List[List[str]]
    total_leaves: int

class NotaryRecord(BaseModel):
    """External notary record"""
    record_id: UUID = Field(default_factory=uuid4)
    snapshot_id: UUID
    notary_type: str
    external_id: str
    root_hash: str
    signature: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    verification_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class VerificationResult(BaseModel):
    """Verification result"""
    is_valid: bool
    entries_checked: int
    tampered_entries: List[UUID] = Field(default_factory=list)
    missing_entries: List[int] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    verified_at: datetime = Field(default_factory=datetime.now)
    external_verification: Optional[Dict[str, Any]] = None
