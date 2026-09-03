"""Middleware for MCP Gateway."""

from .authorization_middleware import AuthorizationMiddleware

__all__ = [
    "AuthorizationMiddleware",
]