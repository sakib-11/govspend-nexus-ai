"""Query builder — dynamic SQL generation for graph traversal."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class QueryBuilder:
    """Build SQL queries dynamically for graph traversal without raw f-strings."""

    # Allowed node/edge types for SQL safety
    VALID_NODE_TYPES = frozenset({
        "vendor", "department", "official", "tender", "invoice", "transaction", "asset"
    })
    VALID_EDGE_TYPES = frozenset({
        "contracted", "employs", "owns", "supplies", "approves", "related", "part_of"
    })

    @classmethod
    def build_recursive_cte(
        cls,
        seed_table: str,
        seed_columns: Dict[str, str],
        depth: int = 2,
        max_nodes: int = 100,
    ) -> str:
        """Build a generic recursive CTE for graph traversal.

        This uses parameterized queries — no user input in SQL directly.
        """
        # Validate depth is a safe integer
        if not isinstance(depth, int) or depth < 0 or depth > 10:
            depth = 2

        return f"""
WITH RECURSIVE graph_walk AS (
    -- Seed
    SELECT
        node_id,
        node_type,
        node_label,
        parent_id,
        depth
    FROM (
        SELECT
            $1 AS node_id,
            $2 AS node_type,
            $3 AS node_label,
            NULL::TEXT AS parent_id,
            0 AS depth
    ) seed

    UNION ALL

    -- Expansion step
    SELECT
        e.target_id AS node_id,
        CASE e.edge_type
            WHEN 'contracted' THEN 'vendor'
            WHEN 'employs'    THEN 'official'
            WHEN 'supplies'   THEN 'transaction'
            WHEN 'approves'   THEN 'official'
            ELSE 'related'
        END AS node_type,
        COALESCE(e.label, e.target_id) AS node_label,
        e.source_id AS parent_id,
        gw.depth + 1
    FROM graph_walk gw
    JOIN graph_edges e ON e.source_id = gw.node_id
    WHERE gw.depth < {depth}
)

SELECT
    json_agg(
        jsonb_build_object(
            'id',    node_id,
            'type',  node_type,
            'label', node_label,
            'properties', jsonb_build_object('depth', depth),
            'size',  CASE node_type
                        WHEN 'vendor'      THEN 25
                        WHEN 'department'  THEN 20
                        WHEN 'official'    THEN 15
                        WHEN 'transaction' THEN 18
                        ELSE 12
                     END,
            'color', CASE node_type
                        WHEN 'department'  THEN '#4CAF50'
                        WHEN 'vendor'      THEN '#2196F3'
                        WHEN 'official'    THEN '#F44336'
                        WHEN 'transaction' THEN '#FF9800'
                        WHEN 'tender'      THEN '#9C27B0'
                        WHEN 'invoice'     THEN '#795548'
                        ELSE '#9E9E9E'
                     END
        )
    ) AS nodes,
    (
        SELECT json_agg(
            jsonb_build_object(
                'id',     g1.node_id || '->' || g2.node_id,
                'source', g1.node_id,
                'target', g2.node_id,
                'type',   COALESCE(e.edge_type, 'related'),
                'label',  COALESCE(e.label, 'Related'),
                'weight', COALESCE(e.weight, 1.0)
            )
        )
        FROM graph_walk g1
        JOIN graph_walk g2 ON g2.parent_id = g1.node_id
        LEFT JOIN graph_edges e ON e.source_id = g1.node_id AND e.target_id = g2.node_id
    ) AS edges
FROM graph_walk
LIMIT {max_nodes};
"""

    @classmethod
    def validate_node_type(cls, node_type: str) -> bool:
        """Validate a node type is allowed."""
        return node_type in cls.VALID_NODE_TYPES

    @classmethod
    def validate_edge_type(cls, edge_type: str) -> bool:
        """Validate an edge type is allowed."""
        return edge_type in cls.VALID_EDGE_TYPES

    @classmethod
    def build_path_query(cls, max_depth: int = 5) -> str:
        """Build a BFS-style path query between two nodes."""
        max_depth = max(1, min(max_depth, 10))

        return f"""
WITH RECURSIVE path_finder AS (
    SELECT
        $1::TEXT AS node_id,
        ARRAY[$1::TEXT] AS path,
        0 AS depth

    UNION ALL

    SELECT
        CASE
            WHEN e.target_id = pf.node_id THEN e.source_id
            ELSE e.target_id
        END AS node_id,
        pf.path || CASE
            WHEN e.target_id = pf.node_id THEN e.source_id
            ELSE e.target_id
        END,
        pf.depth + 1

    FROM path_finder pf
    JOIN graph_edges e ON (e.source_id = pf.node_id OR e.target_id = pf.node_id)
    WHERE pf.depth < {max_depth}
      AND NOT (
          CASE
              WHEN e.target_id = pf.node_id THEN e.source_id
              ELSE e.target_id
          END = ANY(pf.path)
      )
)

SELECT node_id, path, depth
FROM path_finder
WHERE node_id = $2
ORDER BY depth ASC
LIMIT 1;
"""

    @classmethod
    def build_multi_vendor_query(cls, vendor_count: int, depth: int = 2) -> str:
        """Build a query for multiple vendor traversal."""
        depth = max(1, min(depth, 10))
        placeholders = ",".join(f"${i+1}" for i in range(vendor_count))

        return f"""
WITH RECURSIVE multi_vendor_network AS (
    SELECT
        v.vendor_id AS node_id,
        'vendor' AS node_type,
        v.name AS node_label,
        v.token AS vendor_token,
        NULL::TEXT AS parent_id,
        0 AS depth
    FROM vendors v
    WHERE v.token IN ({placeholders})

    UNION ALL

    SELECT
        t.transaction_id::TEXT,
        'transaction',
        t.invoice_number,
        g.vendor_token,
        g.node_id,
        g.depth + 1
    FROM multi_vendor_network g
    JOIN transactions t ON t.vendor_token = g.vendor_token
    WHERE g.depth < {depth}

    UNION ALL

    SELECT
        d.department_id,
        'department',
        d.name,
        g.vendor_token,
        g.node_id,
        g.depth + 1
    FROM multi_vendor_network g
    JOIN transactions t ON t.vendor_token = g.vendor_token
    JOIN departments d ON d.department_id = t.department_id
    WHERE g.depth < {depth}
)

SELECT
    json_agg(
        jsonb_build_object(
            'id', node_id,
            'type', node_type,
            'label', node_label,
            'properties', jsonb_build_object(
                'vendor_token', vendor_token,
                'depth', depth
            )
        )
    ) AS nodes
FROM multi_vendor_network;
"""
