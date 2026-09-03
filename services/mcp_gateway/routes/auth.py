"""Authentication routes — login, MFA, logout, token refresh, user info."""

from datetime import datetime, timezone
from typing import List, Optional, Set

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from ..auth.mfa_handler import MFAHandler
from ..auth.session_manager import SessionManager
from ..auth.token_validator import TokenValidator
from ..auth.user_store import UserStore
from ..models.auth import (
    AuthRequest,
    AuthResponse,
    MFARequest,
    MFASetupRequest,
    MFASetupResponse,
    Permission,
    User,
    UserRole,
    get_permissions_for_roles,
)
from ..rbac.policy_engine import PolicyEngine
from ..utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str
    mfa_code: Optional[str] = None
    device_id: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


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


class PermissionsResponse(BaseModel):
    user_id: str
    username: str
    roles: List[str]
    permissions: List[str]
    jurisdictions: List[str]


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class RoleUpdateRequest(BaseModel):
    roles: List[str]


class UserListResponse(BaseModel):
    users: List[UserResponse]
    count: int


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=AuthResponse)
async def login(
    request: Request,
    body: LoginRequest,
):
    """Authenticate a user with username/password.

    If MFA is enabled and the user has MFA configured, returns
    ``requires_mfa=True`` and the caller must call ``/mfa/verify``.
    """
    # Retrieve services from app.state (set during lifespan)
    user_store: UserStore = request.app.state.user_store
    token_validator: TokenValidator = request.app.state.token_validator
    session_manager: SessionManager = request.app.state.session_manager
    mfa_handler: MFAHandler = request.app.state.mfa_handler

    # 1. Find user
    user = user_store.get_user_by_username(body.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # 2. Check account status
    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked due to too many failed login attempts",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # 3. Verify password
    if not user_store.verify_password(user.user_id, body.password):
        user_store.record_failed_login(user.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # 4. Successful password check → reset counter
    user_store.reset_failed_login(user.user_id)

    # 5. Create session
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    session = await session_manager.create_session(
        user_id=user.user_id,
        ip_address=ip,
        user_agent=ua,
        device_id=body.device_id,
        mfa_verified=False,
    )

    # 6. Check if MFA is required
    if user.mfa_enabled and body.mfa_code:
        # Verify MFA inline
        mfa_request = MFARequest(
            user_id=user.user_id,
            method=user.mfa_methods[0] if user.mfa_methods else "totp",
            code=body.mfa_code,
            session_id=session.session_id,
        )
        verified = await mfa_handler.verify_mfa(mfa_request)
        if not verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code",
            )
        session.mfa_verified = True
        await mfa_handler.update_session_mfa(session.session_id, user.user_id)

    # 7. Generate tokens
    ip_addr = request.client.host if request.client else None
    access_token = token_validator.generate_access_token(user, session.session_id, ip_addr)
    refresh_token = token_validator.generate_refresh_token(user, session.session_id)

    # 8. Update user last login
    user.last_login = datetime.now(timezone.utc)
    user.active_session_id = session.session_id

    requires_mfa = user.mfa_enabled and not session.mfa_verified
    mfa_methods = user.mfa_methods if requires_mfa else []

    logger.info("User logged in: %s (mfa=%s)", user.username, requires_mfa)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=session_manager.config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user,
        requires_mfa=requires_mfa,
        mfa_methods=mfa_methods,
    )


# ---------------------------------------------------------------------------
# MFA
# ---------------------------------------------------------------------------

@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    request: Request,
    body: MFASetupRequest,
):
    """Setup MFA for the authenticated user."""
    token_validator: TokenValidator = request.app.state.token_validator
    mfa_handler: MFAHandler = request.app.state.mfa_handler

    # Authenticate the caller
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    claims = await token_validator.validate(auth_header[len("Bearer "):])
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid token")

    if claims.sub != body.user_id and not any(
        r in ("super_admin", "admin") for r in claims.roles
    ):
        raise HTTPException(status_code=403, detail="Not authorized to setup MFA for this user")

    try:
        return await mfa_handler.setup_mfa(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/mfa/verify")
async def verify_mfa(
    request: Request,
    body: MFARequest,
):
    """Verify an MFA code."""
    mfa_handler: MFAHandler = request.app.state.mfa_handler
    session_manager: SessionManager = request.app.state.session_manager

    verified = await mfa_handler.verify_mfa(body)
    if not verified:
        raise HTTPException(status_code=401, detail="Invalid MFA code")

    # Mark session as MFA-verified
    await mfa_handler.update_session_mfa(body.session_id, body.user_id)

    return {"status": "verified", "message": "MFA verification successful"}


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: Request,
    body: RefreshRequest,
):
    """Refresh an access token using a refresh token."""
    token_validator: TokenValidator = request.app.state.token_validator
    session_manager: SessionManager = request.app.state.session_manager

    # Decode refresh token (no signature check here — validated by token_validator)
    import jwt as pyjwt

    try:
        payload = pyjwt.decode(
            body.refresh_token,
            token_validator.config.SECRET_KEY,
            algorithms=[token_validator.config.JWT_ALGORITHM],
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    session_id = payload.get("session_id")
    if not user_id or not session_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Verify session
    session = await session_manager.get_session(session_id)
    if not session or not session.is_active or session.is_expired():
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    # Get user
    user_store: UserStore = request.app.state.user_store
    user = user_store.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Generate new tokens
    ip = request.client.host if request.client else None
    access_token = token_validator.generate_access_token(user, session_id, ip)
    refresh_token_val = token_validator.generate_refresh_token(user, session_id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token_val,
        expires_in=session_manager.config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user,
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@router.post("/logout")
async def logout(request: Request):
    """Logout user — blacklist token and invalidate session."""
    token_validator: TokenValidator = request.app.state.token_validator
    session_manager: SessionManager = request.app.state.session_manager

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"status": "logged_out", "message": "No active token"}

    token = auth_header[len("Bearer "):]

    # Blacklist the access token
    await token_validator.blacklist_token(token)

    # Invalidate session
    claims = await token_validator.validate(token)
    if claims and claims.session_id:
        await session_manager.invalidate_session(claims.session_id)

    return {"status": "logged_out", "message": "Successfully logged out"}


# ---------------------------------------------------------------------------
# User info
# ---------------------------------------------------------------------------

@router.get("/user/me", response_model=UserResponse)
async def get_current_user(request: Request):
    """Get the currently authenticated user's profile."""
    user: User = request.state.user
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
    )


@router.get("/permissions", response_model=PermissionsResponse)
async def get_user_permissions(request: Request):
    """Get the full effective permission set for the current user."""
    user: User = request.state.user
    policy_engine: PolicyEngine = request.app.state.policy_engine
    perms = policy_engine.get_user_permissions(user)
    return PermissionsResponse(
        user_id=user.user_id,
        username=user.username,
        roles=[r.value for r in user.roles],
        permissions=[p.value for p in perms],
        jurisdictions=user.jurisdictions,
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    request: Request,
):
    """List all users (admin only)."""
    user: User = request.state.user
    policy_engine: PolicyEngine = request.app.state.policy_engine

    if not policy_engine.check_permission(user, Permission.MANAGE_USERS):
        raise HTTPException(status_code=403, detail="Permission denied: manage_users")

    user_store: UserStore = request.app.state.user_store
    all_users = user_store.list_users()
    return UserListResponse(
        users=[
            UserResponse(
                user_id=u.user_id,
                username=u.username,
                email=u.email,
                full_name=u.full_name,
                roles=[r.value for r in u.roles],
                jurisdictions=u.jurisdictions,
                permissions=[p.value for p in u.effective_permissions()],
                mfa_enabled=u.mfa_enabled,
                is_active=u.is_active,
            )
            for u in all_users
        ],
        count=len(all_users),
    )


@router.put("/users/{user_id}/roles")
async def update_user_roles(
    request: Request,
    user_id: str,
    body: RoleUpdateRequest,
):
    """Update a user's roles (admin only)."""
    caller: User = request.state.user
    policy_engine: PolicyEngine = request.app.state.policy_engine

    if not policy_engine.check_permission(caller, Permission.MANAGE_ROLES):
        raise HTTPException(status_code=403, detail="Permission denied: manage_roles")

    user_store: UserStore = request.app.state.user_store
    try:
        roles = [UserRole(r) for r in body.roles]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid role: {exc}")

    updated = user_store.update_user_roles(user_id, roles)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user_id,
        "roles": [r.value for r in updated.roles],
        "message": "Roles updated successfully",
    }
