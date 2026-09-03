"""Policy manager — core orchestrator for version-controlled weight policy management.

Handles creation, activation, deactivation, comparison, and archival of weight
policies with full audit trails.  Works with PostgreSQL or in-memory storage.
"""

import json
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta

from ..models.policy import (
    WeightPolicy,
    DetectorWeights,
    PolicyStatus,
    WeightPolicyQuery,
    PolicyVersionComparison,
    PolicyCreateRequest,
    PolicyUpdateRequest,
    DETECTOR_NAMES,
)
from .audit_service import AuditService
from .validation_service import ValidationService
from ..utils.version_utils import VersionUtils
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PolicyManager:
    """Manage weight policies with version control, caching, and audit trails."""

    def __init__(self, db_pool=None, config=None, redis_client=None):
        self.db_pool = db_pool
        self.config = config
        self.redis = redis_client
        self.audit_service = AuditService(db_pool)
        self.validation_service = ValidationService()
        self.version_utils = VersionUtils()

        # In-memory fallback for standalone / testing
        self._policies: Dict[str, Dict[str, Any]] = {}
        self._active_policy_id: Optional[str] = None

    # ══════════════════════════════════════════════════════════════
    # CRUD
    # ══════════════════════════════════════════════════════════════

    async def create_policy(
        self,
        name: str,
        weights: DetectorWeights,
        created_by: str = "system",
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        calibration_type: Optional[str] = None,
        calibration_reason: Optional[str] = None,
    ) -> WeightPolicy:
        """Create a new weight policy version in DRAFT status."""
        # Validate
        if not self.validation_service.validate_weights_sum(weights):
            total = weights.weight_sum()
            raise ValueError(
                f"Weights must sum to 1.0 (current sum: {total:.4f})"
            )

        range_errors = self.validation_service.validate_weight_ranges(weights)
        if range_errors:
            raise ValueError(f"Invalid weight ranges: {'; '.join(range_errors)}")

        # Version
        latest = await self._get_latest_version()
        new_version = self.version_utils.increment(latest)

        policy = WeightPolicy(
            name=name,
            description=description,
            weights=weights,
            version=new_version,
            status=PolicyStatus.DRAFT,
            created_by=created_by,
            tags=tags or [],
            metadata=metadata or {},
            previous_version=latest,
            calibration_type=calibration_type,
            calibration_reason=calibration_reason,
        )

        if self.db_pool:
            await self._store_policy_to_db(policy)
        else:
            self._store_policy_to_memory(policy)

        await self.audit_service.log_action(
            policy_id=policy.policy_id,
            version=policy.version,
            action="CREATE",
            new_state=policy.model_dump(mode="json"),
            performed_by=created_by,
        )

        await self._invalidate_cache()

        logger.info(
            "Created policy %s/%s (weights sum=%.4f) by %s",
            policy.policy_id,
            policy.version,
            policy.weights_sum,
            created_by,
        )

        return policy

    async def get_policy(self, policy_id: str) -> Optional[WeightPolicy]:
        """Get policy by ID."""
        if self.db_pool:
            return await self._get_policy_from_db(policy_id)
        return self._get_policy_from_memory(policy_id)

    async def get_policy_by_version(self, version: str) -> Optional[WeightPolicy]:
        """Get policy by version string."""
        if self.db_pool:
            return await self._get_policy_by_version_from_db(version)
        for p in self._policies.values():
            if p.get("version") == version:
                return WeightPolicy(**p)
        return None

    async def get_active_policy(self) -> Optional[WeightPolicy]:
        """Get the currently active policy — checks cache first."""
        # Cache check
        cached = await self._get_from_cache()
        if cached:
            return cached

        # DB / memory check
        if self.db_pool:
            policy = await self._get_active_from_db()
        else:
            policy = self._get_active_from_memory()

        if policy:
            await self._set_cache(policy)

        return policy

    async def get_all_policies(
        self, query: Optional[WeightPolicyQuery] = None
    ) -> Tuple[List[WeightPolicy], int]:
        """Get all policies with optional filtering and pagination."""
        if self.db_pool:
            return await self._query_policies_from_db(query)
        return self._query_policies_from_memory(query)

    async def update_policy(
        self,
        policy_id: str,
        update: PolicyUpdateRequest,
    ) -> WeightPolicy:
        """Update a DRAFT policy's weights, name, or description."""
        policy = await self.get_policy(policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")

        if policy.status != PolicyStatus.DRAFT:
            raise ValueError(
                f"Can only update DRAFT policies (current status: {policy.status.value})"
            )

        old_state = policy.model_dump(mode="json")

        if update.weights:
            if not self.validation_service.validate_weights_sum(update.weights):
                raise ValueError(
                    f"Weights must sum to 1.0 (got {update.weights.weight_sum():.4f})"
                )
            policy.weights = update.weights
            policy.weights_sum = update.weights.weight_sum()

        if update.name is not None:
            policy.name = update.name
        if update.description is not None:
            policy.description = update.description
        if update.tags is not None:
            policy.tags = update.tags

        policy.updated_at = datetime.now(timezone.utc)

        if self.db_pool:
            await self._update_policy_in_db(policy)
        else:
            self._store_policy_to_memory(policy)

        await self.audit_service.log_action(
            policy_id=policy.policy_id,
            version=policy.version,
            action="UPDATE",
            old_state=old_state,
            new_state=policy.model_dump(mode="json"),
            performed_by=update.updated_by,
            reason=update.reason,
        )

        return policy

    # ══════════════════════════════════════════════════════════════
    # Activation / deactivation
    # ══════════════════════════════════════════════════════════════

    async def activate_policy(
        self,
        policy_id: str,
        activated_by: str,
        approved_by: Optional[str] = None,
    ) -> WeightPolicy:
        """Activate a policy — deactivates the current active one."""
        policy = await self.get_policy(policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")

        errors = self.validation_service.validate_policy_for_activation(policy)
        if errors:
            raise ValueError(f"Cannot activate: {'; '.join(errors)}")

        # Deactivate current active policy
        current_active = await self.get_active_policy()
        if current_active and current_active.policy_id != policy_id:
            await self.deactivate_policy(
                current_active.policy_id,
                deactivated_by=activated_by,
                reason=f"Superseded by {policy.version}",
            )

        old_state = policy.model_dump(mode="json")
        policy.activate(approved_by or activated_by)

        if self.db_pool:
            await self._update_policy_in_db(policy)
            await self._set_active_in_db(policy, activated_by)
        else:
            self._store_policy_to_memory(policy)
            self._active_policy_id = policy.policy_id

        await self.audit_service.log_action(
            policy_id=policy.policy_id,
            version=policy.version,
            action="ACTIVATE",
            old_state=old_state,
            new_state=policy.model_dump(mode="json"),
            performed_by=activated_by,
            reason=f"Activated by {activated_by}",
        )

        await self._invalidate_cache()
        await self._set_cache(policy)

        logger.info(
            "Activated policy %s/%s by %s",
            policy.policy_id,
            policy.version,
            activated_by,
        )

        return policy

    async def deactivate_policy(
        self,
        policy_id: str,
        deactivated_by: str,
        reason: Optional[str] = None,
    ) -> WeightPolicy:
        """Deactivate a policy."""
        policy = await self.get_policy(policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")

        old_state = policy.model_dump(mode="json")
        policy.deactivate()

        if self.db_pool:
            await self._update_policy_in_db(policy)
            await self._remove_active_from_db(policy_id)
        else:
            self._store_policy_to_memory(policy)
            if self._active_policy_id == policy_id:
                self._active_policy_id = None

        await self.audit_service.log_action(
            policy_id=policy.policy_id,
            version=policy.version,
            action="DEACTIVATE",
            old_state=old_state,
            new_state=policy.model_dump(mode="json"),
            performed_by=deactivated_by,
            reason=reason,
        )

        await self._invalidate_cache()

        return policy

    # ══════════════════════════════════════════════════════════════
    # Comparison
    # ══════════════════════════════════════════════════════════════

    async def compare_versions(
        self, version_a: str, version_b: str
    ) -> PolicyVersionComparison:
        """Compute a structured diff between two policy versions."""
        pa = await self.get_policy_by_version(version_a)
        pb = await self.get_policy_by_version(version_b)

        if not pa or not pb:
            raise ValueError(
                f"Version not found: "
                f"{version_a if not pa else ''} "
                f"{version_b if not pb else ''}"
            )

        weight_diffs = pa.weights.diff(pb.weights)

        status_diff = {
            "a": pa.status.value,
            "b": pb.status.value,
        }

        perf_diff: Optional[Dict[str, float]] = None
        if pa.performance_metrics and pb.performance_metrics:
            all_keys = set(pa.performance_metrics) | set(pb.performance_metrics)
            perf_diff = {}
            for key in all_keys:
                va = pa.performance_metrics.get(key)
                vb = pb.performance_metrics.get(key)
                if va is not None and vb is not None:
                    perf_diff[key] = vb - va

        summary = self._generate_comparison_summary(pa, pb, weight_diffs)

        return PolicyVersionComparison(
            version_a=version_a,
            version_b=version_b,
            weight_diffs=weight_diffs,
            sum_diff=pb.weights_sum - pa.weights_sum,
            status_diff=status_diff,
            performance_diff=perf_diff,
            summary=summary,
        )

    # ══════════════════════════════════════════════════════════════
    # Archival
    # ══════════════════════════════════════════════════════════════

    async def archive_old_policies(self, days: int = 365) -> int:
        """Archive inactive/superseded policies older than ``days``."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        archived = 0

        if self.db_pool:
            archived = await self._archive_old_from_db(cutoff)
        else:
            archived = self._archive_old_from_memory(cutoff)

        logger.info("Archived %d policies older than %d days", archived, days)
        return archived

    # ══════════════════════════════════════════════════════════════
    # Stats
    # ══════════════════════════════════════════════════════════════

    async def get_stats(self) -> Dict[str, Any]:
        """Aggregate policy statistics."""
        policies, total = await self.get_all_policies()

        by_status: Dict[str, int] = {}
        active_version: Optional[str] = None
        latest_version: Optional[str] = None

        for p in policies:
            by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
            if p.status == PolicyStatus.ACTIVE:
                active_version = p.version
            if latest_version is None or p.version > latest_version:
                latest_version = p.version

        return {
            "total_policies": total,
            "by_status": by_status,
            "active_version": active_version,
            "latest_version": latest_version,
        }

    # ══════════════════════════════════════════════════════════════
    # Comparison summary
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _generate_comparison_summary(
        pa: WeightPolicy,
        pb: WeightPolicy,
        weight_diffs: Dict[str, float],
    ) -> str:
        parts = [f"Comparing {pa.version} → {pb.version}:"]

        changed = [f"{k}: {v:+.3f}" for k, v in weight_diffs.items() if abs(v) > 0.001]
        if changed:
            parts.append(f"Weight changes: {', '.join(changed)}")
        else:
            parts.append("No significant weight changes")

        if pa.status != pb.status:
            parts.append(f"Status: {pa.status.value} → {pb.status.value}")

        if pa.performance_metrics and pb.performance_metrics:
            perf_parts = []
            for key in set(pa.performance_metrics) & set(pb.performance_metrics):
                delta = pb.performance_metrics[key] - pa.performance_metrics[key]
                if abs(delta) > 0.001:
                    perf_parts.append(f"{key}: {delta:+.3f}")
            if perf_parts:
                parts.append(f"Performance: {', '.join(perf_parts)}")

        return ". ".join(parts)

    # ══════════════════════════════════════════════════════════════
    # Database implementations
    # ══════════════════════════════════════════════════════════════

    async def _store_policy_to_db(self, policy: WeightPolicy):
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO weight_policies (
                    policy_id, version, weights, weights_sum, name,
                    description, status, calibration_type, calibration_reason,
                    calibration_data, performance_metrics, previous_version,
                    supersedes_version, created_at, updated_at, activated_at,
                    deactivated_at, created_by, approved_by, approved_at,
                    tags, metadata
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                    $21, $22
                )
                ON CONFLICT (policy_id) DO UPDATE SET
                    weights = EXCLUDED.weights,
                    weights_sum = EXCLUDED.weights_sum,
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at
                """,
                policy.policy_id,
                policy.version,
                json.dumps(policy.weights.as_dict()),
                policy.weights_sum,
                policy.name,
                policy.description,
                policy.status.value,
                policy.calibration_type.value if policy.calibration_type else None,
                policy.calibration_reason.value if policy.calibration_reason else None,
                json.dumps(policy.calibration_data) if policy.calibration_data else None,
                json.dumps(policy.performance_metrics) if policy.performance_metrics else None,
                policy.previous_version,
                policy.supersedes_version,
                policy.created_at,
                policy.updated_at,
                policy.activated_at,
                policy.deactivated_at,
                policy.created_by,
                policy.approved_by,
                policy.approved_at,
                policy.tags,
                json.dumps(policy.metadata) if policy.metadata else json.dumps({}),
            )

    async def _update_policy_in_db(self, policy: WeightPolicy):
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE weight_policies SET
                    weights = $1, weights_sum = $2, name = $3,
                    description = $4, status = $5, updated_at = $6,
                    activated_at = $7, deactivated_at = $8,
                    approved_by = $9, approved_at = $10,
                    tags = $11, metadata = $12
                WHERE policy_id = $13
                """,
                json.dumps(policy.weights.as_dict()),
                policy.weights_sum,
                policy.name,
                policy.description,
                policy.status.value,
                policy.updated_at,
                policy.activated_at,
                policy.deactivated_at,
                policy.approved_by,
                policy.approved_at,
                policy.tags,
                json.dumps(policy.metadata) if policy.metadata else json.dumps({}),
                policy.policy_id,
            )

    async def _get_policy_from_db(self, policy_id: str) -> Optional[WeightPolicy]:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM weight_policies WHERE policy_id = $1", policy_id
            )
        return self._row_to_policy(row) if row else None

    async def _get_policy_by_version_from_db(
        self, version: str
    ) -> Optional[WeightPolicy]:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM weight_policies WHERE version = $1", version
            )
        return self._row_to_policy(row) if row else None

    async def _get_active_from_db(self) -> Optional[WeightPolicy]:
        async with self.db_pool.acquire() as conn:
            # Try active_policy table first
            active_row = await conn.fetchrow(
                "SELECT policy_id FROM active_policy WHERE id = 1"
            )
            if active_row:
                row = await conn.fetchrow(
                    "SELECT * FROM weight_policies WHERE policy_id = $1 AND status = 'active'",
                    active_row["policy_id"],
                )
                if row:
                    return self._row_to_policy(row)

            # Fallback: latest active
            row = await conn.fetchrow(
                "SELECT * FROM weight_policies WHERE status = 'active' "
                "ORDER BY version DESC LIMIT 1"
            )
            return self._row_to_policy(row) if row else None

    async def _set_active_in_db(self, policy: WeightPolicy, activated_by: str):
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO active_policy (id, policy_id, version, activated_at, activated_by)
                VALUES (1, $1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE
                SET policy_id = $1, version = $2, activated_at = $3, activated_by = $4
                """,
                policy.policy_id,
                policy.version,
                policy.activated_at,
                activated_by,
            )

    async def _remove_active_from_db(self, policy_id: str):
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM active_policy WHERE policy_id = $1", policy_id
            )

    async def _query_policies_from_db(
        self, query: Optional[WeightPolicyQuery]
    ) -> Tuple[List[WeightPolicy], int]:
        conditions: List[str] = []
        params: list = []
        idx = 1

        if query:
            if query.status:
                conditions.append(f"status = ANY(${idx})")
                params.append([s.value for s in query.status])
                idx += 1
            if query.version:
                conditions.append(f"version = ${idx}")
                params.append(query.version)
                idx += 1
            if query.from_date:
                conditions.append(f"created_at >= ${idx}")
                params.append(query.from_date)
                idx += 1
            if query.to_date:
                conditions.append(f"created_at <= ${idx}")
                params.append(query.to_date)
                idx += 1
            if query.created_by:
                conditions.append(f"created_by = ${idx}")
                params.append(query.created_by)
                idx += 1
            if query.tags:
                conditions.append(f"tags && ${idx}")
                params.append(query.tags)
                idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with self.db_pool.acquire() as conn:
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM weight_policies {where}", *params
            )

            limit = query.limit if query else 100
            offset = query.offset if query else 0

            rows = await conn.fetch(
                f"SELECT * FROM weight_policies {where} ORDER BY version DESC "
                f"LIMIT ${idx} OFFSET ${idx + 1}",
                *params,
                limit,
                offset,
            )

        return [self._row_to_policy(r) for r in rows], count

    async def _archive_old_from_db(self, cutoff: datetime) -> int:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT policy_id FROM weight_policies
                WHERE status IN ('inactive', 'superseded')
                AND updated_at < $1
                AND policy_id NOT IN (SELECT policy_id FROM active_policy)
                """,
                cutoff,
            )
            count = 0
            for row in rows:
                await conn.execute(
                    "UPDATE weight_policies SET status = 'archived', updated_at = $1 "
                    "WHERE policy_id = $2",
                    datetime.now(timezone.utc),
                    row["policy_id"],
                )
                count += 1
            return count

    def _row_to_policy(self, row) -> WeightPolicy:
        weights_data = row["weights"]
        if isinstance(weights_data, str):
            weights_data = json.loads(weights_data)
        elif not isinstance(weights_data, dict):
            weights_data = dict(weights_data)

        return WeightPolicy(
            policy_id=row["policy_id"],
            version=row["version"],
            weights=DetectorWeights(**weights_data),
            name=row["name"],
            description=row.get("description"),
            status=PolicyStatus(row["status"]),
            calibration_type=row.get("calibration_type"),
            calibration_reason=row.get("calibration_reason"),
            calibration_data=dict(row["calibration_data"]) if row.get("calibration_data") else None,
            performance_metrics=dict(row["performance_metrics"]) if row.get("performance_metrics") else None,
            previous_version=row.get("previous_version"),
            supersedes_version=row.get("supersedes_version"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            activated_at=row.get("activated_at"),
            deactivated_at=row.get("deactivated_at"),
            created_by=row["created_by"],
            approved_by=row.get("approved_by"),
            approved_at=row.get("approved_at"),
            tags=row.get("tags") or [],
            metadata=dict(row["metadata"]) if row.get("metadata") else {},
        )

    # ══════════════════════════════════════════════════════════════
    # In-memory implementations
    # ══════════════════════════════════════════════════════════════

    def _store_policy_to_memory(self, policy: WeightPolicy):
        self._policies[policy.policy_id] = policy.model_dump(mode="json")

    def _get_policy_from_memory(self, policy_id: str) -> Optional[WeightPolicy]:
        data = self._policies.get(policy_id)
        return WeightPolicy(**data) if data else None

    def _get_active_from_memory(self) -> Optional[WeightPolicy]:
        if self._active_policy_id:
            return self._get_policy_from_memory(self._active_policy_id)
        # Fallback: find latest active
        for data in self._policies.values():
            if data.get("status") == "active":
                return WeightPolicy(**data)
        return None

    def _query_policies_from_memory(
        self, query: Optional[WeightPolicyQuery]
    ) -> Tuple[List[WeightPolicy], int]:
        items = list(self._policies.values())

        if query:
            if query.status:
                allowed = {s.value for s in query.status}
                items = [p for p in items if p.get("status") in allowed]
            if query.version:
                items = [p for p in items if p.get("version") == query.version]
            if query.created_by:
                items = [p for p in items if p.get("created_by") == query.created_by]
            if query.tags:
                items = [
                    p
                    for p in items
                    if set(query.tags or []) & set(p.get("tags", []))
                ]

        items.sort(key=lambda p: p.get("version", ""), reverse=True)
        total = len(items)

        limit = query.limit if query else 100
        offset = query.offset if query else 0
        page = items[offset : offset + limit]

        return [WeightPolicy(**p) for p in page], total

    def _archive_old_from_memory(self, cutoff: datetime) -> int:
        count = 0
        for pid, data in list(self._policies.items()):
            if data.get("status") in ("inactive", "superseded"):
                updated = data.get("updated_at", "")
                if isinstance(updated, str):
                    try:
                        updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                        if updated_dt < cutoff and pid != self._active_policy_id:
                            data["status"] = "archived"
                            count += 1
                    except ValueError:
                        pass
        return count

    # ══════════════════════════════════════════════════════════════
    # Cache
    # ══════════════════════════════════════════════════════════════

    async def _get_latest_version(self) -> str:
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT version FROM weight_policies ORDER BY version DESC LIMIT 1"
                )
                return row["version"] if row else "v0.0"

        if not self._policies:
            return "v0.0"

        versions = [
            data.get("version", "v0.0") for data in self._policies.values()
        ]
        return self.version_utils.latest(versions) or "v0.0"

    async def _get_from_cache(self) -> Optional[WeightPolicy]:
        if not self.redis:
            return None
        try:
            cached = await self.redis.get(
                self.config.ACTIVE_POLICY_CACHE_KEY if self.config else "active_policy"
            )
            if cached:
                return WeightPolicy.model_validate_json(cached)
        except Exception:
            pass
        return None

    async def _set_cache(self, policy: WeightPolicy):
        if not self.redis:
            return
        try:
            ttl = self.config.CACHE_TTL_SECONDS if self.config else 300
            key = self.config.ACTIVE_POLICY_CACHE_KEY if self.config else "active_policy"
            await self.redis.setex(key, ttl, policy.model_dump_json())
        except Exception:
            pass

    async def _invalidate_cache(self):
        if not self.redis:
            return
        try:
            key = self.config.ACTIVE_POLICY_CACHE_KEY if self.config else "active_policy"
            await self.redis.delete(key)
        except Exception:
            pass
