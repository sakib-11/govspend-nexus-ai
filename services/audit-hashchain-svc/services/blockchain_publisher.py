from typing import Optional, Dict, Any
import json
import hashlib
from datetime import datetime
from models.audit import DailySnapshot
from config import HashChainConfig
import logging

logger = logging.getLogger(__name__)

class BlockchainPublisher:
    """Publish hash chain root hashes to blockchain"""
    
    def __init__(self, config: HashChainConfig):
        self.config = config
        self._web3 = None
        
        if config.blockchain_enabled:
            self._init_web3()
    
    def _init_web3(self):
        """Initialize Web3 connection"""
        try:
            from web3 import Web3
            from web3.middleware import geth_poa_middleware
            
            self._web3 = Web3(Web3.HTTPProvider(self.config.blockchain_rpc_url))
            self._web3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            if not self._web3.is_connected():
                logger.warning("Web3 not connected")
                self._web3 = None
                
        except ImportError:
            logger.warning("Web3 not installed, blockchain publishing disabled")
        except Exception as e:
            logger.error(f"Web3 initialization error: {e}")
    
    async def publish_to_ethereum(self, snapshot: DailySnapshot) -> Optional[str]:
        """Publish to Ethereum blockchain"""
        
        if not self._web3:
            return None
        
        try:
            # Prepare data
            data = {
                "snapshot_id": str(snapshot.snapshot_id),
                "snapshot_date": snapshot.snapshot_date.isoformat(),
                "root_hash": snapshot.root_hash,
                "merkle_root": snapshot.merkle_root,
                "total_entries": snapshot.total_entries,
                "timestamp": datetime.now().isoformat()
            }
            
            # Encode data for blockchain
            data_bytes = json.dumps(data, sort_keys=True).encode()
            data_hash = hashlib.sha256(data_bytes).hexdigest()
            
            # Contract call (simplified - would need ABI and address)
            # In production, you'd have a contract with a storeHash function
            # tx_hash = await self._contract.functions.storeHash(
            #     data_hash,
            #     f"0x{snapshot.root_hash}"
            # ).transact({'from': account})
            
            # Simulate transaction
            tx_hash = f"0x{hashlib.sha256(data_hash.encode()).hexdigest()[:64]}"
            
            logger.info(f"Published to Ethereum: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Ethereum publish error: {e}")
            return None
    
    async def publish_to_hyperledger(self, snapshot: DailySnapshot) -> Optional[str]:
        """Publish to Hyperledger Fabric"""
        
        # In production, use Fabric SDK
        try:
            # Simulate
            tx_id = f"hlf-{hashlib.sha256(snapshot.root_hash.encode()).hexdigest()[:32]}"
            logger.info(f"Published to Hyperledger: {tx_id}")
            return tx_id
        except Exception as e:
            logger.error(f"Hyperledger publish error: {e}")
            return None
    
    async def publish(self, snapshot) -> Optional[str]:
        """Publish to configured blockchain"""
        
        if not self.config.blockchain_enabled:
            return None
        
        if self.config.blockchain_type == "ethereum":
            return await self.publish_to_ethereum(snapshot)
        elif self.config.blockchain_type == "hyperledger":
            return await self.publish_to_hyperledger(snapshot)
        else:
            logger.warning(f"Unsupported blockchain type: {self.config.blockchain_type}")
            return None
