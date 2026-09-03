"""Event Publisher - Publishes events to Redis Streams."""

import json
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import redis.asyncio as redis

from ..models.events import DetectionEvent, EventType, SignalsGeneratedEvent
from ..models.signals import SignalGroup
from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class EventPublisher:
    """Publish events to Redis Streams"""

    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.stream_name = settings.EVENT_STREAM or "detection.events"

    async def publish(self, event: DetectionEvent) -> bool:
        """Publish an event to Redis Stream"""
        try:
            event_data = {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "transaction_id": event.transaction_id,
                "payload": json.dumps(event.payload, default=str),
                "created_at": event.created_at.isoformat(),
                "source": event.source,
                "correlation_id": event.correlation_id or "",
                "metadata": json.dumps(event.metadata, default=str)
            }

            # Publish to stream
            await self.redis_client.xadd(
                self.stream_name,
                event_data,
                maxlen=10000  # Keep last 10k events
            )

            logger.debug(f"Published event {event.event_id} to {self.stream_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return False

    async def publish_signals_generated(
        self,
        transaction_id: str,
        signal_group: SignalGroup,
        detector_results: Dict[str, Any],
        execution_time_ms: float
    ) -> bool:
        """Publish signals generated event"""
        event_id = str(uuid.uuid4())

        payload = {
            "transaction_id": transaction_id,
            "signal_group": signal_group.dict(),
            "total_signals": signal_group.total_signals,
            "max_signal": signal_group.max_signal_value,
            "avg_signal": signal_group.average_signal_value,
            "execution_time_ms": execution_time_ms,
            "detector_results": detector_results,
            "generated_at": datetime.utcnow().isoformat()
        }

        event = DetectionEvent(
            event_id=event_id,
            event_type=EventType.SIGNALS_GENERATED,
            transaction_id=transaction_id,
            payload=payload,
            correlation_id=transaction_id,
            metadata={
                "signal_count": signal_group.total_signals,
                "max_signal": signal_group.max_signal_value
            }
        )

        return await self.publish(event)

    async def publish_detection_started(self, transaction_id: str) -> bool:
        """Publish detection started event"""
        event_id = str(uuid.uuid4())

        event = DetectionEvent(
            event_id=event_id,
            event_type=EventType.DETECTION_STARTED,
            transaction_id=transaction_id,
            payload={"transaction_id": transaction_id},
            correlation_id=transaction_id
        )

        return await self.publish(event)

    async def publish_detection_completed(
        self,
        transaction_id: str,
        execution_time_ms: float,
        signals_count: int
    ) -> bool:
        """Publish detection completed event"""
        event_id = str(uuid.uuid4())

        event = DetectionEvent(
            event_id=event_id,
            event_type=EventType.DETECTION_COMPLETED,
            transaction_id=transaction_id,
            payload={
                "execution_time_ms": execution_time_ms,
                "signals_count": signals_count
            },
            correlation_id=transaction_id
        )

        return await self.publish(event)

    async def publish_detection_failed(
        self,
        transaction_id: str,
        error: str
    ) -> bool:
        """Publish detection failed event"""
        event_id = str(uuid.uuid4())

        event = DetectionEvent(
            event_id=event_id,
            event_type=EventType.DETECTION_FAILED,
            transaction_id=transaction_id,
            payload={"error": error},
            correlation_id=transaction_id
        )

        return await self.publish(event)