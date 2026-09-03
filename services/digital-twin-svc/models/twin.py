"""Digital twin models — vendor/official relationship network."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# ── Node / Edge types ──────────────────────────────────────────────


class NodeType(str):
    DEPARTMENT = "department"
    VENDOR = "vendor"
    OFFICIAL = "official"
    TENDER = "tender"
    INVOICE = "invoice"
    TRANSACTION = "transaction"
    ASSET = "asset"


class EdgeType:
    CONTRACTED = "contracted"
    EMPLOYS = "employs"
    OWNS = "owns"
    SUPPLIES = "supplies"
    APPROVES = "approves"
    RELATED = "related"
    PART_OF = "part_of"


# ── Graph primitives ───────────────────────────────────────────────


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    size: int = 10
    color: Optional[str] = None


class GraphEdge(BaseModel):
    id: str = Field(default_factory=lambda: f"edge-{uuid4().hex[:8]}")
    source: str
    target: str
    type: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0


# ── Query / Response ──────────────────────────────────────────────


class GraphQuery(BaseModel):
    vendor_token: Optional[str] = None
    department_id: Optional[str] = None
    official_id: Optional[str] = None
    transaction_id: Optional[str] = None
    depth: int = 2
    include_edges: bool = True
    include_metadata: bool = True
    limit_nodes: int = 100
    limit_edges: int = 200


class GraphResponse(BaseModel):
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    query_time_ms: float = 0.0
    total_nodes: int = 0
    total_edges: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Digital twins ─────────────────────────────────────────────────


class VendorTwin(BaseModel):
    """Digital twin of a vendor entity."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    vendor_id: str  # tokenised
    name_masked: str
    total_transactions: int = 0
    total_amount: float = 0.0
    departments: List[str] = Field(default_factory=list)
    risk_indicators: Dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OfficialTwin(BaseModel):
    """Digital twin of a government official."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    official_id: str  # tokenised
    name_masked: str
    department: str = ""
    total_approvals: int = 0
    vendors_approved: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RelationshipEdge(BaseModel):
    """Edge in the vendor-official relationship graph."""

    edge_id: str = Field(default_factory=lambda: f"edge-{uuid4().hex[:8]}")
    source_id: str
    target_id: str
    relationship_type: str  # approved_by | same_department | shared_address
    weight: float = 1.0
    transaction_count: int = 0
    total_amount: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NetworkAnalysis(BaseModel):
    """Analysis result for a vendor network."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    vendor_id: str
    hhi: float = 0.0  # Herfindahl-Hirschman Index
    concentration_risk: str = "low"
    repeat_officials: int = 0
    connected_vendors: int = 0
    suspicious_patterns: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Path finding ──────────────────────────────────────────────────


class PathResult(BaseModel):
    found: bool
    path_nodes: List[str] = Field(default_factory=list)
    path_edges: List[str] = Field(default_factory=list)
    distance: int = 0
