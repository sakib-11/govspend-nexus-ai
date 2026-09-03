"""Vendor graph models for graph-based risk detection."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, field_validator


class NodeType(str, Enum):
    """Types of nodes in the vendor graph."""
    VENDOR = "vendor"
    DEPARTMENT = "department"
    OFFICIAL = "official"
    TENDER = "tender"
    PAYMENT = "payment"
    CONTRACT = "contract"


class EdgeType(str, Enum):
    """Types of edges in the vendor graph."""
    SUPPLIES_TO = "supplies_to"
    AWARDED_BY = "awarded_by"
    APPROVED_BY = "approved_by"
    PART_OF = "part_of"
    PAYS = "pays"
    MANAGES = "manages"
    COMPETES_WITH = "competes_with"
    SHARES_OFFICIAL = "shares_official"


class GraphNode(BaseModel):
    """Graph node representation."""
    id: str
    node_type: NodeType
    name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Additional attributes based on type
    vendor_id: Optional[str] = None
    department_id: Optional[str] = None
    official_id: Optional[str] = None
    total_spend: Optional[float] = None
    transaction_count: Optional[int] = None


class GraphEdge(BaseModel):
    """Graph edge representation."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VendorGraph(BaseModel):
    """Complete vendor relationship graph."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    built_at: datetime = Field(default_factory=datetime.utcnow)

    # Graph statistics
    node_count: int = 0
    edge_count: int = 0
    avg_degree: Optional[float] = None

    def update_statistics(self) -> None:
        """Update graph statistics."""
        self.node_count = len(self.nodes)
        self.edge_count = len(self.edges)

        if self.node_count > 0:
            degree_sum = sum(self._get_degree(node.id) for node in self.nodes)
            self.avg_degree = degree_sum / self.node_count

    def _get_degree(self, node_id: str) -> int:
        """Get degree of a node."""
        return sum(1 for edge in self.edges
                  if edge.source_id == node_id or edge.target_id == node_id)


class HHIResult(BaseModel):
    """HHI calculation result."""
    department_id: str
    department_name: str
    hhi_score: float = Field(..., ge=0, le=1)
    normalized_hhi: float = Field(..., ge=0, le=1)
    vendor_count: int
    total_spend: float
    market_concentration_level: str
    dominant_vendors: List[Dict[str, Any]]
    vendors_count: int
    period: str


class RepeatOfficialResult(BaseModel):
    """Repeat official analysis result."""
    official_id: str
    official_name: str
    department_id: str
    department_name: str
    vendor_repeats: Dict[str, int]  # vendor_id -> count
    repeat_score: float = Field(..., ge=0, le=1)
    normalized_repeat: float = Field(..., ge=0, le=1)
    total_vendor_connections: int
    risk_indicators: List[str]


class VendorGraphRiskResult(BaseModel):
    """Complete vendor graph risk detection result."""
    signal_value: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)

    # HHI component
    hhi_score: float
    normalized_hhi: float

    # Repeat official component
    repeat_score: float
    normalized_repeat: float

    # Department context
    department_id: str
    department_name: str

    # Risk indicators
    risk_level: str  # HIGH, MEDIUM, LOW, NEGLIGIBLE
    risk_indicators: List[str]

    # Evidence
    evidence: List[str]
    recommendations: List[str]

    # Detailed results
    hhi_details: Optional[HHIResult] = None
    repeat_details: Optional[List[RepeatOfficialResult]] = None
    graph_stats: Dict[str, Any] = Field(default_factory=dict)

    # Metadata
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[int] = None


class DepartmentSpend(BaseModel):
    """Department spending summary."""
    department_id: str
    department_name: str
    total_spend: float
    vendor_spend: Dict[str, float]  # vendor_id -> spend
    vendor_count: int
    transaction_count: int
    period_start: date
    period_end: date
    hhi_score: Optional[float] = None


class OfficialVendorRelationship(BaseModel):
    """Relationship between official and vendor."""
    official_id: str
    official_name: str
    vendor_id: str
    vendor_name: str
    department_id: str
    interaction_count: int
    total_value: float
    first_interaction: date
    last_interaction: date
    is_repeated: bool = False
    risk_factors: List[str] = Field(default_factory=list)