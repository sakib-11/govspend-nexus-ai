"""Graph visualization routes — Vendor relationship and entity graphs."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])


# ======================================================================
# Mock Data (replace with actual service calls)
# ======================================================================

def _get_mock_vendor_graph(vendor_token: str, depth: int = 2) -> Dict[str, Any]:
    """Generate mock vendor graph data."""
    return {
        "nodes": [
            {"id": vendor_token, "type": "vendor", "label": f"Vendor {vendor_token}", "size": 20, "color": "#2196F3", "data": {"total_amount": 150000}},
            {"id": "dept_001", "type": "department", "label": "Finance Dept", "size": 15, "color": "#4CAF50", "data": {"type": "primary"}},
            {"id": "official_001", "type": "official", "label": "John Doe", "size": 12, "color": "#F44336", "data": {"title": "Director"}},
            {"id": "tx_001", "type": "transaction", "label": "$50,000", "size": 18, "color": "#FF9800", "data": {"date": "2024-01-15", "amount": 50000}},
        ],
        "edges": [
            {"id": "edge_1", "source": "dept_001", "target": vendor_token, "type": "contracted", "label": "Contracts", "weight": 1.0},
            {"id": "edge_2", "source": vendor_token, "target": "official_001", "type": "employs", "label": "Employs", "weight": 0.8},
            {"id": "edge_3", "source": vendor_token, "target": "tx_001", "type": "related", "label": "Transaction", "weight": 1.0},
        ],
        "metadata": {"node_count": 4, "edge_count": 3, "depth": depth},
    }


# ======================================================================
# Endpoints
# ======================================================================

@router.get("/vendor/{vendor_token}")
async def get_vendor_graph(
    vendor_token: str,
    request: Request,
    depth: int = 2,
) -> Dict[str, Any]:
    """Get vendor relationship graph."""
    graph_data = _get_mock_vendor_graph(vendor_token, depth)
    return graph_data


@router.get("/case/{case_id}")
async def get_case_graph(
    case_id: str,
    request: Request,
) -> Dict[str, Any]:
    """Get graph for entities in a case."""
    graph_data = _get_mock_vendor_graph("vendor_123", depth=2)
    graph_data["metadata"]["case_id"] = case_id
    return graph_data


@router.get("/metadata")
async def get_graph_metadata(request: Request) -> Dict[str, Any]:
    """Get graph visualization metadata."""
    return {
        "node_types": {
            "department": {"color": "#4CAF50", "icon": "🏢", "size": 15},
            "vendor": {"color": "#2196F3", "icon": "🏪", "size": 20},
            "official": {"color": "#F44336", "icon": "👤", "size": 12},
            "asset": {"color": "#9E9E9E", "icon": "📦", "size": 10},
            "transaction": {"color": "#FF9800", "icon": "💳", "size": 18},
        },
        "edge_types": {
            "supplies": {"label": "Supplies", "color": "#666"},
            "employs": {"label": "Employs", "color": "#666"},
            "owns": {"label": "Owns", "color": "#666"},
            "contracted": {"label": "Contracted", "color": "#666"},
            "related": {"label": "Related", "color": "#999"},
        },
        "max_depth": 3,
    }