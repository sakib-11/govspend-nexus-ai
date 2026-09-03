"""Audit middleware — logs every MCP request for compliance and observability."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from services.audit_service import AuditService

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Thin ASGI middleware that records request metadata."""

    def __init__(self, audit_service: AuditService) -> None:
        super().__init__()
        self._audit = audit_service

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        start = time.monotonic()

        # Only audit MCP routes
        if not path.startswith("/api/v1/mcp"):
            return await call_next(request)

        method = request.method
        user = getattr(request.state, "user", None)
        user_id = getattr(user, "user_id", "anonymous") if user else "anonymous"

        try:
            response = await call_next(request)
            elapsed = (time.monotonic() - start) * 1000

            self._audit.record(
                user_id=user_id,
                tool_name=path,
                request_id=getattr(request.state, "request_id", ""),
                action=f"http_{method.lower()}",
                success=200 <= response.status_code < 400,
                details={
                    "status_code": response.status_code,
                    "elapsed_ms": round(elapsed, 2),
                },
                ip_address=request.client.host if request.client else None,
                session_id=getattr(request.state, "session_id", None),
            )
            return response
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            self._audit.record(
                user_id=user_id,
                tool_name=path,
                request_id=getattr(request.state, "request_id", ""),
                action=f"http_{method.lower()}",
                success=False,
                details={"error": str(exc), "elapsed_ms": round(elapsed, 2)},
            )
            raise
