"""Query processor — clean, expand, and enrich queries for retrieval."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from config import RAGRetrieverConfig
from models.retrieval import QueryContext
from utils.text_utils import (
    clean_query,
    extract_key_phrases,
    stem_tokens,
    tokenize,
)

logger = logging.getLogger(__name__)

# Hardcoded domain expansions (used when DB is unavailable)
_DOMAIN_MAP: Dict[str, List[str]] = {
    "procurement": ["purchasing", "acquisition", "sourcing"],
    "fraud": ["misconduct", "irregularity", "abuse"],
    "audit": ["review", "examination", "inspection"],
    "compliance": ["adherence", "conformance", "regulation"],
    "vendor": ["supplier", "contractor", "provider"],
    "invoice": ["bill", "charge", "statement"],
    "duplicate": ["copy", "repeat", "replica"],
    "anomaly": ["outlier", "deviation", "irregularity"],
    "price": ["cost", "rate", "tariff"],
}


class QueryProcessor:
    """Clean, expand, and enrich queries for better retrieval."""

    def __init__(self, db_pool=None, config: Optional[RAGRetrieverConfig] = None) -> None:
        self.db_pool = db_pool
        self.config = config or RAGRetrieverConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_query(
        self,
        query: str,
        context: Optional[QueryContext] = None,
    ) -> Dict[str, Any]:
        """Process and enhance *query* for retrieval.

        Returns a dict with original, cleaned, expanded, tokens, stemmed,
        and key_phrases fields.
        """
        cleaned = clean_query(query)
        key_phrases = extract_key_phrases(cleaned)
        tokens = tokenize(cleaned)
        stemmed = stem_tokens(tokens)

        expanded: Optional[str] = None
        if self.config.QUERY_EXPANSION_ENABLED:
            expanded = await self._expand_query(cleaned, context)

        result: Dict[str, Any] = {
            "original": query,
            "cleaned": cleaned,
            "key_phrases": key_phrases,
            "expanded": expanded or cleaned,
            "tokens": tokens,
            "stemmed": stemmed,
        }

        if context:
            result["context"] = {
                "domain": context.domain,
                "jurisdiction": context.jurisdiction,
                "focus_areas": context.focus_areas,
                "case_id": context.case_id,
            }

        return result

    def build_case_context_query(
        self,
        case_signals: List[Dict[str, Any]],
        case_evidence: List[Dict[str, Any]],
        risk_score: Optional[float] = None,
        risk_tier: Optional[str] = None,
    ) -> str:
        """Build a natural-language query from case signals and evidence."""
        parts: List[str] = []

        if case_signals:
            high = [s for s in case_signals if s.get("signal_value", 0) > 0.7]
            if high:
                descs = [
                    f"{s.get('detector_type', 'unknown')} (score: {s.get('signal_value', 0):.2f})"
                    for s in high[:3]
                ]
                parts.append(f"Risk signals detected: {', '.join(descs)}")

        if case_evidence:
            etypes = list({e.get("evidence_type", "unknown") for e in case_evidence[:3]})
            if etypes:
                parts.append(f"Evidence types: {', '.join(etypes)}")

        if risk_tier:
            parts.append(f"Risk tier: {risk_tier}")
            if risk_tier == "HIGH":
                parts.append("High priority investigation")
            elif risk_tier == "BORDERLINE":
                parts.append("Review required for potential fraud indicators")

        parts.append("Government procurement and financial regulations")
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _expand_query(
        self, query: str, context: Optional[QueryContext],
    ) -> str:
        """Expand *query* with synonyms and domain terms."""
        expanded_terms: List[str] = []

        for word in query.split():
            expanded_terms.append(word)

            # DB synonyms (if pool available)
            synonyms = await self._get_synonyms(word)
            expanded_terms.extend(synonyms[:2])

            # Hardcoded domain expansions
            domain_exp = _DOMAIN_MAP.get(word, [])
            expanded_terms.extend(domain_exp[:1])

        # Deduplicate preserving order
        return " ".join(dict.fromkeys(expanded_terms))

    async def _get_synonyms(self, term: str) -> List[str]:
        """Fetch synonyms from the database (falls back to empty list)."""
        if self.db_pool is None:
            return []
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT synonym FROM query_synonyms
                    WHERE term = $1 OR synonym = $1
                    LIMIT 5
                    """,
                    term,
                )
                return [r["synonym"] for r in rows if r["synonym"] != term]
        except Exception:
            logger.debug("Synonym lookup failed for %s", term)
            return []
