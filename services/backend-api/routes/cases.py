"""Case management routes."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from models.case import (
    CaseAction,
    CaseActionResponse,
    CaseDetail,
    CaseFilter,
    CaseStatus,
    CaseSummary,
    CaseTier,
)
from services.case_service import CaseService

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _get_svc(request: Request) -> CaseService:
    svc = getattr(request.app.state, "case_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Case service unavailable")
    return svc


def _get_user(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


# ------------------------------------------------------------------
# List cases
# ------------------------------------------------------------------


class CaseListResponse(BaseModel):
    cases: List[CaseSummary]
    total: int
    limit: int
    offset: int


@router.get("", response_model=CaseListResponse)
async def get_cases(
    request: Request,
    tier: Optional[List[str]] = Query(default=None),
    status: Optional[List[str]] = Query(default=None),
    department: Optional[str] = None,
    vendor_token: Optional[str] = None,
    min_score: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    max_score: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    search: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> CaseListResponse:
    """List cases with filtering and pagination."""
    user = _get_user(request)
    svc = _get_svc(request)

    user_jurisdictions = getattr(user, "jurisdictions", [])

    filters = CaseFilter(
        tier=[CaseTier(t) for t in tier] if tier else None,
        status=[CaseStatus(s) for s in status] if status else None,
        department=department,
        vendor_token=vendor_token,
        min_score=min_score,
        max_score=max_score,
        search=search,
    )

    cases, total = svc.get_cases(
        user_jurisdictions=user_jurisdictions,
        filters=filters,
        limit=limit,
        offset=offset,
    )

    return CaseListResponse(cases=cases, total=total, limit=limit, offset=offset)


# ------------------------------------------------------------------
# Get case detail
# ------------------------------------------------------------------


@router.get("/{case_id}", response_model=CaseDetail)
async def get_case_detail(case_id: str, request: Request) -> CaseDetail:
    """Get full case detail with signals, evidence, and actions."""
    user = _get_user(request)
    svc = _get_svc(request)

    case = svc.get_case_detail(
        case_id,
        user_jurisdictions=getattr(user, "jurisdictions", []),
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


# ------------------------------------------------------------------
# Case actions
# ------------------------------------------------------------------


@router.post("/{case_id}/approve", response_model=CaseActionResponse)
async def approve_case(case_id: str, body: CaseAction, request: Request) -> CaseActionResponse:
    """Approve a case (requires approver/admin role)."""
    user = _get_user(request)
    svc = _get_svc(request)
    body.action = "approve"

    try:
        return svc.perform_action(
            case_id, body,
            user_id=getattr(user, "user_id", "unknown"),
            user_roles=[r.value if hasattr(r, "value") else str(r) for r in getattr(user, "roles", [])],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{case_id}/reject", response_model=CaseActionResponse)
async def reject_case(case_id: str, body: CaseAction, request: Request) -> CaseActionResponse:
    """Reject a case (requires approver/admin role)."""
    user = _get_user(request)
    svc = _get_svc(request)
    body.action = "reject"

    try:
        return svc.perform_action(
            case_id, body,
            user_id=getattr(user, "user_id", "unknown"),
            user_roles=[r.value if hasattr(r, "value") else str(r) for r in getattr(user, "roles", [])],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{case_id}/escalate", response_model=CaseActionResponse)
async def escalate_case(case_id: str, body: CaseAction, request: Request) -> CaseActionResponse:
    """Escalate a case (requires Level 2+ auditor)."""
    user = _get_user(request)
    svc = _get_svc(request)
    body.action = "escalate"

    try:
        return svc.perform_action(
            case_id, body,
            user_id=getattr(user, "user_id", "unknown"),
            user_roles=[r.value if hasattr(r, "value") else str(r) for r in getattr(user, "roles", [])],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{case_id}/close", response_model=CaseActionResponse)
async def close_case(case_id: str, body: CaseAction, request: Request) -> CaseActionResponse:
    """Close a case."""
    user = _get_user(request)
    svc = _get_svc(request)
    body.action = "close"

    try:
        return svc.perform_action(
            case_id, body,
            user_id=getattr(user, "user_id", "unknown"),
            user_roles=[r.value if hasattr(r, "value") else str(r) for r in getattr(user, "roles", [])],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
