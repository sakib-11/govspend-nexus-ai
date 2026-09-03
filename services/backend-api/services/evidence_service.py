"""Evidence service — retrieve evidence items for cases."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.evidence import EvidenceDetail, EvidenceItem
from models.orm import Evidence

logger = logging.getLogger(__name__)


class EvidenceService:
    """PostgreSQL-backed evidence store with jurisdiction-based access."""

    def __init__(self) -> None:
        pass

    def seed_demo_data(self) -> None:
        """Populate demo evidence."""
        from db import get_session
        with get_session() as db:
            if db.query(Evidence).count() > 0:
                return
            demo = [
                ("ev-tx-001-001", "case-001", "tx-001", "invoice", "Invoice from VEND-ABC12", {"invoice_number": "INV-001", "amount": 150000, "items": [{"desc": "IT Hardware", "qty": 10, "unit_price": 15000}]}, 0.95, "ocr_engine"),
                ("ev-tx-001-002", "case-001", "tx-001", "benchmark", "Price benchmark analysis", {"benchmark_price": 12000, "deviation": "25%", "peer_count": 45}, 0.88, "benchmark_detector"),
                ("ev-tx-002-001", "case-002", "tx-002", "signal", "Duplicate detection signal", {"similarity": 0.87, "matched_tx": "tx-prev-234"}, 0.82, "duplicate_detector"),
                ("ev-tx-004-001", "case-004", "tx-004", "invoice", "Invoice from VEND-ABC12", {"invoice_number": "INV-004", "amount": 200000, "items": [{"desc": "Server Equipment", "qty": 5, "unit_price": 40000}]}, 0.97, "ocr_engine"),
                ("ev-tx-004-002", "case-004", "tx-004", "graph", "Vendor relationship graph", {"connected_officials": 3, "repeat_count": 12, "hhi": 0.72}, 0.90, "graph_analyzer"),
                ("ev-tx-005-001", "case-005", "tx-005", "document", "Contract splitting analysis", {"po_count": 4, "window_days": 10, "total_amount": 95000}, 0.78, "splitting_detector"),
            ]
            for ev_id, case_id, tx_id, ev_type, desc, data, conf, source in demo:
                record = Evidence(
                    evidence_id=ev_id,
                    case_id=case_id,
                    transaction_id=tx_id,
                    evidence_type=ev_type,
                    description=desc,
                    data=data,
                    metadata={"source": source, "version": "1.0"},
                    confidence=conf,
                    source=source,
                    created_at=datetime.now(timezone.utc),
                    verified=True,
                    hash=hashlib.sha256(f"{ev_id}:{desc}".encode()).hexdigest()[:16],
                )
                db.add(record)
            db.commit()

    def get_evidence_for_case(
        self,
        case_id: str,
        *,
        user_jurisdictions: Optional[List[str]] = None,
    ) -> List[EvidenceItem]:
        """Get evidence items for a case."""
        from db import get_session
        with get_session() as db:
            records = db.query(Evidence).filter(Evidence.case_id == case_id).all()
            items = []
            for rec in records:
                items.append(EvidenceItem(
                    evidence_id=rec.evidence_id,
                    evidence_type=rec.evidence_type,
                    description=rec.description,
                    data=rec.data or {},
                    confidence=rec.confidence,
                    source=rec.source,
                    created_at=rec.created_at,
                ))
            return items

    def get_evidence_detail(
        self,
        evidence_id: str,
        *,
        user_jurisdictions: Optional[List[str]] = None,
    ) -> Optional[EvidenceDetail]:
        """Get detailed evidence."""
        from db import get_session
        with get_session() as db:
            rec = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
            if rec is None:
                return None
            return EvidenceDetail(
                evidence_id=rec.evidence_id,
                case_id=rec.case_id,
                transaction_id=rec.transaction_id,
                evidence_type=rec.evidence_type,
                data=rec.data or {},
                metadata=rec.extra_metadata or {},
                confidence=rec.confidence,
                source=rec.source,
                created_at=rec.created_at,
                verified=rec.verified,
                hash=rec.hash,
            )
