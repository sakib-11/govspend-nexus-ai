"""Stream models for Redis Streams."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class StreamName(str, Enum):
    """Available stream names."""
    TX_INGESTED = "tx.ingested"
    TX_VALIDATED = "tx.validated"
    TX_DETECTED = "tx.detected"
    TX_SCORED = "tx.scored"
    TX_CANONICALIZED = "tx.canonicalized"
    TX_ERROR = "tx.error"
    TX_AUDIT = "tx.audit"

class StreamMessage(BaseModel):
    """Base stream message."""
    stream: StreamName
    message_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TransactionStreamMessage(StreamMessage):
    """Transaction stream message."""
    transaction_id: str
    source_id: str
    transaction_type: str
    status: str
    version: str = "1.0"

class PublishResult(BaseModel):
    """Result of publishing to stream."""
    success: bool
    stream: str
    message_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class StreamStats(BaseModel):
    """Stream statistics."""
    stream: str
    total_messages: int
    last_message_id: Optional[str] = None
    last_message_timestamp: Optional[datetime] = None
    consumers: List[str] = Field(default_factory=list)
    pending_messages: int = 0
    oldest_message_age_seconds: Optional[float] = None

