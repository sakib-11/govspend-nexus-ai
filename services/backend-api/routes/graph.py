"""Vendor graph routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from models.graph import VendorGraph
from services.graph_service import GraphService

router = APIRouter(prefix="/api/graph", tags=["graph"])


def _get_svc(request: Request) -> GraphService:
    svc = getattr(request.app.state, "graph_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Graph service unavailable")
    return svc


def _get_user(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("/vendor/{vendor_token}", response_model=VendorGraph)
async def get_vendor_graph(
    vendor_token: str,
    request: Request,
    depth: Optional[int] = Query(default=2, ge=1, le=5),
) -> VendorGraph:
    """Get vendor relationship graph."""
    user = _get_user(request)
    svc = _get_svc(request)

    graph = svc.get_vendor_graph(
        vendor_token,
        user_jurisdictions=getattr(user, "jurisdictions", []),
        depth=depth,
    )
    if graph is None:
        raise HTTPException(status_code=404, detail="Vendor graph not found")
    return graph


@router.get("/vendor/{vendor_token}/analyse")
async def analyse_vendor(vendor_token: str, request: Request) -> dict:
    """Get network analysis metrics for a vendor."""
    _get_user(request)
    svc = _get_svc(request)
    return svc.get_analysis(vendor_token)
