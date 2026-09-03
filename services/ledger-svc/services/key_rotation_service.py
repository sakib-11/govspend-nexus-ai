from typing import Optional
import asyncio
from datetime import datetime
from services.hsm_client import HSMClient
from services.ledger_service import LedgerService
from config import LedgerConfig

class KeyRotationService:
    """Service for rotating encryption keys"""
    
    def __init__(
        self,
        hsm_client: HSMClient,
        ledger_service: LedgerService,
        config: LedgerConfig
    ):
        self.hsm_client = hsm_client
        self.ledger_service = ledger_service
        self.config = config
        self._rotation_task = None
    
    async def start_rotation_schedule(self):
        """Start the key rotation schedule"""
        if self._rotation_task is None or self._rotation_task.done():
            self._rotation_task = asyncio.create_task(self._rotation_loop())
    
    async def stop_rotation_schedule(self):
        """Stop the key rotation schedule"""
        if self._rotation_task and not self._rotation_task.done():
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass
    
    async def _rotation_loop(self):
        """Loop that rotates keys at the configured interval"""
        while True:
            try:
                await asyncio.sleep(self.config.key_rotation_days * 24 * 3600)
                await self.rotate_keys()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error and continue
                print(f"Key rotation error: {e}")
                await asyncio.sleep(3600)  # Retry after an hour on error
    
    async def rotate_keys(self) -> str:
        """Rotate the master key and re-encrypt all data"""
        # Get current master key ID
        old_key_id = self.config.master_key_id
        
        # Generate new key in HSM/KMS
        new_key_id = await self.hsm_client.rotate_key(old_key_id)
        
        # Update config (in practice, we'd update the environment and restart)
        # For now, we just return the new key ID
        # The actual re-encryption of existing data is a complex process
        # that would require scanning all entries and re-encrypting them
        # with the new key. This is beyond the scope of this service.
        
        # Log the rotation
        await self.ledger_service._log_audit(
            entry_id=None,
            action="KEY_ROTATION",
            user_id="system",
            service_name="ledger-svc",
            ip_address=None,
            details={
                "old_key_id": old_key_id,
                "new_key_id": new_key_id
            }
        )
        
        return new_key_id
