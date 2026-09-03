"""Unmask service — request/approve workflow with maker-checker pattern."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from models.unmask import (
    UnmaskApproval,
    UnmaskRequestCreate,
    UnmaskResponse,
    UnmaskStatus,
)
from models.orm import UnmaskRequest as UnmaskRequestORM

logger = logging.getLogger(__name__)


class UnmaskService:
    """PostgreSQL-backed unmask request store with maker-checker workflow."""

    def __init__(self) -> None:
        pass

    def create_request(
        self,
        body: UnmaskRequestCreate,
        *,
        user_id: str,
        user_jurisdictions: List[str],
    ) -> UnmaskResponse:
        """Create an unmask request."""
        if body.jurisdiction_id not in user_jurisdictions:
            raise PermissionError("User does not have access to this jurisdiction")

        from db import get_session
        with get_session() as db:
            existing = db.query(UnmaskRequestORM).filter(
                UnmaskRequestORM.case_id == body.case_id,
                UnmaskRequestORM.entity_token == body.entity_token,
                UnmaskRequestORM.status == UnmaskStatus.PENDING.value,
            ).first()
            if existing:
                raise ValueError("A pending unmask request already exists for this entity")

            request_id = f"um-{uuid4().hex[:10]}"
            now = datetime.now(timezone.utc)

            record = UnmaskRequestORM(
                request_id=request_id,
                case_id=body.case_id,
                entity_type=body.entity_type.value,
                entity_token=body.entity_token,
                reason=body.reason,
                jurisdiction_id=body.jurisdiction_id,
                status=UnmaskStatus.PENDING.value,
                requested_by=user_id,
                requested_at=now,
                approved_by=None,
                approved_at=None,
                unmasked_data=None,
            )
            db.add(record)
            db.commit()

            logger.info("Unmask request %s created by %s for %s", request_id, user_id, body.entity_token)

            return UnmaskResponse(
                request_id=request_id,
                case_id=body.case_id,
                entity_type=body.entity_type.value,
                entity_token=body.entity_token,
                status=UnmaskStatus.PENDING,
                requested_by=user_id,
                requested_at=now,
            )

    def approve(
        self,
        request_id: str,
        approval: UnmaskApproval,
        *,
        approver_id: str,
        user_jurisdictions: List[str],
    ) -> UnmaskResponse:
        """Approve or reject an unmask request."""
        from db import get_session
        with get_session() as db:
            rec = db.query(UnmaskRequestORM).filter(UnmaskRequestORM.request_id == request_id).first()
            if rec is None:
                raise ValueError("Request not found")

            if rec.jurisdiction_id not in user_jurisdictions:
                raise PermissionError("User does not have access to this jurisdiction")

            if rec.status != UnmaskStatus.PENDING.value:
                raise ValueError(f"Request already {rec.status}")

            if rec.requested_by == approver_id:
                raise PermissionError("Cannot approve your own request (maker-checker violation)")

            now = datetime.now(timezone.utc)

            if approval.decision.lower() == "approve":
                unmasked_data = {
                    "name": "ABC Corp Pvt Ltd",
                    "pan": "ABCDE1234F",
                    "gst": "22ABCDE1234F1Z5",
                    "address": "123 Main St, City, State",
                    "bank_account": "****-****-****-1234",
                }
                new_status = UnmaskStatus.UNMASKED
            else:
                unmasked_data = None
                new_status = UnmaskStatus.REJECTED

            rec.status = new_status.value
            rec.approved_by = approver_id
            rec.approved_at = now
            rec.unmasked_data = unmasked_data
            db.commit()

            logger.info("Unmask request %s %s by %s", request_id, approval.decision, approver_id)

            return UnmaskResponse(
                request_id=request_id,
                case_id=rec.case_id,
                entity_type=rec.entity_type,
                entity_token=rec.entity_token,
                status=new_status,
                requested_by=rec.requested_by,
                requested_at=rec.requested_at,
                approved_by=approver_id,
                approved_at=now,
                unmasked_data=unmasked_data,
            )

    def get_pending(
        self,
        *,
        user_jurisdictions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get pending unmask requests."""
        from db import get_session
        with get_session() as db:
            query = db.query(UnmaskRequestORM).filter(UnmaskRequestORM.status == UnmaskStatus.PENDING.value)
            if user_jurisdictions:
                query = query.filter(UnmaskRequestORM.jurisdiction_id.in_(user_jurisdictions))
            results = query.order_by(UnmaskRequestORM.requested_at.asc()).all()
            return [
                {
                    "request_id": r.request_id,
                    "case_id": r.case_id,
                    "entity_type": r.entity_type,
                    "entity_token": r.entity_token,
                    "status": r.status,
                    "requested_by": r.requested_by,
                    "requested_at": r.requested_at.isoformat() if r.requested_at else None,
                    "jurisdiction_id": r.jurisdiction_id,
                    "reason": r.reason,
                }
                for r in results
            ]

    def get_status(
        self,
        request_id: str,
        *,
        user_id: Optional[str] = None,
        user_jurisdictions: Optional[List[str]] = None,
    ) -> Optional[UnmaskResponse]:
        """Get unmask request status."""
        from db import get_session
        with get_session() as db:
            rec = db.query(UnmaskRequestORM).filter(UnmaskRequestORM.request_id == request_id).first()
            if rec is None:
                return None

            if user_jurisdictions and rec.jurisdiction_id not in user_jurisdictions:
                return None

            unmasked = None
            if rec.status == UnmaskStatus.UNMASKED.value:
                if user_id and (rec.requested_by == user_id or rec.approved_by == user_id):
                    unmasked = rec.unmasked_data

            return UnmaskResponse(
                request_id=rec.request_id,
                case_id=rec.case_id,
                entity_type=rec.entity_type,
                entity_token=rec.entity_token,
                status=UnmaskStatus(rec.status),
                requested_by=rec.requested_by,
                requested_at=rec.requested_at,
                approved_by=rec.approved_by,
                approved_at=rec.approved_at,
                unmasked_data=unmasked,
            )
