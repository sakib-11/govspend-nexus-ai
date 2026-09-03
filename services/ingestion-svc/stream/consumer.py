"""Redis Stream consumer for processing messages."""

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

import redis.asyncio as redis

from .config import StreamConfig

logger = logging.getLogger(__name__)

class StreamConsumer:
    """Consume messages from Redis streams."""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        consumer_group: str = "default-group",
        consumer_name: str = None
    ):
        self.redis_url = redis_url
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"consumer-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._redis: redis.Redis | None = None
        self._connected = False
        self._running = False
        self._handlers: dict[str, dict[str, Any]] = {}
        
    async def connect(self) -> bool:
        """Connect to Redis."""
        try:
            self._redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
                max_connections=10
            )
            await self._redis.ping()
            self._connected = True
            logger.info(f"✅ Connected to Redis at {self.redis_url}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {str(e)}")
            return False
    
    def register_handler(
        self,
        stream_name: str,
        handler: Callable,
        consumer_group: str | None = None
    ):
        """Register a handler for a stream."""
        group = consumer_group or self.consumer_group
        self._handlers[stream_name] = {
            "handler": handler,
            "consumer_group": group
        }
        logger.info(f"📋 Registered handler for {stream_name}")
    
    async def ensure_consumer_group(self, stream_name: str, consumer_group: str):
        """Ensure consumer group exists."""
        try:
            await self._redis.xgroup_create(
                stream_name,
                consumer_group,
                id="0",
                mkstream=True
            )
            logger.info(f"✅ Created consumer group {consumer_group} for {stream_name}")
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
            logger.debug(f"Consumer group {consumer_group} already exists for {stream_name}")
    
    async def start_consuming(self, streams: list[str] | None = None):
        """Start consuming messages."""
        if not self._connected:
            await self.connect()
        
        self._running = True
        
        # Use all registered streams if none specified
        if streams is None:
            streams = list(self._handlers.keys())
        
        # Ensure consumer groups exist
        for stream in streams:
            if stream in self._handlers:
                group = self._handlers[stream]["consumer_group"]
                await self.ensure_consumer_group(stream, group)
        
        logger.info(f"🔄 Starting consumer {self.consumer_name} on streams: {streams}")
        
        while self._running:
            try:
                for stream_name in streams:
                    handler_info = self._handlers.get(stream_name)
                    if not handler_info:
                        continue
                    messages = await self._redis.xreadgroup(
                        groupname=handler_info["consumer_group"],
                        consumername=self.consumer_name,
                        streams={stream_name: ">"},
                        count=10,
                        block=StreamConfig.BLOCK_TIMEOUT_MS,
                    )
                    if messages:
                        await self._process_messages(stream_name, messages[0][1])
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ Error in consumer loop: {str(e)}")
                await asyncio.sleep(5)
    
    async def _process_messages(self, stream_name: str, entries: list):
        """Process messages from a stream."""
        handler_info = self._handlers.get(stream_name)
        if not handler_info:
            return
        
        handler = handler_info["handler"]
        consumer_group = handler_info["consumer_group"]
        
        for entry_id, fields in entries:
            try:
                # Parse message
                message_data = json.loads(fields["data"])
                
                # Process with handler
                result = await handler(message_data)
                
                if result:
                    # Acknowledge message
                    await self._redis.xack(stream_name, consumer_group, entry_id)
                    logger.debug(f"✅ Processed and acked message {entry_id} from {stream_name}")
                else:
                    logger.warning(f"⚠️ Handler failed for message {entry_id} from {stream_name}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing message {entry_id} from {stream_name}: {str(e)}")
                # Leave message unacknowledged for retry
    
    async def stop_consuming(self):
        """Stop consuming messages."""
        self._running = False
        logger.info(f"🛑 Stopped consumer {self.consumer_name}")
    
    async def get_pending_messages(self, stream_name: str, consumer_group: str) -> list[dict[str, Any]]:
        """Get pending messages for a consumer group."""
        try:
            pending = await self._redis.xpending_range(
                stream_name,
                consumer_group,
                min="-",
                max="+",
                count=100
            )
            return pending
        except Exception as e:
            logger.error(f"Failed to get pending messages: {str(e)}")
            return []
    
    async def health_check(self) -> bool:
        """Check if consumer is healthy."""
        try:
            await self._redis.ping()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

# Example handler
async def example_handler(message: dict[str, Any]) -> bool:
    """Example message handler."""
    logger.info(f"📨 Received transaction: {message.get('document_number', 'unknown')}")
    # Process message here
    return True

