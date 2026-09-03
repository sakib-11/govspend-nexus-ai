"""Event models for Detection Engine."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    TRANSACTION_RECEIVED = "transaction.received"
    DETECTION_STARTED = "detection.started"
    DETECTION_COMPLETED = "detection.completed"
    DETECTION_FAILED = "detection.failed"
    SIGNALS_GENERATED = "signals.generated"
    SIGNAL_ESCALATED = "signal.escalated"
    DETECTOR_COMPLETED = "detector.completed"
    DETECTOR_FAILED = "detector.failed"
    ENGINE_ERROR = "engine.error"


class DetectionEvent(BaseModel):
    """Event emitted by detection engine"""
    event_id: str
    event_type: EventType
    transaction_id: str
    payload: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "detection-core"
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SignalsGeneratedEvent(BaseModel):
    """Signals generated event payload"""
    transaction_id: str
    signal_group: Dict[str, Any]
    total_signals: int
    max_signal: float
    avg_signal: float
    execution_time_ms: float
    detector_results: Dict[str, Any]
    generated_at: datetime = Field(default_factory=datetime.utcnow)