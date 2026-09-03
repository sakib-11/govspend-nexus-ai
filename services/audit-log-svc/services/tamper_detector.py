"""Tamper detector — proactive detection of chain integrity violations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from services.audit_verifier import AuditVerifier

logger = logging.getLogger(__name__)


class TamperDetector:
    """Runs integrity checks and invokes an optional alert callback."""

    def __init__(
        self,
        verifier: AuditVerifier,
        *,
        alert_callback: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> None:
        self._verifier = verifier
        self._alert = alert_callback
        self._last_scan: Optional[datetime] = None
        self._anomalies: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def scan(self) -> Dict[str, Any]:
        """Run a full tamper scan and return the report."""
        tampered = self._verifier.detect_tampering()
        summary = self._verifier.get_verification_summary()

        self._last_scan = datetime.now(timezone.utc)

        report: Dict[str, Any] = {
            "scan_timestamp": self._last_scan.isoformat(),
            "tampered_count": len(tampered),
            "tampered_entries": tampered,
            "summary": summary,
            "anomalies": self._classify_anomalies(tampered),
        }

        self._anomalies = report["anomalies"]

        # Fire alert callback if there are anomalies
        if self._anomalies and self._alert:
            try:
                self._alert(self._anomalies)
            except Exception:
                logger.exception("Alert callback failed")

        return report

    # ------------------------------------------------------------------
    # Anomaly classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_anomalies(tampered: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classify tampered entries into anomaly categories."""
        anomalies: List[Dict[str, Any]] = []
        for entry in tampered:
            details = entry.get("verification_details", {})
            issues = entry.get("issues", [])

            anomaly_type = "unknown"
            severity = "warning"

            if details.get("chain_hash_valid") is False:
                anomaly_type = "chain_hash_mismatch"
                severity = "critical"
            elif details.get("data_hash_valid") is False:
                anomaly_type = "data_tampering"
                severity = "critical"
            elif details.get("previous_hash_valid") is False:
                anomaly_type = "chain_link_broken"
                severity = "critical"

            anomalies.append(
                {
                    "audit_id": entry.get("audit_id"),
                    "sequence_number": entry.get("sequence_number"),
                    "anomaly_type": anomaly_type,
                    "severity": severity,
                    "issues": issues,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        return anomalies

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def last_scan(self) -> Optional[datetime]:
        return self._last_scan

    @property
    def anomalies(self) -> List[Dict[str, Any]]:
        return list(self._anomalies)
