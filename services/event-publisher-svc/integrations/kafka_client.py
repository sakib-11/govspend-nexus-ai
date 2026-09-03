import json
import asyncio
from typing import Optional
from aiokafka import AIOKafkaProducer
import logging

logger = logging.getLogger(__name__)

class KafkaClient:
    """Kafka client for publishing events"""
    
    def __init__(self, config):
        self.config = config
        self.producer: Optional[AIOKafkaProducer] = None
        self.bootstrap_servers = config.kafka_bootstrap_servers
    
    async def start(self):
        """Start the Kafka producer"""
        if not self.bootstrap_servers:
            logger.warning("Kafka bootstrap servers not configured")
            return
        
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await self.producer.start()
            logger.info("Kafka producer started")
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            self.producer = None
    
    async def stop(self):
        """Stop the Kafka producer"""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")
    
    async def produce(self, topic: str, value: str, key: Optional[str] = None):
        """Produce a message to Kafka"""
        
        if not self.producer:
            logger.warning("Kafka producer not started")
            return False
        
        try:
            await self.producer.send_and_wait(
                topic=topic,
                value=value.encode('utf-8'),
                key=key.encode('utf-8') if key else None
            )
            return True
        except Exception as e:
            logger.error(f"Failed to produce message to Kafka: {e}")
            return False