"""Base class for all MCP tools — provides validation, error handling, and lifecycle."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from models.mcp import (
    MCPRequest,
    MCPResponse,
    ToolExecutionContext,
)


def _error_code_for(exc: Exception) -> str:
    """Map common exception types to stable error codes."""
    if isinstance(exc, ValueError):
        return "VALIDATION_ERROR"
    if isinstance(exc, PermissionError):
        return "PERMISSION_DENIED"
    if isinstance(exc, TimeoutError):
        return "TIMEOUT_ERROR"
    if isinstance(exc, KeyError):
        return "MISSING_PARAMETER"
    return "INTERNAL_ERROR"


class BaseTool(ABC):
    """Abstract base that every MCP tool must subclass.

    Subclasses implement :meth:`execute` and optionally override
    :meth:`validate_params` / :meth:`validate_output`.
    """

    def __init__(self) -> None:
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def handle(self, request: MCPRequest) -> MCPResponse:
        """High-level handler that wraps :meth:`execute` with timing and
        error handling.  Returns an :class:`MCPResponse` in all cases.
        """
        start = time.monotonic()

        try:
            context = self._build_context(request)
            validated = await self.validate_params(context.parameters)
            context.parameters = validated

            result = await self.execute(context)

            validated_result = await self.validate_output(result)

            elapsed_ms = (time.monotonic() - start) * 1000
            return MCPResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                success=True,
                data=validated_result,
                execution_time_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self.logger.exception("Tool %s execution failed", request.tool_name)
            return MCPResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                success=False,
                error=str(exc),
                error_code=_error_code_for(exc),
                execution_time_ms=elapsed_ms,
            )

    # ------------------------------------------------------------------
    # Abstract / overridable
    # ------------------------------------------------------------------

    @abstractmethod
    async def execute(self, context: ToolExecutionContext) -> Dict[str, Any]:
        """Core business logic of the tool.  Must return a JSON-serialisable dict."""

    async def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate (and optionally transform) input *params*.

        Raise :class:`ValueError` on invalid input.  Default implementation
        passes through unchanged.
        """
        return params

    async def validate_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the tool's output before it is serialised.

        Default implementation passes through unchanged.
        """
        return output

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context(request: MCPRequest) -> ToolExecutionContext:
        """Derive a typed :class:`ToolExecutionContext` from the raw request."""
        ctx = request.context
        return ToolExecutionContext(
            user_id=request.user_id or "anonymous",
            user_roles=ctx.get("roles", []),
            user_jurisdictions=ctx.get("jurisdictions", []),
            session_id=request.session_id or "",
            ip_address=ctx.get("ip_address"),
            user_agent=ctx.get("user_agent"),
            request_id=request.request_id,
            tool_name=request.tool_name,
            parameters=dict(request.parameters),
            metadata=ctx.get("metadata", {}),
        )
