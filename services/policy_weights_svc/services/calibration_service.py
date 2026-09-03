"""Calibration service — orchestrates weight calibration, evaluation, and history tracking."""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from ..models.policy import (
    CalibrationRequest,
    WeightPolicy,
    DetectorWeights,
)
from .policy_manager import PolicyManager
from .audit_service import AuditService
from ..utils.logging import get_logger

logger = get_logger(__name__)


class CalibrationService:
    """Orchestrate weight calibration workflows."""

    def __init__(self, policy_manager: PolicyManager, audit_service: AuditService, db_pool=None):
        self.policy_manager = policy_manager
        self.audit_service = audit_service
        self.db_pool = db_pool
        # In-memory fallback
        self._history: List[Dict[str, Any]] = []

    async def calibrate_weights(
        self, request: CalibrationRequest
    ) -> WeightPolicy:
        """Create a new policy version from a calibration request."""
        # Validate
        if not request.weights.validate_sum():
            raise ValueError(
                f"Weights must sum to 1.0 (got {request.weights.weight_sum():.4f})"
            )

        # Get current active for reference
        current = await self.policy_manager.get_active_policy()

        # Create new policy
        policy = await self.policy_manager.create_policy(
            name=f"Calibration: {request.name}",
            weights=request.weights,
            created_by=request.created_by,
            description=request.description,
            tags=["calibration", request.calibration_type.value],
            calibration_type=request.calibration_type.value,
            calibration_reason=request.calibration_reason.value,
        )

        # Record calibration history
        await self._record_calibration(
            policy=policy,
            request=request,
            current_policy=current,
        )

        await self.audit_service.log_action(
            policy_id=policy.policy_id,
            version=policy.version,
            action="CALIBRATE",
            new_state=policy.model_dump(mode="json"),
            performed_by=request.created_by,
            reason=(
                f"Calibration type: {request.calibration_type.value}, "
                f"reason: {request.calibration_reason.value}"
            ),
        )

        logger.info(
            "Calibration created policy %s/%s (type=%s, reason=%s)",
            policy.policy_id,
            policy.version,
            request.calibration_type.value,
            request.calibration_reason.value,
        )

        return policy

    async def evaluate_calibration(
        self,
        policy_id: str,
        evaluation_data: Dict[str, Any],
        evaluated_by: str = "system",
    ) -> Dict[str, Any]:
        """Record evaluation results for a calibrated policy."""
        policy = await self.policy_manager.get_policy(policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")

        if self.db_pool:
            await self._store_evaluation_to_db(policy_id, evaluation_data)
        else:
            self._store_evaluation_to_memory(policy_id, evaluation_data)

        # Update policy's performance metrics
        policy.performance_metrics = evaluation_data
        policy.updated_at = datetime.now(timezone.utc)

        if self.policy_manager.db_pool:
            await self.policy_manager._update_policy_in_db(policy)
        else:
            self.policy_manager._store_policy_to_memory(policy)

        await self.audit_service.log_action(
            policy_id=policy.policy_id,
            version=policy.version,
            action="EVALUATE",
            new_state={"performance_metrics": evaluation_data},
            performed_by=evaluated_by,
        )

        logger.info(
            "Evaluation recorded for %s/%s: %s",
            policy.policy_id,
            policy.version,
            list(evaluation_data.keys()),
        )

        return evaluation_data

    async def get_calibration_history(
        self,
        policy_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get calibration history."""
        if self.db_pool:
            return await self._query_calibration_from_db(policy_id, limit, offset)
        return self._query_calibration_from_memory(policy_id, limit, offset)

    # ── Private helpers ───────────────────────────────────────────

    async def _record_calibration(
        self,
        policy: WeightPolicy,
        request: CalibrationRequest,
        current_policy: Optional[WeightPolicy],
    ):
        """Store calibration record."""
        record = {
            "calibration_id": f"cal-{policy.policy_id[:8]}",
            "policy_id": policy.policy_id,
            "version": policy.version,
            "calibration_type": request.calibration_type.value,
            "reason": request.calibration_reason.value,
            "data": request.calibration_data,
            "performance_before": (
                current_policy.performance_metrics if current_policy else None
            ),
            "created_by": request.created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if self.db_pool:
            await self._store_calibration_to_db(record)
        else:
            self._history.append(record)

    async def _store_calibration_to_db(self, record: Dict[str, Any]):
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO calibration_history (
                    calibration_id, policy_id, calibration_type, reason,
                    data, performance_before, created_by, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                record["calibration_id"],
                record["policy_id"],
                record["calibration_type"],
                record["reason"],
                json.dumps(record["data"]) if record["data"] else None,
                json.dumps(record["performance_before"]) if record["performance_before"] else None,
                record["created_by"],
                record["created_at"],
            )

    def _store_calibration_to_memory(self, policy_id: str, evaluation: Dict[str, Any]):
        # Update matching history record
        for record in self._history:
            if record.get("policy_id") == policy_id:
                record["evaluation_results"] = evaluation
                record["completed_at"] = datetime.now(timezone.utc).isoformat()
                record["evaluation_status"] = "completed"
                return

    async def _store_evaluation_to_db(
        self, policy_id: str, evaluation_data: Dict[str, Any]
    ):
        async with self.db_pool.acquire() as conn:
            # Update calibration_history with evaluation
            await conn.execute(
                """
                UPDATE calibration_history
                SET evaluation_results = $1, evaluation_status = 'completed',
                    completed_at = $2, performance_after = $1
                WHERE policy_id = $3
                ORDER BY created_at DESC
                LIMIT 1
                """,
                json.dumps(evaluation_data),
                datetime.now(timezone.utc),
                policy_id,
            )

    def _store_evaluation_to_memory(
        self, policy_id: str, evaluation_data: Dict[str, Any]
    ):
        for record in self._history:
            if record.get("policy_id") == policy_id:
                record["evaluation_results"] = evaluation_data
                record["completed_at"] = datetime.now(timezone.utc).isoformat()
                return

    async def _query_calibration_from_db(
        self,
        policy_id: Optional[str],
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: list = []
        idx = 1

        if policy_id:
            conditions.append(f"policy_id = ${idx}")
            params.append(policy_id)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM calibration_history {where} "
                f"ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
                *params,
                limit,
                offset,
            )
        return [dict(row) for row in rows]

    def _query_calibration_from_memory(
        self,
        policy_id: Optional[str],
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        filtered = self._history
        if policy_id:
            filtered = [r for r in filtered if r.get("policy_id") == policy_id]
        return filtered[offset : offset + limit]
