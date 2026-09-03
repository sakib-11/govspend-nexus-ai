"""Multi-Factor Authentication handler with TOTP, SMS, and Email support."""

import hashlib
import io
import random
import string
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..config import get_config
from ..models.auth import MFARequest, MFASetupRequest, MFASetupResponse
from ..utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pure-Python TOTP (RFC 6238) — zero external deps for core flow
# ---------------------------------------------------------------------------

# Base32 alphabet
_B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def _b32_encode(data: bytes) -> str:
    """RFC 4648 Base32 encode."""
    result = []
    acc = 0
    bits = 0
    for byte in data:
        acc = (acc << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            result.append(_B32[(acc >> bits) & 0x1F])
    if bits:
        result.append(_B32[(acc << (5 - bits)) & 0x1F])
    return "".join(result)


def _hmac_sha1(key: bytes, message: bytes) -> bytes:
    """HMAC-SHA1 implementation (RFC 2104)."""
    block_size = 64
    if len(key) > block_size:
        key = hashlib.sha1(key).digest()

    key_padded = key + b"\x00" * (block_size - len(key))
    o_key_pad = bytes(k ^ 0x5C for k in key_padded)
    i_key_pad = bytes(k ^ 0x36 for k in key_padded)

    return hashlib.sha1(o_key_pad + hashlib.sha1(i_key_pad + message).digest()).digest()


def _int_to_bytes(n: int) -> bytes:
    return n.to_bytes(8, "big")


def _generate_totp(secret_b32: str, time_step: int = 30, digits: int = 6) -> str:
    """Generate a TOTP code."""
    # Decode base32 secret
    secret = bytearray()
    for char in secret_b32.upper():
        if char in _B32:
            idx = _B32.index(char)
            secret.append(idx)

    # Time counter
    counter = int(time.time()) // time_step

    # HMAC-SHA1
    msg = _int_to_bytes(counter)
    h = _hmac_sha1(bytes(secret), msg)

    # Dynamic truncation (RFC 4226)
    offset = h[-1] & 0x0F
    code_int = (
        ((h[offset] & 0x7F) << 24)
        | ((h[offset + 1] & 0xFF) << 16)
        | ((h[offset + 2] & 0xFF) << 8)
        | (h[offset + 3] & 0xFF)
    )
    code_int = code_int % (10 ** digits)
    return str(code_int).zfill(digits)


def _verify_totp(secret_b32: str, code: str, window: int = 1) -> bool:
    """Verify a TOTP code with a ±window tolerance."""
    time_step = 30
    counter = int(time.time()) // time_step

    for delta in range(-window, window + 1):
        expected_counter = counter + delta
        secret_bytes = bytearray()
        for char in secret_b32.upper():
            if char in _B32:
                secret_bytes.append(_B32.index(char))
        msg = _int_to_bytes(expected_counter)
        h = _hmac_sha1(bytes(secret_bytes), msg)
        offset = h[-1] & 0x0F
        code_int = (
            ((h[offset] & 0x7F) << 24)
            | ((h[offset + 1] & 0xFF) << 16)
            | ((h[offset + 2] & 0xFF) << 8)
            | (h[offset + 3] & 0xFF)
        )
        expected = str(code_int % (10 ** len(code))).zfill(len(code))
        if expected == code:
            return True
    return False


# ---------------------------------------------------------------------------
# MFA Handler
# ---------------------------------------------------------------------------


class MFAHandler:
    """Multi-Factor Authentication handler with in-memory + DB storage."""

    def __init__(self, config=None, db_pool=None):
        self.config = config or get_config()
        self.db_pool = db_pool

        # In-memory stores (for dev/test)
        self._mfa_secrets: Dict[str, Dict[str, Any]] = {}
        self._pending_codes: Dict[str, Tuple[str, float]] = {}  # code → (code, expiry)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    async def setup_mfa(self, request: MFASetupRequest) -> MFASetupResponse:
        """Setup MFA for a user."""
        if request.method == "totp":
            return await self._setup_totp(request)
        elif request.method == "sms":
            return await self._setup_sms(request)
        elif request.method == "email":
            return await self._setup_email(request)
        else:
            raise ValueError(f"Unsupported MFA method: {request.method}")

    async def _setup_totp(self, request: MFASetupRequest) -> MFASetupResponse:
        """Setup TOTP — generate secret, provisioning URI, and backup codes."""
        # Generate 20-byte random secret
        secret_bytes = bytes(random.getrandbits(8) for _ in range(20))
        secret_b32 = _b32_encode(secret_bytes)

        # Backup codes (8-char alphanumeric)
        backup_codes = [
            "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            for _ in range(10)
        ]

        # Store
        self._mfa_secrets[request.user_id] = {
            "totp_secret": secret_b32,
            "totp_enabled": True,
            "backup_codes": backup_codes,
            "method": "totp",
        }

        # Persist to DB if available
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO mfa_secrets (user_id, totp_secret, totp_enabled, backup_codes)
                       VALUES ($1, $2, TRUE, $3)
                       ON CONFLICT (user_id) DO UPDATE
                       SET totp_secret = $2, totp_enabled = TRUE, backup_codes = $3, updated_at = NOW()""",
                    request.user_id,
                    secret_b32,
                    backup_codes,
                )
                await conn.execute(
                    """UPDATE users SET mfa_enabled = TRUE
                       WHERE user_id = $1 AND NOT ($2 = ANY(mfa_methods))""",
                    request.user_id,
                    "totp",
                )

        logger.info("TOTP MFA setup for user %s", request.user_id)

        return MFASetupResponse(
            secret=secret_b32,
            qr_code=self._build_provisioning_uri(secret_b32, request.user_id),
            backup_codes=backup_codes,
            method="totp",
            status="setup_complete",
        )

    async def _setup_sms(self, request: MFASetupRequest) -> MFASetupResponse:
        """Setup SMS MFA."""
        if not request.phone_number:
            raise ValueError("Phone number required for SMS MFA")

        code = self._generate_verification_code()
        self._pending_codes[f"sms:{request.user_id}"] = (code, time.time() + self.config.MFA_CODE_EXPIRY_SECONDS)

        # In production: call Twilio/SNS
        logger.info("SMS MFA code sent to %s for user %s", request.phone_number, request.user_id)

        self._mfa_secrets[request.user_id] = {
            "phone_number": request.phone_number,
            "sms_enabled": True,
            "method": "sms",
        }

        backup_codes = [
            "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            for _ in range(10)
        ]

        return MFASetupResponse(
            method="sms",
            status="verification_pending",
            backup_codes=backup_codes,
        )

    async def _setup_email(self, request: MFASetupRequest) -> MFASetupResponse:
        """Setup Email MFA."""
        if not request.email:
            raise ValueError("Email required for Email MFA")

        code = self._generate_verification_code()
        self._pending_codes[f"email:{request.user_id}"] = (code, time.time() + self.config.MFA_CODE_EXPIRY_SECONDS)

        logger.info("Email MFA code sent to %s for user %s", request.email, request.user_id)

        self._mfa_secrets[request.user_id] = {
            "email_enabled": True,
            "method": "email",
        }

        return MFASetupResponse(
            method="email",
            status="verification_pending",
        )

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    async def verify_mfa(self, request: MFARequest) -> bool:
        """Verify an MFA code."""
        if request.method == "totp":
            return await self._verify_totp(request)
        elif request.method == "sms":
            return await self._verify_sms(request)
        elif request.method == "email":
            return await self._verify_email(request)
        else:
            raise ValueError(f"Unsupported MFA method: {request.method}")

    async def _verify_totp(self, request: MFARequest) -> bool:
        """Verify a TOTP code or backup code."""
        secrets = self._mfa_secrets.get(request.user_id)
        if not secrets:
            # Try DB
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT totp_secret, backup_codes FROM mfa_secrets WHERE user_id = $1 AND totp_enabled = TRUE",
                        request.user_id,
                    )
                    if not row:
                        return False
                    secrets = {"totp_secret": row["totp_secret"], "backup_codes": list(row["backup_codes"] or [])}
            else:
                return False

        totp_secret = secrets.get("totp_secret")
        if not totp_secret:
            return False

        # Try TOTP first (±1 window)
        if _verify_totp(totp_secret, request.code, window=1):
            return True

        # Fall back to backup codes
        backup_codes = secrets.get("backup_codes", [])
        if request.code in backup_codes:
            backup_codes.remove(request.code)
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE mfa_secrets SET backup_codes = $1 WHERE user_id = $2",
                        backup_codes,
                        request.user_id,
                    )
            logger.info("Backup code used for user %s", request.user_id)
            return True

        logger.warning("Invalid MFA code for user %s", request.user_id)
        return False

    async def _verify_sms(self, request: MFARequest) -> bool:
        """Verify an SMS code from the pending codes store."""
        return await self._verify_pending_code(f"sms:{request.user_id}", request.code)

    async def _verify_email(self, request: MFARequest) -> bool:
        """Verify an Email code from the pending codes store."""
        return await self._verify_pending_code(f"email:{request.user_id}", request.code)

    async def _verify_pending_code(self, key: str, code: str) -> bool:
        """Verify a time-limited code from the pending store."""
        entry = self._pending_codes.get(key)
        if not entry:
            return False
        stored_code, expiry = entry
        if time.time() > expiry:
            del self._pending_codes[key]
            return False
        if stored_code == code:
            del self._pending_codes[key]
            return True
        return False

    # ------------------------------------------------------------------
    # Session MFA update
    # ------------------------------------------------------------------

    async def update_session_mfa(self, session_id: str, user_id: str) -> bool:
        """Mark a session as MFA-verified."""
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute(
                    "UPDATE sessions SET mfa_verified = TRUE WHERE session_id = $1 AND user_id = $2",
                    session_id,
                    user_id,
                )
                return result.split()[-1] == "1"
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_verification_code(length: int = 6) -> str:
        return "".join(random.choices(string.digits, k=length))

    def _build_provisioning_uri(self, secret_b32: str, user_id: str) -> str:
        """Build an otpauth:// provisioning URI (scan with authenticator apps)."""
        issuer = self.config.MFA_ISSUER
        return f"otpauth://totp/{issuer}:{user_id}?secret={secret_b32}&issuer={issuer}&digits=6&period=30"
