"""JWT token validation with caching and blacklisting."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from ..config import get_config
from ..models.auth import (
    Permission,
    TokenClaims,
    User,
    UserRole,
    get_permissions_for_roles,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class TokenValidator:
    """JWT token validation with Redis-backed blacklist and session checks."""

    _BLACKLIST_PREFIX = "blacklist:token:"
    _USER_CACHE_PREFIX = "user:"
    _SESSION_CACHE_PREFIX = "session:"

    def __init__(self, config=None, redis_client=None, db_pool=None):
        self.config = config or get_config()
        self.redis = redis_client
        self.db_pool = db_pool

    # ------------------------------------------------------------------
    # Core validation
    # ------------------------------------------------------------------

    async def validate(self, token: str) -> Optional[TokenClaims]:
        """Validate a JWT and return decoded claims, or None if invalid."""

        if await self._is_blacklisted(token):
            return None

        try:
            payload = jwt.decode(
                token,
                self.config.SECRET_KEY,
                algorithms=[self.config.JWT_ALGORITHM],
                options={"verify_exp": False, "verify_aud": False},
            )
        except jwt.InvalidTokenError as exc:
            logger.debug("Invalid token: %s", exc)
            return None

        # Manual exp check with timezone-aware datetime
        exp_ts = payload.get("exp")
        if exp_ts is not None:
            exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
            if exp_dt < datetime.now(timezone.utc):
                return None

        claims = TokenClaims(
            sub=payload["sub"],
            email=payload.get("email", ""),
            name=payload.get("name", ""),
            roles=payload.get("roles", []),
            jurisdictions=payload.get("jurisdictions", []),
            permissions=payload.get("permissions", []),
            iss=payload.get("iss", ""),
            aud=payload.get("aud", ""),
            exp=exp_dt if exp_ts else datetime.now(timezone.utc),
            iat=datetime.fromtimestamp(payload.get("iat", 0), tz=timezone.utc),
            session_id=payload.get("session_id"),
            mfa_verified=payload.get("mfa_verified", False),
            device_id=payload.get("device_id"),
            ip_address=payload.get("ip_address"),
        )

        # Verify session is still alive
        if claims.session_id and not await self._verify_session(
            claims.session_id, claims.sub
        ):
            return None

        return claims

    async def get_user_from_token(self, token: str) -> Optional[User]:
        """Validate token and return the associated User object."""

        claims = await self.validate(token)
        if not claims:
            return None

        # Try Redis cache first
        cache_key = f"{self._USER_CACHE_PREFIX}{claims.sub}"
        cached = await self._redis_get(cache_key)
        if cached:
            try:
                return User(**json.loads(cached))
            except Exception:
                pass

        # Fetch from in-memory store
        user = await self._get_user_by_id(claims.sub)
        if user:
            await self._redis_set(cache_key, json.dumps(user.model_dump(mode="json", exclude={"permissions"}), default=str), 300)
        return user

    def _validate_token_sync(self, token: str) -> Optional[TokenClaims]:
        """Synchronous token validation (no DB/Redis) — useful for tests."""
        try:
            payload = jwt.decode(
                token,
                self.config.SECRET_KEY,
                algorithms=[self.config.JWT_ALGORITHM],
                options={"verify_exp": False, "verify_aud": False},
            )
        except jwt.InvalidTokenError:
            return None

        exp_ts = payload.get("exp")
        exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc) if exp_ts else datetime.now(timezone.utc)
        if exp_dt < datetime.now(timezone.utc):
            return None

        return TokenClaims(
            sub=payload["sub"],
            email=payload.get("email", ""),
            name=payload.get("name", ""),
            roles=payload.get("roles", []),
            jurisdictions=payload.get("jurisdictions", []),
            permissions=payload.get("permissions", []),
            iss=payload.get("iss", ""),
            aud=payload.get("aud", ""),
            exp=exp_dt,
            iat=datetime.fromtimestamp(payload.get("iat", 0), tz=timezone.utc),
            session_id=payload.get("session_id"),
            mfa_verified=payload.get("mfa_verified", False),
            device_id=payload.get("device_id"),
            ip_address=payload.get("ip_address"),
        )

    # ------------------------------------------------------------------
    # Blacklisting
    # ------------------------------------------------------------------

    async def blacklist_token(self, token: str, expiry_seconds: int = 86400) -> None:
        """Add a token to the blacklist (e.g. on logout)."""
        token_hash = self._hash_token(token)
        key = f"{self._BLACKLIST_PREFIX}{token_hash}"
        await self._redis_set(key, "1", expiry_seconds)

    async def _is_blacklisted(self, token: str) -> bool:
        token_hash = self._hash_token(token)
        return await self._redis_exists(f"{self._BLACKLIST_PREFIX}{token_hash}")

    # ------------------------------------------------------------------
    # Session verification
    # ------------------------------------------------------------------

    async def _verify_session(self, session_id: str, user_id: str) -> bool:
        """Check if session is active and belongs to the user."""

        cache_key = f"{self._SESSION_CACHE_PREFIX}{session_id}"
        cached = await self._redis_get(cache_key)
        if cached == "active":
            return True
        if cached == "inactive":
            return False

        # Fetch from DB
        session = await self._get_session(session_id)
        if session is None:
            await self._redis_set(cache_key, "inactive", 60)
            return False

        valid = session.is_active and not session.is_expired() and session.user_id == user_id
        await self._redis_set(cache_key, "active" if valid else "inactive", 60)
        return valid

    # ------------------------------------------------------------------
    # JWT generation helpers
    # ------------------------------------------------------------------

    def generate_access_token(self, user: User, session_id: str, ip_address: Optional[str] = None) -> str:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=self.config.ACCESS_TOKEN_EXPIRE_MINUTES)
        effective_perms = get_permissions_for_roles(user.roles)
        payload = {
            "sub": user.user_id,
            "email": user.email,
            "name": user.full_name,
            "roles": [r.value for r in user.roles],
            "jurisdictions": user.jurisdictions,
            "permissions": [p.value for p in effective_perms],
            "iss": self.config.OIDC_ISSUER,
            "aud": self.config.OIDC_CLIENT_ID,
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
            "session_id": session_id,
            "mfa_verified": user.mfa_enabled,
            "type": "access",
        }
        if ip_address:
            payload["ip_address"] = ip_address
        return jwt.encode(payload, self.config.SECRET_KEY, algorithm=self.config.JWT_ALGORITHM)

    def generate_refresh_token(self, user: User, session_id: str) -> str:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(days=self.config.REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": user.user_id,
            "session_id": session_id,
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
            "type": "refresh",
        }
        return jwt.encode(payload, self.config.SECRET_KEY, algorithm=self.config.JWT_ALGORITHM)

    # ------------------------------------------------------------------
    # Storage helpers (in-memory for dev / test, asyncpg in production)
    # ------------------------------------------------------------------

    async def _get_user_by_id(self, user_id: str) -> Optional[User]:
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
                if row:
                    roles = [UserRole(r) for r in row["roles"]]
                    return User(
                        user_id=row["user_id"],
                        username=row["username"],
                        email=row["email"],
                        full_name=row["full_name"],
                        roles=roles,
                        jurisdictions=row["jurisdictions"],
                        permissions=get_permissions_for_roles(roles),
                        mfa_enabled=row["mfa_enabled"],
                        mfa_methods=row["mfa_methods"],
                        is_active=row["is_active"],
                        is_locked=row["is_locked"],
                        failed_login_attempts=row["failed_attempts"],
                    )
        return None

    async def _get_session(self, session_id: str):
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM sessions WHERE session_id = $1", session_id
                )
                if row:
                    from ..models.auth import Session

                    return Session(
                        session_id=row["session_id"],
                        user_id=row["user_id"],
                        created_at=row["created_at"],
                        expires_at=row["expires_at"],
                        last_activity=row["last_activity"],
                        ip_address=row.get("ip_address"),
                        user_agent=row.get("user_agent"),
                        device_id=row.get("device_id"),
                        is_active=row["is_active"],
                        mfa_verified=row["mfa_verified"],
                    )
        return None

    # ------------------------------------------------------------------
    # Redis helpers (graceful no-op when Redis unavailable)
    # ------------------------------------------------------------------

    async def _redis_get(self, key: str) -> Optional[str]:
        if not self.redis:
            return None
        try:
            return await self.redis.get(key)
        except Exception:
            return None

    async def _redis_set(self, key: str, value: str, ttl: int) -> None:
        if not self.redis:
            return
        try:
            await self.redis.setex(key, ttl, value)
        except Exception:
            pass

    async def _redis_exists(self, key: str) -> bool:
        if not self.redis:
            return False
        try:
            return bool(await self.redis.exists(key))
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
