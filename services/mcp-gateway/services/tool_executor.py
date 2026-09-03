"""Tool executor — orchestrates tool execution with validation, timeout, and tracking."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from models.mcp import (
    MCPRequest,
    MCPResponse,
    MCPToolExecution,
)
from tools.registry import ToolRegistry
from services.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)


class ToolExecutor:
    """High-level executor that validates, runs, and tracks tool invocations."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        schema_validator: Optional[SchemaValidator] = None,
    ) -> None:
        self.tool_registry = tool_registry
        self._validator = schema_validator or SchemaValidator()
        self._executions: Dict[str, MCPToolExecution] = {}

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, request: MCPRequest, context: Dict[str, Any]) -> MCPResponse:
        """Execute a tool by name, with full validation and tracking."""

        tool = self.tool_registry.get_tool(request.tool_name)
        if tool is None:
            return self._error_response(
                request, "Tool '{}' not found".format(request.tool_name), "TOOL_NOT_FOUND"
            )
        if not tool.is_active:
            return self._error_response(
                request, "Tool '{}' is not active".format(request.tool_name), "TOOL_INACTIVE"
            )

        handler = self.tool_registry.get_handler(request.tool_name)
        if handler is None:
            return self._error_response(
                request,
                "No handler registered for tool '{}'".format(request.tool_name),
                "HANDLER_NOT_FOUND",
            )

        # Create execution record
        execution = MCPToolExecution(
            request_id=request.request_id,
            tool_name=request.tool_name,
            user_id=request.user_id or "anonymous",
            parameters=request.parameters,
            context=context,
            status="running",
        )
        self._executions[request.request_id] = execution

        try:
            # Input schema validation (soft-fail if schema missing)
            if tool.input_schema:
                self._validator.validate(
                    request.parameters, "{}_input".format(request.tool_name)
                )

            # Execute with timeout and optional retries
            response = await self._run_with_retry(handler, request, context, tool.retry_count, tool.timeout_seconds)

            # Output validation
            if tool.output_schema and response.success and response.data:
                self._validator.validate(response.data, "{}_output".format(request.tool_name))

            # Update execution record
            execution.status = "completed"
            execution.completed_at = datetime.now(timezone.utc)
            execution.result = response.data if response.success else None
            execution.execution_time_ms = response.execution_time_ms

            return response

        except asyncio.TimeoutError:
            msg = "Tool timed out after {}s".format(tool.timeout_seconds)
            execution.status = "failed"
            execution.error = msg
            return self._error_response(request, msg, "TIMEOUT_ERROR", tool.timeout_seconds * 1000)

        except Exception as exc:
            execution.status = "failed"
            execution.error = str(exc)
            logger.exception("Tool %s execution error", request.tool_name)
            return self._error_response(request, str(exc), "EXECUTION_ERROR")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_execution(self, request_id: str) -> Optional[MCPToolExecution]:
        return self._executions.get(request_id)

    def list_executions(self, user_id: Optional[str] = None) -> List[MCPToolExecution]:
        if user_id:
            return [e for e in self._executions.values() if e.user_id == user_id]
        return list(self._executions.values())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _run_with_retry(
        self,
        handler: Any,
        request: MCPRequest,
        context: Dict[str, Any],
        retry_count: int,
        timeout: int,
    ) -> MCPResponse:
        """Execute *handler* with up to *retry_count* retries on failure."""
        last_exc: Optional[Exception] = None
        for attempt in range(1 + retry_count):
            try:
                return await asyncio.wait_for(handler(request, context), timeout=timeout)
            except asyncio.TimeoutError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < retry_count:
                    wait = min(2 ** attempt, 10)
                    logger.warning(
                        "Tool %s attempt %d failed (%s); retrying in %ds",
                        request.tool_name,
                        attempt + 1,
                        exc,
                        wait,
                    )
                    await asyncio.sleep(wait)
        # All retries exhausted — the caller will wrap it
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _error_response(
        request: MCPRequest,
        error: str,
        code: str,
        elapsed_ms: float = 0.0,
    ) -> MCPResponse:
        return MCPResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            success=False,
            error=error,
            error_code=code,
            execution_time_ms=elapsed_ms,
        )
