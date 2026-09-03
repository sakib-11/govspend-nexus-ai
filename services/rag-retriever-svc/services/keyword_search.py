"""Keyword search — sparse retrieval using PostgreSQL full-text search."""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from config import RAGRetrieverConfig
from models.retrieval import RetrievalResult
from utils.text_utils import build_search_vector

logger = logging.getLogger(__name__)


class KeywordSearch:
    """Sparse retrieval via ``tsvector`` / ``tsquery``."""

    def __init__(self, db_pool, config: RAGRetrieverConfig) -> None:
        self.db_pool = db_pool
        self.config = config

    async def search(
        self,
        query: str,
        *,
        match_count: int = 10,
        category_filter: Optional[List[str]] = None,
        active_only: bool = True,
    ) -> List[RetrievalResult]:
        """Return chunks matching the full-text query."""

        tsquery = build_search_vector(query)
        if not tsquery:
            return []

        conditions: List[str] = []
        params: list = [tsquery]
        idx = 2

        if category_filter:
            conditions.append(f"pd.category = ANY(${idx})")
            params.append(category_filter)
            idx += 1
        if active_only:
            conditions.append("pd.is_active = TRUE")

        where = f"AND {' AND '.join(conditions)}" if conditions else ""

        sql = f"""
            SELECT
                pc.chunk_id,
                pc.document_id,
                pc.content,
                ts_rank(pc.search_vector, to_tsquery('english', $1)) AS similarity,
                pd.title AS document_title,
                pd.category AS document_category,
                pc.metadata
            FROM policy_chunks pc
            JOIN policy_documents pd ON pc.document_id = pd.document_id
            WHERE pc.search_vector @@ to_tsquery('english', $1)
            {where}
            ORDER BY similarity DESC
            LIMIT ${idx}
        """
        params.append(match_count)

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
            return [
                RetrievalResult(
                    chunk_id=str(r["chunk_id"]),
                    document_id=str(r["document_id"]),
                    content=r["content"],
                    similarity=float(r["similarity"]),
                    sparse_score=float(r["similarity"]),
                    document_title=r["document_title"],
                    document_category=r["document_category"],
                    metadata=r["metadata"] or {},
                    relevance_confidence=float(r["similarity"]),
                )
                for r in rows
            ]
        except Exception:
            logger.exception("Keyword search failed")
            return []
