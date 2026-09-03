"""Routes for the Backend API."""

from .cases import router as cases_router
from .evidence import router as evidence_router
from .explanation import router as explanation_router
from .graph import router as graph_router
from .unmask import router as unmask_router
from .admin import router as admin_router

__all__ = [
    "cases_router",
    "evidence_router",
    "explanation_router",
    "graph_router",
    "unmask_router",
    "admin_router",
]
