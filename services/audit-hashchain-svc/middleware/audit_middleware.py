from fastapi import Request, HTTPException, status
from typing import Callable
import logging

logger = logging.getLogger(__name__)

class AuditMiddleware:
    """Middleware for audit logging of requests"""
    
    def __init__(self):
        pass
    
    async def __call__(self, request: Request, call_next: Callable):
        """Log request and then call next middleware"""
        
        # Log the request
        logger.info(f"Request: {request.method} {request.url}")
        
        # Process the request
        response = await call_next(request)
        
        # Log the response
        logger.info(f"Response status: {response.status_code}")
        
        return response
