"""Graph service — orchestrates graph queries, analysis, and caching."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from models.twin import (
    GraphEdge,
    GraphNode,
    GraphResponse,
    NetworkAnalysis,
    PathResult,
    VendorTwin,
    OfficialTwin,
    RelationshipEdge,
)
from services.cache_service import CacheService
from services.query_builder import QueryBuilder
from services.relationship_service import RelationshipService

logger = logging.getLogger(__name__)


class GraphService:
    """Production graph service with DB (optional) and in-memory graph."""

    def __init__(
        self,
        db_pool: Any = None,
        cache_service: Optional[CacheService] = None,
    ):
        self.db_pool = db_pool
        self.cache = cache_service or CacheService()
        self.rel_service = RelationshipService()

        # In-memory twin stores (used when DB not available)
        self._vendors: Dict[str, VendorTwin] = {}
        self._officials: Dict[str, OfficialTwin] = {}

    # ── Vendor graph ───────────────────────────────────────────────

    async def get_vendor_graph(
        self,
        vendor_token: str,
        depth: int = 2,
        include_edges: bool = True,
        limit_nodes: int = 100,
    ) -> GraphResponse:
        """Get the graph around a vendor (DB or in-memory)."""
        start = time.time()

        # Check cache
        cache_key = CacheService._make_key("vendor", vendor_token, str(depth))
        cached = await self.cache.get(cache_key)
        if cached:
            return GraphResponse(**cached)

        if self.db_pool:
            response = await self._get_vendor_graph_from_db(
                vendor_token, depth, include_edges, limit_nodes
            )
        else:
            response = self._get_vendor_graph_in_memory(
                vendor_token, depth, include_edges
            )

        response.query_time_ms = (time.time() - start) * 1000
        await self.cache.set(cache_key, response.model_dump(mode="json"))
        return response

    async def _get_vendor_graph_from_db(
        self, vendor_token: str, depth: int, include_edges: bool, limit_nodes: int
    ) -> GraphResponse:
        """Execute vendor graph recursive CTE against Postgres."""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    WITH RECURSIVE vendor_network AS (
                        SELECT
                            v.vendor_id AS node_id, 'vendor' AS node_type,
                            v.name AS node_label, v.token AS vendor_token,
                            NULL::TEXT AS parent_id, 0 AS depth
                        FROM vendors v WHERE v.token = $1

                        UNION ALL

                        SELECT t.transaction_id::TEXT, 'transaction',
                               t.invoice_number, g.vendor_token, g.node_id, g.depth + 1
                        FROM vendor_network g
                        JOIN transactions t ON t.vendor_token = g.vendor_token
                        WHERE g.depth < $2

                        UNION ALL

                        SELECT d.department_id, 'department', d.name,
                               g.vendor_token, g.node_id, g.depth + 1
                        FROM vendor_network g
                        JOIN transactions t ON t.vendor_token = g.vendor_token
                        JOIN departments d ON d.department_id = t.department_id
                        WHERE g.depth < $2

                        UNION ALL

                        SELECT o.official_id::TEXT, 'official', o.name,
                               g.vendor_token, g.node_id, g.depth + 1
                        FROM vendor_network g
                        JOIN vendor_officials vo ON vo.vendor_token = g.vendor_token
                        JOIN officials o ON o.official_id = vo.official_id
                        WHERE g.depth < $2
                    ),
                    deduped AS (
                        SELECT DISTINCT ON (node_id) node_id, node_type,
                               node_label, vendor_token, depth
                        FROM vendor_network ORDER BY node_id, depth
                    )
                    SELECT json_agg(DISTINCT jsonb_build_object(
                        'id', node_id, 'type', node_type, 'label', node_label,
                        'properties', jsonb_build_object('vendor_token', vendor_token, 'depth', depth),
                        'size', CASE node_type WHEN 'vendor' THEN 25 WHEN 'department' THEN 20
                                WHEN 'official' THEN 15 WHEN 'transaction' THEN 18 ELSE 12 END,
                        'color', CASE node_type WHEN 'department' THEN '#4CAF50' WHEN 'vendor' THEN '#2196F3'
                                 WHEN 'official' THEN '#F44336' WHEN 'transaction' THEN '#FF9800'
                                 ELSE '#9E9E9E' END
                    )) AS nodes
                    FROM deduped
                    """,
                    vendor_token,
                    depth,
                )

                nodes = []
                if rows and rows[0].get("nodes"):
                    for nd in rows[0]["nodes"]:
                        nodes.append(GraphNode(**nd))

                # Build edges from adjacency
                edges = []
                if include_edges:
                    for i, n1 in enumerate(nodes):
                        for n2 in nodes[i+1:]:
                            if n1.properties.get("depth", 0) == n2.properties.get("depth", 0) - 1:
                                edges.append(GraphEdge(
                                    source=n1.id, target=n2.id,
                                    type="related", label="Related",
                                ))

                return GraphResponse(
                    nodes=nodes, edges=edges,
                    total_nodes=len(nodes), total_edges=len(edges),
                    metadata={"vendor_token": vendor_token, "depth": depth},
                )

        except Exception as e:
            logger.error(f"DB query failed for vendor graph: {e}")
            return GraphResponse(
                nodes=[], edges=[],
                metadata={"vendor_token": vendor_token, "error": str(e)},
            )

    def _get_vendor_graph_in_memory(
        self, vendor_token: str, depth: int, include_edges: bool
    ) -> GraphResponse:
        """Build vendor graph from in-memory relationship store."""
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []

        # Seed vendor node
        vendor_node = GraphNode(
            id=vendor_token, type="vendor", label=vendor_token,
            size=25, color="#2196F3",
            properties={"depth": 0},
        )
        nodes.append(vendor_node)

        # BFS
        visited = {vendor_token}
        frontier = [vendor_token]

        for d in range(1, depth + 1):
            next_frontier = []
            for node_id in frontier:
                for neighbor_id in self.rel_service._adjacency.get(node_id, set()):
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_frontier.append(neighbor_id)

                        # Determine type from edge
                        node_type = "related"
                        color = "#9E9E9E"
                        for edge in self.rel_service.get_edges_for_node(node_id):
                            other = edge["target"] if edge["source"] == node_id else edge["source"]
                            if other == neighbor_id:
                                node_type = edge["type"]
                                color = {
                                    "contracted": "#2196F3", "employs": "#F44336",
                                    "supplies": "#FF9800", "approves": "#9C27B0",
                                }.get(node_type, "#9E9E9E")
                                break

                        nodes.append(GraphNode(
                            id=neighbor_id, type=node_type, label=neighbor_id,
                            size=max(12, 25 - d * 3), color=color,
                            properties={"depth": d},
                        ))

                        if include_edges:
                            edges.append(GraphEdge(
                                source=node_id, target=neighbor_id,
                                type=node_type, label=node_type.title(),
                            ))

            frontier = next_frontier

        return GraphResponse(
            nodes=nodes, edges=edges,
            total_nodes=len(nodes), total_edges=len(edges),
            metadata={"vendor_token": vendor_token, "depth": depth, "source": "in_memory"},
        )

    # ── Department / Official graphs ──────────────────────────────

    async def get_department_network(
        self, department_id: str, depth: int = 2
    ) -> GraphResponse:
        """Get the network around a department."""
        nodes: List[GraphNode] = []
        nodes.append(GraphNode(
            id=department_id, type="department", label=department_id,
            size=25, color="#4CAF50", properties={"depth": 0},
        ))

        visited = {department_id}
        frontier = [department_id]

        for d in range(1, depth + 1):
            next_frontier = []
            for node_id in frontier:
                for neighbor_id in self.rel_service._adjacency.get(node_id, set()):
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_frontier.append(neighbor_id)
                        nodes.append(GraphNode(
                            id=neighbor_id, type="related", label=neighbor_id,
                            size=max(12, 25 - d * 3), properties={"depth": d},
                        ))
            frontier = next_frontier

        return GraphResponse(
            nodes=nodes, total_nodes=len(nodes),
            metadata={"department_id": department_id, "depth": depth},
        )

    async def get_official_network(
        self, official_id: str, depth: int = 2
    ) -> GraphResponse:
        """Get the network around an official."""
        nodes: List[GraphNode] = []
        nodes.append(GraphNode(
            id=official_id, type="official", label=official_id,
            size=25, color="#F44336", properties={"depth": 0},
        ))

        visited = {official_id}
        frontier = [official_id]

        for d in range(1, depth + 1):
            next_frontier = []
            for node_id in frontier:
                for neighbor_id in self.rel_service._adjacency.get(node_id, set()):
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_frontier.append(neighbor_id)
                        nodes.append(GraphNode(
                            id=neighbor_id, type="related", label=neighbor_id,
                            size=max(12, 25 - d * 3), properties={"depth": d},
                        ))
            frontier = next_frontier

        return GraphResponse(
            nodes=nodes, total_nodes=len(nodes),
            metadata={"official_id": official_id, "depth": depth},
        )

    # ── Multi-vendor ─────────────────────────────────────────────

    async def get_multi_vendor_graph(
        self, vendor_tokens: List[str], depth: int = 2
    ) -> GraphResponse:
        """Get a combined graph for multiple vendors (fraud ring detection)."""
        all_nodes: Dict[str, GraphNode] = {}
        all_edges: List[GraphEdge] = []

        for token in vendor_tokens:
            sub = await self.get_vendor_graph(token, depth=depth, include_edges=True)
            for node in sub.nodes:
                if node.id not in all_nodes:
                    all_nodes[node.id] = node
            all_edges.extend(sub.edges)

        # Find cross-vendor connections
        vendor_set = set(vendor_tokens)
        for n1_id, n1 in all_nodes.items():
            for n2_id, n2 in all_nodes.items():
                if n1_id >= n2_id:
                    continue
                if n1_id in vendor_set and n2_id in vendor_set:
                    continue
                # Shared neighbor → potential connection
                shared = self.rel_service.find_shared_neighbors(n1_id, n2_id)
                if shared:
                    all_edges.append(GraphEdge(
                        source=n1_id, target=n2_id,
                        type="related", label=f"Shared: {', '.join(list(shared)[:3])}",
                        weight=0.5,
                    ))

        return GraphResponse(
            nodes=list(all_nodes.values()),
            edges=all_edges,
            total_nodes=len(all_nodes),
            total_edges=len(all_edges),
            metadata={"vendor_tokens": vendor_tokens, "depth": depth},
        )

    # ── Path finding ─────────────────────────────────────────────

    async def get_relationship_path(
        self, from_id: str, to_id: str, max_depth: int = 5
    ) -> PathResult:
        """Find the shortest path between two nodes."""
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        QueryBuilder.build_path_query(max_depth),
                        from_id, to_id,
                    )
                    if rows:
                        return PathResult(
                            found=True,
                            path_nodes=list(rows[0]["path"]),
                            distance=rows[0]["depth"],
                        )
            except Exception as e:
                logger.error(f"DB path query failed: {e}")

        # Fallback to in-memory BFS
        path = self.rel_service.find_shortest_path(from_id, to_id, max_depth)
        if path:
            return PathResult(found=True, path_nodes=path, distance=len(path) - 1)
        return PathResult(found=False)

    # ── Network analysis ─────────────────────────────────────────

    async def analyse_vendor_network(self, vendor_id: str) -> NetworkAnalysis:
        """Compute network metrics for a vendor."""
        result = self.rel_service.detect_concentration_risk(vendor_id)
        return NetworkAnalysis(
            vendor_id=vendor_id,
            hhi=result["hhi"],
            concentration_risk=result["concentration_risk"],
            repeat_officials=result["repeat_officials"],
            suspicious_patterns=result["suspicious_patterns"],
        )

    # ── Vendor/Official twin management ──────────────────────────

    def create_vendor(self, vendor_id: str, name_masked: str, **kwargs: Any) -> VendorTwin:
        twin = VendorTwin(vendor_id=vendor_id, name_masked=name_masked, **kwargs)
        self._vendors[vendor_id] = twin
        return twin

    def create_official(self, official_id: str, name_masked: str, **kwargs: Any) -> OfficialTwin:
        twin = OfficialTwin(official_id=official_id, name_masked=name_masked, **kwargs)
        self._officials[official_id] = twin
        return twin

    def add_relationship(self, source_id: str, target_id: str, relationship_type: str, **kwargs: Any) -> RelationshipEdge:
        edge_data = self.rel_service.add_relationship(
            source_id, target_id, relationship_type,
            weight=kwargs.get("weight", 1.0),
        )
        return RelationshipEdge(
            source_id=source_id, target_id=target_id,
            relationship_type=relationship_type,
            weight=kwargs.get("weight", 1.0),
            transaction_count=kwargs.get("transaction_count", 0),
            total_amount=kwargs.get("total_amount", 0.0),
        )

    def get_vendor(self, vendor_id: str) -> Optional[VendorTwin]:
        return self._vendors.get(vendor_id)

    def get_official(self, official_id: str) -> Optional[OfficialTwin]:
        return self._officials.get(official_id)

    def get_connections(self, entity_id: str) -> List[RelationshipEdge]:
        edges = self.rel_service.get_edges_for_node(entity_id)
        return [
            RelationshipEdge(
                source_id=e["source"], target_id=e["target"],
                relationship_type=e["type"], weight=e["weight"],
            )
            for e in edges
        ]

    # ── Stats ────────────────────────────────────────────────────

    def get_graph_stats(self) -> Dict[str, Any]:
        return {
            "vendors": len(self._vendors),
            "officials": len(self._officials),
            "edges": len(self.rel_service._edges),
            **self.rel_service.get_graph_stats(),
        }

    # ── Utility ──────────────────────────────────────────────────

    async def check_vendor_jurisdiction(
        self, vendor_token: str, user_jurisdictions: List[str]
    ) -> bool:
        """Check if user has jurisdiction access to this vendor."""
        # Super-admin bypass
        if "ALL" in user_jurisdictions or "*" in user_jurisdictions:
            return True
        # In production, query vendor's department jurisdictions
        return True  # Default allow for now
