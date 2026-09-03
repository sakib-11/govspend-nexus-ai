"""MCP request handlers — thin wrappers used by the route layer."""

from __future__ import annotations

from typing import Any, Dict, Optional

from models.mcp import MCPRequest, MCPResponse
from mcp.server import MCPServer


class MCPHandler:
    """Stateless request handler that delegates to :class:`MCPServer`."""

    def __init__(self, server: MCPServer) -> None:
        self._server = server

    async def handle_execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_id: Optional[str] = None,
        roles: Optional[list[str]] = None,
        jurisdictions: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> MCPResponse:
        """Build an MCPRequest and execute the tool."""
        context: Dict[str, Any] = {
            "roles": roles or [],
            "jurisdictions": jurisdictions or [],
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        request = MCPRequest(
            tool_name=tool_name,
            parameters=parameters,
            context=context,
            user_id=user_id,
            session_id=session_id,
        )

        return await self._server.execute(request, context)

    async def handle_list_tools(self) -> list[Dict[str, Any]]:
        """Return serialisable tool metadata."""
        tools = self._server.registry.get_all_tools()
        return [t.model_dump(mode="json") for t in tools]
