"""Authentication middleware — validates JWT and attaches user/claims to request."""

import asyncio
from typing import Callable, Optional, Set

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from ..auth.token_validator import TokenValidator
from ..models.auth import User, TokenClaims
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Paths that skip authentication entirely
_PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
})

# Path prefixes that are public
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/mfa/verify",
    "/api/v1/auth/mfa/setup",
    "/docs",
    "/openapi.json",
)


def _is_public(path: str) -> bool:
    """Check if a path is public (no auth required)."""
    if path in _PUBLIC_PATHS:
        return True
    for prefix in _PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that:
        1. Skips auth for public endpoints.
        2. Extracts the Bearer token from the Authorization header.
        3. Validates the token via ``TokenValidator``.
        4. Resolves the ``User`` object.
        5. Attaches ``request.state.user`` and ``request.state.claims``.
        6. Returns 401/403 on failure.
    """

    def __init__(self, token_validator: TokenValidator):
        super().__init__()
        self.token_validator = token_validator
        self._user_store: dict[str, User] = {}  # fallback in-memory user store

    def register_user(self, user: User) -> None:
        """Register a user in the in-memory store (for dev/test)."""
        self._user_store[user.user_id] = user

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # 1. Public endpoints → pass through
        if _is_public(path):
            return await call_next(request)

        # 2. Extract token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or malformed Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[len("Bearer "):]

        # 3. Validate token
        claims: Optional[TokenClaims] = None
        try:
            claims = await self.token_validator.validate(token)
        except Exception as exc:
            logger.error("Token validation error: %s", exc)

        if claims is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 4. Resolve user
        user: Optional[User] = None
        try:
            user = await self.token_validator.get_user_from_token(token)
        except Exception as exc:
            logger.error("User resolution error: %s", exc)

        # Fallback: build user from claims + in-memory store
        if user is None:
            user = self._user_store.get(claims.sub)
        if user is None:
            # Build a minimal user from claims
            from ..models.auth import UserRole, get_permissions_for_roles

            roles = [UserRole(r) for r in claims.roles if r in UserRole.__members__]
            user = User(
                user_id=claims.sub,
                username=claims.email,
                email=claims.email,
                name=claims.name,
                roles=roles,
                jurisdictions=claims.jurisdictions,
                permissions=get_permissions_for_roles(roles),
            )

        # 5. Active / locked checks
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )
        if user.is_locked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is locked",
            )

        # 6. Attach to request state
        request.state.claims = claims
        request.state.user = user
        request.state.token = token

        # 7. Background: update session activity (fire-and-forget)
        if claims.session_id:
            asyncio.create_task(self._touch_session(claims.session_id))

        return await call_next(request)

    async def _touch_session(self, session_id: str) -> None:
        """Update session last_activity in the background."""
        try:
            if self.token_validator.db_pool:
                async with self.token_validator.db_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE sessions SET last_activity = NOW() WHERE session_id = $1",
                        session_id,
                    )
        except Exception as exc:
            logger.debug("Session touch failed: %s", exc)
