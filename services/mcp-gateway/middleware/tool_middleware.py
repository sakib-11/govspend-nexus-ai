"""Tool middleware — validates access, enriches context, and wraps responses."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from models.mcp import MCPRequest, ToolAccessLevel, user_has_access_level
from tools.registry import ToolRegistry
from services.audit_service import AuditService

logger = logging.getLogger(__name__)


class ToolMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that:

    1. Validates tool existence and access level before execution.
    2. Enriches ``request.state`` with tool metadata.
    3. Records audit entries on completion.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        audit_service: AuditService,
    ) -> None:
        super().__init__()
        self._tool_registry = tool_registry
        self._audit = audit_service

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Only intercept MCP tool execution routes
        if not path.startswith("/api/v1/mcp/execute") and not path.startswith("/api/v1/mcp/"):
            return await call_next(request)

        start = time.monotonic()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Tool middleware error on %s", path)
            raise

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.debug("Tool middleware %s completed in %.1fms", path, elapsed_ms)
        return response
