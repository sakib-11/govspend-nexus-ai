"""Unmask workflow routes."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Query, Request

from models.unmask import UnmaskApproval, UnmaskRequestCreate, UnmaskResponse
from services.unmask_service import UnmaskService

router = APIRouter(prefix="/api/unmask", tags=["unmask"])


def _get_svc(request: Request) -> UnmaskService:
    svc = getattr(request.app.state, "unmask_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Unmask service unavailable")
    return svc


def _get_user(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.post("/request", response_model=UnmaskResponse)
async def create_unmask_request(body: UnmaskRequestCreate, request: Request) -> UnmaskResponse:
    """Create an unmask request (maker)."""
    user = _get_user(request)
    svc = _get_svc(request)
    try:
        return svc.create_request(
            body,
            user_id=getattr(user, "user_id", "unknown"),
            user_jurisdictions=getattr(user, "jurisdictions", []),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{request_id}/approve", response_model=UnmaskResponse)
async def approve_unmask(request_id: str, body: UnmaskApproval, request: Request) -> UnmaskResponse:
    """Approve or reject an unmask request (checker)."""
    user = _get_user(request)
    svc = _get_svc(request)
    try:
        return svc.approve(
            request_id,
            body,
            approver_id=getattr(user, "user_id", "unknown"),
            user_jurisdictions=getattr(user, "jurisdictions", []),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/requests")
async def list_unmask_requests(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """List pending unmask requests."""
    user = _get_user(request)
    svc = _get_svc(request)
    requests = svc.get_pending(user_jurisdictions=getattr(user, "jurisdictions", []))
    return {"requests": requests[offset : offset + limit], "total": len(requests), "limit": limit, "offset": offset}


@router.get("/{request_id}/status", response_model=UnmaskResponse)
async def get_unmask_status(request_id: str, request: Request) -> UnmaskResponse:
    """Get unmask request status."""
    user = _get_user(request)
    svc = _get_svc(request)
    result = svc.get_status(
        request_id,
        user_id=getattr(user, "user_id", None),
        user_jurisdictions=getattr(user, "jurisdictions", []),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return result
