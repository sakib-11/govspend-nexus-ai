"""Audit middleware — ASGI middleware that logs every request."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from models.audit import AuditEventType, AuditSeverity
from services.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

# Paths that do not need auditing.
_SKIP_PATHS: frozenset[str] = frozenset({"/health", "/metrics", "/favicon.ico"})
_SKIP_PREFIXES: tuple[str, ...] = ("/docs", "/openapi.json", "/redoc")


def _should_skip(path: str) -> bool:
    return path in _SKIP_PATHS or path.startswith(_SKIP_PREFIXES)


# Maps HTTP method → (event_type, default severity).
_METHOD_MAP: dict[str, tuple[AuditEventType, AuditSeverity]] = {
    "GET": (AuditEventType.DATA_ACCESS, AuditSeverity.INFO),
    "POST": (AuditEventType.DATA_MODIFICATION, AuditSeverity.INFO),
    "PUT": (AuditEventType.DATA_MODIFICATION, AuditSeverity.WARNING),
    "PATCH": (AuditEventType.DATA_MODIFICATION, AuditSeverity.WARNING),
    "DELETE": (AuditEventType.DATA_MODIFICATION, AuditSeverity.CRITICAL),
}


class AuditMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that records audit entries for every HTTP request."""

    def __init__(self, audit_logger: AuditLogger) -> None:
        super().__init__()
        self._logger = audit_logger

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if _should_skip(path):
            return await call_next(request)

        start = time.monotonic()
        user = getattr(request.state, "user", None)
        request_id = request.headers.get("X-Request-ID", f"req-{int(time.time())}")

        response: Optional[Response] = None
        error: Optional[str] = None
        status_code = 200

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            error = str(exc)
            status_code = 500
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            event_type, severity = _METHOD_MAP.get(
                request.method,
                (AuditEventType.SYSTEM_EVENT, AuditSeverity.INFO),
            )

            # Escalate severity on errors
            if error or status_code >= 500:
                severity = AuditSeverity.CRITICAL
            elif status_code >= 400:
                severity = AuditSeverity.WARNING

            await self._logger.log(
                event_type=event_type,
                user_id=getattr(user, "user_id", "anonymous"),
                user_roles=(
                    [r.value if hasattr(r, "value") else str(r) for r in user.roles]
                    if user
                    else []
                ),
                user_jurisdictions=getattr(user, "jurisdictions", []) if user else [],
                session_id=getattr(request.state, "session_id", None),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                resource_type=_resource_type(path),
                resource_id=_resource_id(path),
                jurisdiction_id=request.headers.get("X-Jurisdiction"),
                action=f"{request.method} {path}",
                action_details={
                    "method": request.method,
                    "path": path,
                    "query_params": dict(request.query_params),
                },
                request_id=request_id,
                response_status=status_code,
                error_message=error,
                duration_ms=duration_ms,
                severity=severity,
                metadata={"service": "audit-logging-svc", "version": "1.0.0"},
                tags=["http", request.method.lower()],
            )

        return response  # type: ignore[return-value]


def _resource_type(path: str) -> str:
    parts = path.strip("/").split("/")
    return parts[1] if len(parts) >= 2 else "unknown"


def _resource_id(path: str) -> Optional[str]:
    parts = path.strip("/").split("/")
    return parts[2] if len(parts) >= 3 else None
