from fastapi import Request, HTTPException, status
from typing import Callable, Optional
import jwt
from functools import wraps
from config import LedgerConfig

class AuthMiddleware:
    """Authentication middleware for service-to-service communication"""
    
    def __init__(self, config: LedgerConfig):
        self.config = config
        self.allowed_services = config.allowed_services
    
    async def __call__(self, request: Request, call_next: Callable):
        """Authenticate incoming requests"""
        
        # Check if it's a service-to-service request
        service_name = request.headers.get("X-Service-Name")
        if not service_name:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Service name header required"
            )
        
        # Check if service is allowed
        if service_name not in self.allowed_services:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Service {service_name} not authorized"
            )
        
        # Validate mTLS or JWT
        # For mTLS, certificate validation is handled by the server
        # For JWT, verify the token
        auth_header = request.headers.get("Authorization")
        if auth_header:
            try:
                token = auth_header.replace("Bearer ", "")
                # Verify JWT (in production, use proper validation)
                payload = jwt.decode(token, options={"verify_signature": False})
                user_id = payload.get("sub", "system")
                request.state.user_id = user_id
            except Exception:
                request.state.user_id = "system"
        else:
            # Fallback for mTLS - extract from certificate
            request.state.user_id = "system"
        
        request.state.service_name = service_name
        
        return await call_next(request)

def require_service_auth(func):
    """Decorator for requiring service authentication"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Check if request has service_name in state
        req = None
        for arg in args:
            if isinstance(arg, Request):
                req = arg
                break
        if 'req' in kwargs:
            req = kwargs['req']
        
        if not req or not hasattr(req.state, 'service_name'):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Service authentication required"
            )
        
        return await func(*args, **kwargs)
    return wrapper
