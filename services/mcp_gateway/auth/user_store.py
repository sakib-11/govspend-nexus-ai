"""Local user store — provides user CRUD and password verification for non-OIDC setups."""

import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..config import get_config
from ..models.auth import (
    User,
    UserRole,
    get_permissions_for_roles,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Hash a password with a random salt using PBKDF2-SHA256."""
    if salt is None:
        salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return key.hex(), salt


class UserStore:
    """In-memory (or DB-backed) user store for local authentication.

    Seed users are created on first access for dev/test environments.
    """

    def __init__(self, config=None, db_pool=None):
        self.config = config or get_config()
        self.db_pool = db_pool
        self._users: Dict[str, User] = {}
        self._passwords: Dict[str, tuple[str, str]] = {}  # user_id → (hash, salt)
        self._seeded = False

    def _ensure_seeded(self) -> None:
        """Create default users if the store is empty."""
        if self._seeded:
            return
        self._seeded = True

        default_users = [
            {
                "user_id": "admin-001",
                "username": "admin",
                "email": "admin@govspend.gov",
                "full_name": "System Administrator",
                "password": "admin123",
                "roles": [UserRole.ADMIN],
                "jurisdictions": ["federal", "state", "local"],
            },
            {
                "user_id": "auditor-001",
                "username": "auditor1",
                "email": "auditor1@govspend.gov",
                "full_name": "Senior Auditor",
                "password": "auditor123",
                "roles": [UserRole.AUDITOR_LEVEL_3],
                "jurisdictions": ["federal", "ca"],
            },
            {
                "user_id": "auditor-002",
                "username": "auditor2",
                "email": "auditor2@govspend.gov",
                "full_name": "Junior Auditor",
                "password": "auditor123",
                "roles": [UserRole.AUDITOR_LEVEL_1],
                "jurisdictions": ["ca"],
            },
            {
                "user_id": "analyst-001",
                "username": "analyst",
                "email": "analyst@govspend.gov",
                "full_name": "Data Analyst",
                "password": "analyst123",
                "roles": [UserRole.DATA_ANALYST],
                "jurisdictions": ["federal"],
            },
            {
                "user_id": "superadmin-001",
                "username": "superadmin",
                "email": "superadmin@govspend.gov",
                "full_name": "Super Admin",
                "password": "super123",
                "roles": [UserRole.SUPER_ADMIN],
                "jurisdictions": ["federal", "state", "local"],
            },
        ]

        for data in default_users:
            password = data.pop("password")
            user = User(**data, permissions=get_permissions_for_roles(data["roles"]))
            self._users[user.user_id] = user
            h, s = _hash_password(password)
            self._passwords[user.user_id] = (h, s)

        logger.info("Seeded %d default users", len(default_users))

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Look up a user by username."""
        self._ensure_seeded()
        username = username.strip().lower()
        for user in self._users.values():
            if user.username.lower() == username:
                return user
        return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        self._ensure_seeded()
        return self._users.get(user_id)

    def verify_password(self, user_id: str, password: str) -> bool:
        """Verify a password against the stored hash."""
        self._ensure_seeded()
        stored = self._passwords.get(user_id)
        if not stored:
            return False
        h, s = stored
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), s.encode(), 100_000)
        return computed.hex() == h

    def create_user(
        self,
        username: str,
        email: str,
        full_name: str,
        password: str,
        roles: List[UserRole],
        jurisdictions: Optional[List[str]] = None,
        created_by: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        self._ensure_seeded()

        user_id = f"user-{username}"
        if user_id in self._users:
            raise ValueError(f"User {username} already exists")
        # Also check username uniqueness
        for existing in self._users.values():
            if existing.username.lower() == username.lower():
                raise ValueError(f"User {username} already exists")

        user = User(
            user_id=user_id,
            username=username,
            email=email,
            full_name=full_name,
            roles=roles,
            jurisdictions=jurisdictions or [],
            permissions=get_permissions_for_roles(roles),
            created_by=created_by,
        )

        self._users[user_id] = user
        h, s = _hash_password(password)
        self._passwords[user_id] = (h, s)

        logger.info("User created: %s (%s)", username, user_id)
        return user

    def list_users(self) -> List[User]:
        """Return all users."""
        self._ensure_seeded()
        return list(self._users.values())

    def update_user_roles(self, user_id: str, roles: List[UserRole]) -> Optional[User]:
        """Update a user's roles."""
        user = self._users.get(user_id)
        if not user:
            return None
        user.roles = roles
        user.permissions = get_permissions_for_roles(roles)
        user.updated_at = datetime.utcnow()
        return user

    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account."""
        user = self._users.get(user_id)
        if not user:
            return False
        user.is_active = False
        user.updated_at = datetime.utcnow()
        return True

    def record_failed_login(self, user_id: str) -> None:
        """Increment failed login counter; lock if threshold exceeded."""
        user = self._users.get(user_id)
        if not user:
            return
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= self.config.MAX_FAILED_ATTEMPTS:
            user.is_locked = True
            logger.warning("User %s locked after %d failed attempts", user_id, user.failed_login_attempts)

    def reset_failed_login(self, user_id: str) -> None:
        """Reset failed login counter after successful auth."""
        user = self._users.get(user_id)
        if user:
            user.failed_login_attempts = 0
