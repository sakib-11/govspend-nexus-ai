"""MCP wire protocol — JSON-RPC 2.0 inspired message format."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from models.mcp import MCPRequest, MCPResponse


class MCPProtocol:
    """Stateless helpers for encoding / decoding MCP messages.

    The protocol is intentionally kept thin — the heavy lifting (validation,
    execution) lives in the tool executor and route handlers.
    """

    # ------------------------------------------------------------------
    # Incoming
    # ------------------------------------------------------------------

    @staticmethod
    def parse_request(raw: Dict[str, Any]) -> MCPRequest:
        """Parse a raw JSON dict into an :class:`MCPRequest`."""
        return MCPRequest(**raw)

    @staticmethod
    def parse_json(text: str) -> Dict[str, Any]:
        """Parse a JSON string into a dict."""
        return json.loads(text)

    # ------------------------------------------------------------------
    # Outgoing
    # ------------------------------------------------------------------

    @staticmethod
    def format_response(response: MCPResponse) -> Dict[str, Any]:
        """Serialise an :class:`MCPResponse` to a plain dict."""
        return response.model_dump(mode="json")

    @staticmethod
    def to_json(data: Any, indent: int = 0) -> str:
        """Serialise any object to a JSON string."""
        return json.dumps(data, default=str, indent=indent or None)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """Validate that mandatory MCP headers are present."""
        required = ("x-mcp-version", "x-request-id")
        validated: Dict[str, str] = {}
        for key in required:
            if key not in headers:
                raise ValueError(f"Missing required header: {key}")
            validated[key] = headers[key]
        return validated
