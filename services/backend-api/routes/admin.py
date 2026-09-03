"""Admin dashboard routes."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from models.admin import AuditLogEntry, PolicyWeight, PolicyWeightCreate, UserRoleUpdate
from services.admin_service import AdminService

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_svc(request: Request) -> AdminService:
    svc = getattr(request.app.state, "admin_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Admin service unavailable")
    return svc


def _require_admin(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    roles = [r.value if hasattr(r, "value") else str(r) for r in getattr(user, "roles", [])]
    if "admin" not in roles and "super_admin" not in roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ------------------------------------------------------------------
# Policy weights
# ------------------------------------------------------------------


@router.get("/policy-weights", response_model=List[PolicyWeight])
async def get_policy_weights(request: Request) -> List[PolicyWeight]:
    """List all policy weight versions."""
    _require_admin(request)
    svc = _get_svc(request)
    return svc.get_policies()


@router.post("/policy-weights", response_model=PolicyWeight)
async def create_policy_weight(body: PolicyWeightCreate, request: Request) -> PolicyWeight:
    """Create a new policy weight version."""
    user = _require_admin(request)
    svc = _get_svc(request)
    try:
        return svc.create_policy(body, created_by=getattr(user, "user_id", "admin"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------------
# Audit log
# ------------------------------------------------------------------


class AuditLogResponse:
    pass


@router.get("/audit-log")
async def get_audit_logs(
    request: Request,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Get audit logs with filters."""
    _require_admin(request)
    svc = _get_svc(request)
    entries, total = svc.get_audit_logs(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )
    return {
        "entries": [e.model_dump(mode="json") for e in entries],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ------------------------------------------------------------------
# User management
# ------------------------------------------------------------------


@router.put("/users/{user_id}/roles")
async def update_user_roles(user_id: str, body: UserRoleUpdate, request: Request) -> dict:
    """Update user roles and jurisdictions."""
    user = _require_admin(request)
    svc = _get_svc(request)
    if body.user_id != user_id:
        raise HTTPException(status_code=400, detail="User ID mismatch")
    return svc.update_user_roles(
        user_id=user_id,
        roles=body.roles,
        jurisdictions=body.jurisdictions,
        updated_by=getattr(user, "user_id", "admin"),
    )


@router.get("/users")
async def list_users(request: Request) -> dict:
    """List all users."""
    _require_admin(request)
    svc = _get_svc(request)
    return {"users": svc.list_users(), "total": len(svc.list_users())}
