"""Digital twin routes — vendor/official graph and network analysis."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from services.graph_service import GraphService
from services.twin_service import TwinService

router = APIRouter(prefix="/api/v1/twin", tags=["digital-twin"])


# ── Request models ────────────────────────────────────────────────


class CreateVendorRequest(BaseModel):
    vendor_id: str
    name_masked: str
    total_transactions: int = 0
    total_amount: float = 0.0


class AddRelationshipRequest(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str
    weight: float = 1.0
    transaction_count: int = 0
    total_amount: float = 0.0


class MultiVendorRequest(BaseModel):
    vendor_tokens: List[str]
    depth: int = 2


class PathRequest(BaseModel):
    from_id: str
    to_id: str
    max_depth: int = 5


# ── Helpers ───────────────────────────────────────────────────────


def _get_graph_svc(request: Request) -> GraphService:
    svc = getattr(request.app.state, "graph_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Graph service unavailable")
    return svc


def _get_twin_svc(request: Request) -> TwinService:
    svc = getattr(request.app.state, "twin_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Twin service unavailable")
    return svc


# ── Graph endpoints ──────────────────────────────────────────────


@router.get("/vendor/{vendor_token}")
async def get_vendor_graph(
    vendor_token: str,
    request: Request,
    depth: int = Query(default=2, ge=1, le=10),
    include_edges: bool = Query(default=True),
    limit_nodes: int = Query(default=100, ge=1, le=500),
):
    """Get digital twin graph for a vendor."""
    svc = _get_graph_svc(request)
    graph = await svc.get_vendor_graph(
        vendor_token=vendor_token,
        depth=depth,
        include_edges=include_edges,
        limit_nodes=limit_nodes,
    )
    return graph.model_dump(mode="json")


@router.get("/department/{department_id}")
async def get_department_graph(
    department_id: str,
    request: Request,
    depth: int = Query(default=2, ge=1, le=10),
):
    """Get digital twin graph for a department."""
    svc = _get_graph_svc(request)
    graph = await svc.get_department_network(department_id, depth)
    return graph.model_dump(mode="json")


@router.get("/official/{official_id}")
async def get_official_graph(
    official_id: str,
    request: Request,
    depth: int = Query(default=2, ge=1, le=10),
):
    """Get digital twin graph for an official."""
    svc = _get_graph_svc(request)
    graph = await svc.get_official_network(official_id, depth)
    return graph.model_dump(mode="json")


@router.post("/multi-vendor")
async def get_multi_vendor_graph(body: MultiVendorRequest, request: Request):
    """Get combined graph for multiple vendors (fraud ring detection)."""
    if len(body.vendor_tokens) < 2:
        raise HTTPException(status_code=400, detail="At least 2 vendor tokens required")
    if len(body.vendor_tokens) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 vendor tokens allowed")

    svc = _get_graph_svc(request)
    graph = await svc.get_multi_vendor_graph(body.vendor_tokens, body.depth)
    return graph.model_dump(mode="json")


@router.post("/path")
async def find_path(body: PathRequest, request: Request):
    """Find shortest relationship path between two entities."""
    svc = _get_graph_svc(request)
    result = await svc.get_relationship_path(body.from_id, body.to_id, body.max_depth)
    return result.model_dump(mode="json")


@router.get("/vendor/{vendor_id}/analyse")
async def analyse_vendor(vendor_id: str, request: Request):
    """Analyse vendor network for concentration risk."""
    svc = _get_graph_svc(request)
    analysis = await svc.analyse_vendor_network(vendor_id)
    return analysis.model_dump(mode="json")


# ── Legacy twin endpoints ────────────────────────────────────────


@router.post("/vendor")
async def create_vendor(body: CreateVendorRequest, request: Request) -> dict:
    svc = _get_twin_svc(request)
    twin = svc.create_vendor(
        body.vendor_id, body.name_masked,
        total_transactions=body.total_transactions,
        total_amount=body.total_amount,
    )
    return twin.model_dump(mode="json")


@router.post("/relationship")
async def add_relationship(body: AddRelationshipRequest, request: Request) -> dict:
    svc = _get_twin_svc(request)
    edge = svc.add_relationship(
        source_id=body.source_id,
        target_id=body.target_id,
        relationship_type=body.relationship_type,
        weight=body.weight,
        transaction_count=body.transaction_count,
        total_amount=body.total_amount,
    )
    return edge.model_dump(mode="json")


@router.get("/stats")
async def graph_stats(request: Request) -> dict:
    svc = _get_twin_svc(request)
    return svc.get_graph_stats()


@router.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "digital-twin-svc"}
