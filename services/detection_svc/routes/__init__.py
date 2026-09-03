"""Routes package for detection service."""

from .detection import router
from .duplicate import router as duplicate_router
from .timing import router as timing_router
from .vendor_graph import router as vendor_graph_router
from .contract_splitting import router as contract_splitting_router
from .approval_velocity import router as approval_velocity_router

__all__ = [
    "router",
    "duplicate_router",
    "timing_router",
    "vendor_graph_router",
    "contract_splitting_router",
    "approval_velocity_router",
]