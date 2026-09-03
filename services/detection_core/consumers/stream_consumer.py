"""Stream Consumer - Consumes messages from Redis Stream."""

import asyncio
import json
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import redis.asyncio as redis

from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class StreamConsumer:
    """Consume messages from Redis Stream"""

    def __init__(
        self,
        stream_name: str,
        consumer_group: str,
        consumer_name: str,
        handler: Optional[Callable] = None
    ):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.handler = handler
        self.running = False
        self.batch_size = settings.BATCH_SIZE or 100
        self.poll_interval = 1.0

        # Initialize consumer group
        self._init_consumer_group()

    def _init_consumer_group(self):
        """Initialize consumer group if it doesn't exist"""
        try:
            self.redis_client.xgroup_create(
                self.stream_name,
                self.consumer_group,
                id='0',
                mkstream=True
            )
            logger.info(f"Created consumer group {self.consumer_group} on {self.stream_name}")
        except Exception as e:
            # Group may already exist
            if "BUSYGROUP" not in str(e):
                logger.error(f"Failed to create consumer group: {e}")

    async def start(self):
        """Start consuming messages"""
        self.running = True
        logger.info(f"Started consumer {self.consumer_name} on {self.stream_name}")

        while self.running:
            try:
                # Read messages
                messages = await self.redis_client.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.stream_name: '>'},
                    count=self.batch_size,
                    block=1000  # 1 second timeout
                )

                if messages:
                    await self._process_messages(messages)
                else:
                    await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer error: {e}")
                await asyncio.sleep(self.poll_interval * 2)

    async def _process_messages(self, messages):
        """Process messages from stream"""
        for stream_name, stream_messages in messages:
            for message_id, message_data in stream_messages:
                try:
                    # Decode message
                    decoded_data = self._decode_message(message_data)

                    # Process message
                    if self.handler:
                        await self.handler(decoded_data)
                    else:
                        logger.warning(f"No handler for message {message_id}")

                    # Acknowledge message
                    await self.redis_client.xack(
                        self.stream_name,
                        self.consumer_group,
                        message_id
                    )

                except Exception as e:
                    logger.error(f"Failed to process message {message_id}: {e}")
                    # Don't acknowledge, will be retried

    def _decode_message(self, message_data: Dict[bytes, bytes]) -> Dict[str, Any]:
        """Decode message from bytes"""
        decoded = {}
        for key, value in message_data.items():
            key_str = key.decode('utf-8')
            try:
                value_str = value.decode('utf-8')
                # Try JSON parse
                try:
                    decoded[key_str] = json.loads(value_str)
                except json.JSONDecodeError:
                    decoded[key_str] = value_str
            except:
                decoded[key_str] = value
        return decoded

    async def stop(self):
        """Stop consuming messages"""
        self.running = False
        await self.redis_client.close()
        logger.info(f"Stopped consumer {self.consumer_name}")

    def set_handler(self, handler: Callable):
        """Set message handler"""
        self.handler = handler