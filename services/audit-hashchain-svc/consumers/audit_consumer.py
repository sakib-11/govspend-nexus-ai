import asyncio
import json
import logging
from collections.abc import Mapping
from contextlib import suppress
from datetime import datetime
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from services.hashchain_service import HashChainService

from config import HashChainConfig

logger = logging.getLogger(__name__)

class AuditConsumer:
    """Consume audit events and add to hash chain"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        hashchain_service: HashChainService,
        config: HashChainConfig
    ):
        self.redis = redis_client
        self.hashchain_service = hashchain_service
        self.config = config
        self._is_running = False
        self._consume_task: asyncio.Task[None] | None = None
    
    async def start(self):
        """Start consuming audit events"""
        if self._is_running:
            return
        
        self._is_running = True
        self._consume_task = asyncio.create_task(self._consume_loop())
        logger.info("Audit consumer started")
    
    async def stop(self):
        """Stop consuming"""
        self._is_running = False
        if self._consume_task:
            self._consume_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._consume_task
            self._consume_task = None
        logger.info("Audit consumer stopped")
    
    async def _consume_loop(self):
        """Main consumption loop"""
        
        # Initialize consumer group
        try:
            await self.redis.xgroup_create(
                self.config.audit_stream,
                self.config.consumer_group,
                id='$',
                mkstream=True
            )
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                logger.error("Consumer group error: %s", e)
                return
        
        while self._is_running:
            try:
                # Read from stream
                response = await self.redis.xreadgroup(
                    groupname=self.config.consumer_group,
                    consumername=self.config.consumer_name,
                    streams={self.config.audit_stream: '>'},
                    count=self.config.batch_size,
                    block=5000
                )
                
                if not response:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process messages
                messages = response[0][1]
                await self._process_messages(messages)
                
            except Exception:
                logger.exception("Consumer error")
                await asyncio.sleep(1)
    
    @staticmethod
    def _get_field(data: Mapping[Any, Any], field: str) -> Any:
        """Read a Redis field from decoded and raw Redis clients."""
        return data.get(field, data.get(field.encode()))

    async def _dead_letter(self, message_id: str, data: Mapping[Any, Any], error: Exception) -> None:
        """Persist processing failures without putting event payloads in application logs."""
        serializable_data = {
            str(key.decode() if isinstance(key, bytes) else key): (
                value.decode() if isinstance(value, bytes) else value
            )
            for key, value in data.items()
        }
        await self.redis.xadd(
            f"{self.config.audit_stream}.dlq",
            {
                "error_type": type(error).__name__,
                "error": str(error),
                "message_id": message_id,
                "data": json.dumps(serializable_data, default=str),
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def _process_messages(self, messages: list[tuple[Any, Mapping[Any, Any]]]):
        """Process audit messages"""
        
        for message_id, data in messages:
            try:
                # Parse event
                raw_event = self._get_field(data, "event")
                if isinstance(raw_event, bytes):
                    raw_event = raw_event.decode("utf-8")
                event_data = json.loads(raw_event)
                
                # Extract audit details
                raw_audit_id = event_data.get('audit_id')
                actor = event_data.get('user_id', 'system')
                action = event_data.get('action', 'unknown')
                resource = event_data.get('resource_type', 'unknown')
                resource_token = event_data.get('resource_token')
                payload_hash = event_data.get('payload_hash')
                timestamp = event_data.get('timestamp')
                
                if not raw_audit_id or not payload_hash:
                    logger.warning("Skipping incomplete audit event: %s", message_id)
                    await self.redis.xack(
                        self.config.audit_stream,
                        self.config.consumer_group,
                        message_id
                    )
                    continue

                audit_id = UUID(str(raw_audit_id))
                
                # Add to hash chain
                await self.hashchain_service.append_entry(
                    audit_id=audit_id,
                    actor=actor,
                    action=action,
                    resource=resource,
                    payload_hash=payload_hash,
                    resource_token=resource_token,
                    timestamp=self._parse_timestamp(timestamp)
                )
                
                # Acknowledge message
                await self.redis.xack(
                    self.config.audit_stream,
                    self.config.consumer_group,
                    message_id
                )
                
                logger.debug("Processed audit event: %s", audit_id)
                
            except Exception as e:
                logger.exception("Error processing audit message %s", message_id)
                await self._dead_letter(message_id, data, e)
                await self.redis.xack(
                    self.config.audit_stream,
                    self.config.consumer_group,
                    message_id,
                )

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
