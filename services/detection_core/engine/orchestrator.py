"""Detection Orchestrator - Orchestrates detection execution flow."""

import asyncio
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from .runner import DetectorRunner
from .collector import SignalCollector
from ..detectors.registry import DetectorRegistry
from ..services.signal_service import SignalService
from ..services.event_publisher import EventPublisher
from ..models.engine import TransactionContext, DetectorStatus
from ..models.signals import SignalGroup
from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DetectionOrchestrator:
    """Orchestrate detection execution flow"""

    def __init__(
        self,
        registry: Optional[DetectorRegistry] = None,
        runner: Optional[DetectorRunner] = None,
        collector: Optional[SignalCollector] = None,
        signal_service: Optional[SignalService] = None,
        event_publisher: Optional[EventPublisher] = None
    ):
        self.registry = registry or DetectorRegistry()
        self.runner = runner or DetectorRunner(self.registry)
        self.collector = collector or SignalCollector()
        self.signal_service = signal_service or SignalService()
        self.event_publisher = event_publisher or EventPublisher()

        # Configuration
        self.max_concurrent = settings.MAX_CONCURRENT_TRANSACTIONS
        self.processing_timeout = settings.PROCESSING_TIMEOUT_SECONDS

        # Active transactions
        self._active_transactions: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

        logger.info("Detection Orchestrator initialized")

    async def process_transaction(self, raw_transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single transaction through the detection pipeline
        """
        start_time = time.time()
        transaction_id = raw_transaction.get("transaction_id", str(uuid.uuid4()))

        # Create context
        context = self._create_context(transaction_id, raw_transaction)

        try:
            # Acquire semaphore
            async with self._semaphore:
                # Publish detection started event
                await self.event_publisher.publish_detection_started(transaction_id)

                # Run detectors
                signals, executions = await self.runner.run_all_detectors(
                    context,
                    parallel=settings.PARALLEL_DETECTORS
                )

                # Add signals to collector
                for signal in signals:
                    self.collector.add_signal(transaction_id, signal)

                # Get signal group
                signal_group = self.collector.get_signal_group(transaction_id)

                if signal_group:
                    # Save signals
                    await self.signal_service.save_signals(signal_group)

                    # Prepare detector results
                    detector_results = {
                        execution.detector_id: {
                            "status": execution.status.value,
                            "duration_ms": execution.duration_ms,
                            "signal_value": self._get_signal_value(execution.result) if execution.result else None
                        }
                        for execution in executions
                    }

                    # Publish signals generated event
                    execution_time_ms = (time.time() - start_time) * 1000
                    await self.event_publisher.publish_signals_generated(
                        transaction_id,
                        signal_group,
                        detector_results,
                        execution_time_ms
                    )

                    # Publish detection completed
                    await self.event_publisher.publish_detection_completed(
                        transaction_id,
                        execution_time_ms,
                        len(signals)
                    )

                    # Update context
                    context.processing_completed = datetime.utcnow()
                    context.total_duration_ms = execution_time_ms
                    context.is_processed = True
                    context.detector_executions = executions

                    logger.info(
                        f"Transaction {transaction_id} processed: "
                        f"{len(signals)} signals in {execution_time_ms:.0f}ms"
                    )

                    return {
                        "transaction_id": transaction_id,
                        "status": "completed",
                        "signals_count": len(signals),
                        "max_signal": signal_group.max_signal_value,
                        "avg_signal": signal_group.average_signal_value,
                        "execution_time_ms": execution_time_ms,
                        "detector_results": detector_results
                    }
                else:
                    # No signals generated
                    execution_time_ms = (time.time() - start_time) * 1000
                    await self.event_publisher.publish_detection_completed(
                        transaction_id,
                        execution_time_ms,
                        0
                    )

                    return {
                        "transaction_id": transaction_id,
                        "status": "completed_no_signals",
                        "signals_count": 0,
                        "execution_time_ms": execution_time_ms
                    }

        except asyncio.TimeoutError:
            error = f"Processing timed out after {self.processing_timeout}s"
            logger.error(f"Transaction {transaction_id}: {error}")
            await self.event_publisher.publish_detection_failed(transaction_id, error)

            return {
                "transaction_id": transaction_id,
                "status": "timeout",
                "error": error
            }

        except Exception as e:
            error = str(e)
            logger.error(f"Transaction {transaction_id} failed: {error}", exc_info=True)
            await self.event_publisher.publish_detection_failed(transaction_id, error)

            return {
                "transaction_id": transaction_id,
                "status": "failed",
                "error": error
            }
        finally:
            # Clean up
            self.collector.clear(transaction_id)

    def _create_context(self, transaction_id: str, raw_transaction: Dict[str, Any]) -> TransactionContext:
        """Create transaction context"""
        return TransactionContext(
            transaction_id=transaction_id,
            source_id=raw_transaction.get("source_id", "unknown"),
            canonical_transaction=raw_transaction,
            ingested_at=datetime.utcnow(),
            processing_started=datetime.utcnow(),
            department_id=raw_transaction.get("department_id"),
            vendor_id=raw_transaction.get("vendor_id"),
            amount=raw_transaction.get("amount"),
            transaction_date=raw_transaction.get("transaction_date")
        )

    def _get_signal_value(self, result: Dict[str, Any]) -> Optional[float]:
        """Extract signal value from detector result"""
        return result.get("signal_value")

    async def process_batch(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of transactions"""
        tasks = []
        for transaction in transactions:
            task = asyncio.create_task(
                self.process_transaction(transaction)
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "transaction_id": transactions[i].get("transaction_id", "unknown"),
                    "status": "failed",
                    "error": str(result)
                })
            else:
                processed_results.append(result)

        return processed_results

    async def stop(self):
        """Stop orchestrator"""
        for task in self._active_transactions.values():
            task.cancel()

        if self._active_transactions:
            await asyncio.gather(*self._active_transactions.values(), return_exceptions=True)
            self._active_transactions.clear()

        logger.info("Detection Orchestrator stopped")