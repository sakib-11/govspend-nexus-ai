from typing import List, Optional, Any
import hashlib
import json
from models.audit import HashChainEntry, MerkleTree

class MerkleTreeBuilder:
    """Build and verify Merkle trees for hash chain snapshots"""
    
    def __init__(self, hash_algorithm: str = "sha256"):
        self.hash_algorithm = hash_algorithm
        self._hash_func = getattr(hashlib, hash_algorithm)
    
    def build_tree(self, entries: List[HashChainEntry]) -> MerkleTree:
        """Build a Merkle tree from hash chain entries"""
        
        if not entries:
            return MerkleTree(
                root_hash="",
                leaf_hashes=[],
                tree_levels=[],
                total_leaves=0
            )
        
        # Create leaf hashes
        leaf_hashes = []
        for entry in entries:
            leaf_data = f"{entry.sequence_number}:{entry.current_hash}"
            leaf_hash = self._hash_func(leaf_data.encode()).hexdigest()
            leaf_hashes.append(leaf_hash)
        
        # Build tree levels
        tree_levels = [leaf_hashes]
        current_level = leaf_hashes.copy()
        
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    combined = f"{current_level[i]}{current_level[i + 1]}"
                else:
                    combined = current_level[i]
                
                node_hash = self._hash_func(combined.encode()).hexdigest()
                next_level.append(node_hash)
            
            tree_levels.append(next_level)
            current_level = next_level
        
        root_hash = current_level[0] if current_level else ""
        
        return MerkleTree(
            root_hash=root_hash,
            leaf_hashes=leaf_hashes,
            tree_levels=tree_levels,
            total_leaves=len(leaf_hashes)
        )
    
    def verify_proof(
        self,
        entry: HashChainEntry,
        leaf_hash: str,
        merkle_path: List[str],
        root_hash: str
    ) -> bool:
        """Verify a Merkle proof for an entry"""
        
        current_hash = leaf_hash
        
        for sibling_hash in merkle_path:
            # Determine if we should concatenate left or right
            # This depends on the position in the tree
            combined = f"{current_hash}{sibling_hash}"
            current_hash = self._hash_func(combined.encode()).hexdigest()
        
        return current_hash == root_hash
    
    def reconstruct_tree(self, node_rows: List[Any]) -> MerkleTree:
        """Reconstruct a Merkle tree from stored nodes"""
        
        if not node_rows:
            return MerkleTree(
                root_hash="",
                leaf_hashes=[],
                tree_levels=[],
                total_leaves=0
            )
        
        # Group by level
        levels = {}
        for row in node_rows:
            level = row['node_level']
            if level not in levels:
                levels[level] = []
            levels[level].append(row['node_hash'])
        
        # Sort levels
        tree_levels = []
        for level in sorted(levels.keys()):
            tree_levels.append(levels[level])
        
        # Find root hash
        root_hash = tree_levels[-1][0] if tree_levels and tree_levels[-1] else ""
        
        # Find leaf hashes
        leaf_hashes = tree_levels[0] if tree_levels else []
        
        return MerkleTree(
            root_hash=root_hash,
            leaf_hashes=leaf_hashes,
            tree_levels=tree_levels,
            total_leaves=len(leaf_hashes)
        )
    
    def get_merkle_path(
        self,
        tree_levels: List[List[str]],
        leaf_index: int
    ) -> List[str]:
        """Get the Merkle path for a leaf at the given index"""
        
        if leaf_index >= len(tree_levels[0]):
            return []
        
        path = []
        current_index = leaf_index
        current_level = 0
        
        while current_level < len(tree_levels) - 1:
            # Get the sibling
            if current_index % 2 == 0:
                # Left child - sibling is right
                if current_index + 1 < len(tree_levels[current_level]):
                    sibling_hash = tree_levels[current_level][current_index + 1]
                else:
                    sibling_hash = ""
            else:
                # Right child - sibling is left
                sibling_hash = tree_levels[current_level][current_index - 1]
            
            if sibling_hash:
                path.append(sibling_hash)
            
            # Move to next level
            current_index = current_index // 2
            current_level += 1
        
        return path
