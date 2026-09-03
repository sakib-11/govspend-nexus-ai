"""Admin service — policy weights, audit logs, user management."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from models.admin import AuditLogEntry, PolicyWeight, PolicyWeightCreate, UserRoleUpdate
from models.orm import AdminUser, AuditLogEntry as AuditLogEntryORM, PolicyWeight as PolicyWeightORM

logger = logging.getLogger(__name__)


class AdminService:
    """PostgreSQL-backed admin service for policy weights, audit logs, and user management."""

    def __init__(self) -> None:
        self._chain_hash = "0" * 64

    def seed_demo_data(self) -> None:
        """Populate demo data."""
        from db import get_session
        with get_session() as db:
            if db.query(PolicyWeightORM).count() > 0:
                return

            now = datetime(2024, 1, 1, tzinfo=timezone.utc)
            policy = PolicyWeightORM(
                version="1.0",
                weights={
                    "price_deviation": 0.30,
                    "duplicate_fuzzy": 0.20,
                    "vendor_graph_risk": 0.20,
                    "timing_anomaly": 0.10,
                    "contract_splitting": 0.15,
                    "approval_velocity": 0.05,
                },
                is_active=True,
                created_at=now,
                created_by="system",
                description="Initial detector weights",
            )
            db.add(policy)

            demo_users = [
                ("user-001", "alice", ["auditor_level_1"], ["federal"]),
                ("user-002", "bob", ["auditor_level_2"], ["federal", "state-california"]),
                ("user-003", "carol", ["auditor_level_3", "approver"], ["federal", "state-california", "state-new-york"]),
                ("user-004", "dave", ["admin"], ["federal", "state-california", "state-new-york"]),
                ("user-005", "eve", ["super_admin"], ["federal", "state-california", "state-new-york", "local-nyc"]),
            ]
            for uid, uname, roles, jurisd in demo_users:
                user = AdminUser(
                    user_id=uid,
                    username=uname,
                    roles=roles,
                    jurisdictions=jurisd,
                )
                db.add(user)

            for i in range(5):
                self._record_audit(
                    db=db,
                    user_id=f"user-{i:03d}",
                    action=f"demo_action_{i}",
                    resource_type="system",
                    details={"demo": True},
                )
            db.commit()

    # ------------------------------------------------------------------
    # Policy weights
    # ------------------------------------------------------------------

    def get_policies(self) -> List[PolicyWeight]:
        from db import get_session
        with get_session() as db:
            rows = db.query(PolicyWeightORM).order_by(PolicyWeightORM.id.desc()).all()
            return [
                PolicyWeight(
                    version=r.version,
                    weights=r.weights,
                    is_active=r.is_active,
                    created_at=r.created_at,
                    created_by=r.created_by,
                    description=r.description,
                )
                for r in rows
            ]

    def create_policy(
        self,
        body: PolicyWeightCreate,
        *,
        created_by: str,
    ) -> PolicyWeight:
        total = sum(body.weights.values())
        if not (0.999 <= total <= 1.001):
            raise ValueError(f"Weights must sum to 1.0 (current: {total:.4f})")

        from db import get_session
        with get_session() as db:
            rows = db.query(PolicyWeightORM).all()
            if rows:
                latest = rows[0].version
                parts = latest.split(".")
                version = f"{parts[0]}.{int(parts[1]) + 1}"
            else:
                version = "1.0"

            if body.activate:
                for p in rows:
                    p.is_active = False

            record = PolicyWeightORM(
                version=version,
                weights=body.weights,
                is_active=body.activate,
                created_at=datetime.now(timezone.utc),
                created_by=created_by,
                description=body.description,
            )
            db.add(record)
            db.flush()

            self._record_audit(
                db=db,
                user_id=created_by,
                action="policy_create",
                resource_type="policy",
                resource_id=version,
                details={"version": version, "weights": body.weights, "activate": body.activate},
            )
            db.commit()

            logger.info("Policy %s created by %s (active=%s)", version, created_by, body.activate)

            return PolicyWeight(
                version=version,
                weights=body.weights,
                is_active=body.activate,
                created_by=created_by,
                description=body.description,
            )

    def get_active_weights(self) -> Dict[str, float]:
        from db import get_session
        with get_session() as db:
            row = db.query(PolicyWeightORM).filter(PolicyWeightORM.is_active == True).first()  # noqa: E712
            if row:
                return row.weights
            return {}

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def get_audit_logs(
        self,
        *,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[AuditLogEntry], int]:
        from db import get_session
        with get_session() as db:
            query = db.query(AuditLogEntryORM)

            if user_id:
                query = query.filter(AuditLogEntryORM.user_id == user_id)
            if action:
                query = query.filter(AuditLogEntryORM.action.ilike(f"%{action}%"))
            if resource_type:
                query = query.filter(AuditLogEntryORM.resource_type == resource_type)

            total = query.count()
            rows = query.order_by(AuditLogEntryORM.timestamp.desc()).offset(offset).limit(limit).all()

            entries = [
                AuditLogEntry(
                    entry_id=r.entry_id,
                    timestamp=r.timestamp,
                    user_id=r.user_id,
                    action=r.action,
                    resource_type=r.resource_type,
                    resource_id=r.resource_id,
                    details=r.details or {},
                    hash_chain={"sequence": r.sequence, "hash": r.hash},
                )
                for r in rows
            ]
            return entries, total

    def _record_audit(
        self,
        *,
        db,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        entry_id = f"aud-{uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        seq = db.query(AuditLogEntryORM).count() + 1

        payload = f"{self._chain_hash}:{entry_id}:{user_id}:{action}:{seq}"
        entry_hash = hashlib.sha256(payload.encode()).hexdigest()

        record = AuditLogEntryORM(
            entry_id=entry_id,
            timestamp=now,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            sequence=seq,
            hash=entry_hash,
            previous_hash=self._chain_hash,
        )
        db.add(record)
        self._chain_hash = entry_hash
        return entry_id

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def update_user_roles(
        self,
        user_id: str,
        roles: List[str],
        jurisdictions: List[str],
        *,
        updated_by: str,
    ) -> Dict[str, Any]:
        from db import get_session
        with get_session() as db:
            user = db.query(AdminUser).filter(AdminUser.user_id == user_id).first()
            if user is None:
                user = AdminUser(
                    user_id=user_id,
                    username=user_id,
                    roles=roles,
                    jurisdictions=jurisdictions,
                )
                db.add(user)
            else:
                user.roles = roles
                user.jurisdictions = jurisdictions

            self._record_audit(
                db=db,
                user_id=updated_by,
                action="user_role_update",
                resource_type="user",
                resource_id=user_id,
                details={"roles": roles, "jurisdictions": jurisdictions},
            )
            db.commit()

            return {
                "user_id": user_id,
                "roles": roles,
                "jurisdictions": jurisdictions,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        from db import get_session
        with get_session() as db:
            user = db.query(AdminUser).filter(AdminUser.user_id == user_id).first()
            if user is None:
                return None
            return {
                "user_id": user.user_id,
                "username": user.username,
                "roles": user.roles,
                "jurisdictions": user.jurisdictions,
            }

    def list_users(self) -> List[Dict[str, Any]]:
        from db import get_session
        with get_session() as db:
            users = db.query(AdminUser).all()
            return [
                {
                    "user_id": u.user_id,
                    "username": u.username,
                    "roles": u.roles,
                    "jurisdictions": u.jurisdictions,
                }
                for u in users
            ]
