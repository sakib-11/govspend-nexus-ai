"""Vendor graph models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class GraphNode(BaseModel):
    """Graph node representing an entity."""

    id: str
    type: str  # department, vendor, official, transaction
    label: str
    size: int = 10
    color: str = "#9E9E9E"
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Graph edge representing a relationship."""

    id: str
    source: str
    target: str
    type: str  # supplies, employs, owns, contracted, approved_by
    label: str
    weight: float = 1.0
    data: Dict[str, Any] = Field(default_factory=dict)


class VendorGraph(BaseModel):
    """Complete vendor relationship graph."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
