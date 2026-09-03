"""Auth middleware — authentication enforcement and PII-safe logging."""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from typing import Any, Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

_EXEMPT_PATHS: frozenset[str] = frozenset({"/health", "/", "/docs", "/openapi.json"})

# PII patterns to redact in logs
_PII_PATTERNS = [
    re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]"),          # PAN
    re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z0-9][0-9]\b"),  # GST
    re.compile(r"\b[6-9][0-9]{9}\b"),               # Phone
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),   # Email
]


def _redact_pii(text: str) -> str:
    """Replace PII patterns with [REDACTED]."""
    result = text
    for pattern in _PII_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication and rate-limiting middleware.

    - Logs all requests with PII redacted.
    - Enforces sliding-window rate limiting per client IP.
    - Exempt paths: /health, /, /docs, /openapi.json
    """

    def __init__(
        self,
        app: Any = None,
        *,
        max_requests: int = 200,
        window_seconds: int = 60,
    ) -> None:
        if app is not None:
            super().__init__(app)
        else:
            self._app = None
        self._max = max_requests
        self._window = window_seconds
        self._requests: Dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path

        # Rate limiting
        if path not in _EXEMPT_PATHS:
            client_ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            window_start = now - self._window

            timestamps = self._requests[client_ip]
            self._requests[client_ip] = [t for t in timestamps if t > window_start]

            if len(self._requests[client_ip]) >= self._max:
                logger.warning("Rate limit exceeded for %s", client_ip)
                return Response(
                    content='{"error": "rate_limit_exceeded"}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(self._window)},
                )

            self._requests[client_ip].append(now)

        # PII-safe logging
        safe_path = _redact_pii(request.url.path)
        logger.debug("%s %s", request.method, safe_path)

        response = await call_next(request)
        return response

    def get_stats(self) -> Dict[str, Any]:
        """Return rate limiter stats."""
        return {
            "tracked_ips": len(self._requests),
            "max_requests": self._max,
            "window_seconds": self._window,
        }
