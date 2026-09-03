"""Authorization decorators for MCP Gateway."""

from functools import wraps
from typing import List, Optional
from fastapi import Request, HTTPException, status
from models.authorization import ResourceType, ActionType, AuthorizationDecision
from models.auth import Permission


def authorize(resource: ResourceType, action: ActionType):
    """Authorization decorator for route handlers"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from args or kwargs
            request = None
            if 'request' in kwargs:
                request = kwargs['request']
            else:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if not request:
                return await func(*args, **kwargs)
            
            # Check if user is authenticated
            user = getattr(request.state, 'user', None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Check authorization response
            auth_response = getattr(request.state, 'auth_response', None)
            if auth_response:
                if auth_response.decision == AuthorizationDecision.DENY:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=auth_response.message
                    )
                
                if auth_response.decision == AuthorizationDecision.PARTIAL:
                    # Check if specific permission is granted
                    permission_tag = f"{resource.value}:{action.value}"
                    grants = getattr(request.state, 'partial_grants', {})
                    if not grants.get(permission_tag, False):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Permission denied for {permission_tag}"
                        )
                
                # If ALLOW or PARTIAL with grant, continue
                return await func(*args, **kwargs)
            
            # If no auth_response, perform direct check
            permission_value = f"{resource.value}:{action.value}"
            if permission_value not in [p.value for p in user.permissions]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied for {permission_value}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_any_permission(permissions: List[ResourceType], action: ActionType):
    """Require any of the specified permissions"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            if 'request' in kwargs:
                request = kwargs['request']
            else:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if not request:
                return await func(*args, **kwargs)
            
            user = getattr(request.state, 'user', None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_perms = [p.value for p in user.permissions]
            required_perms = [f"{r.value}:{action.value}" for r in permissions]
            
            if not any(p in user_perms for p in required_perms):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Need one of these permissions: {', '.join(required_perms)}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_jurisdiction(jurisdictions: List[str]):
    """Require specific jurisdiction access"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            if 'request' in kwargs:
                request = kwargs['request']
            else:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if not request:
                return await func(*args, **kwargs)
            
            user = getattr(request.state, 'user', None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not user.is_super_admin():
                # Check if user has any of the required jurisdictions
                if not any(j in user.jurisdictions for j in jurisdictions):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied for jurisdictions: {', '.join(jurisdictions)}"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def audit_authorization(action: str):
    """Audit authorization decisions"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            if 'request' in kwargs:
                request = kwargs['request']
            else:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            try:
                result = await func(*args, **kwargs)
                # Log success
                if request:
                    await _log_authorization_audit(request, action, success=True)
                return result
            except Exception as e:
                # Log failure
                if request:
                    await _log_authorization_audit(request, action, success=False, error=str(e))
                raise
        return wrapper
    return decorator

async def _log_authorization_audit(request: Request, action: str, success: bool, error: str = None):
    """Log authorization audit event"""
    
    user = getattr(request.state, 'user', None)
    auth_response = getattr(request.state, 'auth_response', None)
    
    # In production, you'd write to a dedicated audit log
    # For now, we'll just print
    print(f"Authorization Audit: {action} by {user.user_id if user else 'unknown'} - {'Success' if success else 'Failed'} - {error or ''}")