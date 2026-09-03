"""Unmask service — maker-checker workflow with complete audit trail."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from config import UnmaskConfig
from models.audit import AuditEntry, AuditChainVerification
from models.state_machine import can_transition
from models.unmask import (
    UnmaskAction,
    UnmaskApproveRequest,
    UnmaskCreateRequest,
    UnmaskEntityType,
    UnmaskRejectRequest,
    UnmaskRequest,
    UnmaskResponse,
    UnmaskStatus,
    UnmaskViewRequest,
)
from services.audit_service import AuditService
from services.ledger_client import LedgerClient
from services.mfa_service import MFAService
from services.state_machine_service import StateMachineService
from utils.hash_utils import compute_data_checksum

logger = logging.getLogger(__name__)


class UnmaskService:
    """Maker-checker unmask workflow with DB persistence and audit."""

    def __init__(
        self,
        db_pool,
        mfa_service: MFAService,
        ledger_client: LedgerClient,
        audit_service: AuditService,
        config: UnmaskConfig,
    ) -> None:
        self.db_pool = db_pool
        self.mfa = mfa_service
        self.ledger = ledger_client
        self.audit = audit_service
        self.config = config
        self.sm = StateMachineService()

    # ==================================================================
    # CREATE (Maker)
    # ==================================================================

    async def create_request(
        self,
        request: UnmaskCreateRequest,
        user_id: str,
        user_roles: List[str],
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UnmaskResponse:
        """Create a new unmask request (Maker step)."""

        # Role gate
        if not any(r.startswith("auditor_level_") for r in user_roles):
            raise PermissionError("Only auditors can create unmask requests")

        await self._check_rate_limit(user_id, "create_request")

        # Pending limit
        pending = await self._count_pending(user_id)
        if pending >= self.config.MAX_PENDING_REQUESTS:
            raise ValueError(
                f"Maximum pending requests ({self.config.MAX_PENDING_REQUESTS}) exceeded"
            )

        # Duplicate check
        existing = await self._find_existing(
            request.case_id, request.entity_type, request.entity_token,
        )
        if existing:
            raise ValueError("An unmask request already exists for this entity")

        # Build request
        unmask = UnmaskRequest(
            case_id=request.case_id,
            entity_type=request.entity_type,
            entity_token=request.entity_token,
            reason=request.reason,
            requested_by=user_id,
            jurisdiction_id=request.jurisdiction_id,
            status=UnmaskStatus.PENDING,
            metadata=request.metadata,
            expired_at=datetime.now(timezone.utc)
            + timedelta(hours=self.config.REQUEST_TTL_HOURS),
        )

        unmask.data_checksum = compute_data_checksum({
            "case_id": str(unmask.case_id),
            "entity_type": unmask.entity_type.value,
            "entity_token": unmask.entity_token,
            "reason": unmask.reason,
            "requested_by": unmask.requested_by,
        })

        # Persist
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO unmask_requests
                        (request_id, case_id, entity_type, entity_token,
                         reason, requested_by, jurisdiction_id, status,
                         expired_at, data_checksum, metadata)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                    """,
                    str(unmask.request_id),
                    str(unmask.case_id),
                    unmask.entity_type.value,
                    unmask.entity_token,
                    unmask.reason,
                    unmask.requested_by,
                    unmask.jurisdiction_id,
                    unmask.status.value,
                    unmask.expired_at,
                    unmask.data_checksum,
                    json.dumps(unmask.metadata, default=str),
                )

                await self.audit.log_audit(
                    request_id=unmask.request_id,
                    action=UnmaskAction.CREATE.value,
                    user_id=user_id,
                    from_status=None,
                    to_status=UnmaskStatus.PENDING,
                    details={
                        "entity_type": unmask.entity_type.value,
                        "entity_token": unmask.entity_token,
                        "reason": unmask.reason,
                        "case_id": str(unmask.case_id),
                    },
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

        logger.info("Unmask request created: %s by %s", unmask.request_id, user_id)
        return self._to_response(unmask)

    # ==================================================================
    # APPROVE (Checker)
    # ==================================================================

    async def approve_request(
        self,
        request: UnmaskApproveRequest,
        user_id: str,
        user_roles: List[str],
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UnmaskResponse:
        """Approve an unmask request (Checker step)."""

        await self._check_rate_limit(user_id, "approve_request")

        unmask = await self._get_request(request.request_id)
        if not unmask:
            raise ValueError("Request not found")

        # State validation
        if unmask.status != UnmaskStatus.PENDING:
            raise ValueError(
                f"Request is not pending (current: {unmask.status.value})"
            )

        # Expiry check
        if unmask.expired_at and unmask.expired_at < datetime.now(timezone.utc):
            await self._expire_request(unmask.request_id)
            raise ValueError("Request has expired")

        # MFA verification
        mfa_ok = True
        if self.config.MFA_ENABLED:
            mfa_ok = await self.mfa.verify_mfa_for_approval(
                str(request.request_id), user_id, request.mfa_code,
            )
            if not mfa_ok:
                await self.audit.log_audit(
                    request_id=unmask.request_id,
                    action="MFA_FAILED",
                    user_id=user_id,
                    from_status=unmask.status,
                    to_status=unmask.status,
                    details={"context": "approve"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise PermissionError("MFA verification failed")

        # Transition validation
        valid, err = self.sm.validate_transition(
            unmask.status,
            UnmaskAction.APPROVE,
            user_roles,
            mfa_verified=mfa_ok,
            requested_by=unmask.requested_by,
            user_id=user_id,
            self_approval_disallowed=self.config.SELF_APPROVAL_DISALLOWED,
        )
        if not valid:
            raise PermissionError(err)

        # Persist
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE unmask_requests
                    SET status = $1, approved_by = $2, approved_at = NOW(),
                        mfa_verified = $3, mfa_verified_at = NOW(),
                        version = version + 1
                    WHERE request_id = $4
                    """,
                    UnmaskStatus.APPROVED.value,
                    user_id,
                    mfa_ok,
                    str(request.request_id),
                )

                await self.audit.log_audit(
                    request_id=unmask.request_id,
                    action=UnmaskAction.APPROVE.value,
                    user_id=user_id,
                    from_status=UnmaskStatus.PENDING,
                    to_status=UnmaskStatus.APPROVED,
                    details={
                        "notes": request.notes,
                        "mfa_verified": mfa_ok,
                        "approver_roles": user_roles,
                    },
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

        unmask.status = UnmaskStatus.APPROVED
        unmask.approved_by = user_id
        unmask.approved_at = datetime.now(timezone.utc)
        unmask.mfa_verified = mfa_ok

        logger.info("Unmask request approved: %s by %s", unmask.request_id, user_id)
        return self._to_response(unmask)

    # ==================================================================
    # REJECT
    # ==================================================================

    async def reject_request(
        self,
        request: UnmaskRejectRequest,
        user_id: str,
        user_roles: List[str],
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UnmaskResponse:
        """Reject an unmask request."""

        await self._check_rate_limit(user_id, "reject_request")

        unmask = await self._get_request(request.request_id)
        if not unmask:
            raise ValueError("Request not found")

        if unmask.status != UnmaskStatus.PENDING:
            raise ValueError(
                f"Request is not pending (current: {unmask.status.value})"
            )

        valid, err = self.sm.validate_transition(
            unmask.status,
            UnmaskAction.REJECT,
            user_roles,
            requested_by=unmask.requested_by,
            user_id=user_id,
            self_approval_disallowed=self.config.SELF_APPROVAL_DISALLOWED,
        )
        if not valid:
            raise PermissionError(err)

        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE unmask_requests
                    SET status = $1, rejection_reason = $2,
                        version = version + 1
                    WHERE request_id = $3
                    """,
                    UnmaskStatus.REJECTED.value,
                    request.reason,
                    str(request.request_id),
                )

                await self.audit.log_audit(
                    request_id=unmask.request_id,
                    action=UnmaskAction.REJECT.value,
                    user_id=user_id,
                    from_status=UnmaskStatus.PENDING,
                    to_status=UnmaskStatus.REJECTED,
                    details={"reason": request.reason, "rejector_roles": user_roles},
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

        unmask.status = UnmaskStatus.REJECTED
        unmask.rejection_reason = request.reason
        logger.info("Unmask request rejected: %s by %s", unmask.request_id, user_id)
        return self._to_response(unmask)

    # ==================================================================
    # UNMASK (fetch from ledger)
    # ==================================================================

    async def unmask_data(
        self,
        request_id: UUID,
        user_id: str,
        user_roles: List[str],
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UnmaskResponse:
        """Fetch and decrypt data from the ledger."""

        await self._check_rate_limit(user_id, "unmask_data")

        unmask = await self._get_request(request_id)
        if not unmask:
            raise ValueError("Request not found")

        if unmask.status != UnmaskStatus.APPROVED:
            raise ValueError(
                f"Request is not approved (current: {unmask.status.value})"
            )

        if unmask.expired_at and unmask.expired_at < datetime.now(timezone.utc):
            await self._expire_request(request_id)
            raise ValueError("Request has expired")

        valid, err = self.sm.validate_transition(
            unmask.status,
            UnmaskAction.UNMASK,
            user_roles,
            mfa_verified=True,
        )
        if not valid:
            raise PermissionError(err)

        # Fetch from ledger
        ledger_data = await self.ledger.get_encrypted_data(
            entity_type=unmask.entity_type.value,
            entity_token=unmask.entity_token,
            decrypt=True,
        )
        if not ledger_data:
            raise RuntimeError("Failed to retrieve data from ledger")

        data_checksum = compute_data_checksum(ledger_data)

        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE unmask_requests
                    SET status = $1, unmasked_by = $2, unmasked_at = NOW(),
                        unmasked_data = $3, data_checksum = $4,
                        version = version + 1
                    WHERE request_id = $5
                    """,
                    UnmaskStatus.UNMASKED.value,
                    user_id,
                    json.dumps(ledger_data, default=str),
                    data_checksum,
                    str(request_id),
                )

                await self.audit.log_audit(
                    request_id=unmask.request_id,
                    action=UnmaskAction.UNMASK.value,
                    user_id=user_id,
                    from_status=UnmaskStatus.APPROVED,
                    to_status=UnmaskStatus.UNMASKED,
                    details={
                        "entity_type": unmask.entity_type.value,
                        "entity_token": unmask.entity_token,
                        "data_hash": data_checksum,
                        "data_size": len(json.dumps(ledger_data)),
                    },
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

                await conn.execute(
                    """
                    INSERT INTO unmask_access_log
                        (request_id, user_id, action, data_accessed,
                         data_hash, ip_address, user_agent)
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    """,
                    str(request_id),
                    user_id,
                    "UNMASK",
                    [unmask.entity_type.value],
                    data_checksum,
                    ip_address,
                    user_agent,
                )

        unmask.status = UnmaskStatus.UNMASKED
        unmask.unmasked_by = user_id
        unmask.unmasked_at = datetime.now(timezone.utc)
        unmask.unmasked_data = ledger_data

        logger.info("Data unmasked for request: %s by %s", unmask.request_id, user_id)
        return self._to_response(unmask)

    # ==================================================================
    # VIEW
    # ==================================================================

    async def view_unmasked_data(
        self,
        request: UnmaskViewRequest,
        user_id: str,
        user_roles: List[str],
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """View unmasked data with integrity check."""

        await self._check_rate_limit(user_id, "view_data")

        unmask = await self._get_request(request.request_id)
        if not unmask:
            raise ValueError("Request not found")

        if unmask.status != UnmaskStatus.UNMASKED:
            raise ValueError(
                f"Data is not unmasked (current: {unmask.status.value})"
            )

        # Authorization
        allowed, err = self.sm.can_view_data(unmask, user_id, user_roles)
        if not allowed:
            raise PermissionError(err)

        # MFA
        if self.config.MFA_ENABLED:
            mfa_ok = await self.mfa.verify_mfa(user_id, request.mfa_code)
            if not mfa_ok:
                await self.audit.log_audit(
                    request_id=unmask.request_id,
                    action="VIEW_MFA_FAILED",
                    user_id=user_id,
                    from_status=unmask.status,
                    to_status=unmask.status,
                    details={"context": "view"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise PermissionError("MFA verification failed")

        # Integrity check
        if unmask.unmasked_data and unmask.data_checksum:
            current = compute_data_checksum(unmask.unmasked_data)
            if current != unmask.data_checksum:
                await self.audit.log_audit(
                    request_id=unmask.request_id,
                    action="DATA_TAMPERED",
                    user_id=user_id,
                    from_status=unmask.status,
                    to_status=unmask.status,
                    details={"expected": unmask.data_checksum, "actual": current},
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise RuntimeError("Data integrity check failed — possible tampering")

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE unmask_requests
                SET viewed_by = $1, viewed_at = NOW(), version = version + 1
                WHERE request_id = $2
                """,
                user_id, str(request.request_id),
            )

            await self.audit.log_audit(
                request_id=unmask.request_id,
                action=UnmaskAction.VIEW.value,
                user_id=user_id,
                from_status=UnmaskStatus.UNMASKED,
                to_status=UnmaskStatus.VIEWED,
                details={
                    "entity_type": unmask.entity_type.value,
                    "entity_token": unmask.entity_token,
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )

            await conn.execute(
                """
                INSERT INTO unmask_access_log
                    (request_id, user_id, action, data_accessed,
                     ip_address, user_agent)
                VALUES ($1,$2,$3,$4,$5,$6)
                """,
                str(request.request_id),
                user_id,
                "VIEW",
                [unmask.entity_type.value],
                ip_address,
                user_agent,
            )

        unmask.status = UnmaskStatus.VIEWED
        unmask.viewed_by = user_id
        unmask.viewed_at = datetime.now(timezone.utc)

        logger.info("Unmasked data viewed: %s by %s", unmask.request_id, user_id)
        return unmask.unmasked_data or {}

    # ==================================================================
    # Queries
    # ==================================================================

    async def get_request(self, request_id: UUID) -> Optional[UnmaskResponse]:
        """Get a single request as a response DTO."""
        unmask = await self._get_request(request_id)
        if not unmask:
            return None
        return self._to_response(unmask)

    async def list_requests(
        self,
        *,
        case_id: Optional[UUID] = None,
        status: Optional[UnmaskStatus] = None,
        requested_by: Optional[str] = None,
        jurisdiction_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List unmask requests with filters."""
        conditions: List[str] = []
        params: List[Any] = []
        idx = 1

        if case_id:
            conditions.append(f"case_id = ${idx}")
            params.append(str(case_id))
            idx += 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status.value)
            idx += 1
        if requested_by:
            conditions.append(f"requested_by = ${idx}")
            params.append(requested_by)
            idx += 1
        if jurisdiction_id:
            conditions.append(f"jurisdiction_id = ${idx}")
            params.append(jurisdiction_id)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM unmask_requests {where}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx + 1}
                """,
                *params, limit, offset,
            )

        return [dict(r) for r in rows]

    async def get_audit_trail(self, request_id: UUID) -> List[Dict[str, Any]]:
        """Get the full audit trail for a request."""
        return await self.audit.get_audit_trail(request_id=request_id)

    async def verify_audit_chain(self) -> AuditChainVerification:
        """Verify the audit hash chain."""
        result = await self.audit.verify_chain()
        return AuditChainVerification(
            is_valid=result.get("is_valid", True),
            error_message=result.get("error_message"),
        )

    # ==================================================================
    # Internals
    # ==================================================================

    async def _get_request(self, request_id: UUID) -> Optional[UnmaskRequest]:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM unmask_requests WHERE request_id = $1",
                str(request_id),
            )
        if not row:
            return None
        return self._row_to_request(row)

    async def _count_pending(self, user_id: str) -> int:
        async with self.db_pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM unmask_requests
                WHERE requested_by = $1 AND status = 'pending'
                """,
                user_id,
            )
        return count or 0

    async def _find_existing(
        self, case_id: UUID, entity_type: UnmaskEntityType, entity_token: str,
    ) -> Optional[str]:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT request_id FROM unmask_requests
                WHERE case_id = $1 AND entity_type = $2
                  AND entity_token = $3
                  AND status NOT IN ('rejected', 'expired', 'cancelled')
                """,
                str(case_id), entity_type.value, entity_token,
            )
        return str(row["request_id"]) if row else None

    async def _check_rate_limit(self, user_id: str, action: str) -> None:
        window_start = datetime.now(timezone.utc) - timedelta(
            minutes=self.config.RATE_LIMIT_WINDOW_MINUTES,
        )
        async with self.db_pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM unmask_rate_limit
                WHERE user_id = $1 AND action = $2 AND window_start > $3
                """,
                user_id, action, window_start,
            )
            if count and count >= self.config.MAX_REQUESTS_PER_DAY:
                raise ValueError(
                    f"Rate limit exceeded ({self.config.MAX_REQUESTS_PER_DAY} "
                    f"requests per {self.config.RATE_LIMIT_WINDOW_MINUTES} min)"
                )
            await conn.execute(
                "INSERT INTO unmask_rate_limit (user_id, action) VALUES ($1, $2)",
                user_id, action,
            )

    async def _expire_request(self, request_id: UUID) -> None:
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE unmask_requests
                SET status = $1, expired_at = NOW()
                WHERE request_id = $2
                """,
                UnmaskStatus.EXPIRED.value, str(request_id),
            )
        await self.audit.log_audit(
            request_id=request_id,
            action=UnmaskAction.EXPIRE.value,
            user_id="system",
            from_status=None,
            to_status=UnmaskStatus.EXPIRED,
            details={"reason": "auto_expired"},
        )

    def _row_to_request(self, row) -> UnmaskRequest:
        return UnmaskRequest(
            request_id=UUID(row["request_id"]),
            case_id=UUID(row["case_id"]),
            entity_type=UnmaskEntityType(row["entity_type"]),
            entity_token=row["entity_token"],
            reason=row["reason"],
            requested_by=row["requested_by"],
            requested_at=row["requested_at"],
            status=UnmaskStatus(row["status"]),
            approved_by=row.get("approved_by"),
            approved_at=row.get("approved_at"),
            unmasked_by=row.get("unmasked_by"),
            unmasked_at=row.get("unmasked_at"),
            viewed_by=row.get("viewed_by"),
            viewed_at=row.get("viewed_at"),
            expired_at=row.get("expired_at"),
            rejection_reason=row.get("rejection_reason"),
            jurisdiction_id=row["jurisdiction_id"],
            mfa_verified=row.get("mfa_verified", False),
            mfa_verified_at=row.get("mfa_verified_at"),
            unmasked_data=row.get("unmasked_data"),
            data_checksum=row.get("data_checksum"),
            metadata=row.get("metadata") or {},
            version=row.get("version", 1),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _to_response(self, r: UnmaskRequest) -> UnmaskResponse:
        return UnmaskResponse(
            request_id=r.request_id,
            case_id=r.case_id,
            entity_type=r.entity_type.value,
            entity_token=r.entity_token,
            status=r.status.value,
            requested_by=r.requested_by,
            requested_at=r.requested_at,
            approved_by=r.approved_by,
            approved_at=r.approved_at,
            unmasked_data=r.unmasked_data if r.status == UnmaskStatus.UNMASKED else None,
            expires_at=r.expired_at,
            can_view=r.status == UnmaskStatus.UNMASKED,
            can_approve=r.status == UnmaskStatus.PENDING,
            can_reject=r.status == UnmaskStatus.PENDING,
            rejection_reason=r.rejection_reason,
            metadata=r.metadata,
        )
