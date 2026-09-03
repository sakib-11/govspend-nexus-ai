from typing import Callable
from fastapi import Request
from services.encryption_service import EncryptionService

class EncryptionMiddleware:
    """Middleware to handle encryption/decryption of requests and responses"""
    
    def __init__(self, encryption_service: EncryptionService):
        self.encryption_service = encryption_service
    
    async def __call__(self, request: Request, call_next: Callable):
        """Process incoming request and outgoing response"""
        
        # For now, we don't do anything at the middleware level
        # Encryption is handled at the service level
        # This middleware could be used to automatically decrypt request bodies
        # or encrypt response bodies for certain endpoints, but we leave it to
        # the service layer for clarity.
        
        response = await call_next(request)
        return response
