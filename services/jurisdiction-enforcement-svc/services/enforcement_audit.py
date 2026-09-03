from typing import Optional, Dict, Any
import asyncpg
from datetime import datetime
from models.jurisdiction import JurisdictionEnforcementRequest, JurisdictionEnforcementResult

class EnforcementAudit:
    """Audit jurisdiction enforcement decisions"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
    
    async def log_enforcement(
        self,
        request: JurisdictionEnforcementRequest,
        result: JurisdictionEnforcementResult
    ):
        """Log enforcement decision"""
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO jurisdiction_audit_logs (
                    request_id, user_id, resource_type, resource_id,
                    resource_jurisdiction, user_jurisdictions, action,
                    allowed, reason, matching_jurisdictions, hierarchy_check,
                    timestamp
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                )
            """,
                result.request_id,
                result.user_id,
                request.resource_type,
                request.resource_id,
                request.resource_jurisdiction,
                request.user_jurisdictions,
                request.action,
                result.allowed,
                result.reason,
                result.matching_jurisdictions,
                result.hierarchy_check,
                result.timestamp
            )
    
    async def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """Get audit logs with filters"""
        
        conditions = []
        params = []
        param_idx = 1
        
        if user_id:
            conditions.append(f"user_id = ${param_idx}")
            params.append(user_id)
            param_idx += 1
        
        if resource_type:
            conditions.append(f"resource_type = ${param_idx}")
            params.append(resource_type)
            param_idx += 1
        
        if start_date:
            conditions.append(f"timestamp >= ${param_idx}")
            params.append(start_date)
            param_idx += 1
        
        if end_date:
            conditions.append(f"timestamp <= ${param_idx}")
            params.append(end_date)
            param_idx += 1
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
            SELECT * FROM jurisdiction_audit_logs
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def get_stats(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get audit statistics"""
        
        conditions = []
        params = []
        param_idx = 1
        
        if user_id:
            conditions.append(f"user_id = ${param_idx}")
            params.append(user_id)
            param_idx += 1
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
            SELECT 
                COUNT(*) as total_checks,
                SUM(CASE WHEN allowed THEN 1 ELSE 0 END) as allowed_count,
                SUM(CASE WHEN NOT allowed THEN 1 ELSE 0 END) as denied_count,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(DISTINCT resource_id) as unique_resources
            FROM jurisdiction_audit_logs
            {where_clause}
        """
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            return dict(row)