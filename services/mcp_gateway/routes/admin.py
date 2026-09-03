"""Admin routes — user management, account unlock, and system operations."""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from typing import List, Optional

from ..models.auth import User, UserRole, Permission, get_permissions_for_roles
from ..rbac.policy_engine import PolicyEngine
from ..utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class CreateUserRequest(BaseModel):
    username: str
    email: str
    full_name: str
    password: str
    roles: List[str]
    jurisdictions: Optional[List[str]] = None


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    full_name: str
    roles: List[str]
    jurisdictions: List[str]
    permissions: List[str]
    mfa_enabled: bool
    is_active: bool
    is_locked: bool
    failed_login_attempts: int


def _require_admin(user: User, policy_engine: PolicyEngine) -> None:
    """Raise 403 if user is not an admin."""
    if not policy_engine.check_permission(user, Permission.MANAGE_USERS):
        raise HTTPException(status_code=403, detail="Permission denied: manage_users")


@router.post("/users", response_model=UserResponse)
async def create_user(request: Request, body: CreateUserRequest):
    """Create a new user (admin only)."""
    caller: User = request.state.user
    policy_engine: PolicyEngine = request.app.state.policy_engine
    _require_admin(caller, policy_engine)

    user_store = request.app.state.user_store

    try:
        roles = [UserRole(r) for r in body.roles]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid role: {exc}")

    try:
        user = user_store.create_user(
            username=body.username,
            email=body.email,
            full_name=body.full_name,
            password=body.password,
            roles=roles,
            jurisdictions=body.jurisdictions,
            created_by=caller.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        roles=[r.value for r in user.roles],
        jurisdictions=user.jurisdictions,
        permissions=[p.value for p in user.effective_permissions()],
        mfa_enabled=user.mfa_enabled,
        is_active=user.is_active,
        is_locked=user.is_locked,
        failed_login_attempts=user.failed_login_attempts,
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(request: Request, user_id: str):
    """Get a specific user (admin only)."""
    caller: User = request.state.user
    policy_engine: PolicyEngine = request.app.state.policy_engine
    _require_admin(caller, policy_engine)

    user_store = request.app.state.user_store
    user = user_store.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        roles=[r.value for r in user.roles],
        jurisdictions=user.jurisdictions,
        permissions=[p.value for p in user.effective_permissions()],
        mfa_enabled=user.mfa_enabled,
        is_active=user.is_active,
        is_locked=user.is_locked,
        failed_login_attempts=user.failed_login_attempts,
    )


@router.post("/users/{user_id}/unlock")
async def unlock_user(request: Request, user_id: str):
    """Unlock a locked user account (admin only)."""
    caller: User = request.state.user
    policy_engine: PolicyEngine = request.app.state.policy_engine
    _require_admin(caller, policy_engine)

    user_store = request.app.state.user_store
    user = user_store.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_locked = False
    user.failed_login_attempts = 0

    logger.info("User %s unlocked by %s", user_id, caller.user_id)
    return {"user_id": user_id, "message": "Account unlocked"}


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(request: Request, user_id: str):
    """Deactivate a user account (admin only)."""
    caller: User = request.state.user
    policy_engine: PolicyEngine = request.app.state.policy_engine
    _require_admin(caller, policy_engine)

    user_store = request.app.state.user_store
    result = user_store.deactivate_user(user_id)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")

    logger.info("User %s deactivated by %s", user_id, caller.user_id)
    return {"user_id": user_id, "message": "Account deactivated"}


@router.get("/audit-logs")
async def get_audit_logs(request: Request, limit: int = 100):
    """Retrieve recent audit log entries (admin only)."""
    caller: User = request.state.user
    policy_engine: PolicyEngine = request.app.state.policy_engine

    if not policy_engine.check_permission(caller, Permission.VIEW_AUDIT_LOGS):
        raise HTTPException(status_code=403, detail="Permission denied: view_audit_logs")

    audit_middleware = request.app.state.audit_middleware
    logs = audit_middleware._in_memory_logs[-limit:] if hasattr(audit_middleware, "_in_memory_logs") else []

    return {
        "logs": [
            {
                "audit_id": log.audit_id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "success": log.success,
                "ip_address": log.ip_address,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in reversed(logs)
        ],
        "count": len(logs),
    }
