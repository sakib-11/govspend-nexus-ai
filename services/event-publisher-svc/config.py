from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List, Dict
from functools import lru_cache

class EventPublisherConfig(BaseSettings):
    """Event publisher configuration"""
    
    # Service
    service_name: str = "event-publisher-svc"
    port: int = 8006
    debug: bool = False
    
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "govspend"
    db_user: str = "events_user"
    db_password: str = "events_pass"
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Streams
    input_stream: str = "bundle.events"
    output_stream: str = "risk.events"
    priority_stream: str = "risk.priority"
    error_stream: str = "event.errors"
    consumer_group: str = "event-publisher-group"
    consumer_name: str = "event-publisher-1"
    
    # Priority Queue Settings
    priority_queue_key: str = "risk_priority_queue"
    critical_queue: str = "critical_tasks"
    high_queue: str = "high_priority_tasks"
    medium_queue: str = "medium_priority_tasks"
    low_queue: str = "low_priority_tasks"
    
    # Alert Settings
    alert_threshold_high: float = 0.75
    alert_threshold_borderline: float = 0.40
    alert_cooldown_minutes: int = 30  # Prevent alert spam
    
    # Notification Channels
    slack_enabled: bool = False
    slack_webhook_url: Optional[str] = None
    email_enabled: bool = False
    email_smtp_host: Optional[str] = None
    email_smtp_port: int = 587
    email_sender: Optional[str] = None
    webhook_enabled: bool = False
    webhook_endpoints: List[str] = Field(default_factory=list)
    
    # Kafka (optional)
    kafka_enabled: bool = False
    kafka_bootstrap_servers: Optional[str] = None
    kafka_topic_risk_events: str = "govspend.risk.events"
    kafka_topic_cases: str = "govspend.cases"
    
    # Performance
    batch_size: int = 50
    publish_timeout_seconds: int = 10
    worker_count: int = 5
    
    class Config:
        env_prefix = "EVENT_"
        env_file = ".env.event"

@lru_cache()
def get_config() -> EventPublisherConfig:
    return EventPublisherConfig()