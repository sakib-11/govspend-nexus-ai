"""Data export — export audit entries in CSV, JSON, and NDJSON formats."""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.audit import AuditEntry, AuditQuery
from services.audit_retriever import AuditRetriever

logger = logging.getLogger(__name__)


class DataExporter:
    """Export audit log data in various formats.

    Supports:
      - JSON (pretty-printed array)
      - NDJSON (newline-delimited JSON)
      - CSV
      - Summary report (aggregated statistics)

    In production, exports should be written to S3/blob storage
    and a pre-signed URL returned, rather than returning the full
    payload in the HTTP response.
    """

    def __init__(self, retriever: AuditRetriever) -> None:
        self._retriever = retriever

    def export_json(
        self,
        entries: List[Dict[str, Any]],
        *,
        pretty: bool = True,
    ) -> str:
        """Export entries as a JSON array string."""
        return json.dumps(
            [self._serialise_entry(e) for e in entries],
            indent=2 if pretty else None,
            default=str,
        )

    def export_ndjson(self, entries: List[Dict[str, Any]]) -> str:
        """Export entries as newline-delimited JSON."""
        lines = [json.dumps(self._serialise_entry(e), default=str) for e in entries]
        return "\n".join(lines)

    def export_csv(self, entries: List[Dict[str, Any]]) -> str:
        """Export entries as a CSV string with headers."""
        if not entries:
            return ""

        # Flatten key fields into columns
        headers = [
            "audit_id", "event_type", "user_id", "resource_type", "resource_id",
            "action", "severity", "status", "timestamp", "duration_ms",
            "ip_address", "jurisdiction_id", "verified", "sequence_number",
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()

        for entry in entries:
            row = {h: entry.get(h, "") for h in headers}
            # Flatten nested structures
            if "hash_chain" in entry and entry["hash_chain"]:
                row["sequence_number"] = entry["hash_chain"].get("sequence_number", "")
            writer.writerow(row)

        return output.getvalue()

    def generate_summary_report(
        self,
        entries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate an aggregate summary report from entries."""
        if not entries:
            return {
                "total_entries": 0,
                "report_generated_at": datetime.now(timezone.utc).isoformat(),
            }

        # Aggregate by event type
        by_event_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_user: Dict[str, int] = {}
        durations: List[float] = []
        errors = 0

        for e in entries:
            et = e.get("event_type", "unknown")
            by_event_type[et] = by_event_type.get(et, 0) + 1

            sev = e.get("severity", "info")
            by_severity[sev] = by_severity.get(sev, 0) + 1

            uid = e.get("user_id", "unknown")
            by_user[uid] = by_user.get(uid, 0) + 1

            if e.get("duration_ms") is not None:
                durations.append(float(e["duration_ms"]))

            if sev in ("error", "critical"):
                errors += 1

        verified = sum(1 for e in entries if e.get("verified"))

        return {
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(entries),
            "by_event_type": by_event_type,
            "by_severity": by_severity,
            "top_users": dict(sorted(by_user.items(), key=lambda x: -x[1])[:10]),
            "error_rate": round(errors / len(entries), 4),
            "verification_rate": round(verified / len(entries), 4),
            "duration_stats": {
                "count": len(durations),
                "avg_ms": round(sum(durations) / len(durations), 3) if durations else 0,
                "min_ms": min(durations) if durations else 0,
                "max_ms": max(durations) if durations else 0,
            },
        }

    @staticmethod
    def _serialise_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all values are JSON-serialisable."""
        serialised: Dict[str, Any] = {}
        for k, v in entry.items():
            if isinstance(v, datetime):
                serialised[k] = v.isoformat()
            elif isinstance(v, dict):
                serialised[k] = DataExporter._serialise_entry(v)
            else:
                serialised[k] = v
        return serialised
