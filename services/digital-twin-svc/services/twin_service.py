"""Twin service — build and analyse vendor/official relationship networks."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict

from models.twin import NetworkAnalysis, OfficialTwin, RelationshipEdge, VendorTwin

logger = logging.getLogger(__name__)


class TwinService:
    """In-memory digital twin graph with network analysis."""

    def __init__(self) -> None:
        self._vendors: Dict[str, VendorTwin] = {}
        self._officials: Dict[str, OfficialTwin] = {}
        self._edges: List[RelationshipEdge] = []
        self._adjacency: Dict[str, List[str]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_vendor(self, vendor_id: str, name_masked: str, **kwargs: Any) -> VendorTwin:
        twin = VendorTwin(vendor_id=vendor_id, name_masked=name_masked, **kwargs)
        self._vendors[vendor_id] = twin
        return twin

    def create_official(self, official_id: str, name_masked: str, **kwargs: Any) -> OfficialTwin:
        twin = OfficialTwin(official_id=official_id, name_masked=name_masked, **kwargs)
        self._officials[official_id] = twin
        return twin

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        weight: float = 1.0,
        transaction_count: int = 0,
        total_amount: float = 0.0,
    ) -> RelationshipEdge:
        edge = RelationshipEdge(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            weight=weight,
            transaction_count=transaction_count,
            total_amount=total_amount,
        )
        self._edges.append(edge)
        self._adjacency[source_id].append(target_id)
        self._adjacency[target_id].append(source_id)
        return edge

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_vendor(self, vendor_id: str) -> Optional[VendorTwin]:
        return self._vendors.get(vendor_id)

    def get_official(self, official_id: str) -> Optional[OfficialTwin]:
        return self._officials.get(official_id)

    def get_connections(self, entity_id: str) -> List[RelationshipEdge]:
        connected_ids = set(self._adjacency.get(entity_id, []))
        return [e for e in self._edges if e.source_id in connected_ids or e.target_id in connected_ids]

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def analyse_vendor_network(self, vendor_id: str) -> NetworkAnalysis:
        """Compute network metrics for a vendor."""
        connections = self.get_connections(vendor_id)

        # HHI: sum of squared shares
        official_counts: Dict[str, int] = defaultdict(int)
        vendor_set: set = set()
        for edge in connections:
            if edge.source_id != vendor_id:
                vendor_set.add(edge.source_id)
            if edge.target_id != vendor_id:
                vendor_set.add(edge.target_id)
            # Count approvals by official
            if "approved_by" in edge.relationship_type:
                official_id = edge.target_id if edge.source_id == vendor_id else edge.source_id
                official_counts[official_id] += edge.transaction_count

        total_approvals = sum(official_counts.values()) or 1
        shares = [c / total_approvals for c in official_counts.values()]
        hhi = sum(s * s for s in shares)

        concentration = "low"
        if hhi > 0.5:
            concentration = "high"
        elif hhi > 0.25:
            concentration = "medium"

        suspicious: List[str] = []
        if concentration == "high":
            suspicious.append("high_concentration_risk")
        if len(official_counts) > 0 and max(official_counts.values()) > total_approvals * 0.5:
            suspicious.append("single_official_dominance")

        return NetworkAnalysis(
            vendor_id=vendor_id,
            hhi=round(hhi, 4),
            concentration_risk=concentration,
            repeat_officials=len(official_counts),
            connected_vendors=len(vendor_set),
            suspicious_patterns=suspicious,
        )

    def get_graph_stats(self) -> Dict[str, Any]:
        return {
            "vendors": len(self._vendors),
            "officials": len(self._officials),
            "edges": len(self._edges),
        }
