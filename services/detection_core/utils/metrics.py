"""Metrics utilities for Detection Core."""

from typing import Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import time
import threading


class MetricsCollector:
    """Simple in-memory metrics collector"""

    def __init__(self):
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()

    def increment(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Increment a counter"""
        key = self._make_key(name, tags)
        with self._lock:
            self._counters[key] += value

    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Set a gauge value"""
        key = self._make_key(name, tags)
        with self._lock:
            self._gauges[key] = value

    def histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a histogram value"""
        key = self._make_key(name, tags)
        with self._lock:
            self._histograms[key].append(value)

    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics"""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: self._summarize_histogram(v)
                    for k, v in self._histograms.items()
                }
            }

    def _make_key(self, name: str, tags: Optional[Dict[str, str]]) -> str:
        """Create metric key with tags"""
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}{{{tag_str}}}"

    def _summarize_histogram(self, values: list) -> Dict[str, Any]:
        """Summarize histogram values"""
        if not values:
            return {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}

        sorted_vals = sorted(values)
        count = len(values)
        total = sum(values)

        return {
            "count": count,
            "sum": total,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": total / count,
            "p50": sorted_vals[count // 2],
            "p95": sorted_vals[int(count * 0.95)],
            "p99": sorted_vals[int(count * 0.99)]
        }


# Global metrics instance
metrics = MetricsCollector()


class Timer:
    """Context manager for timing operations"""

    def __init__(self, name: str, tags: Optional[Dict[str, str]] = None):
        self.name = name
        self.tags = tags
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        metrics.histogram(f"{self.name}.duration_ms", duration_ms, self.tags)
        if exc_type is not None:
            metrics.increment(f"{self.name}.errors", tags=self.tags)
        else:
            metrics.increment(f"{self.name}.success", tags=self.tags)