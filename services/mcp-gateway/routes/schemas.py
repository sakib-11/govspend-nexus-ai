"""Routes for JSON schema discovery."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/mcp/schema", tags=["mcp-schemas"])


class SchemaListItem(BaseModel):
    name: str
    has_input: bool
    has_output: bool


class SchemaDetail(BaseModel):
    tool_name: str
    version: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


@router.get("", response_model=List[SchemaListItem])
async def list_schemas(request: Request) -> List[SchemaListItem]:
    """List all available tool schemas."""
    registry = request.app.state.tool_registry
    tools = registry.get_all_tools()
    return [
        SchemaListItem(
            name=t.name,
            has_input=bool(t.input_schema),
            has_output=bool(t.output_schema),
        )
        for t in tools
    ]


@router.get("/{tool_name}", response_model=SchemaDetail)
async def get_schema(tool_name: str, request: Request) -> SchemaDetail:
    """Get the schema for a specific tool."""
    registry = request.app.state.tool_registry
    tool = registry.get_tool(tool_name)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tool '{tool_name}' not found")
    return SchemaDetail(
        tool_name=tool.name,
        version=tool.version,
        input_schema=tool.input_schema,
        output_schema=tool.output_schema,
    )
