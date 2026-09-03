"""Metrics collector — Prometheus-compatible counters and histograms for the audit service."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and exposes metrics for the audit logging service.

    In production, replace the in-memory dicts with Prometheus client
    metrics (``prometheus_client.Counter``, ``Histogram``, ``Gauge``).
    """

    def __init__(self) -> None:
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._start_time = time.monotonic()

    # ------------------------------------------------------------------
    # Counters
    # ------------------------------------------------------------------

    def increment_counter(self, name: str, value: int = 1) -> None:
        self._counters[name] += value

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    # ------------------------------------------------------------------
    # Gauges
    # ------------------------------------------------------------------

    def set_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    # ------------------------------------------------------------------
    # Histograms
    # ------------------------------------------------------------------

    def observe_histogram(self, name: str, value: float) -> None:
        self._histograms[name].append(value)

    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
        sorted_vals = sorted(values)
        count = len(sorted_vals)
        return {
            "count": count,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(sorted_vals) / count,
            "p50": sorted_vals[int(count * 0.5)],
            "p95": sorted_vals[min(int(count * 0.95), count - 1)],
            "p99": sorted_vals[min(int(count * 0.99), count - 1)],
        }

    # ------------------------------------------------------------------
    # Audit-specific helpers
    # ------------------------------------------------------------------

    def record_audit_entry(
        self,
        event_type: str,
        severity: str,
        duration_ms: float,
    ) -> None:
        self.increment_counter("audit_entries_total")
        self.increment_counter(f"audit_entries_by_type_{event_type}")
        self.increment_counter(f"audit_entries_by_severity_{severity}")
        self.observe_histogram("audit_entry_duration_ms", duration_ms)

    def record_verification(self, verified: bool, tampered: bool) -> None:
        self.increment_counter("audit_verifications_total")
        if verified:
            self.increment_counter("audit_verifications_passed")
        if tampered:
            self.increment_counter("audit_verifications_tampered")

    def record_chain_update(self, sequence: int) -> None:
        self.set_gauge("audit_chain_length", sequence)
        self.increment_counter("audit_chain_updates_total")

    def record_flush(self, count: int) -> None:
        self.increment_counter("audit_flushes_total")
        self.observe_histogram("audit_flush_batch_size", count)

    # ------------------------------------------------------------------
    # Full metrics snapshot
    # ------------------------------------------------------------------

    def get_all_metrics(self) -> Dict[str, Any]:
        uptime = time.monotonic() - self._start_time
        return {
            "uptime_seconds": round(uptime, 2),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                name: self.get_histogram_stats(name)
                for name in self._histograms
            },
        }
