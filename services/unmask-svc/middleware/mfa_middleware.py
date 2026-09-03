"""MFA middleware — optional MFA enforcement for sensitive endpoints."""

from __future__ import annotations

import logging
from typing import Any, Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

# Paths that require MFA verification
_MFA_REQUIRED_PATHS: frozenset[str] = frozenset({
    "/api/v1/unmask/approve",
    "/api/v1/unmask/unmask",
})


class MFAMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces MFA for sensitive endpoints.

    In production, this would verify a session-level MFA claim.
    For now it simply logs the MFA requirement.
    """

    def __init__(self, app: Any = None, *, mfa_enabled: bool = True) -> None:
        if app is not None:
            super().__init__(app)
        else:
            self._app = None
        self._mfa_enabled = mfa_enabled

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        if self._mfa_enabled and request.url.path in _MFA_REQUIRED_PATHS:
            logger.debug("MFA required for %s", request.url.path)
        return await call_next(request)
