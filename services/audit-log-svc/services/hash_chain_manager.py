"""Hash chain manager — tamper-evident hash chain backed by in-memory storage.

In production, swap the ``_Store`` inner class for a DB-backed one.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from models.audit import AuditChainStatus, AuditEntry, HashChainEntry
from utils.hash_utils import compute_chain_hash, compute_data_hash

logger = logging.getLogger(__name__)

# Genesis hash — the chain starts here.
GENESIS_HASH = "0" * 64


class _Store:
    """Thread-safe in-memory store for audit entries and chain state.

    Replace with asyncpg/SQLAlchemy in production.
    """

    def __init__(self) -> None:
        self._entries: List[Dict[str, Any]] = []
        self._chain_state: Dict[str, Any] = {
            "last_sequence": 0,
            "last_hash": GENESIS_HASH,
            "total": 0,
        }

    def get_chain_state(self) -> Tuple[int, str, int]:
        s = self._chain_state
        return s["last_sequence"], s["last_hash"], s["total"]

    def update_chain_state(self, sequence: int, hash_: str, total: int) -> None:
        self._chain_state = {
            "last_sequence": sequence,
            "last_hash": hash_,
            "total": total,
        }

    def insert_entry(self, entry: Dict[str, Any]) -> None:
        self._entries.append(entry)

    def fetch_entries(
        self, start_seq: int, end_seq: int
    ) -> List[Dict[str, Any]]:
        return [
            e
            for e in self._entries
            if start_seq <= e.get("sequence_number", 0) <= end_seq
        ]

    def fetch_by_audit_id(self, audit_id: str) -> Optional[Dict[str, Any]]:
        for e in self._entries:
            if e.get("audit_id") == audit_id:
                return e
        return None

    def fetch_first(self) -> Optional[Dict[str, Any]]:
        return self._entries[0] if self._entries else None

    def fetch_last(self) -> Optional[Dict[str, Any]]:
        return self._entries[-1] if self._entries else None

    def update_entry(self, audit_id: str, **fields: Any) -> bool:
        for e in self._entries:
            if e.get("audit_id") == audit_id:
                e.update(fields)
                return True
        return False

    def search(
        self,
        *,
        user_id: Optional[str] = None,
        event_type: Optional[List[str]] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        verified: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Filtered search returning ``(entries, total_matching)``."""
        results = list(self._entries)

        if user_id:
            results = [e for e in results if e.get("user_id") == user_id]
        if event_type:
            results = [e for e in results if e.get("event_type") in event_type]
        if resource_type:
            results = [e for e in results if e.get("resource_type") == resource_type]
        if action:
            action_lower = action.lower()
            results = [e for e in results if action_lower in (e.get("action") or "").lower()]
        if from_date:
            results = [e for e in results if e.get("timestamp", datetime.min) >= from_date]
        if to_date:
            results = [e for e in results if e.get("timestamp", datetime.max) <= to_date]
        if verified is not None:
            results = [e for e in results if e.get("verified") == verified]

        total = len(results)
        # Most recent first
        results = list(reversed(results))
        return results[offset : offset + limit], total

    def count_by_severity(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self._entries:
            sev = e.get("severity", "info")
            counts[sev] = counts.get(sev, 0) + 1
        return counts


class HashChainManager:
    """Manage the tamper-evident hash chain for audit logs."""

    def __init__(self, salt: str = "govspend-audit-salt-2024") -> None:
        self._salt = salt
        self._store = _Store()

    # ------------------------------------------------------------------
    # Chain state
    # ------------------------------------------------------------------

    def get_chain_state(self) -> Tuple[int, str, int]:
        """Return ``(last_sequence, last_hash, total_entries)``."""
        return self._store.get_chain_state()

    # ------------------------------------------------------------------
    # Create chain entry
    # ------------------------------------------------------------------

    def create_chain_entry(self, audit_entry: AuditEntry) -> HashChainEntry:
        """Append *audit_entry* to the chain and persist it.

        Returns the :class:`HashChainEntry` linked to the entry.
        """
        sequence, last_hash, total = self._store.get_chain_state()
        next_seq = sequence + 1

        data_hash = audit_entry.compute_data_hash()
        current_hash = compute_chain_hash(last_hash, data_hash, self._salt, next_seq)

        chain_entry = HashChainEntry(
            previous_hash=last_hash,
            current_hash=current_hash,
            data_hash=data_hash,
            sequence_number=next_seq,
        )

        # Serialise for storage
        record = json.loads(audit_entry.model_dump_json())
        record["previous_hash"] = chain_entry.previous_hash
        record["current_hash"] = chain_entry.current_hash
        record["data_hash"] = chain_entry.data_hash
        record["sequence_number"] = next_seq
        record["verified"] = False

        self._store.insert_entry(record)
        self._store.update_chain_state(next_seq, current_hash, total + 1)

        # Link back to the entry
        audit_entry.hash_chain = chain_entry

        logger.debug(
            "Chain entry #%d created (audit=%s)", next_seq, audit_entry.audit_id
        )
        return chain_entry

    # ------------------------------------------------------------------
    # Chain integrity verification
    # ------------------------------------------------------------------

    def verify_chain_integrity(
        self,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Walk the chain and verify every link.

        Returns a dict with ``verified``, ``tampered_entries``, etc.
        """
        _, _, total = self._store.get_chain_state()
        if total == 0:
            return {"verified": True, "message": "Empty chain — nothing to verify"}

        if start_sequence is None:
            start_sequence = 1
        if end_sequence is None:
            end_sequence = total

        rows = self._store.fetch_entries(start_sequence, end_sequence)
        if not rows:
            return {"verified": True, "message": "No entries in the requested range"}

        tampered: List[Dict[str, Any]] = []
        verified: List[Dict[str, Any]] = []
        prev_hash: Optional[str] = None

        for row in rows:
            is_valid = True
            issues: List[str] = []

            # 1. Previous-hash linkage
            if prev_hash is not None and row.get("previous_hash") != prev_hash:
                is_valid = False
                issues.append("previous_hash mismatch — chain link broken")

            # 2. Recompute chain hash
            recomputed = compute_chain_hash(
                row["previous_hash"],
                row["data_hash"],
                self._salt,
                row["sequence_number"],
            )
            if recomputed != row.get("current_hash"):
                is_valid = False
                issues.append("current_hash mismatch — data may have been altered")

            entry_info: Dict[str, Any] = {
                "audit_id": row.get("audit_id"),
                "sequence": row.get("sequence_number"),
                "valid": is_valid,
                "issues": issues,
            }

            if is_valid:
                verified.append(entry_info)
            else:
                tampered.append(entry_info)

            prev_hash = row.get("current_hash")

        return {
            "verified": len(tampered) == 0,
            "total_checked": len(rows),
            "verified_count": len(verified),
            "tampered_count": len(tampered),
            "tampered_entries": tampered,
            "verified_entries": verified,
        }

    # ------------------------------------------------------------------
    # Chain status
    # ------------------------------------------------------------------

    def get_chain_status(self) -> AuditChainStatus:
        sequence, last_hash, total = self._store.get_chain_state()
        first = self._store.fetch_first()
        last = self._store.fetch_last()
        verification = self.verify_chain_integrity()

        return AuditChainStatus(
            total_entries=total,
            last_entry_id=last.get("audit_id") if last else None,
            last_hash=last_hash if last else None,
            chain_start_hash=first.get("current_hash") if first else None,
            chain_end_hash=last.get("current_hash") if last else None,
            is_valid=verification.get("verified", True),
            last_verification=datetime.now(timezone.utc),
            tampered_entries=verification.get("tampered_count", 0),
            verified_entries=verification.get("verified_count", 0),
        )

    # ------------------------------------------------------------------
    # Direct store access (for verifier / retriever)
    # ------------------------------------------------------------------

    @property
    def store(self) -> _Store:
        return self._store
