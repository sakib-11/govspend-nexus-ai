"""Session manager — creates, validates, and invalidates user sessions."""

from datetime import datetime, timedelta
from typing import Dict, Optional

from ..config import get_config
from ..models.auth import Session
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SessionManager:
    """Manages user sessions with optional Redis-backed caching.

    In-memory fallback is always available for dev/test environments.
    """

    _CACHE_PREFIX = "session:"

    def __init__(self, config=None, redis_client=None, db_pool=None):
        self.config = config or get_config()
        self.redis = redis_client
        self.db_pool = db_pool
        self._sessions: Dict[str, Session] = {}  # in-memory store

    async def create_session(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_id: Optional[str] = None,
        mfa_verified: bool = False,
    ) -> Session:
        """Create a new session for *user_id*."""
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=self.config.SESSION_TIMEOUT_MINUTES)

        session = Session(
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
            last_activity=now,
            ip_address=ip_address,
            user_agent=user_agent,
            device_id=device_id,
            is_active=True,
            mfa_verified=mfa_verified,
        )

        # Persist
        self._sessions[session.session_id] = session

        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO sessions
                           (session_id, user_id, expires_at, ip_address, user_agent, device_id, is_active, mfa_verified)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                        session.session_id,
                        user_id,
                        expires_at,
                        ip_address,
                        user_agent,
                        device_id,
                        True,
                        mfa_verified,
                    )
            except Exception as exc:
                logger.error("DB session create failed: %s", exc)

        # Cache in Redis
        await self._cache_session(session)

        logger.info("Session created: %s for user %s", session.session_id, user_id)
        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Fetch a session by ID, checking cache → memory → DB."""
        # 1. Cache
        cached = await self._redis_get(f"{self._CACHE_PREFIX}{session_id}")
        if cached == "invalid":
            return None

        # 2. In-memory
        session = self._sessions.get(session_id)
        if session:
            if session.is_expired():
                await self.invalidate_session(session_id)
                return None
            return session

        # 3. DB
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM sessions WHERE session_id = $1", session_id
                    )
                    if row:
                        session = Session(
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
                        self._sessions[session.session_id] = session
                        if session.is_expired():
                            await self.invalidate_session(session_id)
                            return None
                        await self._cache_session(session)
                        return session
            except Exception as exc:
                logger.error("DB session fetch failed: %s", exc)

        return None

    async def invalidate_session(self, session_id: str) -> None:
        """Mark a session as inactive everywhere."""
        session = self._sessions.pop(session_id, None)
        if session:
            session.invalidate()

        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE sessions SET is_active = FALSE WHERE session_id = $1",
                        session_id,
                    )
            except Exception as exc:
                logger.error("DB session invalidate failed: %s", exc)

        await self._redis_set(f"{self._CACHE_PREFIX}{session_id}", "invalid", 300)
        logger.info("Session invalidated: %s", session_id)

    async def touch_session(self, session_id: str) -> None:
        """Update last_activity timestamp."""
        session = self._sessions.get(session_id)
        if session and not session.is_expired():
            session.touch()
            await self._cache_session(session)

    async def invalidate_all_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user. Returns count invalidated."""
        count = 0
        for sid, session in list(self._sessions.items()):
            if session.user_id == user_id:
                await self.invalidate_session(sid)
                count += 1
        return count

    async def _cache_session(self, session: Session) -> None:
        await self._redis_set(
            f"{self._CACHE_PREFIX}{session.session_id}", "active", 300
        )

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
