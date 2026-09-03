"""Retention manager — lifecycle management for audit log entries."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.hash_chain_manager import HashChainManager

logger = logging.getLogger(__name__)


def _parse_timestamp(ts: Any) -> Optional[datetime]:
    """Parse a timestamp that may be a datetime, ISO string, or other."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None
    return None


class RetentionManager:
    """Manages audit log retention, archival, and cleanup.

    In production:
      - ``archive_entries`` would write to S3/Blob and delete from primary DB
      - ``cleanup_expired`` would run as a scheduled job
      - Retention periods are configurable per event type

    Parameters
    ----------
    chain_manager : HashChainManager
    retention_days : int
        Default retention period in days (0 = forever).
    archive_before_days : int
        Entries older than this are archived.
    """

    def __init__(
        self,
        chain_manager: HashChainManager,
        *,
        retention_days: int = 3650,  # 10 years
        archive_before_days: int = 365,
    ) -> None:
        self._chain = chain_manager
        self._retention_days = retention_days
        self._archive_before_days = archive_before_days
        self._archive_log: List[Dict[str, Any]] = []
        self._cleanup_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_entries_for_archival(
        self,
        before: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Return entries older than the archive threshold."""
        cutoff = before or (
            datetime.now(timezone.utc) - timedelta(days=self._archive_before_days)
        )
        _, _, total = self._chain.get_chain_state()
        if total == 0:
            return []

        all_entries = self._chain.store.fetch_entries(1, total)
        result = []
        for e in all_entries:
            ts = _parse_timestamp(e.get("timestamp"))
            if ts and ts < cutoff:
                result.append(e)
        return result

    def get_entries_for_deletion(
        self,
        before: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Return entries older than the retention period."""
        cutoff = before or (
            datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        )
        _, _, total = self._chain.get_chain_state()
        if total == 0:
            return []

        all_entries = self._chain.store.fetch_entries(1, total)
        result = []
        for e in all_entries:
            ts = _parse_timestamp(e.get("timestamp"))
            if ts and ts < cutoff:
                result.append(e)
        return result

    # ------------------------------------------------------------------
    # Actions (stubs for production implementation)
    # ------------------------------------------------------------------

    async def archive_entries(
        self,
        entries: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Archive entries to cold storage (S3/Blob).

        In production, this would:
          1. Serialize entries to a batch file
          2. Upload to S3/Blob
          3. Record the archive manifest
          4. Delete from primary store
        """
        if entries is None:
            entries = self.get_entries_for_archival()

        if not entries:
            return {"archived": 0, "message": "No entries to archive"}

        count = len(entries)
        archive_id = f"archive-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        self._archive_log.append({
            "archive_id": archive_id,
            "entry_count": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "oldest_entry": entries[0].get("timestamp"),
            "newest_entry": entries[-1].get("timestamp"),
        })

        # In production: upload to S3, then delete from store
        # for e in entries:
        #     self._chain.store.delete_entry(e["audit_id"])

        logger.info("Archived %d entries (archive_id=%s)", count, archive_id)

        return {
            "archive_id": archive_id,
            "archived": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def cleanup_expired(
        self,
        entries: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Remove entries that have exceeded the retention period."""
        if entries is None:
            entries = self.get_entries_for_deletion()

        if not entries:
            return {"deleted": 0, "message": "No entries to delete"}

        count = len(entries)

        # In production: delete from store
        # for e in entries:
        #     self._chain.store.delete_entry(e["audit_id"])

        self._cleanup_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "deleted_count": count,
        })

        logger.info("Cleaned up %d expired entries", count)

        return {
            "deleted": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_retention_status(self) -> Dict[str, Any]:
        """Return current retention status and statistics."""
        _, _, total = self._chain.get_chain_state()
        all_entries = self._chain.store.fetch_entries(1, total) if total > 0 else []
        now = datetime.now(timezone.utc)

        archival_cutoff = now - timedelta(days=self._archive_before_days)
        retention_cutoff = now - timedelta(days=self._retention_days)

        pending_archive = 0
        pending_delete = 0
        for e in all_entries:
            ts = _parse_timestamp(e.get("timestamp"))
            if ts:
                if ts < archival_cutoff:
                    pending_archive += 1
                if ts < retention_cutoff:
                    pending_delete += 1

        return {
            "total_entries": total,
            "retention_days": self._retention_days,
            "archive_before_days": self._archive_before_days,
            "pending_archive": pending_archive,
            "pending_deletion": pending_delete,
            "total_archives": len(self._archive_log),
            "total_cleanups": len(self._cleanup_log),
            "last_archive": self._archive_log[-1] if self._archive_log else None,
            "last_cleanup": self._cleanup_log[-1] if self._cleanup_log else None,
        }
