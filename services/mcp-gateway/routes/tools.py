"""Routes for tool discovery and metadata."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from models.mcp import MCPTool, ToolCategory, ToolAccessLevel, user_has_access_level

router = APIRouter(prefix="/api/v1/mcp/tools", tags=["mcp-tools"])


class ToolListItem(BaseModel):
    name: str
    description: str
    category: str
    access_level: str
    version: str
    tags: List[str]


class ToolDetail(BaseModel):
    tool_id: str
    name: str
    description: str
    category: str
    access_level: str
    version: str
    tags: List[str]
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    timeout_seconds: int
    is_active: bool
    is_deprecated: bool


class ToolSchemaResponse(BaseModel):
    tool_name: str
    version: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("", response_model=List[ToolListItem])
async def list_tools(request: Request) -> List[ToolListItem]:
    """List all tools accessible to the current user."""
    registry = request.app.state.tool_registry
    user = getattr(request.state, "user", None)

    if user:
        roles = [r.value if hasattr(r, "value") else str(r) for r in user.roles]
        tools = registry.get_accessible_tools(roles)
    else:
        tools = registry.get_tools_by_access(ToolAccessLevel.PUBLIC)

    return [
        ToolListItem(
            name=t.name,
            description=t.description,
            category=t.category.value,
            access_level=t.access_level.value,
            version=t.version,
            tags=t.tags,
        )
        for t in tools
    ]


@router.get("/{tool_name}", response_model=ToolDetail)
async def get_tool(tool_name: str, request: Request) -> ToolDetail:
    """Get full details for a specific tool."""
    registry = request.app.state.tool_registry
    tool = registry.get_tool(tool_name)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tool '{tool_name}' not found")
    return ToolDetail(
        tool_id=tool.tool_id,
        name=tool.name,
        description=tool.description,
        category=tool.category.value,
        access_level=tool.access_level.value,
        version=tool.version,
        tags=tool.tags,
        input_schema=tool.input_schema,
        output_schema=tool.output_schema,
        timeout_seconds=tool.timeout_seconds,
        is_active=tool.is_active,
        is_deprecated=tool.is_deprecated,
    )


@router.get("/category/{category}")
async def list_tools_by_category(category: str, request: Request) -> List[ToolListItem]:
    """List tools filtered by category."""
    registry = request.app.state.tool_registry
    try:
        cat = ToolCategory(category)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category: {category}. Valid: {[c.value for c in ToolCategory]}",
        )

    tools = registry.get_tools_by_category(cat)
    return [
        ToolListItem(
            name=t.name,
            description=t.description,
            category=t.category.value,
            access_level=t.access_level.value,
            version=t.version,
            tags=t.tags,
        )
        for t in tools
    ]
