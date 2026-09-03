"""Context manager — builds and enriches tool execution contexts."""

from __future__ import annotations

from typing import Any, Dict, Optional

from models.mcp import MCPRequest, ToolExecutionContext


class ContextManager:
    """Builds a :class:`ToolExecutionContext` from a raw HTTP request
    and any additional runtime data.

    This is the single place where we decide what context fields are
    populated — tools never read ``request.state`` directly.
    """

    @staticmethod
    def build(
        request: MCPRequest,
        *,
        user: Any = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ToolExecutionContext:
        """Create an execution context from a request and optional user object."""

        # If a user object is provided (from auth middleware), merge its fields.
        user_id = request.user_id or _safe_attr(user, "user_id") or "anonymous"
        roles: list[str] = list(request.context.get("roles", []))
        jurisdictions: list[str] = list(request.context.get("jurisdictions", []))

        if user is not None:
            user_roles = _safe_attr(user, "roles")
            if user_roles:
                roles = [r.value if hasattr(r, "value") else str(r) for r in user_roles]
            user_juris = _safe_attr(user, "jurisdictions")
            if user_juris:
                jurisdictions = list(user_juris)

        return ToolExecutionContext(
            user_id=user_id,
            user_roles=roles,
            user_jurisdictions=jurisdictions,
            session_id=request.session_id or "",
            ip_address=ip_address or request.context.get("ip_address"),
            user_agent=user_agent or request.context.get("user_agent"),
            request_id=request.request_id,
            tool_name=request.tool_name,
            parameters=dict(request.parameters),
            metadata=request.context.get("metadata", {}),
        )


def _safe_attr(obj: Any, name: str) -> Any:
    """Return ``getattr(obj, name, None)`` without raising."""
    try:
        return getattr(obj, name, None)
    except Exception:
        return None
