import httpx
import json
from typing import Dict, Any, Optional
import asyncio

class WebhookDispatcher:
    """Webhook dispatch client"""
    
    def __init__(self, config):
        self.config = config
        self.client = httpx.AsyncClient(timeout=5.0)
    
    async def dispatch(
        self, 
        data: Dict[str, Any],
        endpoint: Optional[str] = None
    ) -> bool:
        """Dispatch webhook"""
        
        url = endpoint or self.config.webhook_endpoints[0] if self.config.webhook_endpoints else None
        if not url:
            return False
        
        try:
            response = await self.client.post(
                url,
                json=data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'GovSpend-Nexus-AI/1.0'
                }
            )
            return response.status_code < 300
        except Exception as e:
            print(f"Webhook error: {e}")
            return False