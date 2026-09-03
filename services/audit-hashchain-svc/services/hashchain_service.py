from typing import Optional, List, Dict, Any, Tuple
import asyncpg
import json
import hashlib
import hmac
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from models.audit import HashChainEntry, DailySnapshot, VerificationResult
from utils.merkle_utils import MerkleTreeBuilder
from config import HashChainConfig
import logging

logger = logging.getLogger(__name__)

class HashChainService:
    """Core hash chain service with tamper-evident logging"""
    
    def __init__(self, db_pool: asyncpg.Pool, config: HashChainConfig):
        self.db_pool = db_pool
        self.config = config
        self._cache = {}
        self._sequence_cache = None
    
    async def append_entry(
        self,
        audit_id: UUID,
        actor: str,
        action: str,
        resource: str,
        payload_hash: str,
        resource_token: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> HashChainEntry:
        """Append a new hash chain entry"""
        
        if not timestamp:
            timestamp = datetime.now()
        
        # Calculate hash chain entry using database function
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT * FROM calculate_hash_chain_entry(
                    $1, $2, $3, $4, $5, $6
                )
            """, audit_id, actor, action, resource, payload_hash, timestamp)
            
            sequence_number = result['sequence_number']
            previous_hash = result['previous_hash']
            current_hash = result['current_hash']
            
            # Insert entry
            entry_id = uuid4()
            await conn.execute("""
                INSERT INTO hash_chain_entries (
                    entry_id, audit_id, sequence_number, previous_hash,
                    current_hash, payload_hash, actor, action, resource,
                    resource_token, timestamp
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
                )
            """,
                str(entry_id),
                str(audit_id),
                sequence_number,
                previous_hash,
                current_hash,
                payload_hash,
                actor,
                action,
                resource,
                resource_token,
                timestamp
            )
            
            # Update cache
            self._sequence_cache = sequence_number
            
            # Build entry
            entry = HashChainEntry(
                entry_id=entry_id,
                audit_id=audit_id,
                sequence_number=sequence_number,
                previous_hash=previous_hash,
                current_hash=current_hash,
                payload_hash=payload_hash,
                actor=actor,
                action=action,
                resource=resource,
                resource_token=resource_token,
                timestamp=timestamp
            )
            
            logger.info(f"Hash chain entry created: {entry_id} (seq: {sequence_number})")
            return entry
    
    async def get_entry(self, entry_id: UUID) -> Optional[HashChainEntry]:
        """Get hash chain entry by ID"""
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM hash_chain_entries
                WHERE entry_id = $1
            """, str(entry_id))
            
            if not row:
                return None
            
            return self._row_to_entry(row)
    
    async def get_entry_by_sequence(self, sequence: int) -> Optional[HashChainEntry]:
        """Get entry by sequence number"""
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM hash_chain_entries
                WHERE sequence_number = $1
            """, sequence)
            
            if not row:
                return None
            
            return self._row_to_entry(row)
    
    async def get_latest_entry(self) -> Optional[HashChainEntry]:
        """Get the latest hash chain entry"""
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM hash_chain_entries
                ORDER BY sequence_number DESC
                LIMIT 1
            """)
            
            if not row:
                return None
            
            return self._row_to_entry(row)
    
    async def verify_chain(
        self,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None
    ) -> VerificationResult:
        """Verify the hash chain integrity"""
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM verify_hash_chain($1, $2)
            """, start_sequence, end_sequence)
            
            if not rows:
                return VerificationResult(
                    is_valid=True,
                    entries_checked=0
                )
            
            # Process verification results
            is_valid = True
            tampered_entries = []
            missing_entries = []
            validation_errors = []
            entries_checked = 0
            
            for row in rows:
                entries_checked += 1
                if not row['is_valid']:
                    is_valid = False
                    if row['entry_id']:
                        tampered_entries.append(row['entry_id'])
                    validation_errors.append(row['error_message'])
            
            return VerificationResult(
                is_valid=is_valid,
                entries_checked=entries_checked,
                tampered_entries=tampered_entries,
                missing_entries=missing_entries,
                validation_errors=validation_errors
            )
    
    async def create_snapshot(self, snapshot_date: date) -> DailySnapshot:
        """Create a daily snapshot with Merkle tree"""
        
        # Get entries for the day
        start_time = datetime.combine(snapshot_date, datetime.min.time())
        end_time = datetime.combine(snapshot_date, datetime.max.time())
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM hash_chain_entries
                WHERE timestamp BETWEEN $1 AND $2
                ORDER BY sequence_number ASC
            """, start_time, end_time)
            
            if not rows:
                logger.warning(f"No entries found for snapshot date {snapshot_date}")
                return None
            
            entries = [self._row_to_entry(row) for row in rows]
            
            # Build Merkle tree
            merkle_builder = MerkleTreeBuilder()
            merkle_tree = merkle_builder.build_tree(entries)
            
            # Calculate snapshot hash
            snapshot_data = {
                "snapshot_date": snapshot_date.isoformat(),
                "start_sequence": entries[0].sequence_number,
                "end_sequence": entries[-1].sequence_number,
                "merkle_root": merkle_tree.root_hash,
                "total_entries": len(entries)
            }
            snapshot_hash = hashlib.sha256(
                json.dumps(snapshot_data, sort_keys=True).encode()
            ).hexdigest()
            
            # Store snapshot
            snapshot_id = uuid4()
            await conn.execute("""
                INSERT INTO daily_snapshots (
                    snapshot_id, snapshot_date, start_sequence, end_sequence,
                    merkle_root, root_hash, total_entries, snapshot_hash,
                    created_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, NOW()
                )
            """,
                str(snapshot_id),
                snapshot_date,
                entries[0].sequence_number,
                entries[-1].sequence_number,
                merkle_tree.root_hash,
                merkle_tree.root_hash,
                len(entries),
                snapshot_hash
            )
            
            # Store Merkle tree nodes
            for level_idx, level in enumerate(merkle_tree.tree_levels):
                for node_idx, node_hash in enumerate(level):
                    is_leaf = level_idx == 0
                    await conn.execute("""
                        INSERT INTO merkle_tree_nodes (
                            snapshot_id, node_hash, node_level, node_index,
                            is_leaf
                        ) VALUES (
                            $1, $2, $3, $4, $5
                        )
                    """,
                        str(snapshot_id),
                        node_hash,
                        level_idx,
                        node_idx,
                        is_leaf
                    )
            
            snapshot = DailySnapshot(
                snapshot_id=snapshot_id,
                snapshot_date=snapshot_date,
                start_sequence=entries[0].sequence_number,
                end_sequence=entries[-1].sequence_number,
                merkle_root=merkle_tree.root_hash,
                root_hash=merkle_tree.root_hash,
                total_entries=len(entries),
                snapshot_hash=snapshot_hash,
                created_at=datetime.now()
            )
            
            logger.info(f"Snapshot created: {snapshot_id} for {snapshot_date}")
            return snapshot
    
    async def get_snapshot(self, snapshot_date: date) -> Optional[DailySnapshot]:
        """Get snapshot by date"""
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM daily_snapshots
                WHERE snapshot_date = $1
            """, snapshot_date)
            
            if not row:
                return None
            
            return self._row_to_snapshot(row)
    
    async def verify_snapshot(self, snapshot_id: UUID) -> VerificationResult:
        """Verify a snapshot's integrity"""
        
        async with self.db_pool.acquire() as conn:
            # Get snapshot
            snapshot_row = await conn.fetchrow("""
                SELECT * FROM daily_snapshots
                WHERE snapshot_id = $1
            """, str(snapshot_id))
            
            if not snapshot_row:
                return VerificationResult(
                    is_valid=False,
                    entries_checked=0,
                    validation_errors=["Snapshot not found"]
                )
            
            # Get Merkle tree nodes
            node_rows = await conn.fetch("""
                SELECT * FROM merkle_tree_nodes
                WHERE snapshot_id = $1
                ORDER BY node_level ASC, node_index ASC
            """, str(snapshot_id))
            
            # Reconstruct Merkle tree
            merkle_builder = MerkleTreeBuilder()
            reconstructed_tree = merkle_builder.reconstruct_tree(node_rows)
            
            # Verify root hash
            if reconstructed_tree.root_hash != snapshot_row['merkle_root']:
                return VerificationResult(
                    is_valid=False,
                    entries_checked=0,
                    validation_errors=["Merkle root mismatch"]
                )
            
            # Verify entries
            entries = await conn.fetch("""
                SELECT * FROM hash_chain_entries
                WHERE sequence_number BETWEEN $1 AND $2
            """, snapshot_row['start_sequence'], snapshot_row['end_sequence'])
            
            # Verify each entry's hash
            for entry in entries:
                entry_hash = hashlib.sha256(
                    f"{entry['previous_hash']}{entry['actor']}{entry['action']}{entry['resource']}{entry['payload_hash']}{entry['timestamp']}".encode()
                ).hexdigest()
                
                if entry_hash != entry['current_hash']:
                    return VerificationResult(
                        is_valid=False,
                        entries_checked=len(entries),
                        tampered_entries=[entry['entry_id']],
                        validation_errors=[f"Entry {entry['entry_id']} hash mismatch"]
                    )
            
            return VerificationResult(
                is_valid=True,
                entries_checked=len(entries)
            )
    
    def _row_to_entry(self, row) -> HashChainEntry:
        """Convert database row to HashChainEntry"""
        return HashChainEntry(
            entry_id=UUID(row['entry_id']),
            audit_id=UUID(row['audit_id']),
            sequence_number=row['sequence_number'],
            previous_hash=row['previous_hash'],
            current_hash=row['current_hash'],
            payload_hash=row['payload_hash'],
            actor=row['actor'],
            action=row['action'],
            resource=row['resource'],
            resource_token=row['resource_token'],
            timestamp=row['timestamp'],
            merkle_root=row.get('merkle_root'),
            merkle_path=row.get('merkle_path'),
            signature=row.get('signature'),
            verified=row.get('verified', False),
            verified_at=row.get('verified_at')
        )
    
    def _row_to_snapshot(self, row) -> DailySnapshot:
        """Convert database row to DailySnapshot"""
        return DailySnapshot(
            snapshot_id=UUID(row['snapshot_id']),
            snapshot_date=row['snapshot_date'],
            start_sequence=row['start_sequence'],
            end_sequence=row['end_sequence'],
            merkle_root=row['merkle_root'],
            root_hash=row['root_hash'],
            total_entries=row['total_entries'],
            snapshot_hash=row['snapshot_hash'],
            external_reference=row.get('external_reference'),
            blockchain_tx_hash=row.get('blockchain_tx_hash'),
            notary_signature=row.get('notary_signature'),
            notary_timestamp=row.get('notary_timestamp'),
            created_at=row['created_at'],
            verified=row.get('verified', False),
            verified_at=row.get('verified_at')
        )
