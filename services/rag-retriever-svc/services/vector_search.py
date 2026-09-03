"""Vector search — dense retrieval using pgvector cosine similarity."""

from __future__ import annotations

import logging
from typing import List, Optional

from config import RAGRetrieverConfig
from models.retrieval import RetrievalResult

logger = logging.getLogger(__name__)


class VectorSearch:
    """Dense vector search via pgvector cosine distance."""

    def __init__(self, db_pool, embedding_service, config: RAGRetrieverConfig) -> None:
        self.db_pool = db_pool
        self.embedding_service = embedding_service
        self.config = config
        self._dim = config.EMBEDDING_DIMENSION

    async def search(
        self,
        query_embedding: List[float],
        *,
        match_count: int = 10,
        match_threshold: float = 0.65,
        category_filter: Optional[List[str]] = None,
        active_only: bool = True,
        offset: int = 0,
    ) -> List[RetrievalResult]:
        """Return the most similar chunks via cosine similarity."""

        # Pad / truncate to expected dimension
        embedding = self._normalise_dim(query_embedding)
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"

        conditions: List[str] = []
        params: list = [embedding_str, match_threshold]
        idx = 3

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
                1 - (pc.embedding <=> $1::vector) AS similarity,
                pd.title AS document_title,
                pd.category AS document_category,
                pc.metadata
            FROM policy_chunks pc
            JOIN policy_documents pd ON pc.document_id = pd.document_id
            WHERE 1 - (pc.embedding <=> $1::vector) > $2
            {where}
            ORDER BY pc.embedding <=> $1::vector
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([match_count, offset])

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
            return [
                RetrievalResult(
                    chunk_id=str(r["chunk_id"]),
                    document_id=str(r["document_id"]),
                    content=r["content"],
                    similarity=float(r["similarity"]),
                    dense_score=float(r["similarity"]),
                    document_title=r["document_title"],
                    document_category=r["document_category"],
                    metadata=r["metadata"] or {},
                    relevance_confidence=float(r["similarity"]),
                )
                for r in rows
            ]
        except Exception:
            logger.exception("Vector search failed")
            return []

    def _normalise_dim(self, embedding: List[float]) -> List[float]:
        if len(embedding) == self._dim:
            return embedding
        if len(embedding) > self._dim:
            return embedding[: self._dim]
        return embedding + [0.0] * (self._dim - len(embedding))
