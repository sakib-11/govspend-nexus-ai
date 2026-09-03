"""Audit verifier — verify individual entries and full chain integrity."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.audit import AuditEntry, AuditEventType, AuditVerificationResult
from models.verification import VerificationReport
from services.hash_chain_manager import HashChainManager
from utils.hash_utils import compute_chain_hash, compute_data_hash

logger = logging.getLogger(__name__)


class AuditVerifier:
    """Verify audit entries and the hash chain."""

    def __init__(self, chain_manager: HashChainManager) -> None:
        self._chain = chain_manager

    # ------------------------------------------------------------------
    # Single-entry verification
    # ------------------------------------------------------------------

    def verify_entry(self, audit_id: str) -> AuditVerificationResult:
        """Verify a single audit entry's data hash and chain hash."""
        record = self._chain.store.fetch_by_audit_id(audit_id)
        if record is None:
            return AuditVerificationResult(
                audit_id=audit_id,
                verified=False,
                chain_valid=False,
                tampered=True,
                previous_hash_valid=False,
                data_hash_valid=False,
                chain_sequence_valid=False,
                verification_details={"error": "entry_not_found"},
            )

        # Recompute data hash
        data_payload = {
            "audit_id": record["audit_id"],
            "event_type": record["event_type"],
            "user_id": record["user_id"],
            "resource_type": record["resource_type"],
            "resource_id": record.get("resource_id"),
            "action": record["action"],
            "timestamp": record.get("timestamp", ""),
        }
        computed_data_hash = compute_data_hash(data_payload)
        data_hash_valid = computed_data_hash == record.get("data_hash")

        # Recompute chain hash
        computed_chain_hash = compute_chain_hash(
            record["previous_hash"],
            record["data_hash"],
            self._chain._salt,
            record["sequence_number"],
        )
        chain_hash_valid = computed_chain_hash == record.get("current_hash")

        # Previous-hash linkage
        prev_hash_valid = True
        seq = record.get("sequence_number", 0)
        if seq > 1:
            prev_records = self._chain.store.fetch_entries(seq - 1, seq - 1)
            if prev_records:
                prev_hash_valid = record["previous_hash"] == prev_records[0]["current_hash"]

        all_valid = data_hash_valid and chain_hash_valid and prev_hash_valid

        # Persist verification result
        self._chain.store.update_entry(
            audit_id,
            verified=all_valid,
            verified_at=datetime.now(timezone.utc),
        )

        return AuditVerificationResult(
            audit_id=audit_id,
            verified=all_valid,
            chain_valid=chain_hash_valid,
            tampered=not all_valid,
            previous_hash_valid=prev_hash_valid,
            data_hash_valid=data_hash_valid,
            chain_sequence_valid=True,
            verification_details={
                "data_hash_valid": data_hash_valid,
                "chain_hash_valid": chain_hash_valid,
                "previous_hash_valid": prev_hash_valid,
            },
        )

    # ------------------------------------------------------------------
    # Full chain verification
    # ------------------------------------------------------------------

    def verify_chain(self, start_sequence: Optional[int] = None) -> Dict[str, Any]:
        """Walk the chain and verify integrity."""
        return self._chain.verify_chain_integrity(start_sequence)

    # ------------------------------------------------------------------
    # Tamper detection
    # ------------------------------------------------------------------

    def detect_tampering(self) -> List[Dict[str, Any]]:
        """Scan every entry and return the list of tampered ones."""
        tampered: List[Dict[str, Any]] = []
        _, _, total = self._chain.get_chain_state()
        if total == 0:
            return tampered

        for seq in range(1, total + 1):
            entries = self._chain.store.fetch_entries(seq, seq)
            if not entries:
                continue
            entry = entries[0]
            result = self.verify_entry(entry["audit_id"])
            if result.tampered:
                tampered.append(
                    {
                        "audit_id": entry["audit_id"],
                        "sequence_number": seq,
                        "verification_details": result.verification_details,
                    }
                )
        return tampered

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_verification_summary(self) -> Dict[str, Any]:
        """Return aggregate verification stats."""
        _, _, total = self._chain.get_chain_state()
        chain_status = self._chain.get_chain_status()

        verified_count = 0
        tampered_count = 0
        for seq in range(1, total + 1):
            entries = self._chain.store.fetch_entries(seq, seq)
            if entries and entries[0].get("verified"):
                verified_count += 1
            else:
                tampered_count += 1

        return {
            "total_entries": total,
            "verified_entries": verified_count,
            "tampered_entries": tampered_count,
            "chain_valid": chain_status.is_valid,
            "chain_total": chain_status.total_entries,
        }
