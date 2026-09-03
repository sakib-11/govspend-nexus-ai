"""Batch processor — high-throughput batch logging with backpressure and circuit breaker."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from models.audit import AuditEntry, AuditEventType, AuditSeverity, AuditStatus
from services.hash_chain_manager import HashChainManager

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject new batches
    HALF_OPEN = "half_open"  # Testing recovery


class BatchProcessor:
    """High-throughput batch processor with circuit breaker pattern.

    Accumulates entries and writes them in configurable batches.
    If writes fail repeatedly, the circuit opens and entries are
    queued for later replay.

    Parameters
    ----------
    chain_manager : HashChainManager
    batch_size : int
        Max entries per batch write.
    flush_interval : float
        Seconds between automatic flushes.
    circuit_threshold : int
        Consecutive failures before opening the circuit.
    circuit_recovery : float
        Seconds to wait before testing recovery.
    """

    def __init__(
        self,
        chain_manager: HashChainManager,
        *,
        batch_size: int = 100,
        flush_interval: float = 5.0,
        circuit_threshold: int = 5,
        circuit_recovery: float = 30.0,
    ) -> None:
        self._chain = chain_manager
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._circuit_threshold = circuit_threshold
        self._circuit_recovery = circuit_recovery

        self._queue: deque[AuditEntry] = deque()
        self._retry_queue: deque[AuditEntry] = deque()
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._running = False
        self._flush_task: Optional[asyncio.Task[None]] = None

        # Stats
        self._stats = {
            "total_queued": 0,
            "total_flushed": 0,
            "total_failed": 0,
            "batches_processed": 0,
            "circuit_opens": 0,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._flush_task = asyncio.ensure_future(self._flush_loop())

    async def stop(self) -> None:
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def enqueue(self, entry: AuditEntry) -> None:
        """Add an audit entry to the processing queue."""
        self._stats["total_queued"] += 1
        self._queue.append(entry)

        if len(self._queue) >= self._batch_size:
            await self.flush()

    async def flush(self) -> int:
        """Process all queued entries in batches.  Returns number flushed."""
        if not self._queue:
            return 0

        # Check circuit breaker
        if self._circuit_state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._circuit_state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker: HALF_OPEN — testing recovery")
            else:
                logger.warning("Circuit breaker: OPEN — queuing entries for retry")
                while self._queue:
                    self._retry_queue.append(self._queue.popleft())
                return 0

        entries = list(self._queue)
        self._queue.clear()
        flushed = 0

        # Process in sub-batches
        for i in range(0, len(entries), self._batch_size):
            batch = entries[i : i + self._batch_size]
            try:
                for entry in batch:
                    self._chain.create_chain_entry(entry)
                    entry.status = AuditStatus.COMPLETED
                flushed += len(batch)
                self._stats["total_flushed"] += len(batch)
                self._stats["batches_processed"] += 1
                self._record_success()
            except Exception as exc:
                logger.exception("Batch flush failed: %s", exc)
                self._stats["total_failed"] += len(batch)
                self._record_failure()
                # Re-queue failed entries
                for entry in batch:
                    self._retry_queue.append(entry)

        # Process retry queue if circuit is healthy
        if self._circuit_state == CircuitState.CLOSED and self._retry_queue:
            await self._process_retry_queue()

        return flushed

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def _record_success(self) -> None:
        self._failure_count = 0
        self._circuit_state = CircuitState.CLOSED

    def _record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._circuit_threshold:
            self._circuit_state = CircuitState.OPEN
            self._stats["circuit_opens"] += 1
            logger.error(
                "Circuit breaker: OPEN after %d consecutive failures",
                self._failure_count,
            )

    def _should_attempt_recovery(self) -> bool:
        if self._last_failure_time is None:
            return True
        return (time.monotonic() - self._last_failure_time) >= self._circuit_recovery

    async def _process_retry_queue(self) -> None:
        entries = list(self._retry_queue)
        self._retry_queue.clear()
        for entry in entries:
            try:
                self._chain.create_chain_entry(entry)
                entry.status = AuditStatus.COMPLETED
                self._stats["total_flushed"] += 1
            except Exception:
                self._retry_queue.append(entry)

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    async def _flush_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                if self._queue:
                    await self.flush()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Batch flush loop error")

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "queue_size": len(self._queue),
            "retry_queue_size": len(self._retry_queue),
            "circuit_state": self._circuit_state.value,
            "failure_count": self._failure_count,
        }
