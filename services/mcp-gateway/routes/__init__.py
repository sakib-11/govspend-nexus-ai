"""Routes for MCP Gateway."""

from .mcp import router as mcp_router
from .tools import router as tools_router
from .schemas import router as schemas_router
from .authorization import router as authorization_router

__all__ = [
    "mcp_router",
    "tools_router",
    "schemas_router",
    "authorization_router",
]
