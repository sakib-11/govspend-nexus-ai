"""Rate limiter middleware — sliding-window rate limiting for the audit API."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

# Paths exempt from rate limiting
_EXEMPT_PATHS: frozenset[str] = frozenset({"/health", "/metrics", "/"})


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter.

    Limits are enforced per client IP.  In production, replace the in-memory
    dict with Redis-based sliding window for distributed deployments.

    Parameters
    ----------
    max_requests : int
        Maximum requests allowed in the window.
    window_seconds : int
        Duration of the sliding window in seconds.
    """

    def __init__(
        self,
        app: Any = None,
        *,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> None:
        if app is not None:
            super().__init__(app)
        else:
            # Allow instantiation without app for testing
            self._app = None
        self._max = max_requests
        self._window = window_seconds
        self._requests: Dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if path in _EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - self._window

        # Prune old entries
        timestamps = self._requests[client_ip]
        self._requests[client_ip] = [t for t in timestamps if t > window_start]
        timestamps = self._requests[client_ip]

        if len(timestamps) >= self._max:
            retry_after = int(timestamps[0] - window_start) + 1
            logger.warning("Rate limit exceeded for %s on %s", client_ip, path)
            return Response(
                content='{"error": "rate_limit_exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self._max),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Window": f"{self._window}s",
                },
            )

        timestamps.append(now)
        remaining = self._max - len(timestamps)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._max)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = f"{self._window}s"
        return response

    def get_stats(self) -> Dict[str, int]:
        """Return current rate limiter stats (for health/metrics endpoint)."""
        return {
            "tracked_ips": len(self._requests),
            "max_requests": self._max,
            "window_seconds": self._window,
        }
