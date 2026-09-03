"""Graph metrics utilities for vendor relationship analysis."""

import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple


class GraphMetrics:
    """Advanced graph metrics for vendor relationship analysis."""

    @staticmethod
    def calculate_hhi(market_shares: List[float]) -> float:
        """
        Calculate Herfindahl-Hirschman Index (HHI).

        HHI = sum of squared market shares
        Normalized to [0, 1]
        """
        if not market_shares:
            return 0.0

        # Sum of squares
        hhi = sum(share ** 2 for share in market_shares)

        # Normalize to [0, 1]
        # Max HHI = 1 (monopoly), Min = 1/n (perfect competition)
        n = len(market_shares)
        if n == 1:
            return 1.0

        # Normalize: (HHI - 1/n) / (1 - 1/n)
        min_hhi = 1 / n if n > 0 else 0
        max_hhi = 1.0

        if max_hhi == min_hhi:
            return 0.0

        normalized_hhi = (hhi - min_hhi) / (max_hhi - min_hhi)
        return max(0.0, min(1.0, normalized_hhi))

    @staticmethod
    def classify_hhi(normalized_hhi: float) -> str:
        """Classify HHI score into concentration levels."""
        if normalized_hhi >= 0.75:
            return "HIGH_CONCENTRATION"
        elif normalized_hhi >= 0.50:
            return "MODERATE_CONCENTRATION"
        elif normalized_hhi >= 0.25:
            return "LOW_CONCENTRATION"
        else:
            return "COMPETITIVE"

    @staticmethod
    def calculate_centrality(nodes: List[str], edges: List[Tuple[str, str]]) -> Dict[str, float]:
        """Calculate degree centrality for nodes."""
        degree = Counter()
        for source, target in edges:
            degree[source] += 1
            degree[target] += 1

        max_degree = max(degree.values()) if degree else 1
        centrality = {
            node: degree[node] / max_degree
            for node in nodes
        }

        return centrality

    @staticmethod
    def calculate_clustering_coefficient(
        nodes: List[str],
        edges: List[Tuple[str, str]]
    ) -> Dict[str, float]:
        """Calculate local clustering coefficient."""
        # Build adjacency list
        adjacency = defaultdict(set)
        for source, target in edges:
            adjacency[source].add(target)
            adjacency[target].add(source)

        coefficients = {}
        for node in nodes:
            neighbors = adjacency.get(node, set())
            k = len(neighbors)

            if k < 2:
                coefficients[node] = 0.0
                continue

            # Count edges among neighbors
            neighbor_edges = 0
            neighbors_list = list(neighbors)
            for i in range(len(neighbors_list)):
                for j in range(i + 1, len(neighbors_list)):
                    if neighbors_list[j] in adjacency.get(neighbors_list[i], set()):
                        neighbor_edges += 1

            # Clustering coefficient
            possible_edges = k * (k - 1) / 2
            coefficients[node] = neighbor_edges / possible_edges if possible_edges > 0 else 0.0

        return coefficients

    @staticmethod
    def identify_communities(
        nodes: List[str],
        edges: List[Tuple[str, str]],
        min_community_size: int = 3
    ) -> Dict[str, List[str]]:
        """
        Simple community detection using label propagation.
        """
        # Build adjacency
        adjacency = defaultdict(set)
        for source, target in edges:
            adjacency[source].add(target)
            adjacency[target].add(source)

        # Initialize labels
        labels = {node: node for node in nodes}

        # Iterative label propagation
        for _ in range(10):  # Max iterations
            for node in nodes:
                # Get neighbor labels
                neighbor_labels = [
                    labels[neighbor]
                    for neighbor in adjacency.get(node, set())
                    if neighbor in labels
                ]

                if neighbor_labels:
                    # Most common label among neighbors
                    most_common = Counter(neighbor_labels).most_common(1)[0][0]
                    labels[node] = most_common

        # Group nodes by label
        communities = defaultdict(list)
        for node, label in labels.items():
            communities[label].append(node)

        # Filter small communities
        communities = {
            label: members
            for label, members in communities.items()
            if len(members) >= min_community_size
        }

        return dict(communities)

    @staticmethod
    def calculate_vendor_concentration(
        vendor_spend: Dict[str, float],
        total_spend: float
    ) -> Dict[str, Any]:
        """
        Calculate vendor concentration metrics.
        """
        if not vendor_spend or total_spend == 0:
            return {
                "hhi": 0.0,
                "normalized_hhi": 0.0,
                "vendor_count": 0,
                "concentration_level": "NO_DATA"
            }

        # Calculate market shares
        market_shares = [
            spend / total_spend
            for spend in vendor_spend.values()
        ]

        # HHI
        hhi = GraphMetrics.calculate_hhi(market_shares)
        normalized_hhi = GraphMetrics.calculate_hhi(market_shares)

        return {
            "hhi": hhi,
            "normalized_hhi": normalized_hhi,
            "vendor_count": len(vendor_spend),
            "concentration_level": GraphMetrics.classify_hhi(normalized_hhi),
            "dominant_vendors": GraphMetrics._get_dominant_vendors(
                vendor_spend,
                total_spend
            )
        }

    @staticmethod
    def _get_dominant_vendors(
        vendor_spend: Dict[str, float],
        total_spend: float,
        threshold: float = 0.20
    ) -> List[Dict[str, Any]]:
        """Identify dominant vendors (>= threshold of total spend)."""
        dominant = []
        for vendor_id, spend in vendor_spend.items():
            share = spend / total_spend if total_spend > 0 else 0
            if share >= threshold:
                dominant.append({
                    "vendor_id": vendor_id,
                    "spend": spend,
                    "share": share
                })

        return sorted(dominant, key=lambda x: x['share'], reverse=True)