"""Tokenization service — HMAC-based token generation with database persistence."""

from __future__ import annotations

import logging
from typing import List, Optional

from config import MaskedEvidenceConfig
from utils.crypto_utils import generate_hmac_token, hash_identifier

logger = logging.getLogger(__name__)


class TokenizationService:
    """Generate and manage HMAC-based tokens for PII identifiers.

    Tokens are deterministic: the same raw identifier + HMAC key always
    produces the same token.  The service stores only the SHA-256 hash of
    the raw identifier in the database — the raw value is never persisted.
    """

    def __init__(self, config: MaskedEvidenceConfig, db_pool) -> None:
        self.config = config
        self.db_pool = db_pool
        # In-memory L1 cache: "entity_type:raw" -> token
        self._cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def tokenize(
        self,
        raw_identifier: str,
        entity_type: str,
        *,
        prefix: Optional[str] = None,
    ) -> Optional[str]:
        """Generate an HMAC-based token for *raw_identifier*.

        Returns ``None`` if the input is empty.
        """
        if not raw_identifier or not raw_identifier.strip():
            return None

        cache_key = f"{entity_type}:{raw_identifier}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        token = generate_hmac_token(
            raw_identifier,
            self.config.HMAC_KEY,
            token_length=self.config.TOKEN_LENGTH,
        )

        prefix = prefix or self.config.TOKEN_PREFIX
        full_token = f"{prefix}-{token}"

        self._cache[cache_key] = full_token

        try:
            await self._store_mapping(full_token, raw_identifier, entity_type, prefix)
        except Exception:
            logger.exception("Failed to store token mapping for %s", full_token)
            # Token generation still succeeds even if persistence fails

        return full_token

    async def verify_token(self, token: str) -> bool:
        """Return ``True`` if *token* exists in the mapping table."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT 1 FROM token_mappings WHERE token = $1", token
                )
                return row is not None
        except Exception:
            logger.exception("Token verification failed for %s", token)
            return False

    async def get_hash_for_token(self, token: str) -> Optional[str]:
        """Return the SHA-256 hash stored for *token* (for verification)."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT raw_identifier_hash FROM token_mappings WHERE token = $1",
                    token,
                )
                return row["raw_identifier_hash"] if row else None
        except Exception:
            logger.exception("Failed to fetch hash for token %s", token)
            return None

    async def get_tokens_for_entity(self, entity_type: str) -> List[str]:
        """Return all tokens belonging to *entity_type*."""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT token FROM token_mappings WHERE entity_type = $1 "
                    "ORDER BY created_at DESC",
                    entity_type,
                )
                return [r["token"] for r in rows]
        except Exception:
            logger.exception("Failed to fetch tokens for entity %s", entity_type)
            return []

    def clear_cache(self) -> None:
        """Drop all in-memory cached tokens."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _store_mapping(
        self,
        token: str,
        raw_identifier: str,
        entity_type: str,
        prefix: str,
    ) -> None:
        """Persist the token <-> hash mapping in the database."""
        raw_hash = hash_identifier(raw_identifier)
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO token_mappings (token, raw_identifier_hash, entity_type, prefix)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (token) DO UPDATE
                SET raw_identifier_hash = $2, entity_type = $3, prefix = $4
                """,
                token,
                raw_hash,
                entity_type,
                prefix,
            )
