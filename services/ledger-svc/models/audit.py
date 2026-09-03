from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4

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
