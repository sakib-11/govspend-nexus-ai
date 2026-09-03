"""Authentication routes — OIDC/PKCE login and user session management."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from models.auth import AuthRequest, AuthResponse, MFASetupRequest, MFARequest

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

# ======================================================================
# PKCE helpers
# ======================================================================

_PkceLength = 64
def _generate_code_verifier() -> str:
    return secrets.token_urlsafe(_PkceLength)
def _generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().replace("=", "")
    return challenge

# ======================================================================
# Endpoints
# ======================================================================

@router.post("/login")
async def login(
    body: AuthRequest,
    request: Request,
) -> AuthResponse:
    """Authenticate user via OIDC PKCE and issue JWT."""
    # For production, integrate with OIDC discovery
    # For now, mock validation with demo credentials
    if body.username == "auditor@example.com" and body.password == "auditor123":
        # Generate session ID
        session_id = f"session_{secrets.token_hex(16)}"

        # Mock JWT (replace with real JWT signing)
        token_data = {
            "user_id": "user_123",
            "username": body.username,
            "exp": 3600,  # 1 hour
        }
        token = json.dumps(token_data)

        # Store user in session
        user = type(
            "User",
            (),
            {
                "user_id": "user_123",
                "username": body.username,
                "email": body.username,
                "full_name": "Demo Auditor",
                "roles": ["auditor_level_2"],
                "jurisdictions": ["all"],
                "permissions": ["read_cases", "approve_cases", "approve_unmask"],
                "mfa_enabled": False,
                "last_login": None,
                "session_id": session_id,
            },
        )()

        request.state.user = user

        # Set session cookie
        response = Response(content=json.dumps({"token": token, "user": user.__dict__}))
        response.set_cookie("session_token", token, httponly=True, secure=False)

        return AuthResponse(
            token=token,
            user=user.__dict__,
            requires_mfa=False,
        )

    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/oidc/config")
async def get_oidc_config() -> Dict[str, Any]:
    """Provide OIDC discovery document for frontend PKCE flow."""
    return {
        "issuer": "https://auth.govspend.ai",
        "authorization_endpoint": "https://auth.govspend.ai/oauth/authorize",
        "token_endpoint": "https://auth.govspend.ai/oauth/token",
        "userinfo_endpoint": "https://auth.govspend.ai/oauth/userinfo",
        "jwks_uri": "https://auth.govspend.ai/oauth/jwks",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["openid", "profile", "email", "roles", "jurisdictions"],
        "claims_supported": [
            "sub",
            "aud",
            "iss",
            "auth_time",
            "name",
            "given_name",
            "family_name",
            "preferred_username",
            "email",
            "roles",
            "jurisdictions",
            "permissions",
            "mfa_enabled",
        ],
    }


@router.get("/user/me")
async def get_current_user(request: Request) -> Dict[str, Any]:
    """Return current user profile with roles, jurisdictions and permissions."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "roles": user.roles,
        "jurisdictions": user.jurisdictions,
        "permissions": user.permissions,
        "mfa_enabled": user.mfa_enabled,
        "last_login": user.last_login,
    }


@router.post("/logout")
async def logout(request: Request) -> Dict[str, str]:
    """Clear user session and revoke tokens."""
    # In production, invalidate JWT and session
    request.state.user = None
    return {"status": "logged out"}


@router.post("/mfa/setup")
async def setup_mfa(
    body: MFASetupRequest,
    request: Request,
) -> Dict[str, Any]:
    """Provision TOTP secret for MFA and return QR code."""
    # In production, integrate with TOTP service
    secret = secrets.token_urlsafe(32)

    # Mock QR code URL (TOTP URI)
    qr_url = f"otpauth://totp/GovSpend:{body.username}?secret={secret}&issuer=GovSpend"

    return {
        "secret": secret,
        "qr_code_url": qr_url,
        "backup_codes": [secrets.token_hex(4) for _ in range(8)],
    }


@router.post("/mfa/verify")
async def verify_mfa(body: MFARequest, request: Request) -> Dict[str, Any]:
    """Verify TOTP code and enable MFA for user."""
    # In production, integrate with TOTP verification
    if body.code == "123456":
        user = getattr(request.state, "user", None)
        if user:
            user.mfa_enabled = True
            return {"verified": True}

    raise HTTPException(status_code=400, detail="Invalid MFA code")