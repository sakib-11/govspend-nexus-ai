"""Case service — case management with filtering, pagination, and actions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from models.case import (
    CaseAction,
    CaseActionResponse,
    CaseDetail,
    CaseFilter,
    CaseStatus,
    CaseSummary,
    CaseTier,
)
from models.orm import Case

logger = logging.getLogger(__name__)


class CaseService:
    """PostgreSQL-backed case management service."""

    def __init__(self) -> None:
        pass

    def get_case_count(self) -> int:
        """Return total number of cases (used by health checks)."""
        from db import get_session
        from models.orm import Case
        try:
            with get_session() as db:
                return db.query(Case).count()
        except Exception:  # pragma: no cover - DB may be unavailable at health check
            logger.exception("Failed to count cases for health check")
            return 0

    # ------------------------------------------------------------------
    # Seed data (called once at startup to populate demo data)
    # ------------------------------------------------------------------

    def seed_demo_data(self) -> None:
        """Populate the store with demo cases for development."""
        from db import get_session
        with get_session() as db:
            if db.query(Case).count() > 0:
                return
            demo_cases = [
                self._make_demo_case("case-001", "tx-001", 0.87, CaseTier.HIGH, "IT Department", "VEND-ABC12", 150000.0),
                self._make_demo_case("case-002", "tx-002", 0.62, CaseTier.BORDERLINE, "HR Department", "VEND-DEF34", 75000.0),
                self._make_demo_case("case-003", "tx-003", 0.31, CaseTier.LOW, "Finance", "VEND-GHI56", 25000.0),
                self._make_demo_case("case-004", "tx-004", 0.91, CaseTier.HIGH, "IT Department", "VEND-ABC12", 200000.0),
                self._make_demo_case("case-005", "tx-005", 0.55, CaseTier.BORDERLINE, "Procurement", "VEND-JKL78", 95000.0),
            ]
            for c in demo_cases:
                db.add(c)
            db.commit()
            logger.info("Seeded %d demo cases", len(demo_cases))

    def _make_demo_case(
        self,
        case_id: str,
        tx_id: str,
        score: float,
        tier: CaseTier,
        dept: str,
        vendor: str,
        amount: float,
    ) -> Case:
        now = datetime.now(timezone.utc)
        return Case(
            case_id=case_id,
            transaction_id=tx_id,
            risk_score=score,
            tier=tier.value,
            status=CaseStatus.NEW.value,
            confidence_factor=0.85,
            weights_version="1.0",
            department=dept,
            vendor_token=vendor,
            amount=amount,
            transaction_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            jurisdiction_id="federal",
            transaction={"amount": amount, "currency": "USD", "date": "2024-01-15"},
            vendor={"token": vendor, "name_masked": vendor[:6] + "***"},
            signals=[
                {"detector_type": "price_deviation", "signal_value": score * 0.9, "confidence": 0.88},
                {"detector_type": "vendor_graph_risk", "signal_value": score * 0.7, "confidence": 0.82},
            ],
            signals_summary={"total": 2, "high_signals": 1, "avg_confidence": 0.85},
            evidence_ids=[f"ev-{tx_id}-001", f"ev-{tx_id}-002"],
            evidence_summary={"total": 2},
            assigned_to=None,
            created_at=now,
            updated_at=now,
            actions=[],
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_cases(
        self,
        *,
        user_jurisdictions: Optional[List[str]] = None,
        filters: Optional[CaseFilter] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[CaseSummary], int]:
        """Get filtered, paginated cases."""
        from db import get_session
        with get_session() as db:
            query = db.query(Case)

            if user_jurisdictions:
                query = query.filter(
                    (Case.jurisdiction_id.in_(user_jurisdictions)) | (Case.jurisdiction_id == None)  # noqa: E711
                )

            if filters:
                if filters.tier:
                    tier_vals = {t.value for t in filters.tier}
                    query = query.filter(Case.tier.in_(tier_vals))
                if filters.status:
                    st_vals = {s.value for s in filters.status}
                    query = query.filter(Case.status.in_(st_vals))
                if filters.department:
                    dept_lower = filters.department.lower()
                    query = query.filter(Case.department.ilike(f"%{dept_lower}%"))
                if filters.vendor_token:
                    query = query.filter(Case.vendor_token == filters.vendor_token)
                if filters.min_score is not None:
                    query = query.filter(Case.risk_score >= filters.min_score)
                if filters.max_score is not None:
                    query = query.filter(Case.risk_score <= filters.max_score)
                if filters.search:
                    q = filters.search.lower()
                    query = query.filter(
                        (Case.case_id.ilike(f"%{q}%"))
                        | (Case.vendor_token.ilike(f"%{q}%"))
                        | (Case.department.ilike(f"%{q}%"))
                    )

            query = query.order_by(Case.risk_score.desc(), Case.created_at.desc())
            total = query.count()
            page = query.offset(offset).limit(limit).all()

            summaries = []
            for c in page:
                dept = c.department
                tx_date = c.transaction_date
                created = c.created_at
                updated = c.updated_at

                summaries.append(CaseSummary(
                    case_id=c.case_id,
                    transaction_id=c.transaction_id,
                    risk_score=c.risk_score,
                    tier=CaseTier(c.tier),
                    status=CaseStatus(c.status),
                    department=dept,
                    vendor_token=c.vendor_token,
                    amount=c.amount,
                    transaction_date=tx_date,
                    top_signals=(c.signals or [])[:3],
                    signal_count=len(c.signals or []),
                    created_at=created,
                    updated_at=updated,
                ))

            return summaries, total

    def get_case_detail(
        self,
        case_id: str,
        *,
        user_jurisdictions: Optional[List[str]] = None,
    ) -> Optional[CaseDetail]:
        """Get full case detail."""
        from db import get_session
        with get_session() as db:
            c = db.query(Case).filter(Case.case_id == case_id).first()
            if c is None:
                return None

            if user_jurisdictions and c.jurisdiction_id:
                if c.jurisdiction_id not in user_jurisdictions:
                    return None

            dept = c.department
            if isinstance(dept, str):
                dept = {"name": dept}

            return CaseDetail(
                case_id=c.case_id,
                transaction_id=c.transaction_id,
                risk_score=c.risk_score,
                tier=CaseTier(c.tier),
                status=CaseStatus(c.status),
                confidence_factor=c.confidence_factor,
                weights_version=c.weights_version,
                transaction=c.transaction or {},
                vendor=c.vendor or {},
                department=dept,
                signals=c.signals or [],
                signals_summary=c.signals_summary or {},
                evidence_ids=c.evidence_ids or [],
                evidence_summary=c.evidence_summary or {},
                jurisdiction_id=c.jurisdiction_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
                assigned_to=c.assigned_to,
                actions=c.actions or [],
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def perform_action(
        self,
        case_id: str,
        action: CaseAction,
        *,
        user_id: str,
        user_roles: List[str],
    ) -> CaseActionResponse:
        """Perform an action on a case."""
        from db import get_session
        with get_session() as db:
            c = db.query(Case).filter(Case.case_id == case_id).first()
            if c is None:
                raise ValueError(f"Case {case_id} not found")

            valid_actions = {"approve", "reject", "escalate", "close"}
            if action.action not in valid_actions:
                raise ValueError(f"Invalid action. Must be one of: {', '.join(sorted(valid_actions))}")

            if action.action in ("approve", "reject"):
                if "approver" not in user_roles and "admin" not in user_roles and "super_admin" not in user_roles:
                    raise PermissionError("Only approvers and admins can approve/reject cases")

            if action.action == "escalate":
                if not any(r in user_roles for r in ("auditor_level_2", "auditor_level_3", "admin", "super_admin")):
                    raise PermissionError("Only Level 2+ auditors can escalate cases")

            new_status = {
                "approve": CaseStatus.APPROVED,
                "reject": CaseStatus.REJECTED,
                "escalate": CaseStatus.ESCALATED,
                "close": CaseStatus.CLOSED,
            }[action.action]

            c.status = new_status.value
            c.assigned_to = user_id
            c.updated_at = datetime.now(timezone.utc)

            action_record = {
                "action_id": f"act-{uuid4().hex[:8]}",
                "action": action.action,
                "user_id": user_id,
                "action_time": datetime.now(timezone.utc).isoformat(),
                "notes": action.notes,
                "details": {"new_status": new_status.value, "reason": action.reason},
            }
            actions = c.actions or []
            actions.append(action_record)
            c.actions = actions

            db.commit()

            logger.info("Case %s %s by %s -> %s", case_id, action.action, user_id, new_status.value)

            return CaseActionResponse(
                case_id=case_id,
                action=action.action,
                status="completed",
                performed_by=user_id,
                message=f"Case {action.action} completed successfully",
            )
