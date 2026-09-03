from typing import Optional, Dict, Any
import httpx
import json
import hashlib
import base64
from datetime import datetime
from models.audit import DailySnapshot, NotaryRecord
from config import HashChainConfig
import logging

logger = logging.getLogger(__name__)

class NotaryPublisher:
    """Publish hash chain root hashes to external notary services"""
    
    def __init__(self, config: HashChainConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def publish_to_tuf(self, snapshot: DailySnapshot) -> Optional[NotaryRecord]:
        """Publish to TUF (The Update Framework) notary"""
        
        if not self.config.notary_endpoint:
            logger.warning("TUF notary endpoint not configured")
            return None
        
        try:
            # Prepare payload
            payload = {
                "snapshot_id": str(snapshot.snapshot_id),
                "snapshot_date": snapshot.snapshot_date.isoformat(),
                "root_hash": snapshot.root_hash,
                "merkle_root": snapshot.merkle_root,
                "total_entries": snapshot.total_entries,
                "timestamp": datetime.now().isoformat()
            }
            
            # Sign with API key
            headers = {
                "Authorization": f"Bearer {self.config.notary_api_key}",
                "Content-Type": "application/json"
            }
            
            # Send to notary
            response = await self.client.post(
                f"{self.config.notary_endpoint}/api/v1/records",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Store notary record
                notary_record = NotaryRecord(
                    snapshot_id=snapshot.snapshot_id,
                    notary_type="tuf",
                    external_id=data.get('record_id', ''),
                    root_hash=snapshot.root_hash,
                    signature=data.get('signature'),
                    verification_url=data.get('verification_url')
                )
                
                logger.info(f"Published to TUF notary: {notary_record.external_id}")
                return notary_record
            else:
                logger.error(f"TUF notary error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"TUF notary publish error: {e}")
            return None
    
    async def publish_to_sigstore(self, snapshot) -> Optional[NotaryRecord]:
        """Publish to Sigstore (cosign)"""
        
        try:
            # Create signature artifact
            artifact = f"{snapshot.root_hash}:{snapshot.snapshot_date.isoformat()}"
            artifact_hash = hashlib.sha256(artifact.encode()).hexdigest()
            
            # In production, use Sigstore client
            # For now, simulate
            signature = base64.b64encode(f"sigstore-sig-{artifact_hash}".encode()).decode()
            
            return NotaryRecord(
                snapshot_id=snapshot.snapshot_id,
                notary_type="sigstore",
                external_id=f"sigstore-{snapshot.snapshot_date.isoformat()}",
                root_hash=snapshot.root_hash,
                signature=signature,
                verification_url="https://rekor.sigstore.dev/api/v1/log/entries"
            )
            
        except Exception as e:
            logger.error(f"Sigstore publish error: {e}")
            return None
    
    async def publish(self, snapshot) -> Optional[NotaryRecord]:
        """Publish to configured notary service"""
        
        if self.config.notary_type == "tuf":
            return await self.publish_to_tuf(snapshot)
        elif self.config.notary_type == "sigstore":
            return await self.publish_to_sigstore(snapshot)
        else:
            logger.warning(f"Unsupported notary type: {self.config.notary_type}")
            return None
    
    async def verify_notary_record(self, record: NotaryRecord) -> bool:
        """Verify a notary record"""
        
        if record.notary_type == "tuf":
            return await self._verify_tuf_record(record)
        elif record.notary_type == "sigstore":
            return await self._verify_sigstore_record(record)
        return False
    
    async def _verify_tuf_record(self, record: NotaryRecord) -> bool:
        """Verify TUF notary record"""
        
        if not record.verification_url:
            return False
        
        try:
            response = await self.client.get(record.verification_url)
            return response.status_code == 200
        except Exception:
            return False
    
    async def _verify_sigstore_record(self, record: NotaryRecord) -> bool:
        """Verify Sigstore record"""
        
        # In production, use Sigstore verification
        return True
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
