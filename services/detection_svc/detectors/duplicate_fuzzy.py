"""Duplicate / Fuzzy Detector.

Detection pipeline:
1. Exact hash matching (invoice_doc_hash) → instant signal = 1.0
2. Fuzzy similarity search across vendor / amount / date window
3. Multi-algorithm weighted similarity scoring per candidate
4. Evidence generation, confidence calculation, and recommendations
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .base import BaseDetector
from ..config import settings
from ..models.detection import DetectionType
from ..models.duplicate import (
    DuplicateMatchType,
    FuzzyMatchCandidate,
    SimilarityMatch,
)
from ..services.duplicate_cache import DuplicateCache
from ..services.similarity_service import SimilarityService
from ..utils.logging import get_logger
from ..utils.text_processing import TextProcessor

logger = get_logger(__name__)


class DuplicateFuzzyDetector(BaseDetector):
    """Detect duplicate or near-duplicate transactions.

    Combines three complementary strategies:
    * **Exact hash** – SHA-256 content fingerprint (signal = 1.0)
    * **Vendor + amount + date** – structural candidate search
    * **Fuzzy similarity** – trigram / Levenshtein / sequence scoring

    Parameters
    ----------
    similarity_service : optional
        Injected similarity service (for testing / customisation).
    duplicate_cache : optional
        Injected Redis cache (for testing / customisation).
    """

    def __init__(
        self,
        similarity_service: Optional[SimilarityService] = None,
        duplicate_cache: Optional[DuplicateCache] = None,
    ) -> None:
        super().__init__(DetectionType.DUPLICATE)
        self.similarity_service = similarity_service or SimilarityService()
        self.duplicate_cache = duplicate_cache or DuplicateCache()
        self.text_processor = TextProcessor()

        # Tuning knobs
        self.amount_tolerance: float = 0.02  # ±2%
        self.date_window_days: int = 30
        self.similarity_threshold: float = 0.85
        self.max_candidates: int = 50
        self.max_results: int = 10

        logger.info("DuplicateFuzzyDetector initialised")

    # ------------------------------------------------------------------
    # BaseDetector interface
    # ------------------------------------------------------------------

    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Run duplicate detection on *transaction*."""
        start_time = asyncio.get_event_loop().time()

        try:
            tx_data = self._extract_transaction_data(transaction)

            # Step 1: exact hash
            hash_duplicate = await self._check_hash_duplicate(tx_data)
            if hash_duplicate:
                logger.info("Exact hash duplicate found for %s", tx_data["transaction_id"])
                result = self._create_hash_duplicate_result(tx_data)
            else:
                # Step 2: fuzzy candidates → similarity scoring
                candidates = await self._search_fuzzy_matches(tx_data)
                result = await self._process_fuzzy_matches(tx_data, candidates)

            # Metadata
            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            result["processing_time_ms"] = int(elapsed)
            result["computed_at"] = datetime.utcnow().isoformat()

            # Cache
            await self.duplicate_cache.cache_result(tx_data["transaction_id"], result)

            logger.info(
                "Duplicate detection completed for %s: signal=%.3f, matches=%s",
                tx_data["transaction_id"],
                result["signal_value"],
                result["duplicate_count"],
            )
            return result

        except Exception as exc:
            logger.error("Duplicate detection failed: %s", exc, exc_info=True)
            return self._create_error_result(transaction, str(exc))

    def get_weight(self) -> float:
        return 0.20

    def get_required_fields(self) -> List[str]:
        return [
            "vendor_token",
            "vendor_name",
            "amount",
            "transaction_date",
            "invoice_doc_hash",
        ]

    # ------------------------------------------------------------------
    # Step 1 — data extraction
    # ------------------------------------------------------------------

    def _extract_transaction_data(
        self, transaction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalise raw transaction dict into internal shape."""
        return {
            "transaction_id": transaction.get("transaction_id", str(uuid.uuid4())),
            "vendor_token": transaction.get("vendor_token", ""),
            "vendor_name": transaction.get("vendor_name", ""),
            "amount": float(transaction.get("amount", 0)),
            "transaction_date": transaction.get(
                "transaction_date", datetime.utcnow().date()
            ),
            "document_number": transaction.get("document_number", ""),
            "invoice_hash": transaction.get("invoice_doc_hash", ""),
            "document_text": transaction.get("document_text", ""),
            "line_items": transaction.get("line_items", []),
            "category": transaction.get("category", ""),
            "region": transaction.get("region", ""),
        }

    # ------------------------------------------------------------------
    # Step 2 — exact hash lookup
    # ------------------------------------------------------------------

    async def _check_hash_duplicate(self, tx_data: Dict[str, Any]) -> bool:
        """Return ``True`` if the invoice hash already exists."""
        invoice_hash = tx_data.get("invoice_hash", "")
        if not invoice_hash:
            return False

        # Check cache first
        cached = await self.duplicate_cache.get_hash_duplicate(invoice_hash)
        if cached is not None:
            return cached

        exists = await self._query_hash_match(invoice_hash)
        await self.duplicate_cache.cache_hash_duplicate(invoice_hash, exists)
        return exists

    async def _query_hash_match(self, invoice_hash: str) -> bool:
        """Query the database for an existing hash.

        This is a *stub* that always returns ``False`` until a real
        database adapter is wired in.
        """
        # TODO: wire up asyncpg pool
        # async with db_pool.acquire() as conn:
        #     row = await conn.fetchrow(
        #         "SELECT 1 FROM transactions WHERE invoice_doc_hash = $1 LIMIT 1",
        #         invoice_hash,
        #     )
        #     return row is not None
        return False

    # ------------------------------------------------------------------
    # Step 3 — fuzzy candidate search
    # ------------------------------------------------------------------

    async def _search_fuzzy_matches(
        self, tx_data: Dict[str, Any]
    ) -> List[FuzzyMatchCandidate]:
        """Collect candidate transactions for similarity scoring."""
        candidates: List[FuzzyMatchCandidate] = []

        # Strategy A: same vendor, amount ±tolerance, date window
        vendor_matches = await self._query_potential_duplicates(
            vendor_token=tx_data["vendor_token"],
            amount=tx_data["amount"],
            date_window=self.date_window_days,
            amount_tolerance=self.amount_tolerance,
        )
        candidates.extend(vendor_matches)

        # Strategy B: vendor name fallback (when token not available)
        if not tx_data.get("vendor_token"):
            name_matches = await self._query_by_vendor_name(
                vendor_name=tx_data["vendor_name"],
                amount=tx_data["amount"],
                date_window=self.date_window_days,
            )
            candidates.extend(name_matches)

        # Strategy C: amount-only (catch different-vendor duplicates)
        amount_matches = await self._query_by_amount_only(
            amount=tx_data["amount"],
            date_window=self.date_window_days,
        )
        candidates.extend(amount_matches)

        # De-dupe and drop self
        candidates = self._deduplicate_candidates(candidates, tx_data["transaction_id"])
        return candidates[: self.max_candidates]

    async def _query_potential_duplicates(
        self,
        vendor_token: str,
        amount: float,
        date_window: int,
        amount_tolerance: float,
    ) -> List[FuzzyMatchCandidate]:
        """Query by vendor + amount range + date window.

        Stub — returns ``[]`` until a database adapter is wired in.
        """
        # TODO: wire up asyncpg pool
        return []

    async def _query_by_vendor_name(
        self, vendor_name: str, amount: float, date_window: int
    ) -> List[FuzzyMatchCandidate]:
        """Query by approximate vendor name (trigram / soundex)."""
        # TODO: implement pg_trgm or application-level name search
        return []

    async def _query_by_amount_only(
        self, amount: float, date_window: int
    ) -> List[FuzzyMatchCandidate]:
        """Query by amount range alone."""
        # TODO: wire up asyncpg pool
        return []

    def _deduplicate_candidates(
        self,
        candidates: List[FuzzyMatchCandidate],
        current_transaction_id: str,
    ) -> List[FuzzyMatchCandidate]:
        """Remove duplicates and the current transaction."""
        seen: set = set()
        unique: List[FuzzyMatchCandidate] = []
        for c in candidates:
            if c.transaction_id == current_transaction_id:
                continue
            if c.transaction_id in seen:
                continue
            seen.add(c.transaction_id)
            unique.append(c)
        return unique

    # ------------------------------------------------------------------
    # Step 4 — similarity scoring
    # ------------------------------------------------------------------

    async def _process_fuzzy_matches(
        self,
        tx_data: Dict[str, Any],
        candidates: List[FuzzyMatchCandidate],
    ) -> Dict[str, Any]:
        """Score each candidate and produce the final result dict."""
        if not candidates:
            return self._create_no_match_result(tx_data)

        matches: List[SimilarityMatch] = []
        for candidate in candidates:
            match = await self._compute_similarity(tx_data, candidate)
            if match.similarity_score >= self.similarity_threshold:
                matches.append(match)

        if not matches:
            return self._create_no_match_result(tx_data)

        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        matches = matches[: self.max_results]

        return self._create_fuzzy_match_result(tx_data, matches)

    async def _compute_similarity(
        self,
        tx_data: Dict[str, Any],
        candidate: FuzzyMatchCandidate,
    ) -> SimilarityMatch:
        """Full field-level similarity between *tx_data* and *candidate*."""
        doc1 = {
            "vendor_name": tx_data["vendor_name"],
            "document_number": tx_data["document_number"],
            "amount": tx_data["amount"],
            "transaction_date": tx_data["transaction_date"],
            "document_text": tx_data.get("document_text", ""),
            "line_items": tx_data.get("line_items", []),
        }
        doc2 = {
            "vendor_name": candidate.vendor_name,
            "document_number": candidate.document_number,
            "amount": candidate.amount,
            "transaction_date": candidate.transaction_date,
            "document_text": candidate.document_text or "",
            "line_items": candidate.line_items or [],
        }

        field_sims = await self.similarity_service.compute_field_similarities(doc1, doc2)
        combined_score, _ = await self.similarity_service.compute_combined_similarity(
            doc1,
            doc2,
            weights={
                "text": 0.30,
                "vendor": 0.25,
                "document_number": 0.15,
                "amount": 0.15,
                "date": 0.10,
                "line_items": 0.05,
            },
        )

        evidence = self._build_similarity_evidence(combined_score, field_sims, doc1, doc2)

        return SimilarityMatch(
            transaction_id=candidate.transaction_id,
            vendor_id=candidate.vendor_token,
            vendor_name=candidate.vendor_name,
            document_number=candidate.document_number,
            amount=candidate.amount,
            transaction_date=candidate.transaction_date,
            similarity_score=combined_score,
            match_type=DuplicateMatchType.FUZZY_SIMILARITY,
            evidence=evidence,
            matched_fields=field_sims,
        )

    def _build_similarity_evidence(
        self,
        combined_score: float,
        field_sims: Dict[str, float],
        doc1: Dict[str, Any],
        doc2: Dict[str, Any],
    ) -> List[str]:
        """Produce human-readable evidence bullets."""
        evidence: List[str] = [f"Overall similarity score: {combined_score:.3f}"]

        if field_sims.get("vendor", 0) > 0.8:
            evidence.append(
                f"Vendor name matches: '{doc1['vendor_name']}' ↔ '{doc2['vendor_name']}'"
            )

        if field_sims.get("document_number", 0) > 0.8:
            evidence.append(
                f"Document number similar: '{doc1['document_number']}' ↔ '{doc2['document_number']}'"
            )

        if field_sims.get("amount", 0) > 0.8:
            evidence.append(
                f"Amount within tolerance: ${doc1['amount']:.2f} ↔ ${doc2['amount']:.2f}"
            )

        if field_sims.get("text", 0) > 0.7:
            evidence.append("Document text shows significant similarity")

        d1 = doc1.get("transaction_date")
        d2 = doc2.get("transaction_date")
        if d1 and d2:
            days_diff = abs((d2 - d1).days)
            if days_diff <= 3:
                evidence.append(f"Transactions within {days_diff} days")

        if field_sims.get("line_items", 0) > 0.7:
            evidence.append("Line items show significant overlap")

        return evidence

    # ------------------------------------------------------------------
    # Result factories
    # ------------------------------------------------------------------

    def _create_hash_duplicate_result(
        self, tx_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Result for an exact hash hit."""
        return {
            "signal_value": 1.0,
            "confidence": 1.0,
            "match_type": DuplicateMatchType.EXACT_HASH,
            "matches": [],
            "best_match": None,
            "duplicate_count": 1,
            "hash_duplicate": True,
            "fuzzy_matches": [],
            "detection_methods_used": ["exact_hash"],
            "evidence": [
                f"Exact hash match found: {tx_data.get('invoice_hash', '')[:16]}…",
                "Transaction is an exact duplicate",
                "This requires immediate review",
            ],
            "recommendations": [
                "Flag for immediate investigation",
                "Check for duplicate payment",
                "Verify if this is a legitimate duplicate transaction",
            ],
        }

    def _create_fuzzy_match_result(
        self,
        tx_data: Dict[str, Any],
        matches: List[SimilarityMatch],
    ) -> Dict[str, Any]:
        """Result for one or more fuzzy matches above threshold."""
        best_match = matches[0]
        best_score = best_match.similarity_score

        # Map similarity to a [0, 1] signal via piece-wise transform
        signal_value = (
            min(1.0, (best_score - 0.6) / 0.4) if best_score > 0.6 else 0.0
        )
        confidence = self._calculate_fuzzy_confidence(matches)
        evidence = self._build_fuzzy_evidence(best_match, matches)
        recommendations = self._build_fuzzy_recommendations(best_score, len(matches))

        return {
            "signal_value": signal_value,
            "confidence": confidence,
            "match_type": DuplicateMatchType.FUZZY_SIMILARITY,
            "matches": [m.model_dump(mode="json") for m in matches],
            "best_match": best_match.model_dump(mode="json"),
            "duplicate_count": len(matches),
            "hash_duplicate": False,
            "fuzzy_matches": [m.model_dump(mode="json") for m in matches],
            "detection_methods_used": ["fuzzy_similarity"],
            "evidence": evidence,
            "recommendations": recommendations,
        }

    def _create_no_match_result(
        self, tx_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Result when no duplicates or near-duplicates are found."""
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "match_type": DuplicateMatchType.NO_MATCH,
            "matches": [],
            "best_match": None,
            "duplicate_count": 0,
            "hash_duplicate": False,
            "fuzzy_matches": [],
            "detection_methods_used": ["none"],
            "evidence": [
                "No duplicate transactions found",
                f"Checked {self.date_window_days} days of history",
                "No matches above similarity threshold",
            ],
            "recommendations": [
                "No action required",
                "Transaction appears to be unique",
            ],
        }

    def _create_error_result(
        self, transaction: Dict[str, Any], error: str
    ) -> Dict[str, Any]:
        """Result when detection fails."""
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "match_type": DuplicateMatchType.NO_MATCH,
            "matches": [],
            "best_match": None,
            "duplicate_count": 0,
            "hash_duplicate": False,
            "fuzzy_matches": [],
            "detection_methods_used": ["error"],
            "evidence": [f"Detection failed: {error}"],
            "recommendations": [
                "Retry detection",
                "Check transaction data completeness",
            ],
            "transaction_id": transaction.get("transaction_id", str(uuid.uuid4())),
            "error": error,
        }

    # ------------------------------------------------------------------
    # Confidence & evidence builders
    # ------------------------------------------------------------------

    def _calculate_fuzzy_confidence(
        self, matches: List[SimilarityMatch]
    ) -> float:
        """Compute overall confidence from the match list.

        Factors:
        * Best-match similarity score
        * Number of high-scoring matches (consistency signal)
        * Strength of the vendor field (strongest discriminator)
        """
        if not matches:
            return 0.0

        base = min(1.0, matches[0].similarity_score)

        # Multiple high-scoring matches increase confidence
        high_count = sum(1 for m in matches if m.similarity_score > 0.8)
        if high_count > 1:
            base = min(1.0, base + 0.05 * high_count)

        # Strong vendor match adds confidence
        if matches[0].matched_fields and matches[0].matched_fields.get("vendor", 0) > 0.9:
            base = min(1.0, base + 0.05)

        return min(1.0, base)

    def _build_fuzzy_evidence(
        self,
        best_match: SimilarityMatch,
        all_matches: List[SimilarityMatch],
    ) -> List[str]:
        """Build evidence bullets for a fuzzy match result."""
        evidence: List[str] = [
            f"Best match: {best_match.vendor_name} "
            f"(similarity: {best_match.similarity_score:.3f})",
            f"Amount: ${best_match.amount:.2f} – Date: {best_match.transaction_date}",
        ]

        for field, score in best_match.matched_fields.items():
            if score > 0.7:
                evidence.append(
                    f"{field.replace('_', ' ').title()} similarity: {score:.3f}"
                )

        if len(all_matches) > 1:
            evidence.append(f"Found {len(all_matches)} potential duplicates")

        return evidence

    def _build_fuzzy_recommendations(
        self, best_score: float, duplicate_count: int
    ) -> List[str]:
        """Produce actionable recommendations from match quality."""
        recs: List[str] = []

        if best_score >= 0.95:
            recs.append("Highly likely duplicate – prioritise investigation")
            recs.append("Verify if payment was already processed")
            recs.append("Check for duplicate invoice submission")
        elif best_score >= 0.85:
            recs.append("Strong potential duplicate – recommend review")
            recs.append("Compare line items and supporting documents")
        elif best_score >= 0.70:
            recs.append("Similar transaction found – consider secondary review")
            recs.append("Check for regular patterns or authorised repeats")

        if duplicate_count > 2:
            recs.append("Multiple matches found – investigate pattern")
            recs.append("Review vendor relationship and billing patterns")

        if best_score < 0.85:
            recs.append(
                "Similarity below threshold – may be legitimate similar transaction"
            )

        return recs
