"""Graph builder service for constructing vendor relationship graphs."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import asyncpg
from ..config import settings
from ..models.vendor_graph import (
    VendorGraph, GraphNode, GraphEdge, NodeType, EdgeType
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class GraphBuilder:
    """Build vendor relationship graph from transaction data."""

    def __init__(self):
        self.db_pool = None

    async def _get_db_pool(self):
        """Get or create database connection pool."""
        if not self.db_pool:
            self.db_pool = await asyncpg.create_pool(
                settings.DATABASE_URL,
                min_size=5,
                max_size=20
            )
        return self.db_pool

    async def build_graph(
        self,
        department_id: Optional[str] = None,
        lookback_days: int = 365,
        include_officials: bool = True
    ) -> VendorGraph:
        """
        Build vendor relationship graph for a department.
        """
        logger.info(f"Building graph for department {department_id} over {lookback_days} days")

        pool = await self._get_db_pool()

        async with pool.acquire() as conn:
            # Get department transactions
            transactions = await self._fetch_transactions(
                conn,
                department_id,
                lookback_days
            )

            # Get vendors
            vendors = await self._fetch_vendors(conn, transactions)

            # Get officials (approvers, managers)
            officials = await self._fetch_officials(
                conn,
                transactions,
                include_officials
            )

            # Build nodes
            nodes = await self._build_nodes(conn, vendors, officials, transactions)

            # Build edges
            edges = await self._build_edges(
                conn,
                transactions,
                vendors,
                officials
            )

            # Create graph
            graph = VendorGraph(nodes=nodes, edges=edges)
            graph.update_statistics()

            logger.info(
                f"Graph built: {graph.node_count} nodes, {graph.edge_count} edges"
            )

            return graph

    async def _fetch_transactions(
        self,
        conn,
        department_id: Optional[str],
        lookback_days: int
    ) -> List[Dict[str, Any]]:
        """Fetch transactions for graph building."""
        cutoff_date = datetime.utcnow().date() - timedelta(days=lookback_days)

        query = """
            SELECT
                t.*,
                v.name as vendor_name,
                v.vendor_id,
                d.name as department_name,
                o.name as official_name,
                o.official_id
            FROM transactions t
            LEFT JOIN vendors v ON t.vendor_id = v.id
            LEFT JOIN departments d ON t.department_id = d.id
            LEFT JOIN officials o ON t.approved_by = o.id
            WHERE
                t.transaction_date >= $1
                AND t.status = 'completed'
                AND t.amount > 0
        """

        params = [cutoff_date]

        if department_id:
            query += " AND t.department_id = $2"
            params.append(department_id)

        rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows]

    async def _fetch_vendors(
        self,
        conn,
        transactions: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch vendor details."""
        vendor_ids = list(set(t.get('vendor_id') for t in transactions if t.get('vendor_id')))

        if not vendor_ids:
            return {}

        query = """
            SELECT * FROM vendors
            WHERE id = ANY($1::text[])
        """

        rows = await conn.fetch(query, vendor_ids)

        return {row['id']: dict(row) for row in rows}

    async def _fetch_officials(
        self,
        conn,
        transactions: List[Dict[str, Any]],
        include_officials: bool
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch officials (approvers, managers)."""
        if not include_officials:
            return {}

        official_ids = list(set(
            t.get('approved_by')
            for t in transactions
            if t.get('approved_by')
        ))

        if not official_ids:
            return {}

        query = """
            SELECT * FROM officials
            WHERE id = ANY($1::text[])
        """

        rows = await conn.fetch(query, official_ids)

        return {row['id']: dict(row) for row in rows}

    async def _build_nodes(
        self,
        conn,
        vendors: Dict[str, Dict[str, Any]],
        officials: Dict[str, Dict[str, Any]],
        transactions: List[Dict[str, Any]]
    ) -> List[GraphNode]:
        """Build graph nodes."""
        nodes = []

        # Vendor nodes
        vendor_spend = defaultdict(float)
        vendor_transactions = defaultdict(int)

        for tx in transactions:
            vendor_id = tx.get('vendor_id')
            if vendor_id:
                vendor_transactions[vendor_id] += 1
                vendor_spend[vendor_id] += float(tx.get('amount', 0))

        for vendor_id, vendor_data in vendors.items():
            node = GraphNode(
                id=vendor_id,
                node_type=NodeType.VENDOR,
                name=vendor_data.get('name', 'Unknown Vendor'),
                vendor_id=vendor_id,
                total_spend=vendor_spend.get(vendor_id, 0),
                transaction_count=vendor_transactions.get(vendor_id, 0),
                metadata={
                    'tax_id': vendor_data.get('tax_id'),
                    'registration': vendor_data.get('registration_number'),
                    'category': vendor_data.get('category')
                }
            )
            nodes.append(node)

        # Department nodes
        departments = {}
        for tx in transactions:
            dept_id = tx.get('department_id')
            dept_name = tx.get('department_name', 'Unknown Department')
            if dept_id and dept_id not in departments:
                departments[dept_id] = dept_name

        for dept_id, dept_name in departments.items():
            node = GraphNode(
                id=dept_id,
                node_type=NodeType.DEPARTMENT,
                name=dept_name,
                department_id=dept_id,
                metadata={
                    'transaction_count': sum(
                        1 for tx in transactions
                        if tx.get('department_id') == dept_id
                    )
                }
            )
            nodes.append(node)

        # Official nodes
        for official_id, official_data in officials.items():
            node = GraphNode(
                id=official_id,
                node_type=NodeType.OFFICIAL,
                name=official_data.get('name', 'Unknown Official'),
                official_id=official_id,
                metadata={
                    'role': official_data.get('role'),
                    'department_id': official_data.get('department_id'),
                    'approval_count': sum(
                        1 for tx in transactions
                        if tx.get('approved_by') == official_id
                    )
                }
            )
            nodes.append(node)

        return nodes

    async def _build_edges(
        self,
        conn,
        transactions: List[Dict[str, Any]],
        vendors: Dict[str, Dict[str, Any]],
        officials: Dict[str, Dict[str, Any]]
    ) -> List[GraphEdge]:
        """Build graph edges."""
        edges = []

        # Vendor -> Department edges (supplies_to)
        vendor_dept_relationships = set()
        for tx in transactions:
            vendor_id = tx.get('vendor_id')
            dept_id = tx.get('department_id')

            if vendor_id and dept_id:
                edge_key = (vendor_id, dept_id, EdgeType.SUPPLIES_TO)
                if edge_key not in vendor_dept_relationships:
                    vendor_dept_relationships.add(edge_key)

                    # Calculate total spend for this relationship
                    total_spend = sum(
                        float(tx2.get('amount', 0))
                        for tx2 in transactions
                        if tx2.get('vendor_id') == vendor_id
                        and tx2.get('department_id') == dept_id
                    )

                    edge = GraphEdge(
                        source_id=vendor_id,
                        target_id=dept_id,
                        edge_type=EdgeType.SUPPLIES_TO,
                        weight=min(1.0, total_spend / 1000000),  # Normalize by 1M
                        metadata={
                            'transaction_count': sum(
                                1 for tx2 in transactions
                                if tx2.get('vendor_id') == vendor_id
                                and tx2.get('department_id') == dept_id
                            ),
                            'total_spend': total_spend
                        }
                    )
                    edges.append(edge)

        # Official -> Department edges (manages)
        official_dept_relationships = set()
        for tx in transactions:
            official_id = tx.get('approved_by')
            dept_id = tx.get('department_id')

            if official_id and dept_id:
                edge_key = (official_id, dept_id, EdgeType.MANAGES)
                if edge_key not in official_dept_relationships:
                    official_dept_relationships.add(edge_key)

                    edge = GraphEdge(
                        source_id=official_id,
                        target_id=dept_id,
                        edge_type=EdgeType.MANAGES,
                        metadata={
                            'approval_count': sum(
                                1 for tx2 in transactions
                                if tx2.get('approved_by') == official_id
                                and tx2.get('department_id') == dept_id
                            )
                        }
                    )
                    edges.append(edge)

        # Official -> Vendor edges (approves)
        official_vendor_relationships = defaultdict(lambda: {'count': 0, 'total_value': 0})
        for tx in transactions:
            official_id = tx.get('approved_by')
            vendor_id = tx.get('vendor_id')

            if official_id and vendor_id:
                key = (official_id, vendor_id)
                official_vendor_relationships[key]['count'] += 1
                official_vendor_relationships[key]['total_value'] += float(tx.get('amount', 0))

        for (official_id, vendor_id), data in official_vendor_relationships.items():
            edge = GraphEdge(
                source_id=official_id,
                target_id=vendor_id,
                edge_type=EdgeType.APPROVES,
                weight=min(1.0, data['count'] / 10),  # Normalize by 10 approvals
                metadata={
                    'approval_count': data['count'],
                    'total_value': data['total_value']
                }
            )
            edges.append(edge)

        # Vendor -> Vendor edges (shares_official)
        # Connect vendors that share officials
        official_vendors = defaultdict(set)
        for tx in transactions:
            official_id = tx.get('approved_by')
            vendor_id = tx.get('vendor_id')
            if official_id and vendor_id:
                official_vendors[official_id].add(vendor_id)

        # Add edges between vendors sharing the same official
        for official_id, vendor_set in official_vendors.items():
            vendor_list = list(vendor_set)
            for i in range(len(vendor_list)):
                for j in range(i + 1, len(vendor_list)):
                    edge = GraphEdge(
                        source_id=vendor_list[i],
                        target_id=vendor_list[j],
                        edge_type=EdgeType.SHARES_OFFICIAL,
                        metadata={
                            'official_id': official_id,
                            'official_name': officials.get(official_id, {}).get('name', 'Unknown')
                        }
                    )
                    edges.append(edge)

        return edges