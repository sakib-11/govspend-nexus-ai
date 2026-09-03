"""MFA service — TOTP-based multi-factor authentication with backup codes."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from config import UnmaskConfig

logger = logging.getLogger(__name__)


class MFAService:
    """TOTP-based MFA with backup codes and lockout support.

    In production, TOTP secrets would be provisioned per user via a
    dedicated MFA management flow.  This service handles code generation,
    verification, and backup-code consumption.
    """

    def __init__(self, config: UnmaskConfig, db_pool=None) -> None:
        self.config = config
        self.db_pool = db_pool
        # In-memory store for dev/testing: user_id -> TOTP secret
        self._secrets: dict[str, str] = {}
        # In-memory backup codes: user_id -> list of code hashes
        self._backup_codes: dict[str, list[str]] = {}
        # Failed attempt counters: user_id -> (count, first_failure_at)
        self._failures: dict[str, tuple[int, datetime]] = {}

    # ------------------------------------------------------------------
    # TOTP
    # ------------------------------------------------------------------

    def generate_totp_secret(self, user_id: str) -> str:
        """Generate and store a TOTP secret for *user_id*."""
        secret = secrets.token_hex(20)
        self._secrets[user_id] = secret
        return secret

    def generate_code(self, user_id: str) -> Optional[str]:
        """Generate a 6-digit TOTP code for *user_id*.

        Returns ``None`` if no secret is provisioned.
        """
        secret = self._secrets.get(user_id)
        if not secret:
            return None

        # Time-based one-time password (30-second window)
        counter = int(time.time()) // 30
        digest = hmac.new(
            secret.encode("utf-8"),
            counter.to_bytes(8, "big"),
            hashlib.sha256,
        ).hexdigest()
        code = str(int(digest[:8], 16))[-self.config.MFA_CODE_LENGTH:]
        return code.zfill(self.config.MFA_CODE_LENGTH)

    def verify_code(self, user_id: str, code: str) -> bool:
        """Verify a TOTP code for *user_id*.

        Accepts codes from the current and previous time window to allow
        for clock skew.
        """
        if self._is_locked_out(user_id):
            logger.warning("MFA lockout active for %s", user_id)
            return False

        for offset in (0, -1):
            secret = self._secrets.get(user_id)
            if not secret:
                continue
            counter = int(time.time()) // 30 + offset
            digest = hmac.new(
                secret.encode("utf-8"),
                counter.to_bytes(8, "big"),
                hashlib.sha256,
            ).hexdigest()
            expected = str(int(digest[:8], 16))[-self.config.MFA_CODE_LENGTH:].zfill(
                self.config.MFA_CODE_LENGTH
            )
            if hmac.compare_digest(code, expected):
                self._clear_failures(user_id)
                return True

        self._record_failure(user_id)
        return False

    # ------------------------------------------------------------------
    # Backup codes
    # ------------------------------------------------------------------

    def generate_backup_codes(self, user_id: str, count: int = 10) -> List[str]:
        """Generate plaintext backup codes and store their hashes."""
        codes: List[str] = []
        hashed: List[str] = []
        for _ in range(count):
            code = secrets.token_hex(4).upper()  # 8-char hex code
            codes.append(code)
            hashed.append(hashlib.sha256(code.encode("utf-8")).hexdigest())
        self._backup_codes[user_id] = hashed
        return codes

    def verify_backup_code(self, user_id: str, code: str) -> bool:
        """Consume a backup code for *user_id*."""
        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        stored = self._backup_codes.get(user_id, [])
        if code_hash in stored:
            stored.remove(code_hash)
            self._clear_failures(user_id)
            return True
        self._record_failure(user_id)
        return False

    # ------------------------------------------------------------------
    # Combined verification
    # ------------------------------------------------------------------

    async def verify_mfa(
        self, user_id: str, code: str, context: str = "",
    ) -> bool:
        """Verify an MFA code (TOTP or backup) for a given context."""
        if not self.config.MFA_ENABLED:
            return True

        if not code:
            return False

        # Try TOTP first
        if self.verify_code(user_id, code):
            return True

        # Fall back to backup code
        return self.verify_backup_code(user_id, code)

    async def verify_mfa_for_approval(
        self, request_id: str, user_id: str, code: Optional[str],
    ) -> bool:
        """Verify MFA for an approval action."""
        if not self.config.MFA_ENABLED:
            return True
        if not code:
            return False
        return await self.verify_mfa(user_id, code, context=f"approve:{request_id}")

    # ------------------------------------------------------------------
    # Lockout
    # ------------------------------------------------------------------

    def _record_failure(self, user_id: str) -> None:
        count, first_at = self._failures.get(user_id, (0, datetime.now(timezone.utc)))
        count += 1
        self._failures[user_id] = (count, first_at)

    def _clear_failures(self, user_id: str) -> None:
        self._failures.pop(user_id, None)

    def _is_locked_out(self, user_id: str) -> bool:
        entry = self._failures.get(user_id)
        if not entry:
            return False
        count, first_at = entry
        if count >= self.config.MFA_MAX_ATTEMPTS:
            lockout_until = first_at + timedelta(minutes=self.config.MFA_LOCKOUT_MINUTES)
            if datetime.now(timezone.utc) < lockout_until:
                return True
            # Lockout expired
            self._clear_failures(user_id)
        return False
