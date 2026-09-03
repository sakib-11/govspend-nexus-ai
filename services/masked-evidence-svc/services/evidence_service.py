"""Evidence service — persist masked transactions, cases, and evidence records."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from models.evidence import (
    EvidenceQuery,
    MaskedCase,
    MaskedEvidenceRecord,
    MaskedTransaction,
)
from services.masking_service import MaskingService
from services.tokenization_service import TokenizationService
from utils.crypto_utils import generate_evidence_hash

logger = logging.getLogger(__name__)

# Default fields to mask per entity type
_TRANSACTION_FIELDS = ["vendor_name", "vendor_id", "invoice_number", "po_number", "account_number"]
_CASE_FIELDS = _TRANSACTION_FIELDS + ["official_name", "official_id", "official_email", "official_phone", "vendor_pan", "vendor_gst", "vendor_address"]
_EVIDENCE_FIELDS = ["vendor_name", "vendor_id", "official_name", "invoice_number"]


class EvidenceService:
    """Manage masked evidence in the database."""

    def __init__(
        self,
        db_pool,
        masking_service: MaskingService,
        tokenization_service: TokenizationService,
    ) -> None:
        self.db_pool = db_pool
        self.masking = masking_service
        self.tokenization = tokenization_service

    # ------------------------------------------------------------------
    # Store operations
    # ------------------------------------------------------------------

    async def store_masked_transaction(
        self,
        transaction_id: UUID,
        raw_data: Dict[str, Any],
    ) -> MaskedTransaction:
        """Mask and persist a transaction."""
        masked_data, tokens = await self.masking.mask_data(
            raw_data=raw_data,
            fields_to_mask=_TRANSACTION_FIELDS,
            entity_type="transaction",
        )

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO masked_transactions (transaction_id, masked_data, tokens)
                VALUES ($1, $2, $3)
                ON CONFLICT (transaction_id) DO UPDATE
                SET masked_data = $2, tokens = $3, updated_at = NOW()
                """,
                str(transaction_id),
                json.dumps(masked_data, default=str),
                json.dumps(tokens, default=str),
            )

        logger.info("Stored masked transaction %s", transaction_id)
        return MaskedTransaction(
            transaction_id=transaction_id,
            masked_data=masked_data,
            tokens=tokens,
        )

    async def store_masked_case(
        self,
        case_id: UUID,
        transaction_id: UUID,
        case_data: Dict[str, Any],
        risk_score: float,
        tier: str,
        jurisdiction_id: str,
    ) -> MaskedCase:
        """Mask and persist a case."""
        masked_data, tokens = await self.masking.mask_data(
            raw_data=case_data,
            fields_to_mask=_CASE_FIELDS,
            entity_type="case",
        )

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO masked_cases
                    (case_id, transaction_id, masked_case_data, tokens,
                     risk_score, tier, jurisdiction_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (case_id) DO UPDATE
                SET masked_case_data = $3, tokens = $4, risk_score = $5,
                    tier = $6, jurisdiction_id = $7, updated_at = NOW()
                """,
                str(case_id),
                str(transaction_id),
                json.dumps(masked_data, default=str),
                json.dumps(tokens, default=str),
                risk_score,
                tier,
                jurisdiction_id,
            )

        logger.info("Stored masked case %s", case_id)
        return MaskedCase(
            case_id=case_id,
            transaction_id=transaction_id,
            masked_case_data=masked_data,
            tokens=tokens,
            risk_score=risk_score,
            tier=tier,
            jurisdiction_id=jurisdiction_id,
        )

    async def store_masked_evidence(
        self,
        case_id: UUID,
        evidence_type: str,
        evidence_data: Dict[str, Any],
    ) -> MaskedEvidenceRecord:
        """Mask and persist an evidence record."""
        evidence_id = uuid4()

        masked_data, tokens = await self.masking.mask_data(
            raw_data=evidence_data,
            fields_to_mask=_EVIDENCE_FIELDS,
            entity_type="evidence",
        )

        evidence_hash = generate_evidence_hash(masked_data)

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO masked_evidence
                    (evidence_id, case_id, evidence_type, masked_data,
                     tokens, evidence_hash)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                str(evidence_id),
                str(case_id),
                evidence_type,
                json.dumps(masked_data, default=str),
                json.dumps(tokens, default=str),
                evidence_hash,
            )

        logger.info("Stored masked evidence %s for case %s", evidence_id, case_id)
        return MaskedEvidenceRecord(
            evidence_id=evidence_id,
            case_id=case_id,
            evidence_type=evidence_type,
            masked_data=masked_data,
            tokens=tokens,
            evidence_hash=evidence_hash,
        )

    # ------------------------------------------------------------------
    # Retrieve operations
    # ------------------------------------------------------------------

    async def get_masked_case(
        self,
        case_id: UUID,
        *,
        jurisdiction_id: Optional[str] = None,
    ) -> Optional[MaskedCase]:
        """Fetch a masked case, optionally enforcing jurisdiction."""
        async with self.db_pool.acquire() as conn:
            if jurisdiction_id:
                row = await conn.fetchrow(
                    "SELECT * FROM masked_cases WHERE case_id = $1 AND jurisdiction_id = $2",
                    str(case_id), jurisdiction_id,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM masked_cases WHERE case_id = $1",
                    str(case_id),
                )

        if not row:
            return None

        return MaskedCase(
            case_id=UUID(row["case_id"]),
            transaction_id=UUID(row["transaction_id"]),
            masked_case_data=row["masked_case_data"],
            tokens=row["tokens"],
            risk_score=float(row["risk_score"]),
            tier=row["tier"],
            jurisdiction_id=row["jurisdiction_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_masked_evidence(
        self, evidence_id: UUID,
    ) -> Optional[MaskedEvidenceRecord]:
        """Fetch a single masked evidence record."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM masked_evidence WHERE evidence_id = $1",
                str(evidence_id),
            )

        if not row:
            return None

        return MaskedEvidenceRecord(
            evidence_id=UUID(row["evidence_id"]),
            case_id=UUID(row["case_id"]),
            evidence_type=row["evidence_type"],
            masked_data=row["masked_data"],
            tokens=row["tokens"],
            evidence_hash=row.get("evidence_hash"),
            created_at=row["created_at"],
        )

    async def query_evidence(
        self, query: EvidenceQuery,
    ) -> List[Dict[str, Any]]:
        """Query masked evidence with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if query.case_id:
            conditions.append(f"case_id = ${idx}")
            params.append(str(query.case_id))
            idx += 1

        if query.evidence_type:
            conditions.append(f"evidence_type = ${idx}")
            params.append(query.evidence_type)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM masked_evidence {where}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx + 1}
                """,
                *params, query.limit, query.offset,
            )

        return [dict(r) for r in rows]
