"""Audit logging middleware — records every request to the audit trail."""

import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from ..models.auth import AuditLog
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Paths that should never be audited
_SKIP_PATHS: frozenset[str] = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})
_SKIP_PREFIXES: tuple[str, ...] = ("/static/",)


def _should_audit(path: str) -> bool:
    if path in _SKIP_PATHS:
        return False
    return not any(path.startswith(p) for p in _SKIP_PREFIXES)


def _resource_type_from_path(path: str) -> str:
    """Extract the resource type from an API path like ``/api/v1/auth/login``."""
    parts = [p for p in path.strip("/").split("/") if p]
    # /api/v1/{resource}/...
    if len(parts) >= 3 and parts[0] == "api":
        return parts[2]  # 'auth', 'detect', etc.
    if len(parts) >= 1:
        return parts[-1]
    return "unknown"


def _resource_id_from_path(path: str) -> Optional[str]:
    """If the path has a trailing ID segment, return it."""
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) >= 4 and parts[0] == "api":
        return parts[3]
    return None


class AuditMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that creates an ``AuditLog`` entry for every auditable request.

    The entry captures:
        - user (from request.state set by AuthMiddleware)
        - HTTP method, path, query params
        - client IP and user-agent
        - response status, duration
        - jurisdiction (from claims)
    """

    def __init__(self, audit_store: Optional[Any] = None):
        super().__init__()
        # audit_store is an object with an async ``append(log: AuditLog)`` method
        self.audit_store = audit_store
        self._in_memory_logs: list[AuditLog] = []  # fallback

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        if not _should_audit(path):
            return await call_next(request)

        start = time.monotonic()
        success = True
        error_message: Optional[str] = None
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            if status_code >= 400:
                success = False
                error_message = f"HTTP {status_code}"
        except Exception as exc:
            success = False
            error_message = str(exc)
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000

            # Extract user context from request.state (set by AuthMiddleware)
            user = getattr(request.state, "user", None)
            claims = getattr(request.state, "claims", None)

            audit = AuditLog(
                user_id=user.user_id if user else None,
                action=request.method,
                resource_type=_resource_type_from_path(path),
                resource_id=_resource_id_from_path(path),
                details={
                    "path": path,
                    "query_params": dict(request.query_params),
                    "method": request.method,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                timestamp=datetime.now(timezone.utc),
                success=success,
                error_message=error_message,
                jurisdiction_id=(
                    claims.jurisdictions[0]
                    if claims and claims.jurisdictions
                    else None
                ),
            )

            # Persist
            if self.audit_store:
                try:
                    await self.audit_store.append(audit)
                except Exception as exc:
                    logger.warning("Audit store write failed: %s", exc)
            else:
                self._in_memory_logs.append(audit)
                if len(self._in_memory_logs) > 10000:
                    self._in_memory_logs = self._in_memory_logs[-5000:]

            logger.debug(
                "AUDIT %s %s → %d (%.1fms) user=%s",
                request.method,
                path,
                status_code,
                duration_ms,
                user.user_id if user else "anonymous",
            )

        return response
