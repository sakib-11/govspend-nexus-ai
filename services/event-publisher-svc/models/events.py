from enum import Enum
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4

class EventType(str, Enum):
    """Types of risk events"""
    CASE_CREATED = "case_created"
    RISK_SCORED = "risk_scored"
    HIGH_RISK_ALERT = "high_risk_alert"
    BORDERLINE_RISK = "borderline_risk"
    CASE_ASSIGNED = "case_assigned"
    CASE_UPDATED = "case_updated"
    CASE_ESCALATED = "case_escalated"
    CASE_RESOLVED = "case_resolved"
    NOTIFICATION_SENT = "notification_sent"
    ALERT_TRIGGERED = "alert_triggered"
    
class PriorityLevel(str, Enum):
    """Priority levels for events"""
    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"         # Action within 1 hour
    MEDIUM = "medium"     # Action within 4 hours
    LOW = "low"          # Action within 24 hours
    BACKGROUND = "background"  # No immediate action

class EventSource(str, Enum):
    """Source of the event"""
    SCORING_SERVICE = "scoring_service"
    EVIDENCE_BUNDLE_SERVICE = "evidence_bundle_service"
    DETECTION_SERVICE = "detection_service"
    HUMAN_REVIEW = "human_review"
    SYSTEM_AUTO = "system_auto"
    EXTERNAL = "external"

class CaseStatus(str, Enum):
    """Status of a risk case"""
    NEW = "new"
    ASSIGNED = "assigned"
    UNDER_REVIEW = "under_review"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REJECTED = "rejected"

class RiskEvent(BaseModel):
    """Base risk event model"""
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
    
    # Core identifiers
    event_id: str = Field(default_factory=lambda: f"evt-{uuid4().hex[:12]}")
    event_type: EventType
    event_version: str = "1.0"
    
    # Source
    source: EventSource
    source_id: str  # Original ID from source system
    
    # Transaction reference
    transaction_id: str
    bundle_id: Optional[str] = None
    
    # Risk data
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_tier: str
    priority: PriorityLevel
    
    # Case data
    case_id: Optional[str] = None
    case_status: Optional[CaseStatus] = None
    
    # Details
    summary: str
    description: Optional[str] = None
    detectors_triggered: List[str] = Field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    
    # Timestamps
    occurred_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    # Tracking
    processed: bool = False
    acknowledged: bool = False
    acknowledgment_by: Optional[str] = None
    acknowledgment_at: Optional[datetime] = None
    
    def is_high_priority(self) -> bool:
        """Check if event is high priority"""
        return self.priority in [PriorityLevel.CRITICAL, PriorityLevel.HIGH]
    
    def is_expired(self) -> bool:
        """Check if event has expired"""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at

class PriorityQueueItem(BaseModel):
    """Item in priority queue"""
    event_id: str
    transaction_id: str
    priority: PriorityLevel
    payload: Dict[str, Any]
    enqueued_at: datetime = Field(default_factory=datetime.now)
    attempts: int = 0
    max_attempts: int = 3
    last_attempt_at: Optional[datetime] = None
    error: Optional[str] = None
    
    def should_retry(self) -> bool:
        """Check if item should be retried"""
        return self.attempts < self.max_attempts
    
    def increment_attempts(self):
        """Increment attempt counter"""
        self.attempts += 1
        self.last_attempt_at = datetime.now()

class Alert(BaseModel):
    """Alert model for notifications"""
    alert_id: str = Field(default_factory=lambda: f"alt-{uuid4().hex[:8]}")
    event_id: str
    priority: PriorityLevel
    alert_type: str  # email, slack, webhook, sms
    
    # Content
    subject: str
    message: str
    recipients: List[str] = Field(default_factory=list)
    channels: List[str] = Field(default_factory=list)
    
    # Data
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Status
    sent: bool = False
    sent_at: Optional[datetime] = None
    delivered: bool = False
    delivered_at: Optional[datetime] = None
    read: bool = False
    read_at: Optional[datetime] = None
    
    # Retry
    retry_count: int = 0
    max_retries: int = 3
    error: Optional[str] = None

class NotificationPreference(BaseModel):
    """User notification preferences"""
    user_id: str
    email: Optional[str] = None
    slack_webhook: Optional[str] = None
    phone: Optional[str] = None
    
    # Thresholds
    min_risk_score_for_notification: float = 0.40
    notify_on_high_risk: bool = True
    notify_on_borderline: bool = False
    notify_on_low_risk: bool = False
    
    # Channels
    email_enabled: bool = True
    slack_enabled: bool = False
    sms_enabled: bool = False
    
    # Hours
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    timezone: str = "UTC"