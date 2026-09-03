"""Authorization routes for MCP Gateway."""

from fastapi import APIRouter, Request, HTTPException, status, Depends
from typing import Optional, List
from models.authorization import (
    AuthorizationRequest, AuthorizationResponse,
    AuthorizationPolicy, AuthorizationDecision,
    ResourceType, ActionType
)
from auth.authorization_engine import AuthorizationEngine
from middleware.authorization_middleware import AuthorizationMiddleware

router = APIRouter(prefix="/api/v1/authorization", tags=["authorization"])

@router.post("/check")
async def check_authorization(
    request: Request,
    auth_request: AuthorizationRequest,
    auth_engine: AuthorizationEngine
):
    """Check authorization for a specific request"""
    
    # Only admins can check authorization
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can check authorization"
        )
    
    # Authorize
    response = await auth_engine.authorize(auth_request)
    return response

@router.get("/check/{resource_type}/{action}")
async def check_permission(
    request: Request,
    resource_type: ResourceType,
    action: ActionType,
    auth_engine: AuthorizationEngine
):
    """Check if current user has a specific permission"""
    
    user = getattr(request.state, 'user', None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Build minimal auth request
    auth_request = AuthorizationRequest(
        user_id=user.user_id,
        user_roles=[r.value for r in user.roles],
        user_permissions=[p.value for p in user.permissions],
        user_jurisdictions=user.jurisdictions,
        resource_type=resource_type,
        action=action
    )
    
    response = await auth_engine.authorize(auth_request)
    
    return {
        "user_id": user.user_id,
        "resource": f"{resource_type.value}:{action.value}",
        "allowed": response.decision == AuthorizationDecision.ALLOW,
        "message": response.message
    }

@router.get("/permissions")
async def get_user_permissions(
    request: Request,
    auth_engine: AuthorizationEngine
):
    """Get current user's permissions"""
    
    user = getattr(request.state, 'user', None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Get permissions from user object
    permissions = [p.value for p in user.permissions]
    
    return {
        "user_id": user.user_id,
        "username": user.username,
        "roles": [r.value for r in user.roles],
        "permissions": permissions,
        "jurisdictions": user.jurisdictions
    }

@router.get("/audit")
async def get_authorization_audit(
    request: Request,
    auth_engine: AuthorizationEngine,
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Get authorization audit logs"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view audit logs"
        )
    
    async with auth_engine.db_pool.acquire() as conn:
        query = """
            SELECT * FROM authorization_audit_logs
            WHERE ($1::text IS NULL OR user_id = $1)
            ORDER BY timestamp DESC
            LIMIT $2 OFFSET $3
        """
        
        rows = await conn.fetch(query, user_id, limit, offset)
        
        return {
            "total": len(rows),
            "limit": limit,
            "offset": offset,
            "logs": [dict(row) for row in rows]
        }

@router.post("/policies")
async def create_authorization_policy(
    request: Request,
    policy: AuthorizationPolicy,
    auth_engine: AuthorizationEngine
):
    """Create an authorization policy"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage policies"
        )
    
    policy.created_by = user.user_id
    
    async with auth_engine.db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO authorization_policies (
                policy_id, name, description, version,
                permission_rules, jurisdiction_rules, role_rules,
                allow_overrides, deny_overrides, is_active,
                created_at, created_by
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
            )
        """,
            policy.policy_id,
            policy.name,
            policy.description,
            policy.version,
            policy.permission_rules,
            policy.jurisdiction_rules,
            policy.role_rules,
            policy.allow_overrides,
            policy.deny_overrides,
            policy.is_active,
            policy.created_at,
            policy.created_by
        )
        
        # Clear cache
        await auth_engine.redis.delete("auth_policies:active")
    
    return policy