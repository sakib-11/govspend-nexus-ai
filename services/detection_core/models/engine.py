"""Models for Detection Engine."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DetectorStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DetectorExecution(BaseModel):
    """Individual detector execution record"""
    detector_id: str
    detector_name: str
    status: DetectorStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    retry_count: int = 0


class TransactionContext(BaseModel):
    """Transaction processing context"""
    transaction_id: str
    source_id: str
    canonical_transaction: Dict[str, Any]
    ingested_at: datetime
    processing_started: datetime
    processing_completed: Optional[datetime] = None

    # Metadata
    priority: str = "normal"
    department_id: Optional[str] = None
    vendor_id: Optional[str] = None
    amount: Optional[float] = None
    transaction_date: Optional[datetime] = None

    # Execution tracking
    detector_executions: List[DetectorExecution] = Field(default_factory=list)
    total_duration_ms: Optional[float] = None
    is_processed: bool = False
    error: Optional[str] = None


class EngineConfig(BaseModel):
    """Engine configuration"""
    max_concurrent_transactions: int = 10
    detector_timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5
    parallel_detectors: bool = True
    batch_size: int = 100
    processing_timeout_seconds: int = 60