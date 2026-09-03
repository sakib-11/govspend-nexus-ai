"""Serialization helpers for evidence bundles."""

import json
import gzip
from typing import Any, Dict, Optional
from datetime import datetime, date
from decimal import Decimal

from ..models.evidence_bundle import EvidenceBundle, BundleFormat


class _EnhancedEncoder(json.JSONEncoder):
    """Handles types that the default encoder cannot serialize."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, set):
            return sorted(obj)
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        return super().default(obj)


class BundleSerializer:
    """Serialize / deserialize evidence bundles to various formats."""

    @staticmethod
    def to_json(
        bundle: EvidenceBundle,
        format: BundleFormat = BundleFormat.JSON_EXTENDED,
        compress: bool = False,
    ) -> bytes:
        """Serialize bundle to JSON bytes.

        ``compress=True`` applies gzip on top for transport.
        """
        if format == BundleFormat.JSON_COMPACT:
            payload = json.dumps(
                bundle.to_dict(compact=True),
                separators=(",", ":"),
                cls=_EnhancedEncoder,
                default=str,
            )
        elif format == BundleFormat.JSON:
            payload = json.dumps(
                bundle.to_dict(),
                cls=_EnhancedEncoder,
                default=str,
            )
        else:  # JSON_EXTENDED
            payload = json.dumps(
                bundle.to_dict(),
                indent=2,
                cls=_EnhancedEncoder,
                default=str,
            )

        encoded = payload.encode("utf-8")
        if compress:
            encoded = gzip.compress(encoded)
        return encoded

    @staticmethod
    def from_json(data: bytes, compressed: bool = False) -> EvidenceBundle:
        """Deserialize a bundle from JSON bytes."""
        if compressed:
            data = gzip.decompress(data)
        return EvidenceBundle.model_validate_json(data)

    @staticmethod
    def to_db_row(bundle: EvidenceBundle) -> Dict[str, Any]:
        """Convert bundle to a dict suitable for asyncpg INSERT."""
        return {
            "bundle_id": bundle.bundle_id,
            "transaction_id": bundle.transaction_id,
            "version": bundle.version,
            "status": bundle.status.value,
            "bundle_format": bundle.format.value,
            "bundle_data": bundle.to_json(),
            "weights_version": bundle.weights_version,
            "risk_score": bundle.risk_score,
            "risk_tier": bundle.risk_tier,
            "confidence_factor": bundle.confidence_factor,
            "detector_types": bundle.get_detector_types(),
            "evidence_count": bundle.get_evidence_count(),
            "size_bytes": bundle.size_bytes,
            "storage_checksum": bundle.storage_checksum,
            "tags": bundle.tags,
            "metadata": bundle.metadata,
            "assembled_at": bundle.assembled_at,
            "created_at": bundle.created_at,
            "updated_at": bundle.updated_at,
        }

    @staticmethod
    def from_db_row(row: Dict[str, Any]) -> Optional[EvidenceBundle]:
        """Reconstruct a full bundle from a database row.

        Expects the ``bundle_data`` column to contain the full JSON blob.
        """
        bundle_data = row.get("bundle_data")
        if not bundle_data:
            return None

        try:
            if isinstance(bundle_data, str):
                return EvidenceBundle.model_validate_json(bundle_data)
            return EvidenceBundle.model_validate(bundle_data)
        except Exception:
            return None

    @staticmethod
    def evidence_items_to_db_rows(
        bundle_id: str,
        items: list,
    ) -> list:
        """Convert evidence items to dicts for batch INSERT."""
        rows = []
        for item in items:
            rows.append(
                (
                    bundle_id,
                    item.evidence_id,
                    item.source.value,
                    item.source_type,
                    item.confidence,
                    item.relevance_score,
                    json.dumps(item.data, default=str),
                )
            )
        return rows
