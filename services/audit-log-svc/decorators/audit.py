"""Audit decorators — add audit logging to any async function or route."""

from __future__ import annotations

import asyncio
import logging
import time
from functools import wraps
from typing import Any, Callable, List, Optional

from fastapi import Request

from models.audit import AuditEventType, AuditSeverity
from services.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


def audit_log(
    event_type: AuditEventType,
    action: str,
    *,
    severity: AuditSeverity = AuditSeverity.INFO,
    resource_type: Optional[str] = None,
    include_request_data: bool = True,
    include_response_data: bool = False,
) -> Callable:
    """Decorator that records an audit entry for the wrapped function.

    The function must accept a ``request: Request`` as a keyword argument
    (FastAPI dependency-injection style).
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request: Optional[Request] = kwargs.get("request")
            if request is None:
                for a in args:
                    if isinstance(a, Request):
                        request = a
                        break

            audit_logger: Optional[AuditLogger] = None
            if request and hasattr(request.app.state, "audit_logger"):
                audit_logger = request.app.state.audit_logger

            start = time.monotonic()
            error: Optional[str] = None
            result: Any = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as exc:
                error = str(exc)
                raise
            finally:
                if audit_logger is None:
                    return
                duration_ms = (time.monotonic() - start) * 1000
                user = getattr(request.state, "user", None) if request else None

                final_resource_type = resource_type
                if not final_resource_type and request:
                    parts = request.url.path.strip("/").split("/")
                    final_resource_type = parts[1] if len(parts) >= 2 else "unknown"

                resource_id = kwargs.get("resource_id") or kwargs.get("case_id")
                if not resource_id and request:
                    parts = request.url.path.strip("/").split("/")
                    resource_id = parts[2] if len(parts) >= 3 else None

                # Fire-and-forget so the response isn't delayed
                asyncio.ensure_future(
                    audit_logger.log(
                        event_type=event_type,
                        user_id=getattr(user, "user_id", "system") if user else "system",
                        user_roles=(
                            [r.value if hasattr(r, "value") else str(r) for r in user.roles]
                            if user
                            else []
                        ),
                        user_jurisdictions=getattr(user, "jurisdictions", []) if user else [],
                        session_id=(
                            getattr(request.state, "session_id", None) if request else None
                        ),
                        ip_address=request.client.host if request and request.client else None,
                        user_agent=request.headers.get("user-agent") if request else None,
                        resource_type=final_resource_type or "unknown",
                        resource_id=resource_id,
                        jurisdiction_id=(
                            request.headers.get("X-Jurisdiction") if request else None
                        ),
                        action=action,
                        action_details={
                            "function": func.__name__,
                            "args_count": len(args),
                            "kwargs_keys": list(kwargs.keys()),
                        },
                        request_id=(
                            request.headers.get("X-Request-ID", "") if request else ""
                        ),
                        response_status=500 if error else 200,
                        error_message=error,
                        duration_ms=duration_ms,
                        severity=severity,
                        metadata={"decorator": "audit_log", "function": func.__name__},
                    )
                )

        return wrapper

    return decorator


def audit_case_action(action: str) -> Callable:
    """Shorthand decorator for case-related actions."""
    return audit_log(
        AuditEventType.CASE_ACTION,
        action,
        resource_type="case",
        severity=AuditSeverity.WARNING,
    )


def audit_sensitive_action(action: str) -> Callable:
    """Shorthand decorator for sensitive data actions."""
    return audit_log(
        AuditEventType.DATA_ACCESS,
        action,
        resource_type="sensitive",
        severity=AuditSeverity.CRITICAL,
    )


def audit_admin_action(action: str) -> Callable:
    """Shorthand decorator for admin actions."""
    return audit_log(
        AuditEventType.ADMIN_ACTION,
        action,
        severity=AuditSeverity.ALERT,
    )
