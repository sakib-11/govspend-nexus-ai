"""Audit service — tamper-evident hash-chain audit logging."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from config import UnmaskConfig
from models.unmask import UnmaskStatus

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64


class AuditService:
    """Write audit entries with a hash chain and verify integrity."""

    def __init__(self, db_pool, config: UnmaskConfig) -> None:
        self.db_pool = db_pool
        self.config = config

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def log_audit(
        self,
        request_id: UUID,
        action: str,
        user_id: str,
        from_status: Optional[UnmaskStatus],
        to_status: Optional[UnmaskStatus],
        details: Dict[str, Any],
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert an audit entry with HMAC signature.

        The database trigger automatically computes the hash chain links
        (``previous_hash`` / ``current_hash``) so we only supply the
        payload hash and signature here.
        """
        payload = {
            "request_id": str(request_id),
            "action": action,
            "user_id": user_id,
            "from_status": from_status.value if from_status else None,
            "to_status": to_status.value if to_status else None,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        payload_str = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        signature = hmac.new(
            self.config.AUDIT_HASH_SALT.encode("utf-8"),
            payload_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        async with self.db_pool.acquire() as conn:
            audit_id = await conn.fetchval(
                """
                INSERT INTO unmask_audit_log
                    (request_id, action, user_id, from_status, to_status,
                     details, ip_address, user_agent, payload_hash, signature)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING audit_id
                """,
                str(request_id),
                action,
                user_id,
                from_status.value if from_status else None,
                to_status.value if to_status else None,
                json.dumps(details, default=str),
                ip_address,
                user_agent,
                payload_hash,
                signature,
            )

            # Return the full entry (with hash chain fields from trigger)
            row = await conn.fetchrow(
                "SELECT * FROM unmask_audit_log WHERE audit_id = $1",
                audit_id,
            )
            return dict(row) if row else {"audit_id": audit_id}

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_audit_trail(
        self,
        *,
        request_id: Optional[UUID] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve audit entries with optional filters."""
        conditions: List[str] = []
        params: List[Any] = []
        idx = 1

        if request_id:
            conditions.append(f"request_id = ${idx}")
            params.append(str(request_id))
            idx += 1
        if user_id:
            conditions.append(f"user_id = ${idx}")
            params.append(user_id)
            idx += 1
        if action:
            conditions.append(f"action = ${idx}")
            params.append(action)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM unmask_audit_log {where}
                ORDER BY timestamp DESC
                LIMIT ${idx} OFFSET ${idx + 1}
                """,
                *params, limit, offset,
            )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Chain verification
    # ------------------------------------------------------------------

    async def verify_chain(self) -> Dict[str, Any]:
        """Verify the entire audit hash chain integrity.

        Returns ``{"is_valid": bool, "error_message": str | None}``.
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM unmask_audit_log ORDER BY timestamp ASC, audit_id ASC"
            )

        if not rows:
            return {"is_valid": True, "error_message": None}

        prev_hash = GENESIS_HASH
        tampered: list[str] = []

        for row in rows:
            expected_prev = row["previous_hash"]
            if expected_prev != prev_hash:
                tampered.append(str(row["audit_id"]))
                return {
                    "is_valid": False,
                    "error_message": f"Chain break at {row['audit_id']}: previous_hash mismatch",
                    "tampered_entries": tampered,
                }

            # Recompute current hash
            hash_data = (
                f"{row['previous_hash']}{row['action']}{row['user_id']}"
                f"{row['request_id']}{row['timestamp']}{row['payload_hash']}"
                f"{row['from_status'] or ''}{row['to_status'] or ''}"
            )
            computed = hashlib.sha256(hash_data.encode("utf-8")).hexdigest()
            if computed != row["current_hash"]:
                tampered.append(str(row["audit_id"]))
                return {
                    "is_valid": False,
                    "error_message": f"Hash mismatch at {row['audit_id']}",
                    "tampered_entries": tampered,
                }

            prev_hash = row["current_hash"]

        return {"is_valid": True, "error_message": None}

    async def get_chain_status(self) -> Dict[str, Any]:
        """Return a summary of the audit chain state."""
        async with self.db_pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_entries,
                    MAX(timestamp) as last_entry_time,
                    COUNT(DISTINCT request_id) as unique_requests
                FROM unmask_audit_log
                """
            )
            last_entry = await conn.fetchrow(
                "SELECT audit_id, current_hash FROM unmask_audit_log "
                "ORDER BY timestamp DESC, audit_id DESC LIMIT 1"
            )

        verification = await self.verify_chain()

        return {
            "total_entries": stats["total_entries"] if stats else 0,
            "last_entry_time": stats["last_entry_time"] if stats else None,
            "unique_requests": stats["unique_requests"] if stats else 0,
            "last_entry_id": str(last_entry["audit_id"]) if last_entry else None,
            "last_hash": last_entry["current_hash"] if last_entry else None,
            "chain_valid": verification.get("is_valid", True),
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
