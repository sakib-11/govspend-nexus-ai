import httpx
from typing import Optional, List
import asyncio

class SlackNotifier:
    """Slack notification client"""
    
    def __init__(self, webhook_url: str, config):
        self.webhook_url = webhook_url
        self.config = config
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def send(
        self, 
        message: str, 
        channel: Optional[str] = None,
        blocks: Optional[List[Dict]] = None
    ) -> bool:
        """Send message to Slack"""
        
        payload = {
            "text": message,
            "channel": channel,
            "mrkdwn": True
        }
        
        if blocks:
            payload["blocks"] = blocks
        
        try:
            response = await self.client.post(
                self.webhook_url,
                json=payload
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Slack error: {e}")
            return False
    
    async def send_block(
        self, 
        blocks: List[Dict],
        channel: Optional[str] = None
    ) -> bool:
        """Send Slack block message"""
        
        return await self.send(
            message="",  # Not used with blocks
            channel=channel,
            blocks=blocks
        )