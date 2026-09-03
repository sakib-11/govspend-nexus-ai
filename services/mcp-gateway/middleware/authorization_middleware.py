"""Authorization middleware for MCP Gateway."""

from fastapi import Request, HTTPException, status
from typing import Callable, Optional, List
from functools import wraps
from models.authorization import (
    AuthorizationRequest, AuthorizationResponse, AuthorizationDecision,
    ResourceType, ActionType, PermissionTag, ToolTag
)
from auth.authorization_engine import AuthorizationEngine
from models.auth import User


class AuthorizationMiddleware:
    """Authorization middleware for MCP Gateway"""
    
    def __init__(self, auth_engine: AuthorizationEngine):
        self.auth_engine = auth_engine
    
    async def __call__(self, request: Request, call_next: Callable):
        """Authorize request"""
        
        # Skip authorization for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Get user from request state (set by auth middleware)
        user = getattr(request.state, 'user', None)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Build authorization request
        auth_request = await self._build_authorization_request(request, user)
        
        # Authorize
        auth_response = await self.auth_engine.authorize(auth_request)
        
        # Store authorization result in request state
        request.state.auth_response = auth_response
        
        # Check decision
        if auth_response.decision == AuthorizationDecision.DENY:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=auth_response.message
            )
        
        # Handle partial authorization
        if auth_response.decision == AuthorizationDecision.PARTIAL:
            # Store partial grants for route handlers
            request.state.partial_grants = auth_response.partial_grants
        
        # Continue
        return await call_next(request)
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public"""
        public_paths = [
            "/health",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/auth/mfa",
            "/docs",
            "/openapi.json"
        ]
        return any(path.startswith(p) for p in public_paths)
    
    async def _build_authorization_request(
        self, 
        request: Request, 
        user: User
    ) -> AuthorizationRequest:
        """Build authorization request from FastAPI request"""
        
        # Determine resource type and action from path
        resource_type, action = self._parse_path(request.url.path, request.method)
        
        # Extract resource ID from path
        resource_id = self._extract_resource_id(request.url.path)
        
        # Build tool tags from path and query parameters
        tool_tags = await self._build_tool_tags(request)
        
        return AuthorizationRequest(
            user_id=user.user_id,
            user_roles=[r.value for r in user.roles],
            user_permissions=[p.value for p in user.permissions],
            user_jurisdictions=user.jurisdictions,
            resource_type=resource_type,
            action=action,
            resource_id=resource_id,
            resource_jurisdiction=request.headers.get("X-Jurisdiction"),
            resource_owner_id=request.headers.get("X-Resource-Owner"),
            tool_tags=tool_tags,
            context={
                "path": request.url.path,
                "method": request.method,
                "query_params": dict(request.query_params),
                "headers": dict(request.headers)
            },
            mfa_verified=getattr(request.state, 'mfa_verified', False),
            session_id=getattr(request.state, 'session_id', None),
            ip_address=request.client.host if request.client else None
        )
    
    def _parse_path(self, path: str, method: str) -> tuple:
        """Parse resource type and action from path"""
        
        # Map HTTP methods to actions
        method_map = {
            "GET": ActionType.VIEW,
            "POST": ActionType.CREATE,
            "PUT": ActionType.UPDATE,
            "PATCH": ActionType.UPDATE,
            "DELETE": ActionType.DELETE
        }
        
        action = method_map.get(method, ActionType.VIEW)
        
        # Map paths to resource types
        path_parts = path.strip("/").split("/")
        if len(path_parts) >= 2:
            resource_name = path_parts[1]  # /api/v1/{resource}
            
            # Special handling for nested resources
            if len(path_parts) >= 4:
                resource_name = path_parts[3]  # /api/v1/{parent}/{id}/{resource}
            
            # Map to ResourceType
            resource_map = {
                "transactions": ResourceType.TRANSACTION,
                "detections": ResourceType.DETECTION,
                "scores": ResourceType.SCORE,
                "cases": ResourceType.CASE,
                "evidence": ResourceType.EVIDENCE,
                "users": ResourceType.USER,
                "policies": ResourceType.POLICY,
                "audit": ResourceType.AUDIT,
                "reports": ResourceType.REPORT
            }
            
            resource_type = resource_map.get(resource_name, ResourceType.SYSTEM)
        else:
            resource_type = ResourceType.SYSTEM
        
        return resource_type, action
    
    def _extract_resource_id(self, path: str) -> Optional[str]:
        """Extract resource ID from path"""
        parts = path.strip("/").split("/")
        if len(parts) >= 3:
            return parts[2]  # /api/v1/resource/{id}
        return None
    
    async def _build_tool_tags(self, request: Request) -> List[ToolTag]:
        """Build tool tags from request"""
        
        # Extract from path and parameters
        tool_tags = []
        
        # Get tool from query parameter or header
        tool_id = request.headers.get("X-Tool-ID") or request.query_params.get("tool_id")
        
        if tool_id:
            # Fetch tool configuration from database/cache
            tool_config = await self._get_tool_config(tool_id)
            if tool_config:
                tool_tags.append(tool_config)
        
        # Add default tool tag based on resource
        resource_type, action = self._parse_path(request.url.path, request.method)
        
        default_tool = ToolTag(
            tool_id="default",
            resource_type=resource_type,
            required_permissions=[
                PermissionTag(resource=resource_type, action=action)
            ],
            jurisdiction_required=bool(request.headers.get("X-Jurisdiction"))
        )
        tool_tags.append(default_tool)
        
        return tool_tags
    
    async def _get_tool_config(self, tool_id: str) -> Optional[ToolTag]:
        """Get tool configuration from cache/database"""
        
        # Check cache first
        # In production, you'd fetch from Redis or database
        return None


def require_permission(resource: ResourceType, action: ActionType):
    """Decorator to require specific permission"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from args or kwargs
            request = kwargs.get('request')
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if not request:
                return await func(*args, **kwargs)
            
            # Check authorization response
            auth_response = getattr(request.state, 'auth_response', None)
            if not auth_response:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Authorization required"
                )
            
            if auth_response.decision == AuthorizationDecision.DENY:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=auth_response.message
                )
            
            # For partial decisions, check if specific permission is granted
            if auth_response.decision == AuthorizationDecision.PARTIAL:
                permission_tag = PermissionTag(resource=resource, action=action)
                grants = getattr(request.state, 'partial_grants', {})
                if not grants.get(permission_tag.to_string(), False):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied for {resource.value}:{action.value}"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator