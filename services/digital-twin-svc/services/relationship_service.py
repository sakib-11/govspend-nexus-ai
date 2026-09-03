"""Relationship service — managing and querying graph edges."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class RelationshipService:
    """In-memory relationship store with analytics."""

    def __init__(self):
        self._edges: List[Dict[str, Any]] = []
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)
        self._edge_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add a directed edge to the graph."""
        edge = {
            "id": f"{source_id}->{target_id}:{edge_type}",
            "source": source_id,
            "target": target_id,
            "type": edge_type,
            "weight": weight,
            "properties": properties or {},
        }

        self._edges.append(edge)
        self._adjacency[source_id].add(target_id)
        self._adjacency[target_id].add(source_id)
        self._edge_index[source_id].append(edge)
        self._edge_index[target_id].append(edge)

        return edge

    def get_neighbors(self, node_id: str, max_depth: int = 1) -> Set[str]:
        """BFS to find all reachable nodes up to depth."""
        visited = set()
        frontier = {node_id}

        for _ in range(max_depth):
            next_frontier: Set[str] = set()
            for node in frontier:
                for neighbor in self._adjacency.get(node, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.add(neighbor)
            frontier = next_frontier

        return visited

    def get_edges_for_node(self, node_id: str) -> List[Dict[str, Any]]:
        """Get all edges touching a node."""
        return self._edge_index.get(node_id, [])

    def find_shared_neighbors(
        self, node_a: str, node_b: str
    ) -> Set[str]:
        """Find nodes connected to both A and B."""
        neighbors_a = self._adjacency.get(node_a, set())
        neighbors_b = self._adjacency.get(node_b, set())
        return neighbors_a & neighbors_b

    def detect_concentration_risk(
        self,
        vendor_id: str,
        official_counts: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Detect HHI concentration risk for a vendor's officials."""
        if official_counts is None:
            # Compute from edges
            official_counts = {}
            for edge in self.get_edges_for_node(vendor_id):
                if edge["type"] in ("employs", "contracted"):
                    other = edge["target"] if edge["source"] == vendor_id else edge["source"]
                    official_counts[other] = official_counts.get(other, 0) + 1

        total = sum(official_counts.values()) or 1
        shares = [c / total for c in official_counts.values()]
        hhi = sum(s * s for s in shares)

        concentration = "low"
        if hhi > 0.5:
            concentration = "high"
        elif hhi > 0.25:
            concentration = "medium"

        suspicious = []
        if concentration == "high":
            suspicious.append("high_concentration_risk")
        if official_counts and max(official_counts.values()) > total * 0.5:
            suspicious.append("single_official_dominance")

        return {
            "hhi": round(hhi, 4),
            "concentration_risk": concentration,
            "repeat_officials": len(official_counts),
            "suspicious_patterns": suspicious,
        }

    def find_shortest_path(
        self,
        start: str,
        end: str,
        max_depth: int = 5,
    ) -> Optional[List[str]]:
        """BFS shortest path between two nodes."""
        if start == end:
            return [start]

        visited = {start}
        queue = [(start, [start])]

        for _ in range(max_depth):
            next_queue = []
            for node, path in queue:
                for neighbor in self._adjacency.get(node, set()):
                    if neighbor == end:
                        return path + [neighbor]
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_queue.append((neighbor, path + [neighbor]))
            queue = next_queue

        return None

    def get_communities(
        self, min_size: int = 3
    ) -> List[Set[str]]:
        """Simple community detection via connected components."""
        visited: Set[str] = set()
        communities: List[Set[str]] = []

        for node in list(self._adjacency.keys()):
            if node in visited:
                continue

            component: Set[str] = set()
            stack = [node]

            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                for neighbor in self._adjacency.get(current, set()):
                    if neighbor not in visited:
                        stack.append(neighbor)

            if len(component) >= min_size:
                communities.append(component)

        return communities

    def compute_edge_weights(self, transactions: List[Dict[str, Any]]) -> None:
        """Update edge weights based on transaction history."""
        tx_by_pair: Dict[Tuple[str, str], int] = defaultdict(int)

        for tx in transactions:
            vendor = tx.get("vendor_token", "")
            dept = tx.get("department_id", "")
            if vendor and dept:
                key = tuple(sorted([vendor, dept]))
                tx_by_pair[key] += 1

        for edge in self._edges:
            key = tuple(sorted([edge["source"], edge["target"]]))
            count = tx_by_pair.get(key, 0)
            if count > 0:
                edge["weight"] = min(1.0, count / 100.0)
                edge["properties"]["transaction_count"] = count

    def get_graph_stats(self) -> Dict[str, Any]:
        """Return graph statistics."""
        type_counts: Dict[str, int] = defaultdict(int)
        for edge in self._edges:
            type_counts[edge["type"]] += 1

        return {
            "total_edges": len(self._edges),
            "unique_nodes": len(self._adjacency),
            "edge_types": dict(type_counts),
        }
