"""Consumer for detection events stream, triggers scoring."""

import asyncio
import json
from datetime import datetime, timezone

import redis.asyncio as redis

from ..config import settings
from ..services import ScoringEngine, SignalFetcher
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DetectionConsumer:
    """Consumes detection events and triggers scoring."""

    def __init__(
        self,
        redis_client: redis.Redis,
        signal_fetcher: SignalFetcher,
        scoring_engine: ScoringEngine,
    ):
        self.redis = redis_client
        self.signal_fetcher = signal_fetcher
        self.scoring_engine = scoring_engine
        self.config = settings

    async def initialize(self):
        """Initialize consumer group."""
        try:
            await self.redis.xgroup_create(
                self.config.INPUT_STREAM,
                self.config.CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
            logger.info(f"Created consumer group {self.config.CONSUMER_GROUP}")
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
            logger.info(f"Consumer group {self.config.CONSUMER_GROUP} already exists")

    async def consume_loop(self):
        """Main consumption loop."""
        await self.initialize()
        logger.info("Starting detection event consumption loop")

        while True:
            try:
                # Read from stream
                response = await self.redis.xreadgroup(
                    groupname=self.config.CONSUMER_GROUP,
                    consumername=self.config.CONSUMER_NAME,
                    streams={self.config.INPUT_STREAM: ">"},
                    count=self.config.BATCH_SIZE,
                    block=5000,  # 5 second block
                )

                if not response:
                    continue

                # Process messages
                messages = response[0][1]
                await self._process_messages(messages)

            except asyncio.CancelledError:
                logger.info("Consumption loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in consumption loop: {e}")
                await asyncio.sleep(1)

    async def _process_messages(self, messages: list[tuple]):
        """Process batch of messages from stream."""
        transaction_ids = []
        message_map: dict[str, tuple] = {}

        for message_id, data in messages:
            try:
                event_data = json.loads(data[b"event"])
                tx_id = event_data.get("transaction_id")
                if tx_id:
                    transaction_ids.append(tx_id)
                    message_map[tx_id] = (message_id, event_data)
            except Exception as e:
                logger.error(f"Error parsing message {message_id}: {e}")
                await self.redis.xack(
                    self.config.INPUT_STREAM,
                    self.config.CONSUMER_GROUP,
                    message_id,
                )

        if not transaction_ids:
            return

        # Fetch signals for all transactions
        try:
            signals_map = await self.signal_fetcher.fetch_signals_bulk(
                transaction_ids,
                min_confidence=self.config.MIN_CONFIDENCE,
            )

            # Score each transaction
            results = await self.scoring_engine.score_transactions_bulk(
                signals_map,
                weights_version=self.config.DEFAULT_WEIGHTS_VERSION,
                min_confidence=self.config.MIN_CONFIDENCE,
                confidence_floor=self.config.CONFIDENCE_FLOOR,
            )

            # Publish results
            for tx_id, result in results.items():
                if tx_id in message_map:
                    message_id, event_data = message_map[tx_id]
                    await self._publish_result(result, event_data)
                    await self.redis.xack(
                        self.config.INPUT_STREAM,
                        self.config.CONSUMER_GROUP,
                        message_id,
                    )

        except Exception as e:
            logger.error(f"Error processing messages: {e}")
            # Don't ack messages on error - they'll be retried

    async def _publish_result(self, result, source_event: dict):
        """Publish scoring result to output stream."""
        try:
            event = {
                "transaction_id": result.transaction_id,
                "risk_score": result.risk_score,
                "risk_tier": result.risk_tier.value,
                "weighted_sum": result.weighted_sum,
                "confidence_factor": result.confidence_factor,
                "weights_version": result.weights_version,
                "detectors_used": list(result.components.keys()),
                "source_event": source_event,
                "timestamp": result.calculated_at.isoformat(),
            }

            await self.redis.xadd(
                self.config.OUTPUT_STREAM,
                {"event": json.dumps(event, default=str)},
                maxlen=10000,
            )
            logger.info(f"Published scoring result for {result.transaction_id}: {result.risk_tier.value}")

        except Exception as e:
            logger.error(f"Error publishing result: {e}")
            await self.redis.xadd(
                self.config.ERROR_STREAM,
                {
                    "error": str(e),
                    "transaction_id": result.transaction_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )