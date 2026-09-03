"""Audit consumer — ingest audit events from external sources (Redis streams, queues)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from models.audit import AuditEventType, AuditSeverity
from services.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class AuditConsumer:
    """Consume audit events from an external source and write them to the log.

    This is a lightweight adapter; in production it would subscribe to a
    Redis Stream or Kafka topic.
    """

    def __init__(self, audit_logger: AuditLogger) -> None:
        self._logger = audit_logger

    async def process_event(self, raw: Dict[str, Any]) -> None:
        """Process a single raw event dict."""
        try:
            event_type_str = raw.get("event_type", "system_event")
            try:
                event_type = AuditEventType(event_type_str)
            except ValueError:
                event_type = AuditEventType.SYSTEM_EVENT

            severity_str = raw.get("severity", "info")
            try:
                severity = AuditSeverity(severity_str)
            except ValueError:
                severity = AuditSeverity.INFO

            await self._logger.log(
                event_type=event_type,
                user_id=raw.get("user_id", "system"),
                action=raw.get("action", "external_event"),
                resource_type=raw.get("resource_type", "external"),
                request_id=raw.get("request_id", ""),
                severity=severity,
                resource_id=raw.get("resource_id"),
                jurisdiction_id=raw.get("jurisdiction_id"),
                action_details=raw.get("action_details", {}),
                metadata=raw.get("metadata", {}),
                tags=raw.get("tags", []),
            )
        except Exception:
            logger.exception("Failed to process audit event: %s", raw)
