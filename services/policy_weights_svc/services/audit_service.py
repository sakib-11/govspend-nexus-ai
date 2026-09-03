"""Audit service — immutable audit logging for all policy changes.

Works with either a PostgreSQL pool or an in-memory list for standalone use.
"""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from ..models.policy import PolicyAuditLog
from ..utils.logging import get_logger

logger = get_logger(__name__)


class AuditService:
    """Append-only audit trail for policy lifecycle events."""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        # In-memory fallback for standalone / testing
        self._memory_log: List[Dict[str, Any]] = []

    async def log_action(
        self,
        policy_id: str,
        version: str,
        action: str,
        new_state: Dict[str, Any],
        performed_by: str,
        old_state: Optional[Dict[str, Any]] = None,
        changed_fields: Optional[List[str]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> PolicyAuditLog:
        """Record an audit event."""
        # Auto-detect changed fields
        if changed_fields is None and old_state and new_state:
            changed_fields = []
            all_keys = set(old_state.keys()) | set(new_state.keys())
            for key in sorted(all_keys):
                if old_state.get(key) != new_state.get(key):
                    changed_fields.append(key)

        audit = PolicyAuditLog(
            policy_id=policy_id,
            version=version,
            action=action,
            old_state=old_state,
            new_state=new_state,
            changed_fields=changed_fields or [],
            performed_by=performed_by,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=reason,
        )

        if self.db_pool:
            await self._store_to_db(audit)
        else:
            self._store_to_memory(audit)

        logger.info(
            "Audit: %s on %s/%s by %s (changed: %d fields)",
            action,
            policy_id,
            version,
            performed_by,
            len(audit.changed_fields),
        )

        return audit

    async def get_audit_logs(
        self,
        policy_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PolicyAuditLog]:
        """Query audit logs."""
        if self.db_pool:
            return await self._query_from_db(policy_id, action, limit, offset)
        return self._query_from_memory(policy_id, action, limit, offset)

    async def get_policy_history(self, policy_id: str) -> List[PolicyAuditLog]:
        """Get complete history for a single policy."""
        return await self.get_audit_logs(policy_id=policy_id, limit=1000)

    # ── Database path ─────────────────────────────────────────────

    async def _store_to_db(self, audit: PolicyAuditLog):
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO policy_audit_log (
                    audit_id, policy_id, version, action, old_state,
                    new_state, changed_fields, performed_by, performed_at,
                    ip_address, user_agent, reason
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                audit.audit_id,
                audit.policy_id,
                audit.version,
                audit.action,
                json.dumps(audit.old_state) if audit.old_state else None,
                json.dumps(audit.new_state, default=str),
                audit.changed_fields,
                audit.performed_by,
                audit.performed_at,
                audit.ip_address,
                audit.user_agent,
                audit.reason,
            )

    async def _query_from_db(
        self,
        policy_id: Optional[str],
        action: Optional[str],
        limit: int,
        offset: int,
    ) -> List[PolicyAuditLog]:
        conditions: List[str] = []
        params: list = []
        idx = 1

        if policy_id:
            conditions.append(f"policy_id = ${idx}")
            params.append(policy_id)
            idx += 1
        if action:
            conditions.append(f"action = ${idx}")
            params.append(action)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT * FROM policy_audit_log
            {where}
            ORDER BY performed_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([limit, offset])

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [self._row_to_log(row) for row in rows]

    @staticmethod
    def _row_to_log(row) -> PolicyAuditLog:
        return PolicyAuditLog(
            audit_id=row["audit_id"],
            policy_id=row["policy_id"],
            version=row["version"],
            action=row["action"],
            old_state=dict(row["old_state"]) if row["old_state"] else None,
            new_state=dict(row["new_state"]) if row["new_state"] else {},
            changed_fields=row["changed_fields"] or [],
            performed_by=row["performed_by"],
            performed_at=row["performed_at"],
            ip_address=row.get("ip_address"),
            user_agent=row.get("user_agent"),
            reason=row.get("reason"),
        )

    # ── Memory path ──────────────────────────────────────────────

    def _store_to_memory(self, audit: PolicyAuditLog):
        self._memory_log.append(audit.model_dump(mode="json"))

    def _query_from_memory(
        self,
        policy_id: Optional[str],
        action: Optional[str],
        limit: int,
        offset: int,
    ) -> List[PolicyAuditLog]:
        filtered = self._memory_log

        if policy_id:
            filtered = [e for e in filtered if e.get("policy_id") == policy_id]
        if action:
            filtered = [e for e in filtered if e.get("action") == action]

        # Sort by performed_at descending
        filtered.sort(key=lambda e: e.get("performed_at", ""), reverse=True)
        page = filtered[offset : offset + limit]

        return [PolicyAuditLog(**e) for e in page]
