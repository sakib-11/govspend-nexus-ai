from fastapi import Request, HTTPException, status
from typing import Callable, Optional, List
from functools import wraps
from models.jurisdiction import JurisdictionEnforcementRequest, JurisdictionAccess
from services.jurisdiction_enforcer import JurisdictionEnforcer

class JurisdictionMiddleware:
    """Jurisdiction enforcement middleware"""
    
    def __init__(self, enforcer: JurisdictionEnforcer):
        self.enforcer = enforcer
    
    async def __call__(self, request: Request, call_next: Callable):
        """Enforce jurisdiction for request"""
        
        # Skip jurisdiction enforcement for certain paths
        if self._should_skip_enforcement(request.url.path):
            return await call_next(request)
        
        # Get user from request state
        user = getattr(request.state, 'user', None)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Get resource jurisdiction from request
        resource_jurisdiction = self._get_resource_jurisdiction(request)
        if not resource_jurisdiction:
            # If no jurisdiction specified, use default or skip
            return await call_next(request)
        
        # Build enforcement request
        enforcement_request = JurisdictionEnforcementRequest(
            user_id=user.user_id,
            user_jurisdictions=user.jurisdictions,
            resource_type=self._get_resource_type(request.url.path),
            resource_id=self._get_resource_id(request.url.path),
            resource_jurisdiction=resource_jurisdiction,
            action=request.method.lower(),
            context={
                "path": request.url.path,
                "method": request.method,
                "headers": dict(request.headers)
            }
        )
        
        # Enforce jurisdiction
        result = await self.enforcer.enforce(enforcement_request)
        
        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Jurisdiction access denied: {result.reason}"
            )
        
        # Store enforcement result in request state
        request.state.jurisdiction_result = result
        
        return await call_next(request)
    
    def _should_skip_enforcement(self, path: str) -> bool:
        """Check if enforcement should be skipped for this path"""
        skip_paths = [
            "/health",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/auth/mfa",
            "/api/v1/jurisdiction/public"
        ]
        return any(path.startswith(p) for p in skip_paths)
    
    def _get_resource_jurisdiction(self, request: Request) -> Optional[str]:
        """Extract resource jurisdiction from request"""
        
        # Check header
        jurisdiction = request.headers.get("X-Jurisdiction")
        if jurisdiction:
            return jurisdiction
        
        # Check query parameter
        jurisdiction = request.query_params.get("jurisdiction")
        if jurisdiction:
            return jurisdiction
        
        # Check path parameter
        path_parts = request.url.path.strip("/").split("/")
        if "jurisdiction" in path_parts:
            idx = path_parts.index("jurisdiction")
            if idx + 1 < len(path_parts):
                return path_parts[idx + 1]
        
        return None
    
    def _get_resource_type(self, path: str) -> str:
        """Extract resource type from path"""
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[1]
        return "unknown"
    
    def _get_resource_id(self, path: str) -> Optional[str]:
        """Extract resource ID from path"""
        parts = path.strip("/").split("/")
        if len(parts) >= 3:
            return parts[2]
        return None