"""Webhook alerts — notify external systems when tamper or critical events are detected."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class WebhookAlertService:
    """Send webhook alerts for critical audit events.

    Supports:
      - Tamper detection alerts
      - Critical severity escalation
      - Chain integrity failure notifications
      - Configurable retry with exponential backoff

    In production, ``send_fn`` should be replaced with ``httpx.AsyncClient.post``.
    """

    def __init__(
        self,
        *,
        webhook_urls: Optional[List[str]] = None,
        signing_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        send_fn: Optional[Callable] = None,
    ) -> None:
        self._urls = webhook_urls or []
        self._signing_key = signing_key
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._send_fn = send_fn or self._default_send
        self._alert_history: List[Dict[str, Any]] = []
        self._stats = {"sent": 0, "failed": 0}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def alert_tamper_detected(
        self,
        tampered_entries: List[Dict[str, Any]],
        chain_valid: bool,
    ) -> None:
        """Send alert when tamper is detected in the audit chain."""
        payload = {
            "alert_type": "tamper_detected",
            "severity": "critical",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "chain_valid": chain_valid,
            "tampered_count": len(tampered_entries),
            "tampered_entries": tampered_entries[:10],  # Cap for payload size
        }
        await self._send_alert(payload)

    async def alert_critical_event(
        self,
        event_type: str,
        user_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send alert for a critical severity audit event."""
        payload = {
            "alert_type": "critical_event",
            "severity": "warning",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "action": action,
            "details": details or {},
        }
        await self._send_alert(payload)

    async def alert_chain_integrity_failure(
        self,
        total_checked: int,
        tampered_count: int,
        verified_count: int,
    ) -> None:
        """Send alert when chain verification finds integrity issues."""
        payload = {
            "alert_type": "chain_integrity_failure",
            "severity": "critical",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_checked": total_checked,
            "tampered_count": tampered_count,
            "verified_count": verified_count,
            "integrity_ratio": round(verified_count / max(total_checked, 1), 4),
        }
        await self._send_alert(payload)

    async def alert_flush_failure(self, error: str, count: int) -> None:
        """Send alert when buffer flush fails."""
        payload = {
            "alert_type": "flush_failure",
            "severity": "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error,
            "entries_lost": count,
        }
        await self._send_alert(payload)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send_alert(self, payload: Dict[str, Any]) -> None:
        if not self._urls:
            logger.debug("No webhook URLs configured, skipping alert: %s", payload.get("alert_type"))
            return

        body = json.dumps(payload, default=str)
        signature = self._sign(body) if self._signing_key else None

        for url in self._urls:
            for attempt in range(1, self._max_retries + 1):
                try:
                    await self._send_fn(url, body, signature)
                    self._stats["sent"] += 1
                    self._alert_history.append({
                        "url": url,
                        "alert_type": payload.get("alert_type"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "attempt": attempt,
                    })
                    # Cap history
                    if len(self._alert_history) > 1000:
                        self._alert_history = self._alert_history[-500:]
                    break
                except Exception as exc:
                    logger.warning(
                        "Webhook alert failed (url=%s, attempt=%d/%d): %s",
                        url, attempt, self._max_retries, exc,
                    )
                    if attempt == self._max_retries:
                        self._stats["failed"] += 1
                        logger.error("Webhook alert exhausted retries for %s", url)
                    else:
                        await asyncio.sleep(self._retry_delay * (2 ** (attempt - 1)))

    def _sign(self, body: str) -> str:
        return hmac.new(
            self._signing_key.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    async def _default_send(url: str, body: str, signature: Optional[str]) -> None:
        """Placeholder — in production, use httpx.AsyncClient."""
        logger.info("WEBHOOK → %s (type=%s)", url, json.loads(body).get("alert_type"))

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        return {
            "webhook_urls": len(self._urls),
            "alerts_sent": self._stats["sent"],
            "alerts_failed": self._stats["failed"],
            "recent_alerts": self._alert_history[-10:],
        }
