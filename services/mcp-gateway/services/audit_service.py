"""Audit service — structured audit logging for all tool executions."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class AuditService:
    """Append-only audit log backed by an in-memory list.

    In production, swap this for DB / Kafka / S3 writes.
    """

    def __init__(self, max_entries: int = 10_000) -> None:
        self._entries: List[Dict[str, Any]] = []
        self._max = max_entries

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        user_id: str,
        tool_name: str,
        request_id: str,
        action: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Record an audit event.  Returns the ``audit_id``."""
        audit_id = f"aud-{uuid4().hex[:10]}"
        entry: Dict[str, Any] = {
            "audit_id": audit_id,
            "user_id": user_id,
            "tool_name": tool_name,
            "request_id": request_id,
            "action": action,
            "success": success,
            "ip_address": ip_address,
            "session_id": session_id,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._entries.append(entry)
        # Evict oldest if over capacity
        if len(self._entries) > self._max:
            self._entries = self._entries[-self._max:]

        logger.info(
            "AUDIT %s user=%s tool=%s action=%s success=%s",
            audit_id,
            user_id,
            tool_name,
            action,
            success,
        )
        return audit_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def query(
        self,
        *,
        user_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query audit entries (most recent first)."""
        results = self._entries
        if user_id:
            results = [e for e in results if e["user_id"] == user_id]
        if tool_name:
            results = [e for e in results if e["tool_name"] == tool_name]
        return list(reversed(results[-limit:]))

    def get_by_request_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        for entry in reversed(self._entries):
            if entry["request_id"] == request_id:
                return entry
        return None
