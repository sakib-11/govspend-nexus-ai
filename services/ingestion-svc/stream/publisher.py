"""Redis Stream publisher for canonical transactions."""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import redis.asyncio as redis
from redis.exceptions import RedisError

from ..models.stream import StreamMessage, PublishResult, StreamName
from ..models.canonical import CanonicalTransaction
from .config import StreamConfig

logger = logging.getLogger(__name__)

class StreamPublisher:
    """Publish messages to Redis streams."""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        max_len: int = StreamConfig.MAX_LEN,
        trim_threshold: int = StreamConfig.TRIM_THRESHOLD
    ):
        self.redis_url = redis_url
        self.max_len = max_len
        self.trim_threshold = trim_threshold
        self._redis = None
        self._connected = False
        
    async def connect(self) -> bool:
        """Connect to Redis."""
        try:
            self._redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
                max_connections=10
            )
            # Test connection
            await self._redis.ping()
            self._connected = True
            logger.info(f"✅ Connected to Redis at {self.redis_url}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {str(e)}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._connected = False
            logger.info("Disconnected from Redis")
    
    async def publish_transaction(
        self,
        transaction: CanonicalTransaction,
        stream_name: str = StreamConfig.STREAM_TX_INGESTED,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PublishResult:
        """
        Publish a canonical transaction to a stream.
        
        Args:
            transaction: CanonicalTransaction to publish
            stream_name: Target stream name
            metadata: Additional metadata
            
        Returns:
            PublishResult with status
        """
        if not self._connected:
            await self.connect()
        
        try:
            # Prepare message
            message = self._prepare_message(transaction, stream_name, metadata)
            
            # Convert to JSON
            message_data = json.dumps(message, default=str)
            
            # Trim stream if needed
            await self._trim_stream(stream_name)
            
            # Publish to stream
            message_id = await self._redis.xadd(
                stream_name,
                {"data": message_data},
                maxlen=self.max_len
            )
            
            logger.info(f"📤 Published transaction {transaction.document_number} to {stream_name} (ID: {message_id})")
            
            return PublishResult(
                success=True,
                stream=stream_name,
                message_id=message_id,
                timestamp=datetime.now(),
                metadata={
                    "transaction_id": transaction.id,
                    "document_number": transaction.document_number,
                    "source_id": transaction.source_id
                }
            )
            
        except RedisError as e:
            logger.error(f"❌ Redis error publishing to {stream_name}: {str(e)}")
            return PublishResult(
                success=False,
                stream=stream_name,
                error=str(e),
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"❌ Unexpected error publishing to {stream_name}: {str(e)}", exc_info=True)
            return PublishResult(
                success=False,
                stream=stream_name,
                error=str(e),
                timestamp=datetime.now()
            )
    
    def _prepare_message(
        self,
        transaction: CanonicalTransaction,
        stream_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare message payload."""
        # Convert transaction to dict
        tx_dict = transaction.dict()
        
        # Add stream metadata
        message = {
            "transaction_id": transaction.id or f"tx-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "source_id": transaction.source_id,
            "document_number": transaction.document_number,
            "transaction_type": transaction.transaction_type.value,
            "status": transaction.status.value,
            "total_amount": str(transaction.total_amount),
            "vendor": transaction.vendor.name,
            "buyer": transaction.buyer.name,
            "timestamp": datetime.now().isoformat(),
            "stream": stream_name,
            "version": "1.0"
        }
        
        # Add full transaction data
        message["transaction"] = tx_dict
        
        # Add metadata
        if metadata:
            message["metadata"] = metadata
        
        return message
    
    async def _trim_stream(self, stream_name: str):
        """Trim stream if it exceeds threshold."""
        try:
            # Get stream length
            stream_len = await self._redis.xlen(stream_name)
            
            if stream_len > self.trim_threshold:
                # Trim to max_len
                await self._redis.xtrim(stream_name, maxlen=self.max_len, approximate=True)
                logger.info(f"✂️ Trimmed stream {stream_name} from {stream_len} to {self.max_len}")
                
        except Exception as e:
            logger.warning(f"Failed to trim stream {stream_name}: {str(e)}")
    
    async def publish_batch(
        self,
        transactions: List[CanonicalTransaction],
        stream_name: str = StreamConfig.STREAM_TX_INGESTED
    ) -> List[PublishResult]:
        """
        Publish multiple transactions in batch.
        
        Args:
            transactions: List of transactions
            stream_name: Target stream name
            
        Returns:
            List of publish results
        """
        results = []
        for transaction in transactions:
            result = await self.publish_transaction(transaction, stream_name)
            results.append(result)
        
        successful = sum(1 for r in results if r.success)
        logger.info(f"📤 Batch published {successful}/{len(transactions)} transactions to {stream_name}")
        
        return results
    
    async def get_stream_info(self, stream_name: str) -> Dict[str, Any]:
        """Get information about a stream."""
        try:
            # Get stream length
            length = await self._redis.xlen(stream_name)
            
            # Get last message
            last_messages = await self._redis.xrevrange(stream_name, count=1)
            last_message_id = None
            last_message_timestamp = None
            
            if last_messages:
                last_message_id = last_messages[0][0]
                # Parse timestamp from message ID
                timestamp_ms = int(last_message_id.split('-')[0])
                last_message_timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
            
            return {
                "stream": stream_name,
                "length": length,
                "last_message_id": last_message_id,
                "last_message_timestamp": last_message_timestamp.isoformat() if last_message_timestamp else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get stream info for {stream_name}: {str(e)}")
            return {"error": str(e)}
    
    async def health_check(self) -> bool:
        """Check if Redis is healthy."""
        try:
            if not self._connected:
                await self.connect()
            await self._redis.ping()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

# Singleton instance
_publisher = None

def get_publisher() -> StreamPublisher:
    """Get or create the stream publisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = StreamPublisher()
    return _publisher

