"""Event bus — publish/subscribe for inter-service communication."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventBus:
    """In-process event bus backed by an in-memory pub/sub registry.

    For production, wire this to Redis Streams or Kafka.  The in-memory
    version keeps services testable without external infrastructure.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._published: List[Dict[str, Any]] = []

    def subscribe(self, topic: str, handler: Callable) -> None:
        self._subscribers.setdefault(topic, []).append(handler)

    async def publish(self, topic: str, event: Dict[str, Any]) -> int:
        """Publish an event.  Returns the number of handlers invoked."""
        self._published.append({"topic": topic, "event": event})
        handlers = self._subscribers.get(topic, [])
        invoked = 0
        for handler in handlers:
            try:
                if callable(handler):
                    result = handler(event)
                    if hasattr(result, "__await__"):
                        await result
                    invoked += 1
            except Exception:
                logger.exception("Event handler failed for topic=%s", topic)
        return invoked

    def get_published(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        if topic:
            return [p for p in self._published if p["topic"] == topic]
        return list(self._published)

    def clear(self) -> None:
        self._published.clear()


# Singleton
_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
