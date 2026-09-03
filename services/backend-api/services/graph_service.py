"""Graph service — vendor relationship graph with network analysis."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.graph import GraphEdge, GraphNode, VendorGraph
from models.orm import GraphEdge as GraphEdgeORM, GraphNode as GraphNodeORM

logger = logging.getLogger(__name__)

_NODE_COLORS = {
    "department": "#4CAF50",
    "vendor": "#2196F3",
    "official": "#F44336",
    "transaction": "#FF9800",
    "policy": "#9C27BB",
}


class GraphService:
    """PostgreSQL-backed vendor relationship graph."""

    def __init__(self) -> None:
        pass

    def seed_demo_data(self) -> None:
        """Populate demo graph data."""
        from db import get_session
        with get_session() as db:
            if db.query(GraphNodeORM).count() > 0:
                return
            nodes = [
                ("VEND-ABC12", "vendor", "VEND-ABC12***", 20),
                ("VEND-DEF34", "vendor", "VEND-DEF34***", 12),
                ("VEND-GHI56", "vendor", "VEND-GHI56***", 8),
                ("DEPT-IT", "department", "IT Department", 15),
                ("DEPT-HR", "department", "HR Department", 10),
                ("OFF-001", "official", "Official-001", 12),
                ("OFF-002", "official", "Official-002", 8),
                ("OFF-003", "official", "Official-003", 6),
                ("TX-001", "transaction", "TX-001 ($150K)", 8),
                ("TX-004", "transaction", "TX-004 ($200K)", 10),
            ]
            for nid, ntype, label, size in nodes:
                node = GraphNodeORM(
                    id=nid,
                    type=ntype,
                    label=label,
                    size=size,
                    color=_NODE_COLORS.get(ntype, "#9E9E9E"),
                    data={},
                    metadata={},
                )
                db.add(node)

            edges = [
                ("e1", "VEND-ABC12", "DEPT-IT", "supplies", "supplies", 3.0),
                ("e2", "VEND-ABC12", "OFF-001", "approved_by", "approved_by", 5.0),
                ("e3", "VEND-ABC12", "OFF-002", "approved_by", "approved_by", 2.0),
                ("e4", "VEND-DEF34", "DEPT-HR", "supplies", "supplies", 2.0),
                ("e5", "VEND-DEF34", "OFF-003", "approved_by", "approved_by", 1.0),
                ("e6", "TX-001", "VEND-ABC12", "from_vendor", "from", 1.0),
                ("e7", "TX-001", "DEPT-IT", "for_dept", "for", 1.0),
                ("e8", "TX-004", "VEND-ABC12", "from_vendor", "from", 1.0),
                ("e9", "TX-004", "DEPT-IT", "for_dept", "for", 1.0),
            ]
            for eid, src, tgt, etype, label, weight in edges:
                edge = GraphEdgeORM(
                    id=eid,
                    source=src,
                    target=tgt,
                    type=etype,
                    label=label,
                    weight=weight,
                    data={},
                )
                db.add(edge)
            db.commit()

    def get_vendor_graph(
        self,
        vendor_token: str,
        *,
        user_jurisdictions: Optional[List[str]] = None,
        depth: int = 2,
    ) -> Optional[VendorGraph]:
        """Get the vendor relationship graph up to *depth* hops."""
        from db import get_session
        with get_session() as db:
            node = db.query(GraphNodeORM).filter(GraphNodeORM.id == vendor_token).first()
            if node is None:
                return None

            all_nodes = {n.id: n for n in db.query(GraphNodeORM).all()}
            all_edges = db.query(GraphEdgeORM).all()

            adjacency: Dict[str, List[str]] = defaultdict(list)
            for e in all_edges:
                adjacency[e.source].append(e.target)
                adjacency[e.target].append(e.source)

            visited: set = set()
            queue = [(vendor_token, 0)]
            reachable_ids: set = set()

            while queue:
                nid, d = queue.pop(0)
                if nid in visited or d > depth:
                    continue
                visited.add(nid)
                reachable_ids.add(nid)
                for neighbor in adjacency.get(nid, []):
                    if neighbor not in visited:
                        queue.append((neighbor, d + 1))

            nodes = [
                GraphNode(
                    id=n.id,
                    type=n.type,
                    label=n.label,
                    size=n.size,
                    color=n.color,
                    data=n.data or {},
                    metadata=n.node_metadata or {},
                )
                for nid, n in all_nodes.items()
                if nid in reachable_ids
            ]
            edges = [
                GraphEdge(
                    id=e.id,
                    source=e.source,
                    target=e.target,
                    type=e.type,
                    label=e.label,
                    weight=e.weight,
                    data=e.data or {},
                )
                for e in all_edges
                if e.source in reachable_ids and e.target in reachable_ids
            ]

            return VendorGraph(
                nodes=nodes,
                edges=edges,
                metadata={
                    "vendor_token": vendor_token,
                    "depth": depth,
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                },
            )

    def get_analysis(self, vendor_token: str) -> Dict[str, Any]:
        """Compute network metrics for a vendor."""
        from db import get_session
        with get_session() as db:
            node = db.query(GraphNodeORM).filter(GraphNodeORM.id == vendor_token).first()
            if node is None:
                return {"error": "vendor not found"}

            edges = db.query(GraphEdgeORM).filter(GraphEdgeORM.source == vendor_token).all()

            official_approvals: Dict[str, int] = defaultdict(int)
            for e in edges:
                if e.type == "approved_by":
                    official_approvals[e.target] += int(e.weight or 1)

            total = sum(official_approvals.values()) or 1
            shares = [c / total for c in official_approvals.values()]
            hhi = sum(s * s for s in shares)

            concentration = "low"
            if hhi > 0.5:
                concentration = "high"
            elif hhi > 0.25:
                concentration = "medium"

            suspicious: List[str] = []
            if concentration == "high":
                suspicious.append("high_concentration_risk")
            if official_approvals and max(official_approvals.values()) > total * 0.5:
                suspicious.append("single_official_dominance")

            return {
                "vendor_token": vendor_token,
                "hhi": round(hhi, 4),
                "concentration_risk": concentration,
                "repeat_officials": len(official_approvals),
                "suspicious_patterns": suspicious,
            }
