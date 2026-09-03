"""Service for computing similarities between documents."""

import re
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logging import get_logger
from ..utils.text_processing import TextProcessor

logger = get_logger(__name__)


class SimilarityService:
    """Service for computing field-level and combined document similarities."""

    def __init__(self) -> None:
        self.text_processor = TextProcessor()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def compute_field_similarities(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any],
    ) -> Dict[str, float]:
        """Compute similarity scores for every relevant field pair.

        Returns a dict keyed by field name with similarity ∈ [0, 1].
        """
        similarities: Dict[str, float] = {}

        if doc1.get("document_text") and doc2.get("document_text"):
            similarities["text"] = self._compute_text_similarity(
                doc1["document_text"], doc2["document_text"]
            )

        if doc1.get("vendor_name") and doc2.get("vendor_name"):
            similarities["vendor"] = self._compute_name_similarity(
                doc1["vendor_name"], doc2["vendor_name"]
            )

        if doc1.get("document_number") and doc2.get("document_number"):
            similarities["document_number"] = self._compute_number_similarity(
                doc1["document_number"], doc2["document_number"]
            )

        if doc1.get("amount") is not None and doc2.get("amount") is not None:
            similarities["amount"] = self._compute_amount_similarity(
                doc1["amount"], doc2["amount"]
            )

        if doc1.get("transaction_date") and doc2.get("transaction_date"):
            similarities["date"] = self._compute_date_similarity(
                doc1["transaction_date"], doc2["transaction_date"]
            )

        if doc1.get("line_items") and doc2.get("line_items"):
            similarities["line_items"] = self._compute_line_items_similarity(
                doc1["line_items"], doc2["line_items"]
            )

        return similarities

    async def compute_combined_similarity(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any],
        weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """Compute weighted average of field-level similarities.

        Returns ``(combined_score, field_similarities)``.
        """
        default_weights = {
            "text": 0.30,
            "vendor": 0.25,
            "document_number": 0.15,
            "amount": 0.15,
            "date": 0.10,
            "line_items": 0.05,
        }
        weights = weights or default_weights

        field_sims = await self.compute_field_similarities(doc1, doc2)

        total_score = 0.0
        total_weight = 0.0
        for field, similarity in field_sims.items():
            w = weights.get(field, 0.1)
            total_score += similarity * w
            total_weight += w

        combined_score = total_score / total_weight if total_weight > 0 else 0.0
        return combined_score, field_sims

    # ------------------------------------------------------------------
    # Per-field comparators (private)
    # ------------------------------------------------------------------

    def _compute_text_similarity(self, text1: str, text2: str) -> float:
        """Full-document text similarity using weighted multi-algorithm combo."""
        if not text1 or not text2:
            return 0.0
        return self.text_processor.compute_weighted_similarity(
            text1, text2,
            trigram_weight=0.4,
            levenshtein_weight=0.3,
            sequence_weight=0.3,
        )

    def _compute_name_similarity(self, name1: str, name2: str) -> float:
        """Vendor name similarity (word-overlap + sequence match)."""
        if not name1 or not name2:
            return 0.0

        norm1 = self.text_processor.normalize_text(name1)
        norm2 = self.text_processor.normalize_text(name2)

        if norm1 == norm2:
            return 1.0

        # Word-set overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        overlap = (
            len(words1 & words2) / max(len(words1), len(words2))
            if words1 and words2
            else 0.0
        )

        sequence_sim = SequenceMatcher(None, norm1, norm2).ratio()
        return (overlap * 0.6) + (sequence_sim * 0.4)

    def _compute_number_similarity(self, num1: str, num2: str) -> float:
        """Document / invoice number similarity."""
        if not num1 or not num2:
            return 0.0

        # Strip common prefixes (e.g. INV-, PO-)
        clean1 = re.sub(r"^[A-Z]{0,5}[-]?", "", num1.upper())
        clean2 = re.sub(r"^[A-Z]{0,5}[-]?", "", num2.upper())

        if clean1 == clean2:
            return 1.0
        if clean1 in clean2 or clean2 in clean1:
            return 0.9

        sim = SequenceMatcher(None, clean1, clean2).ratio()

        # Penalise large length differences
        length_ratio = min(len(clean1), len(clean2)) / max(len(clean1), len(clean2))
        if length_ratio < 0.7:
            sim *= length_ratio

        return sim

    def _compute_amount_similarity(self, amount1: float, amount2: float) -> float:
        """Amount similarity — 0 at 10% diff, 1 at identical."""
        if amount1 <= 0 or amount2 <= 0:
            return 0.0

        diff = abs(amount1 - amount2)
        avg = (amount1 + amount2) / 2
        if avg == 0:
            return 0.0

        diff_ratio = diff / avg
        similarity = max(0.0, 1.0 - (diff_ratio / 0.1))  # 10% → 0
        return min(1.0, similarity)

    def _compute_date_similarity(self, date1: date, date2: date) -> float:
        """Date proximity similarity (days-apart based)."""
        if not date1 or not date2:
            return 0.0

        days_diff = abs((date2 - date1).days)
        if days_diff == 0:
            return 1.0
        elif days_diff <= 3:
            return 0.9
        elif days_diff <= 7:
            return 0.8
        elif days_diff <= 15:
            return 0.6
        elif days_diff <= 30:
            return 0.4
        else:
            return max(0.0, 1.0 - (days_diff / 30))

    def _compute_line_items_similarity(
        self,
        items1: List[Dict[str, Any]],
        items2: List[Dict[str, Any]],
    ) -> float:
        """Similarity between two line-item lists via best-match assignment."""
        if not items1 or not items2:
            return 0.0

        similarities: List[float] = []
        for item1 in items1:
            best_match = 0.0
            desc1 = item1.get("description", "")
            amount1 = item1.get("amount", 0)

            for item2 in items2:
                desc2 = item2.get("description", "")
                amount2 = item2.get("amount", 0)

                desc_sim = self.text_processor.compute_weighted_similarity(desc1, desc2)
                amount_sim = (
                    self._compute_amount_similarity(amount1, amount2)
                    if amount1 > 0 and amount2 > 0
                    else 0.0
                )

                item_sim = (desc_sim * 0.6) + (amount_sim * 0.4)
                best_match = max(best_match, item_sim)

            similarities.append(best_match)

        return sum(similarities) / len(similarities) if similarities else 0.0
