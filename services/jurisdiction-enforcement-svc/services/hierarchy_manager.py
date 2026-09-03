from typing import List, Optional, Dict, Set, Tuple
from collections import defaultdict
import networkx as nx
from models.jurisdiction import Jurisdiction, JurisdictionLevel

class HierarchyManager:
    """Manage jurisdiction hierarchy with graph support"""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self._graph = nx.DiGraph()
        self._hierarchy_cache = {}
        self._initialize_hierarchy()
    
    def _initialize_hierarchy(self):
        """Initialize jurisdiction hierarchy"""
        # This would load from database in production
        # For now, we'll use a default hierarchy
        
        # Create sample hierarchy
        jurisdictions = self._get_sample_jurisdictions()
        
        for jur in jurisdictions:
            self._graph.add_node(jur.jurisdiction_id, data=jur)
            if jur.parent_id and jur.parent_id in [j.jurisdiction_id for j in jurisdictions]:
                self._graph.add_edge(jur.parent_id, jur.jurisdiction_id)
        
        self._update_ancestors_descendants()
    
    def _get_sample_jurisdictions(self) -> List[Jurisdiction]:
        """Get sample jurisdictions for testing"""
        
        return [
            Jurisdiction(
                jurisdiction_id="jur-001",
                code="US",
                name="United States",
                level=JurisdictionLevel.FEDERAL,
                depth=0,
                jurisdiction_type=JurisdictionType.GEOGRAPHIC
            ),
            Jurisdiction(
                jurisdiction_id="jur-002",
                code="US-CA",
                name="California",
                level=JurisdictionLevel.STATE,
                parent_id="jur-001",
                depth=1,
                jurisdiction_type=JurisdictionType.GEOGRAPHIC
            ),
            Jurisdiction(
                jurisdiction_id="jur-003",
                code="US-CA-SF",
                name="San Francisco",
                level=JurisdictionLevel.CITY,
                parent_id="jur-002",
                depth=2,
                jurisdiction_type=JurisdictionType.GEOGRAPHIC
            ),
            Jurisdiction(
                jurisdiction_id="jur-004",
                code="US-NY",
                name="New York",
                level=JurisdictionLevel.STATE,
                parent_id="jur-001",
                depth=1,
                jurisdiction_type=JurisdictionType.GEOGRAPHIC
            ),
            Jurisdiction(
                jurisdiction_id="jur-005",
                code="US-CA-LA",
                name="Los Angeles",
                level=JurisdictionLevel.CITY,
                parent_id="jur-002",
                depth=2,
                jurisdiction_type=JurisdictionType.GEOGRAPHIC
            ),
            Jurisdiction(
                jurisdiction_id="jur-006",
                code="FED-AUDIT",
                name="Federal Audit",
                level=JurisdictionLevel.AGENCY,
                parent_id="jur-001",
                depth=1,
                jurisdiction_type=JurisdictionType.ORGANIZATIONAL
            ),
            Jurisdiction(
                jurisdiction_id="jur-007",
                code="CA-AUDIT",
                name="California Audit",
                level=JurisdictionLevel.AGENCY,
                parent_id="jur-002",
                depth=2,
                jurisdiction_type=JurisdictionType.ORGANIZATIONAL
            ),
        ]
    
    def _update_ancestors_descendants(self):
        """Update ancestor and descendant relationships"""
        
        for node_id in self._graph.nodes():
            # Get ancestors (path to root)
            ancestors = []
            current = node_id
            while True:
                parents = list(self._graph.predecessors(current))
                if not parents:
                    break
                parent = parents[0]
                ancestors.append(parent)
                current = parent
            
            # Get descendants
            descendants = list(nx.descendants(self._graph, node_id))
            
            # Update node data
            self._graph.nodes[node_id]['data'].ancestors = ancestors
            self._graph.nodes[node_id]['data'].descendants = descendants
    
    def get_ancestors(self, jurisdiction_id: str) -> List[str]:
        """Get all ancestors of a jurisdiction"""
        
        if jurisdiction_id not in self._graph:
            return []
        
        node_data = self._graph.nodes[jurisdiction_id]['data']
        return node_data.ancestors
    
    def get_descendants(self, jurisdiction_id: str) -> List[str]:
        """Get all descendants of a jurisdiction"""
        
        if jurisdiction_id not in self._graph:
            return []
        
        node_data = self._graph.nodes[jurisdiction_id]['data']
        return node_data.descendants
    
    def get_parent(self, jurisdiction_id: str) -> Optional[str]:
        """Get parent of a jurisdiction"""
        
        if jurisdiction_id not in self._graph:
            return None
        
        parents = list(self._graph.predecessors(jurisdiction_id))
        return parents[0] if parents else None
    
    def get_children(self, jurisdiction_id: str) -> List[str]:
        """Get children of a jurisdiction"""
        
        if jurisdiction_id not in self._graph:
            return []
        
        return list(self._graph.successors(jurisdiction_id))
    
    def get_root(self, jurisdiction_id: str) -> Optional[str]:
        """Get root ancestor of a jurisdiction"""
        
        ancestors = self.get_ancestors(jurisdiction_id)
        return ancestors[-1] if ancestors else jurisdiction_id
    
    def get_level(self, jurisdiction_id: str) -> int:
        """Get depth level of a jurisdiction"""
        
        if jurisdiction_id not in self._graph:
            return -1
        
        return self._graph.nodes[jurisdiction_id]['data'].depth
    
    def is_ancestor(self, ancestor_id: str, descendant_id: str) -> bool:
        """Check if one jurisdiction is an ancestor of another"""
        
        if ancestor_id not in self._graph or descendant_id not in self._graph:
            return False
        
        return ancestor_id in self.get_ancestors(descendant_id)
    
    def is_descendant(self, descendant_id: str, ancestor_id: str) -> bool:
        """Check if one jurisdiction is a descendant of another"""
        
        return self.is_ancestor(ancestor_id, descendant_id)
    
    def get_common_ancestors(self, jurisdiction_ids: List[str]) -> List[str]:
        """Find common ancestors for multiple jurisdictions"""
        
        if not jurisdiction_ids:
            return []
        
        ancestor_sets = [set(self.get_ancestors(jid) + [jid]) for jid in jurisdiction_ids]
        common = set.intersection(*ancestor_sets)
        return list(common)
    
    def get_lowest_common_ancestor(self, jurisdiction_ids: List[str]) -> Optional[str]:
        """Find the lowest common ancestor of multiple jurisdictions"""
        
        common_ancestors = self.get_common_ancestors(jurisdiction_ids)
        if not common_ancestors:
            return None
        
        # Find the one with maximum depth (lowest level)
        depths = {jid: self.get_level(jid) for jid in common_ancestors}
        return max(depths, key=depths.get)
    
    def is_jurisdiction_in_hierarchy(self, jurisdiction_id: str) -> bool:
        """Check if jurisdiction exists in hierarchy"""
        return jurisdiction_id in self._graph
    
    def get_path(self, from_id: str, to_id: str) -> List[str]:
        """Get path between two jurisdictions"""
        
        try:
            path = nx.shortest_path(self._graph, from_id, to_id)
            return path
        except nx.NetworkXNoPath:
            return []
    
    def get_subtree(self, root_id: str) -> List[str]:
        """Get all jurisdictions under a root"""
        
        if root_id not in self._graph:
            return []
        
        return [root_id] + self.get_descendants(root_id)
    
    def get_hierarchy_levels(self) -> Dict[int, List[str]]:
        """Get jurisdictions grouped by level"""
        
        levels = defaultdict(list)
        for node_id in self._graph.nodes():
            level = self.get_level(node_id)
            levels[level].append(node_id)
        
        return dict(levels)
    
    async def reload_from_database(self):
        """Reload hierarchy from database"""
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM jurisdictions WHERE is_active = TRUE
            """)
            
            # Clear existing graph
            self._graph.clear()
            
            # Rebuild
            for row in rows:
                jurisdiction = Jurisdiction(
                    jurisdiction_id=row['jurisdiction_id'],
                    code=row['code'],
                    name=row['name'],
                    level=JurisdictionLevel(row['level']),
                    parent_id=row['parent_id'],
                    depth=row['depth'],
                    jurisdiction_type=JurisdictionType(row['jurisdiction_type'])
                )
                self._graph.add_node(jurisdiction.jurisdiction_id, data=jurisdiction)
            
            # Add edges
            for node_id in self._graph.nodes():
                data = self._graph.nodes[node_id]['data']
                if data.parent_id and data.parent_id in self._graph:
                    self._graph.add_edge(data.parent_id, node_id)
            
            self._update_ancestors_descendants()