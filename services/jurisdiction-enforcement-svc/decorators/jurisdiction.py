from typing import List, Optional, Callable
from functools import wraps
from fastapi import Request, HTTPException, status
from models.jurisdiction import JurisdictionEnforcementRequest
from services.jurisdiction_enforcer import JurisdictionEnforcer

def require_jurisdiction(
    jurisdiction_id: Optional[str] = None,
    multiple_jurisdictions: Optional[List[str]] = None,
    require_hierarchy: bool = False
):
    """Decorator to require jurisdiction access"""
    
    def decorator(func: Callable):
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
            
            # Get user
            user = getattr(request.state, 'user', None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Determine required jurisdictions
            jurisdictions = []
            if jurisdiction_id:
                jurisdictions = [jurisdiction_id]
            elif multiple_jurisdictions:
                jurisdictions = multiple_jurisdictions
            else:
                # Try to get from path
                path_parts = request.url.path.strip("/").split("/")
                if "jurisdiction" in path_parts:
                    idx = path_parts.index("jurisdiction")
                    if idx + 1 < len(path_parts):
                        jurisdictions = [path_parts[idx + 1]]
            
            if not jurisdictions:
                return await func(*args, **kwargs)
            
            # Check jurisdiction access
            enforcer = request.app.state.jurisdiction_enforcer
            
            if require_hierarchy:
                # Check if user has any jurisdiction that is ancestor/descendant
                accessible = await enforcer.get_accessible_jurisdictions(
                    user.jurisdictions,
                    jurisdictions
                )
                if not accessible:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Jurisdiction hierarchy access denied"
                    )
            else:
                # Check direct access
                if not any(j in user.jurisdictions for j in jurisdictions):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Jurisdiction access denied for {jurisdictions}"
                    )
            
            # Store checked jurisdictions in request state
            request.state.jurisdictions_checked = jurisdictions
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_same_jurisdiction():
    """Decorator to require user and resource share jurisdiction"""
    
    def decorator(func: Callable):
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
            
            # Get resource jurisdiction
            resource_jurisdiction = request.headers.get("X-Resource-Jurisdiction")
            if not resource_jurisdiction:
                # Try to get from path
                path_parts = request.url.path.strip("/").split("/")
                if "jurisdiction" in path_parts:
                    idx = path_parts.index("jurisdiction")
                    if idx + 1 < len(path_parts):
                        resource_jurisdiction = path_parts[idx + 1]
            
            if not resource_jurisdiction:
                return await func(*args, **kwargs)
            
            # Check if user has access to resource jurisdiction
            if resource_jurisdiction not in user.jurisdictions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User does not have access to resource jurisdiction"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def with_jurisdiction_audit():
    """Audit jurisdiction checks"""
    
    def decorator(func: Callable):
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
                
                # Log successful jurisdiction check
                if request and hasattr(request.state, 'user'):
                    user = request.state.user
                    await _log_jurisdiction_check(request, user, success=True)
                
                return result
                
            except HTTPException as e:
                # Log failed jurisdiction check
                if request and hasattr(request.state, 'user'):
                    user = request.state.user
                    await _log_jurisdiction_check(request, user, success=False, error=e.detail)
                raise
        
        async def _log_jurisdiction_check(request: Request, user, success: bool, error: str = None):
            """Log jurisdiction check"""
            # In production, you'd log to audit service
            pass
        
        return wrapper
    return decorator