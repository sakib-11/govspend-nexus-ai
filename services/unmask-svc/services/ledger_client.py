"""Ledger client — HTTP client for the ledger service."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from config import UnmaskConfig

logger = logging.getLogger(__name__)


class LedgerClient:
    """HTTP client that fetches encrypted data from the ledger service.

    Uses ``httpx`` for async HTTP and includes automatic retry on
    transient failures.
    """

    def __init__(self, config: UnmaskConfig) -> None:
        self.config = config
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                import httpx

                self._client = httpx.AsyncClient(
                    base_url=self.config.LEDGER_SERVICE_URL,
                    timeout=self.config.LEDGER_TIMEOUT_SECONDS,
                    headers={
                        "Authorization": f"Bearer {self.config.LEDGER_SERVICE_TOKEN}",
                        "Content-Type": "application/json",
                    },
                )
            except ImportError:
                logger.error("httpx not installed — ledger client unavailable")
                return None
        return self._client

    async def get_encrypted_data(
        self,
        entity_type: str,
        entity_token: str,
        *,
        decrypt: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Fetch encrypted data from the ledger.

        Returns the decrypted payload on success, or ``None`` on failure.
        """
        client = await self._get_client()
        if client is None:
            return None

        params = {"decrypt": str(decrypt).lower()}
        url = f"/api/v1/ledger/{entity_type}/{entity_token}"

        for attempt in range(3):
            try:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 404:
                    logger.warning("Ledger: data not found for %s/%s", entity_type, entity_token)
                    return None
                logger.warning(
                    "Ledger returned %d on attempt %d for %s/%s",
                    response.status_code, attempt + 1, entity_type, entity_token,
                )
            except Exception as exc:
                logger.warning(
                    "Ledger request failed (attempt %d): %s", attempt + 1, exc,
                )

        logger.error("Ledger: all retries exhausted for %s/%s", entity_type, entity_token)
        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None
