from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
from services.ledger_service import LedgerService

class AuditService:
    """Service for managing audit logs"""
    
    def __init__(self, ledger_service: LedgerService):
        self.ledger_service = ledger_service
    
    async def get_audit_logs(
        self,
        entry_id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get audit logs with filtering"""
        # For simplicity, we'll use the ledger service's method and filter in memory
        # In a production system, we'd add these filters to the database query.
        logs = await self.ledger_service.get_audit_logs(entry_id, limit=1000, offset=0)  # Get more to filter
        
        # Apply filters
        filtered_logs = []
        for log in logs:
            if start_time and log['timestamp'] < start_time:
                continue
            if end_time and log['timestamp'] > end_time:
                continue
            if user_id and log['user_id'] != user_id:
                continue
            if action and log['action'] != action:
                continue
            filtered_logs.append(log)
            if len(filtered_logs) >= limit + offset:
                break
        
        # Apply offset
        return filtered_logs[offset:offset+limit]
    
    async def get_audit_trail_for_entry(self, entry_id: UUID) -> List[Dict[str, Any]]:
        """Get the complete audit trail for a specific entry"""
        return await self.ledger_service.get_audit_logs(entry_id=entry_id, limit=10000)
    
    async def verify_audit_integrity(self) -> bool:
        """Verify the integrity of the audit log hash chain"""
        # Get all audit logs in order
        logs = await self.ledger_service.get_audit_logs(limit=10000, offset=0)
        
        previous_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        
        for log in logs:
            # Reconstruct the payload
            payload = f"{log['action']}:{log['user_id']}:{log['service_name']}:{log['details']}"
            payload_hash = hashlib.sha256(payload.encode()).hexdigest()
            
            # Check if the stored payload_hash matches
            if log['payload_hash'] != payload_hash:
                return False
            
            # Check the chain
            if log['previous_hash'] != previous_hash:
                return False
            
            # Update previous_hash for next iteration
            previous_hash = log['current_hash']
        
        return True
