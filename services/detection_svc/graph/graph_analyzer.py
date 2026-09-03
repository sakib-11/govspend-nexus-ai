"""Graph analyzer service for detecting risk patterns in vendor graphs."""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from ..models.vendor_graph import VendorGraph, GraphNode, NodeType, EdgeType, HHIResult, RepeatOfficialResult
from ..utils.graph_metrics import GraphMetrics
from ..utils.logging import get_logger

logger = get_logger(__name__)


class GraphAnalyzer:
    """Analyze vendor relationship graph for risk indicators."""

    def __init__(self):
        self.metrics = GraphMetrics()

    async def analyze_hhi(
        self,
        graph: VendorGraph,
        department_id: str,
        period: str = "last_12_months"
    ) -> HHIResult:
        """
        Calculate HHI for department.
        """
        # Get department node
        dept_node = next(
            (n for n in graph.nodes
             if n.node_type == NodeType.DEPARTMENT and n.id == department_id),
            None
        )

        if not dept_node:
            raise ValueError(f"Department {department_id} not found in graph")

        # Get vendors supplying to this department
        vendor_edges = [
            e for e in graph.edges
            if e.edge_type == EdgeType.SUPPLIES_TO
            and e.target_id == department_id
        ]

        # Calculate vendor spend distribution
        vendor_spend = {}
        for edge in vendor_edges:
            vendor_id = edge.source_id
            total_spend = edge.metadata.get('total_spend', 0)
            vendor_spend[vendor_id] = total_spend

        # Get vendor names
        vendor_names = {}
        for node in graph.nodes:
            if node.node_type == NodeType.VENDOR:
                vendor_names[node.id] = node.name

        total_spend = sum(vendor_spend.values())

        # Calculate market shares
        market_shares = [
            spend / total_spend if total_spend > 0 else 0
            for spend in vendor_spend.values()
        ]

        # HHI
        hhi = self.metrics.calculate_hhi(market_shares)
        normalized_hhi = hhi  # Already normalized

        # Get dominant vendors
        dominant_vendors = []
        threshold = 0.20  # 20% market share threshold

        for vendor_id, spend in vendor_spend.items():
            share = spend / total_spend if total_spend > 0 else 0
            if share >= threshold:
                dominant_vendors.append({
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_names.get(vendor_id, "Unknown"),
                    "spend": spend,
                    "share": share
                })

        dominant_vendors.sort(key=lambda x: x['share'], reverse=True)

        return HHIResult(
            department_id=department_id,
            department_name=dept_node.name,
            hhi_score=hhi,
            normalized_hhi=normalized_hhi,
            vendor_count=len(vendor_spend),
            total_spend=total_spend,
            market_concentration_level=self.metrics.classify_hhi(normalized_hhi),
            dominant_vendors=dominant_vendors,
            vendors_count=len(vendor_spend),
            period=period
        )

    async def analyze_repeat_officials(
        self,
        graph: VendorGraph,
        department_id: str
    ) -> List[RepeatOfficialResult]:
        """
        Analyze repeat official-vendor relationships.
        """
        # Get officials in department
        officials = [
            n for n in graph.nodes
            if n.node_type == NodeType.OFFICIAL
        ]

        results = []

        for official in officials:
            # Get vendors this official approves
            approval_edges = [
                e for e in graph.edges
                if e.edge_type == EdgeType.APPROVES
                and e.source_id == official.id
            ]

            if not approval_edges:
                continue

            # Count repeats per vendor
            vendor_repeats = {}
            for edge in approval_edges:
                vendor_id = edge.target_id
                approval_count = edge.metadata.get('approval_count', 1)
                vendor_repeats[vendor_id] = vendor_repeats.get(vendor_id, 0) + approval_count

            # Calculate repeat score
            total_approvals = sum(vendor_repeats.values())
            vendor_count = len(vendor_repeats)

            if vendor_count == 0:
                repeat_score = 0.0
            else:
                # Higher score if few vendors get most approvals
                hhi = sum((count / total_approvals) ** 2
                         for count in vendor_repeats.values())

                # Normalize HHI to get repeat score
                min_hhi = 1 / vendor_count if vendor_count > 0 else 0
                normalized_hhi = (hhi - min_hhi) / (1 - min_hhi) if min_hhi < 1 else 0

                repeat_score = normalized_hhi

            # Identify risk indicators
            risk_indicators = []

            # Vendor concentration risk
            if repeat_score > 0.7:
                risk_indicators.append("HIGH_VENDOR_CONCENTRATION")

            # High approval count
            if total_approvals > 100:
                risk_indicators.append("HIGH_APPROVAL_VOLUME")

            # Too few vendors
            if vendor_count < 3 and total_approvals > 10:
                risk_indicators.append("FEW_VENDORS_HIGH_APPROVALS")

            # Get vendor names
            vendor_names = {}
            for node in graph.nodes:
                if node.node_type == NodeType.VENDOR:
                    vendor_names[node.id] = node.name

            # Create result
            result = RepeatOfficialResult(
                official_id=official.id,
                official_name=official.name,
                department_id=department_id,
                department_name=next(
                    (n.name for n in graph.nodes
                     if n.node_type == NodeType.DEPARTMENT and n.id == department_id),
                    "Unknown"
                ),
                vendor_repeats={
                    vendor_names.get(vid, vid): count
                    for vid, count in vendor_repeats.items()
                },
                repeat_score=repeat_score,
                normalized_repeat=repeat_score,
                total_vendor_connections=len(vendor_repeats),
                risk_indicators=risk_indicators
            )

            results.append(result)

        return results

    async def detect_risk_patterns(
        self,
        graph: VendorGraph,
        department_id: str
    ) -> Dict[str, Any]:
        """
        Detect risk patterns in the graph.
        """
        risk_patterns = []

        # Pattern 1: High vendor concentration (HHI > 0.7)
        hhi_result = await self.analyze_hhi(graph, department_id)
        if hhi_result.normalized_hhi > 0.7:
            risk_patterns.append({
                "pattern": "HIGH_VENDOR_CONCENTRATION",
                "severity": "HIGH",
                "description": f"Vendor market concentration is high (HHI: {hhi_result.normalized_hhi:.3f})",
                "details": {
                    "hhi": hhi_result.normalized_hhi,
                    "dominant_vendors": hhi_result.dominant_vendors
                }
            })

        # Pattern 2: Repeat official relationships
        repeat_results = await self.analyze_repeat_officials(graph, department_id)

        for result in repeat_results:
            if result.repeat_score > 0.7:
                risk_patterns.append({
                    "pattern": "REPEAT_OFFICIAL_RISK",
                    "severity": "HIGH",
                    "description": (
                        f"Official {result.official_name} has high vendor repeat rate "
                        f"(score: {result.repeat_score:.3f})"
                    ),
                    "details": {
                        "official_id": result.official_id,
                        "vendor_repeats": result.vendor_repeats,
                        "total_vendors": result.total_vendor_connections
                    }
                })

        # Pattern 3: Vendor sharing officials (collusion risk)
        # Find vendors that share multiple officials
        official_sharing = defaultdict(set)
        for edge in graph.edges:
            if edge.edge_type == EdgeType.SHARES_OFFICIAL:
                official_sharing[edge.metadata.get('official_id')].add(edge.source_id)
                official_sharing[edge.metadata.get('official_id')].add(edge.target_id)

        for official_id, vendor_set in official_sharing.items():
            if len(vendor_set) > 3:  # More than 3 vendors sharing same official
                risk_patterns.append({
                    "pattern": "OFFICIAL_SHARING_RISK",
                    "severity": "MEDIUM",
                    "description": f"Official shares relationships with {len(vendor_set)} vendors",
                    "details": {
                        "official_id": official_id,
                        "vendor_count": len(vendor_set),
                        "vendors": list(vendor_set)[:5]  # First 5
                    }
                })

        # Pattern 4: Vendor dominance in multiple departments
        vendor_department_count = defaultdict(int)
        for edge in graph.edges:
            if edge.edge_type == EdgeType.SUPPLIES_TO:
                vendor_department_count[edge.source_id] += 1

        for vendor_id, dept_count in vendor_department_count.items():
            if dept_count > 5:  # Vendor supplies to more than 5 departments
                vendor_name = next(
                    (n.name for n in graph.nodes
                     if n.node_type == NodeType.VENDOR and n.id == vendor_id),
                    "Unknown"
                )
                risk_patterns.append({
                    "pattern": "VENDOR_DOMINANCE",
                    "severity": "MEDIUM",
                    "description": f"Vendor {vendor_name} supplies to {dept_count} departments",
                    "details": {
                        "vendor_id": vendor_id,
                        "department_count": dept_count
                    }
                })

        return {
            "risk_patterns": risk_patterns,
            "pattern_count": len(risk_patterns),
            "high_severity_count": sum(1 for p in risk_patterns if p['severity'] == "HIGH")
        }