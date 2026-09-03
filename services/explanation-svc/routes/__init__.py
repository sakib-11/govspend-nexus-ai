"""Routes for Explanation Service."""

from .admin import router as admin_router
from .auth import router as auth_router
from .cases import router as cases_router
from .explanation import router as explanation_router
from .graph import router as graph_router
from .unmask import router as unmask_router

__all__ = [
    "admin_router",
    "auth_router",
    "cases_router",
    "explanation_router",
    "graph_router",
    "unmask_router",
]
