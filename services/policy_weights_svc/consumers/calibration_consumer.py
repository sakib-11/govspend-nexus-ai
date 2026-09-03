"""Redis stream consumer — reads calibration events and creates new policy versions."""

import json
import asyncio
from typing import List, Tuple, Optional
from datetime import datetime, timezone

import redis.asyncio as aioredis

from ..models.policy import CalibrationType, WeightChangeReason, DetectorWeights
from ..services.calibration_service import CalibrationService
from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class CalibrationConsumer:
    """Consume calibration.events and create policy versions."""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        calibration_service: CalibrationService,
        config=None,
    ):
        self.redis = redis_client
        self.calibration_service = calibration_service
        self.config = config or settings

        self.stream = self.config.INPUT_STREAM
        self.group = self.config.CONSUMER_GROUP
        self.consumer = self.config.CONSUMER_NAME
        self.batch_size = self.config.BATCH_SIZE

    async def initialize(self):
        """Create consumer group if it doesn't exist."""
        try:
            await self.redis.xgroup_create(
                self.stream, self.group, id="0", mkstream=True
            )
            logger.info("Created consumer group %s", self.group)
        except aioredis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
            logger.info("Consumer group %s already exists", self.group)

    async def consume_loop(self):
        """Main consumption loop."""
        await self.initialize()
        logger.info("Starting calibration consumption loop")

        consecutive_errors = 0

        while True:
            try:
                response = await self.redis.xreadgroup(
                    groupname=self.group,
                    consumername=self.consumer,
                    streams={self.stream: ">"},
                    count=self.batch_size,
                    block=5000,
                )

                if not response:
                    consecutive_errors = 0
                    continue

                messages = response[0][1]
                if messages:
                    await self._process_messages(messages)
                    consecutive_errors = 0

            except asyncio.CancelledError:
                logger.info("Consumption loop cancelled")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(
                    "Error in consumption loop (attempt %d): %s",
                    consecutive_errors,
                    e,
                    exc_info=True,
                )
                delay = min(30, 2 ** min(consecutive_errors, 5))
                await asyncio.sleep(delay)

    async def _process_messages(self, messages: List[Tuple[bytes, dict]]):
        """Parse calibration events and create policies."""
        for message_id, data in messages:
            try:
                event_raw = data.get(b"event") or data.get("event")
                if isinstance(event_raw, bytes):
                    event_raw = event_raw.decode("utf-8")
                event = json.loads(event_raw)

                await self._handle_calibration_event(event)

                mid = message_id.decode("utf-8") if isinstance(message_id, bytes) else message_id
                await self.redis.xack(self.stream, self.group, mid)

            except Exception as e:
                logger.error("Failed to process calibration message: %s", e)
                mid = message_id.decode("utf-8") if isinstance(message_id, bytes) else message_id
                await self.redis.xack(self.stream, self.group, mid)

    async def _handle_calibration_event(self, event: dict):
        """Handle a single calibration event."""
        weights_data = event.get("weights", {})
        weights = DetectorWeights(**weights_data)

        from ..models.policy import CalibrationRequest

        request = CalibrationRequest(
            name=event.get("name", "Stream Calibration"),
            description=event.get("description"),
            weights=weights,
            calibration_type=CalibrationType(
                event.get("calibration_type", "automated")
            ),
            calibration_reason=WeightChangeReason(
                event.get("calibration_reason", "performance_improvement")
            ),
            calibration_data=event.get("calibration_data"),
            created_by=event.get("created_by", "calibration-consumer"),
        )

        policy = await self.calibration_service.calibrate_weights(request)
        logger.info(
            "Calibration consumer created policy %s/%s",
            policy.policy_id,
            policy.version,
        )
