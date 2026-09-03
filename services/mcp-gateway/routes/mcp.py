"""MCP core routes — execute tools, query execution status, health."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from models.mcp import MCPRequest, MCPResponse, MCPToolExecution, ToolAccessLevel

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])


# ------------------------------------------------------------------
# Request / response bodies
# ------------------------------------------------------------------


class ExecuteRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}
    async_execution: bool = False


class ExecuteByNameRequest(BaseModel):
    parameters: Dict[str, Any] = {}


class ExecutionListResponse(BaseModel):
    executions: List[MCPToolExecution]
    total: int
    user_id: Optional[str] = None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _enrich_request(request_obj: MCPRequest, http_request: Request) -> MCPRequest:
    """Copy auth state from the FastAPI request into the MCP request."""
    user = getattr(http_request.state, "user", None)
    if user:
        request_obj.user_id = getattr(user, "user_id", request_obj.user_id)
        roles = getattr(user, "roles", [])
        request_obj.context["roles"] = [r.value if hasattr(r, "value") else str(r) for r in roles]
        request_obj.context["jurisdictions"] = getattr(user, "jurisdictions", [])

    session = getattr(http_request.state, "session_id", None)
    if session:
        request_obj.session_id = session

    if http_request.client:
        request_obj.context["ip_address"] = http_request.client.host
    request_obj.context["user_agent"] = http_request.headers.get("user-agent")

    return request_obj


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@router.post("/execute", response_model=MCPResponse)
async def execute_tool(body: ExecuteRequest, http_request: Request) -> MCPResponse:
    """Execute any registered MCP tool."""
    executor = http_request.app.state.tool_executor

    mcp_request = MCPRequest(
        tool_name=body.tool_name,
        parameters=body.parameters,
        async_execution=body.async_execution,
    )
    mcp_request = _enrich_request(mcp_request, http_request)

    return await executor.execute(mcp_request, mcp_request.context)


@router.post("/{tool_name}/execute", response_model=MCPResponse)
async def execute_tool_by_name(
    tool_name: str,
    body: ExecuteByNameRequest,
    http_request: Request,
) -> MCPResponse:
    """Execute a specific tool by path parameter."""
    executor = http_request.app.state.tool_executor

    mcp_request = MCPRequest(
        tool_name=tool_name,
        parameters=body.parameters,
    )
    mcp_request = _enrich_request(mcp_request, http_request)

    return await executor.execute(mcp_request, mcp_request.context)


@router.get("/execution/{request_id}")
async def get_execution_status(request_id: str, http_request: Request) -> MCPToolExecution:
    """Query the status of a previous execution."""
    executor = http_request.app.state.tool_executor
    execution = executor.get_execution(request_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution '{request_id}' not found",
        )

    # Access control: users can only see their own executions unless admin
    user = getattr(http_request.state, "user", None)
    if user and execution.user_id != getattr(user, "user_id", None):
        is_admin = any(
            r.value in ("super_admin", "admin") if hasattr(r, "value") else r in ("super_admin", "admin")
            for r in getattr(user, "roles", [])
        )
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorised to view this execution",
            )

    return execution


@router.get("/executions", response_model=ExecutionListResponse)
async def list_executions(
    http_request: Request,
    user_id: Optional[str] = None,
) -> ExecutionListResponse:
    """List executions.  Admins can filter by user_id."""
    executor = http_request.app.state.tool_executor
    user = getattr(http_request.state, "user", None)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    is_admin = any(
        r.value in ("super_admin", "admin") if hasattr(r, "value") else r in ("super_admin", "admin")
        for r in getattr(user, "roles", [])
    )

    target_user = None
    if user_id and is_admin:
        target_user = user_id
    else:
        target_user = getattr(user, "user_id", None)

    executions = executor.list_executions(target_user)
    return ExecutionListResponse(executions=executions, total=len(executions), user_id=target_user)
