"""Redis stream consumer — reads scoring.results and assembles evidence bundles."""

import json
import asyncio
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone

import redis.asyncio as aioredis

from ..models.evidence_bundle import BundleFormat
from ..services.bundle_assembler import BundleAssembler
from ..services.bundle_storage import BundleStorage
from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ScoringConsumer:
    """Consume scoring.results events and assemble evidence bundles.

    Flow::

        scoring.results stream
            ↓
        ScoringConsumer.consume_loop()
            ↓  (batch of messages)
        BundleAssembler.assemble_bundles_bulk()
            ↓
        BundleStorage.store_bundles_bulk()
            ↓
        Publish bundle.events / bundle.errors
            ↓
        xack each processed message
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        bundle_assembler: BundleAssembler,
        bundle_storage: BundleStorage,
        config=None,
    ):
        self.redis = redis_client
        self.bundle_assembler = bundle_assembler
        self.bundle_storage = bundle_storage
        self.config = config or settings

        self.stream = self.config.INPUT_STREAM
        self.group = self.config.CONSUMER_GROUP
        self.consumer = self.config.CONSUMER_NAME
        self.batch_size = self.config.BATCH_SIZE

    # ── Lifecycle ─────────────────────────────────────────────────

    async def initialize(self):
        """Create the consumer group if it does not exist."""
        try:
            await self.redis.xgroup_create(
                self.stream,
                self.group,
                id="0",
                mkstream=True,
            )
            logger.info("Created consumer group %s on stream %s", self.group, self.stream)
        except aioredis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
            logger.info("Consumer group %s already exists", self.group)

    async def consume_loop(self):
        """Main consumption loop — runs until cancelled."""
        await self.initialize()
        logger.info(
            "Starting consumption loop — stream=%s, group=%s, consumer=%s, batch=%d",
            self.stream,
            self.group,
            self.consumer,
            self.batch_size,
        )

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
                logger.info("Consumption loop cancelled — shutting down")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(
                    "Error in consumption loop (attempt %d): %s",
                    consecutive_errors,
                    e,
                    exc_info=True,
                )
                # Exponential backoff, capped at 30s
                delay = min(30, 2 ** min(consecutive_errors, 5))
                await asyncio.sleep(delay)

    # ── Message processing ────────────────────────────────────────

    async def _process_messages(self, messages: List[Tuple[bytes, dict]]):
        """Parse scoring-result messages, assemble bundles, store, and ack."""
        scoring_results: Dict[str, Dict[str, Any]] = {}
        message_map: Dict[str, bytes] = {}  # tx_id → message_id

        for message_id, data in messages:
            try:
                event_raw = data.get(b"event") or data.get("event")
                if isinstance(event_raw, bytes):
                    event_raw = event_raw.decode("utf-8")
                event_data = json.loads(event_raw)

                tx_id = event_data.get("transaction_id")
                if tx_id:
                    scoring_results[tx_id] = event_data
                    # message_id may be bytes or str
                    if isinstance(message_id, bytes):
                        message_id = message_id.decode("utf-8")
                    message_map[tx_id] = message_id
                else:
                    logger.warning("Message %s missing transaction_id — skipping", message_id)
                    await self._ack(message_id)

            except (json.JSONDecodeError, KeyError) as e:
                logger.error("Failed to parse message %s: %s", message_id, e)
                await self._ack(message_id)

        if not scoring_results:
            return

        logger.info("Processing %d scoring results", len(scoring_results))

        try:
            # Assemble bundles
            bundles = await self.bundle_assembler.assemble_bundles_bulk(
                scoring_results,
                include_benchmarks=self.config.INCLUDE_BENCHMARKS,
                bundle_format=BundleFormat(self.config.DEFAULT_FORMAT),
            )

            # Store bundles
            refs = await self.bundle_storage.store_bundles_bulk(bundles)

            # Publish events and ack
            for tx_id, bundle in bundles.items():
                message_id = message_map.get(tx_id)
                if not message_id:
                    continue

                if bundle.status.value != "ERROR":
                    await self._publish_bundle_event(bundle)
                else:
                    await self._publish_error_event(bundle)

                await self._ack(message_id)

            logger.info(
                "Batch complete: %d bundles assembled, %d stored",
                len(bundles),
                len(refs),
            )

        except Exception as e:
            logger.error(
                "Failed to process batch of %d results: %s",
                len(scoring_results),
                e,
                exc_info=True,
            )
            # On batch failure, don't ack — messages will be redelivered

    # ── Publishing ────────────────────────────────────────────────

    async def _publish_bundle_event(self, bundle):
        """Publish a bundle_ready event to the output stream."""
        try:
            event = {
                "event_type": "bundle_ready",
                "bundle_id": bundle.bundle_id,
                "transaction_id": bundle.transaction_id,
                "risk_tier": bundle.risk_tier,
                "risk_score": bundle.risk_score,
                "detector_count": len(bundle.detector_evidences),
                "evidence_count": bundle.get_evidence_count(),
                "storage_checksum": bundle.storage_checksum,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await self.redis.xadd(
                self.config.OUTPUT_STREAM,
                {"event": json.dumps(event, default=str)},
                maxlen=10_000,
            )
            logger.debug("Published bundle_ready for %s", bundle.transaction_id)

        except Exception as e:
            logger.error("Failed to publish bundle event: %s", e)

    async def _publish_error_event(self, bundle):
        """Publish a bundle_error event to the error stream."""
        try:
            event = {
                "event_type": "bundle_error",
                "bundle_id": bundle.bundle_id,
                "transaction_id": bundle.transaction_id,
                "error": bundle.metadata.get("error", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await self.redis.xadd(
                self.config.ERROR_STREAM,
                {"event": json.dumps(event, default=str)},
                maxlen=10_000,
            )

        except Exception as e:
            logger.error("Failed to publish error event: %s", e)

    # ── Ack ───────────────────────────────────────────────────────

    async def _ack(self, message_id):
        """Acknowledge a single message."""
        try:
            if isinstance(message_id, str):
                message_id = message_id.encode("utf-8")
            await self.redis.xack(self.stream, self.group, message_id)
        except Exception as e:
            logger.error("Failed to ack message %s: %s", message_id, e)
