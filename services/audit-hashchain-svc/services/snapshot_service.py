from typing import Optional, Dict, Any
import asyncio
import logging
from datetime import datetime, timedelta, date
import asyncpg
from models.audit import DailySnapshot
from services.hashchain_service import HashChainService
from services.notary_publisher import NotaryPublisher
from services.blockchain_publisher import BlockchainPublisher
from config import HashChainConfig

logger = logging.getLogger(__name__)

class SnapshotService:
    """Service for creating and managing daily snapshots"""
    
    def __init__(
        self,
        hashchain_service: HashChainService,
        notary_publisher: NotaryPublisher,
        blockchain_publisher: BlockchainPublisher,
        config: HashChainConfig
    ):
        self.hashchain_service = hashchain_service
        self.notary_publisher = notary_publisher
        self.blockchain_publisher = blockchain_publisher
        self.config = config
        self._is_running = False
        self._last_snapshot_date = None
    
    async def start(self):
        """Start the snapshot service"""
        if self._is_running:
            return
        
        self._is_running = True
        asyncio.create_task(self._run_loop())
        logger.info("Snapshot service started")
    
    async def stop(self):
        """Stop the snapshot service"""
        self._is_running = False
        logger.info("Snapshot service stopped")
    
    async def _run_loop(self):
        """Main snapshot loop"""
        while self._is_running:
            try:
                await self._check_and_create_snapshot()
            except Exception as e:
                logger.error(f"Snapshot error: {e}")
            
            # Wait for next check
            await asyncio.sleep(3600)  # Check every hour
    
    async def _check_and_create_snapshot(self):
        """Check if snapshot needed and create one"""
        
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # Check if we already have a snapshot for yesterday
        existing = await self.hashchain_service.get_snapshot(yesterday)
        if existing:
            return
        
        # Create snapshot for yesterday
        logger.info(f"Creating snapshot for {yesterday}")
        snapshot = await self.hashchain_service.create_snapshot(yesterday)
        
        if snapshot:
            # Publish to notary
            notary_record = await self.notary_publisher.publish(snapshot)
            if notary_record:
                await self._update_snapshot_notary(snapshot.snapshot_id, notary_record)
            
            # Publish to blockchain
            tx_hash = await self.blockchain_publisher.publish(snapshot)
            if tx_hash:
                await self._update_snapshot_blockchain(snapshot.snapshot_id, tx_hash)
            
            logger.info(f"Snapshot created for {yesterday}: {snapshot.snapshot_id}")
    
    async def _update_snapshot_notary(self, snapshot_id, notary_record):
        """Update snapshot with notary record"""
        
        async with self.hashchain_service.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE daily_snapshots
                SET 
                    external_reference = $1,
                    notary_signature = $2,
                    notary_timestamp = NOW()
                WHERE snapshot_id = $3
            """,
                notary_record.external_id,
                notary_record.signature,
                str(snapshot_id)
            )
            
            # Store notary record
            await conn.execute("""
                INSERT INTO notary_records (
                    snapshot_id, notary_type, external_id,
                    root_hash, signature, verification_url
                ) VALUES (
                    $1, $2, $3, $4, $5, $6
                )
            """,
                str(snapshot_id),
                notary_record.notary_type,
                notary_record.external_id,
                notary_record.root_hash,
                notary_record.signature,
                notary_record.verification_url
            )
    
    async def _update_snapshot_blockchain(self, snapshot_id, tx_hash):
        """Update snapshot with blockchain transaction"""
        
        async with self.hashchain_service.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE daily_snapshots
                SET blockchain_tx_hash = $1
                WHERE snapshot_id = $2
            """, tx_hash, str(snapshot_id))
    
    async def force_create_snapshot(self, snapshot_date: date) -> Optional[DailySnapshot]:
        """Force create a snapshot for a specific date"""
        
        snapshot = await self.hashchain_service.create_snapshot(snapshot_date)
        if snapshot:
            # Publish to notary
            notary_record = await self.notary_publisher.publish(snapshot)
            if notary_record:
                await self._update_snapshot_notary(snapshot.snapshot_id, notary_record)
            
            # Publish to blockchain
            tx_hash = await self.blockchain_publisher.publish(snapshot)
            if tx_hash:
                await self._update_snapshot_blockchain(snapshot.snapshot_id, tx_hash)
        
        return snapshot
    
    async def get_snapshot_status(self) -> Dict[str, Any]:
        """Get snapshot service status"""
        
        latest_snapshot = await self.hashchain_service.get_snapshot(
            date.today() - timedelta(days=1)
        )
        
        return {
            "is_running": self._is_running,
            "latest_snapshot": latest_snapshot.model_dump() if latest_snapshot else None,
            "last_check": datetime.now().isoformat(),
            "config": {
                "snapshot_interval_hours": self.config.snapshot_interval_hours,
                "retention_days": self.config.snapshot_retention_days
            }
        }
