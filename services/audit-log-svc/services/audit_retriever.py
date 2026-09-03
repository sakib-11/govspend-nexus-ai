"""Audit retriever — search, filter, and aggregate audit entries."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from models.audit import (
    AuditEntry,
    AuditEventType,
    AuditQuery,
    AuditSeverity,
    AuditStatus,
)
from services.hash_chain_manager import HashChainManager

logger = logging.getLogger(__name__)


class AuditRetriever:
    """Search and retrieve audit entries with rich filtering."""

    def __init__(self, chain_manager: HashChainManager) -> None:
        self._chain = chain_manager

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: AuditQuery) -> Tuple[List[Dict[str, Any]], int]:
        """Run a filtered search against the in-memory store.

        Returns ``(entries_as_dicts, total_matching)``.
        """
        event_type_vals = [e.value for e in query.event_type] if query.event_type else None

        entries, total = self._chain.store.search(
            user_id=query.user_id,
            event_type=event_type_vals,
            resource_type=query.resource_type,
            action=query.action,
            from_date=query.from_date,
            to_date=query.to_date,
            verified=query.verified,
            limit=query.limit,
            offset=query.offset,
        )

        # Additional filters not handled by the store
        if query.resource_id:
            entries = [e for e in entries if e.get("resource_id") == query.resource_id]
            total = sum(
                1
                for e in self._chain.store.fetch_entries(1, self._chain.get_chain_state()[2] or 1)
                if e.get("resource_id") == query.resource_id
            )

        if query.severity:
            sev_vals = {s.value for s in query.severity}
            entries = [e for e in entries if e.get("severity") in sev_vals]

        if query.status:
            st_vals = {s.value for s in query.status}
            entries = [e for e in entries if e.get("status") in st_vals]

        if query.jurisdiction_id:
            entries = [e for e in entries if e.get("jurisdiction_id") == query.jurisdiction_id]

        if query.tampered is not None:
            if query.tampered:
                entries = [e for e in entries if not e.get("verified")]
            else:
                entries = [e for e in entries if e.get("verified")]

        return entries, total

    # ------------------------------------------------------------------
    # User audit
    # ------------------------------------------------------------------

    def get_user_audit(
        self, user_id: str, *, limit: int = 100, offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = AuditQuery(user_id=user_id, limit=limit, offset=offset)
        return self.search(query)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Aggregate statistics for the audit log."""
        _, _, total = self._chain.get_chain_state()
        severity_counts = self._chain.store.count_by_severity()

        entries = self._chain.store.fetch_entries(1, total) if total > 0 else []

        # Apply date filters
        if from_date:
            entries = [e for e in entries if e.get("timestamp", datetime.min) >= from_date]
        if to_date:
            entries = [e for e in entries if e.get("timestamp", datetime.max) <= to_date]

        unique_users = {e.get("user_id") for e in entries if e.get("user_id")}
        unique_resources = {e.get("resource_type") for e in entries if e.get("resource_type")}

        durations = [e["duration_ms"] for e in entries if e.get("duration_ms") is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "total_entries": len(entries),
            "unique_users": len(unique_users),
            "resource_types": len(unique_resources),
            "severity_breakdown": severity_counts,
            "error_count": severity_counts.get("error", 0) + severity_counts.get("critical", 0),
            "avg_duration_ms": round(avg_duration, 3),
            "earliest_entry": min(
                (e.get("timestamp") for e in entries if e.get("timestamp")),
                default=None,
            ),
            "latest_entry": max(
                (e.get("timestamp") for e in entries if e.get("timestamp")),
                default=None,
            ),
        }
