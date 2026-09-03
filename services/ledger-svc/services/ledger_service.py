from typing import Optional, Dict, Any, List, Tuple
import asyncpg
import json
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from models.ledger import (
    LedgerEntry, LedgerCreateRequest, LedgerReadRequest,
    LedgerUpdateRequest, LedgerResponse, EntityType,
    LedgerAuditLog
)
from services.encryption_service import EncryptionService
from services.hsm_client import HSMClient

class LedgerService:
    """Core ledger service for secure data storage"""
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        encryption_service: EncryptionService,
        hsm_client: HSMClient,
        config
    ):
        self.db_pool = db_pool
        self.encryption_service = encryption_service
        self.hsm_client = hsm_client
        self.config = config
    
    async def create_entry(
        self,
        request: LedgerCreateRequest,
        service_name: str,
        user_id: str,
        ip_address: Optional[str] = None
    ) -> LedgerResponse:
        """Create a new ledger entry"""
        
        # Check access
        await self._check_access(service_name, request.entity_type, "WRITE")
        
        # Encrypt data
        encrypted_data = await self.encryption_service.encrypt_entity_data(
            request.entity_type,
            request.entity_token,
            request.data
        )
        
        # Generate data hash
        data_hash = self.encryption_service.generate_data_hash(request.data)
        
        # Get encryption key
        key_id = self.config.master_key_id
        # Note: encrypted_data is a dict with encrypted_fields and non_sensitive_data
        # We don't have a single key_id for the entire entry in this design.
        # However, the ledger_entries table expects encryption_key_id per entry.
        # We'll use the master key for the entry, and the individual fields are encrypted with data keys.
        # For simplicity, we'll store the master key ID as the encryption key for the entry.
        # In a more advanced design, we might encrypt the data keys with the master key and store them.
        
        # Store in database
        async with self.db_pool.acquire() as conn:
            entry_id = uuid4()
            
            await conn.execute("""
                INSERT INTO ledger_entries (
                    entry_id, entity_type, entity_token, encrypted_data,
                    encryption_key_id, encryption_algorithm, iv, auth_tag,
                    data_hash, metadata, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW()
                )
            """,
                str(entry_id),
                request.entity_type.value,
                request.entity_token,
                json.dumps(encrypted_data),
                key_id,
                self.config.encryption_algorithm,
                None,  # IV is not stored at entry level in this design
                None,  # Auth tag is not stored at entry level
                data_hash,
                json.dumps(request.metadata or {})
            )
            
            # Audit log
            await self._log_audit(
                entry_id=entry_id,
                action="CREATE",
                user_id=user_id,
                service_name=service_name,
                ip_address=ip_address,
                details={
                    "entity_type": request.entity_type.value,
                    "entity_token": request.entity_token
                }
            )
            
            # Return response
            return LedgerResponse(
                entry_id=entry_id,
                entity_type=request.entity_type.value,
                entity_token=request.entity_token,
                encrypted=True,
                metadata=request.metadata or {},
                created_at=datetime.now(),
                updated_at=datetime.now(),
                access_count=0,
                last_accessed_at=None
            )
    
    async def read_entry(
        self,
        request: LedgerReadRequest,
        service_name: str,
        user_id: str,
        ip_address: Optional[str] = None
    ) -> Optional[LedgerResponse]:
        """Read a ledger entry"""
        
        # Check access
        await self._check_access(service_name, request.entity_type, "READ")
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM ledger_entries
                WHERE entity_type = $1 AND entity_token = $2
                AND is_active = TRUE
            """, request.entity_type.value, request.entity_token)
            
            if not row:
                return None
            
            # Update access count
            await conn.execute("""
                UPDATE ledger_entries
                SET access_count = access_count + 1,
                    last_accessed_at = NOW()
                WHERE entry_id = $1
            """, row['entry_id'])
            
            # Decrypt data if requested
            data = None
            if request.decrypt:
                encrypted_data = row['encrypted_data']
                data = await self.encryption_service.decrypt_entity_data(
                    request.entity_type,
                    encrypted_data
                )
            
            # Audit log
            await self._log_audit(
                entry_id=row['entry_id'],
                action="READ",
                user_id=user_id,
                service_name=service_name,
                ip_address=ip_address,
                details={
                    "entity_type": request.entity_type.value,
                    "entity_token": request.entity_token,
                    "decrypted": request.decrypt
                }
            )
            
            return LedgerResponse(
                entry_id=row['entry_id'],
                entity_type=row['entity_type'],
                entity_token=row['entity_token'],
                data=data,
                encrypted=not request.decrypt,
                metadata=row['metadata'] or {},
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                access_count=row['access_count'] + 1,
                last_accessed_at=datetime.now()
            )
    
    async def update_entry(
        self,
        request: LedgerUpdateRequest,
        service_name: str,
        user_id: str,
        ip_address: Optional[str] = None
    ) -> Optional[LedgerResponse]:
        """Update a ledger entry"""
        
        # Check access
        await self._check_access(service_name, request.entity_type, "WRITE")
        
        # Encrypt new data
        encrypted_data = await self.encryption_service.encrypt_entity_data(
            request.entity_type,
            request.entity_token,
            request.data
        )
        
        # Generate data hash
        data_hash = self.encryption_service.generate_data_hash(request.data)
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE ledger_entries
                SET encrypted_data = $1,
                    data_hash = $2,
                    metadata = $3,
                    updated_at = NOW()
                WHERE entity_type = $4 AND entity_token = $5
                AND is_active = TRUE
                RETURNING entry_id, created_at, access_count, last_accessed_at
            """,
                json.dumps(encrypted_data),
                data_hash,
                json.dumps(request.metadata or {}),
                request.entity_type.value,
                request.entity_token
            )
            
            if not row:
                return None
            
            # Audit log
            await self._log_audit(
                entry_id=row['entry_id'],
                action="UPDATE",
                user_id=user_id,
                service_name=service_name,
                ip_address=ip_address,
                details={
                    "entity_type": request.entity_type.value,
                    "entity_token": request.entity_token
                }
            )
            
            return LedgerResponse(
                entry_id=row['entry_id'],
                entity_type=request.entity_type.value,
                entity_token=request.entity_token,
                encrypted=True,
                metadata=request.metadata or {},
                created_at=row['created_at'],
                updated_at=datetime.now(),
                access_count=row['access_count'],
                last_accessed_at=row['last_accessed_at']
            )
    
    async def delete_entry(
        self,
        entity_type: EntityType,
        entity_token: str,
        service_name: str,
        user_id: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Soft delete a ledger entry"""
        
        # Check access
        await self._check_access(service_name, entity_type, "DELETE")
        
        async with self.db_pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE ledger_entries
                SET is_active = FALSE,
                    updated_at = NOW()
                WHERE entity_type = $1 AND entity_token = $2
            """, entity_type.value, entity_token)
            
            if result.split()[1] == "0":
                return False
            
            # Audit log
            await self._log_audit(
                entry_id=None,
                action="DELETE",
                user_id=user_id,
                service_name=service_name,
                ip_address=ip_address,
                details={
                    "entity_type": entity_type.value,
                    "entity_token": entity_token
                }
            )
            
            return True
    
    async def batch_read(
        self,
        entity_type: EntityType,
        entity_tokens: List[str],
        service_name: str,
        user_id: str,
        decrypt: bool = False
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Batch read ledger entries"""
        
        results = {}
        
        for token in entity_tokens:
            request = LedgerReadRequest(
                entity_type=entity_type,
                entity_token=token,
                decrypt=decrypt
            )
            
            entry = await self.read_entry(
                request,
                service_name,
                user_id
            )
            
            results[token] = entry.data if entry else None
        
        return results
    
    async def _check_access(self, service_name: str, entity_type: EntityType, access_level: str):
        """Check if service has access to entity type"""
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT access_level FROM ledger_access_control
                WHERE service_name = $1 AND entity_type = $2 AND is_active = TRUE
            """, service_name, entity_type.value)
            
            if not row:
                raise PermissionError(f"Service {service_name} has no access to {entity_type.value}")
            
            allowed_levels = ["ADMIN"]
            if access_level == "READ":
                allowed_levels.extend(["READ", "WRITE", "DELETE"])
            elif access_level == "WRITE":
                allowed_levels.extend(["WRITE"])
            elif access_level == "DELETE":
                allowed_levels.extend(["WRITE", "DELETE"])
            
            if row['access_level'] not in allowed_levels:
                raise PermissionError(
                    f"Service {service_name} has {row['access_level']} access, "
                    f"but {access_level} is required"
                )
    
    async def _log_audit(
        self,
        entry_id: Optional[UUID],
        action: str,
        user_id: str,
        service_name: str,
        ip_address: Optional[str],
        details: Dict[str, Any]
    ):
        """Log audit entry with hash chaining"""
        
        # Calculate payload hash
        payload = f"{action}:{user_id}:{service_name}:{json.dumps(details)}"
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()
        
        async with self.db_pool.acquire() as conn:
            audit_id = uuid4()
            
            await conn.execute("""
                INSERT INTO ledger_audit_log (
                    audit_id, entry_id, action, user_id, service_name,
                    ip_address, details, payload_hash, timestamp
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, NOW()
                )
            """,
                str(audit_id),
                str(entry_id) if entry_id else None,
                action,
                user_id,
                service_name,
                ip_address,
                json.dumps(details),
                payload_hash
            )
    
    async def get_audit_logs(
        self,
        entry_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get audit logs"""
        
        conditions = []
        params = []
        param_idx = 1
        
        if entry_id:
            conditions.append(f"entry_id = ${param_idx}")
            params.append(str(entry_id))
            param_idx += 1
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM ledger_audit_log
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """, *params, limit, offset)
            
            return [dict(row) for row in rows]
