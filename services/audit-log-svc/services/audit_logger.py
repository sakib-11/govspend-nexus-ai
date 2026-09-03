"""Audit logger — the primary public API for recording audit events."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.audit import (
    AuditEntry,
    AuditEventType,
    AuditSeverity,
    AuditStatus,
    HashChainEntry,
)
from services.hash_chain_manager import HashChainManager

logger = logging.getLogger(__name__)


class AuditLogger:
    """Log audit events with hash-chain integrity.

    Supports both synchronous and buffered (async) modes.  In buffered
    mode, entries are flushed every ``flush_interval`` seconds or when the
    buffer reaches ``buffer_size``.
    """

    def __init__(
        self,
        chain_manager: HashChainManager,
        *,
        async_logging: bool = True,
        buffer_size: int = 1000,
        flush_interval: float = 5.0,
    ) -> None:
        self._chain = chain_manager
        self._async = async_logging
        self._buffer: List[AuditEntry] = []
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._flush_task: Optional[asyncio.Task[None]] = None  # type: ignore[type-arg]
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background flush loop (call inside ``asyncio``)."""
        if self._running:
            return
        self._running = True
        self._flush_task = asyncio.ensure_future(self._flush_loop())

    async def stop(self) -> None:
        """Stop the background loop and flush remaining entries."""
        self._running = False
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def log(
        self,
        *,
        event_type: AuditEventType,
        user_id: str,
        action: str,
        resource_type: str,
        request_id: str = "",
        severity: AuditSeverity = AuditSeverity.INFO,
        resource_id: Optional[str] = None,
        jurisdiction_id: Optional[str] = None,
        user_roles: Optional[List[str]] = None,
        user_jurisdictions: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        action_details: Optional[Dict[str, Any]] = None,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        response_status: Optional[int] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> AuditEntry:
        """Log an audit entry with full context."""
        entry = AuditEntry(
            event_type=event_type,
            user_id=user_id,
            user_roles=user_roles or [],
            user_jurisdictions=user_jurisdictions or [],
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            jurisdiction_id=jurisdiction_id,
            action=action,
            action_details=action_details or {},
            request_id=request_id,
            request_data=request_data,
            response_data=response_data,
            response_status=response_status,
            error_message=error_message,
            duration_ms=duration_ms,
            severity=severity,
            status=AuditStatus.PENDING,
            metadata=metadata or {},
            tags=tags or [],
            timestamp=datetime.now(timezone.utc),
        )

        if self._async:
            await self._buffer_entry(entry)
        else:
            await self._write_sync(entry)

        return entry

    async def get_entry(self, audit_id: str) -> Optional[AuditEntry]:
        """Retrieve a single audit entry by ID."""
        record = self._chain.store.fetch_by_audit_id(audit_id)
        if record is None:
            return None
        return self._record_to_entry(record)

    async def flush(self) -> int:
        """Flush all buffered entries.  Returns the number flushed."""
        if not self._buffer:
            return 0
        entries = self._buffer[:]
        self._buffer.clear()
        count = 0
        for entry in entries:
            try:
                await self._write_sync(entry)
                count += 1
            except Exception:
                logger.exception("Failed to flush audit entry %s", entry.audit_id)
        return count

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _buffer_entry(self, entry: AuditEntry) -> None:
        self._buffer.append(entry)
        if len(self._buffer) >= self._buffer_size:
            await self.flush()

    async def _write_sync(self, entry: AuditEntry) -> None:
        """Write an entry synchronously (chain append + status update)."""
        chain_entry = self._chain.create_chain_entry(entry)
        entry.status = AuditStatus.COMPLETED
        entry.hash_chain = chain_entry
        logger.info(
            "AUDIT %s user=%s action=%s severity=%s",
            entry.audit_id,
            entry.user_id,
            entry.action,
            entry.severity.value,
        )

    async def _flush_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                if self._buffer:
                    await self.flush()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Flush loop error")

    @staticmethod
    def _record_to_entry(record: Dict[str, Any]) -> AuditEntry:
        """Deserialise a stored record back into an :class:`AuditEntry`."""
        hash_chain = None
        if record.get("previous_hash") and record.get("current_hash"):
            hash_chain = HashChainEntry(
                previous_hash=record["previous_hash"],
                current_hash=record["current_hash"],
                data_hash=record.get("data_hash", ""),
                sequence_number=record.get("sequence_number", 0),
            )

        return AuditEntry(
            audit_id=record["audit_id"],
            event_type=AuditEventType(record["event_type"]),
            event_version=record.get("event_version", "1.0"),
            user_id=record["user_id"],
            user_roles=record.get("user_roles", []),
            user_jurisdictions=record.get("user_jurisdictions", []),
            session_id=record.get("session_id"),
            ip_address=record.get("ip_address"),
            user_agent=record.get("user_agent"),
            resource_type=record["resource_type"],
            resource_id=record.get("resource_id"),
            jurisdiction_id=record.get("jurisdiction_id"),
            action=record["action"],
            action_details=record.get("action_details", {}),
            request_id=record.get("request_id", ""),
            request_data=record.get("request_data"),
            response_data=record.get("response_data"),
            response_status=record.get("response_status"),
            error_message=record.get("error_message"),
            duration_ms=record.get("duration_ms"),
            timestamp=record.get("timestamp", datetime.now(timezone.utc)),
            hash_chain=hash_chain,
            severity=AuditSeverity(record.get("severity", "info")),
            status=AuditStatus(record.get("status", "completed")),
            metadata=record.get("metadata", {}),
            tags=record.get("tags", []),
            verified=record.get("verified", False),
            verified_at=record.get("verified_at"),
            verification_hash=record.get("verification_hash"),
        )
