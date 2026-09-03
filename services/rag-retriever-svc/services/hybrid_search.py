"""Hybrid search — combine dense (vector) and sparse (keyword) retrieval."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

from config import RAGRetrieverConfig
from models.retrieval import RetrievalResult
from utils.relevance_utils import combine_dense_sparse, normalise_scores

logger = logging.getLogger(__name__)


class HybridSearch:
    """Run dense and sparse searches in parallel, fuse scores."""

    def __init__(
        self,
        vector_search,
        keyword_search,
        embedding_service,
        config: RAGRetrieverConfig,
    ) -> None:
        self.vector = vector_search
        self.keyword = keyword_search
        self.embedding = embedding_service
        self.config = config
        self.dense_w = config.DENSE_WEIGHT
        self.sparse_w = config.SPARSE_WEIGHT

    async def search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        *,
        match_count: int = 10,
        match_threshold: float = 0.65,
        category_filter: Optional[List[str]] = None,
        active_only: bool = True,
    ) -> List[RetrievalResult]:
        """Hybrid search with parallel execution and score fusion."""

        # Ensure we have an embedding
        if query_embedding is None:
            embeddings = await self.embedding.generate_embeddings([query])
            query_embedding = embeddings[0] if embeddings else None
            if query_embedding is None:
                logger.warning("No embedding — falling back to keyword-only")
                return await self.keyword.search(
                    query, match_count=match_count,
                    category_filter=category_filter, active_only=active_only,
                )

        # Fetch extra candidates from each retriever for better fusion
        over_fetch = match_count * 2

        dense_task = self.vector.search(
            query_embedding,
            match_count=over_fetch,
            match_threshold=match_threshold,
            category_filter=category_filter,
            active_only=active_only,
        )
        sparse_task = self.keyword.search(
            query,
            match_count=over_fetch,
            category_filter=category_filter,
            active_only=active_only,
        )

        dense_results, sparse_results = await asyncio.gather(
            dense_task, sparse_task, return_exceptions=True,
        )

        # Gracefully handle exceptions
        if isinstance(dense_results, Exception):
            logger.warning("Dense search failed: %s", dense_results)
            dense_results = []
        if isinstance(sparse_results, Exception):
            logger.warning("Sparse search failed: %s", sparse_results)
            sparse_results = []

        # Normalise scores per retriever
        dense_sims = [r.similarity for r in dense_results]
        sparse_sims = [r.similarity for r in sparse_results]
        dense_norm = normalise_scores(dense_sims)
        sparse_norm = normalise_scores(sparse_sims)

        # Build score maps
        dense_map: Dict[str, float] = {
            r.chunk_id: dense_norm[i] for i, r in enumerate(dense_results)
        }
        sparse_map: Dict[str, float] = {
            r.chunk_id: sparse_norm[i] for i, r in enumerate(sparse_results)
        }

        # Fuse scores
        combined = combine_dense_sparse(dense_map, sparse_map, self.dense_w, self.sparse_w)

        # Build result lookup
        result_lookup: Dict[str, RetrievalResult] = {}
        for r in dense_results:
            result_lookup[r.chunk_id] = r
            result_lookup[r.chunk_id].dense_score = r.similarity
        for r in sparse_results:
            if r.chunk_id not in result_lookup:
                result_lookup[r.chunk_id] = r
            result_lookup[r.chunk_id].sparse_score = r.similarity

        # Sort by fused score
        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)

        final: List[RetrievalResult] = []
        for chunk_id, score in ranked[:match_count]:
            result = result_lookup.get(chunk_id)
            if result is None:
                continue
            result.similarity = round(score, 6)
            result.relevance_confidence = round(score, 6)
            final.append(result)

        return final
