import json
import asyncio
from typing import List, Dict, Any
from datetime import datetime
import redis.asyncio as redis
from services.event_publisher import EventPublisher

class BundleConsumer:
    """Consume bundle events and publish risk events"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        event_publisher: EventPublisher,
        config
    ):
        self.redis = redis_client
        self.event_publisher = event_publisher
        self.config = config
        
        self.stream = config.input_stream
        self.group = config.consumer_group
        self.consumer = config.consumer_name
        self.batch_size = config.batch_size
    
    async def initialize(self):
        """Initialize consumer group"""
        try:
            await self.redis.xgroup_create(
                self.stream, 
                self.group, 
                id='$', 
                mkstream=True
            )
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
    
    async def consume_loop(self):
        """Main consumption loop"""
        await self.initialize()
        
        while True:
            try:
                response = await self.redis.xreadgroup(
                    groupname=self.group,
                    consumername=self.consumer,
                    streams={self.stream: '>'},
                    count=self.batch_size,
                    block=5000
                )
                
                if not response:
                    await asyncio.sleep(0.1)
                    continue
                
                messages = response[0][1]
                await self.process_messages(messages)
                
            except Exception as e:
                print(f"Error consuming messages: {e}")
                await asyncio.sleep(1)
    
    async def process_messages(self, messages: List[tuple]):
        """Process bundle events and publish risk events"""
        
        for message_id, data in messages:
            try:
                event_data = json.loads(data[b'event'])
                
                # Check if this is a bundle ready event
                if event_data.get('event_type') == 'bundle_ready':
                    # Publish risk event
                    await self.event_publisher.publish_risk_event(event_data)
                
                # Acknowledge message
                await self.redis.xack(self.stream, self.group, message_id)
                
            except Exception as e:
                print(f"Error processing message {message_id}: {e}")
                
                # Move to error stream
                await self.redis.xadd(
                    self.config.error_stream,
                    {
                        'error': str(e),
                        'message_id': message_id,
                        'timestamp': datetime.now().isoformat()
                    }
                )
                
                # Acknowledge original message to avoid reprocessing
                await self.redis.xack(self.stream, self.group, message_id)