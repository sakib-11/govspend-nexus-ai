"""RAG retriever service — main orchestrator for all retrieval components."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import RAGRetrieverConfig
from models.retrieval import (
    ContextualRetrievalRequest,
    QueryContext,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
)
from services.context_builder import ContextBuilder
from utils.text_utils import truncate

logger = logging.getLogger(__name__)


class RAGRetrieverService:
    """Orchestrate query processing, search, reranking, caching, and metrics."""

    def __init__(
        self,
        db_pool,
        query_processor,
        hybrid_search,
        embedding_service,
        reranker_service,
        config: RAGRetrieverConfig,
    ) -> None:
        self.db_pool = db_pool
        self.qp = query_processor
        self.hybrid = hybrid_search
        self.embedding = embedding_service
        self.reranker = reranker_service
        self.config = config

    # ------------------------------------------------------------------
    # Main retrieval
    # ------------------------------------------------------------------

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        """Full retrieval pipeline: cache → query → search → rerank → respond."""

        start = time.monotonic()
        cache_hit = False

        # 1. Cache check
        cache_key = self._cache_key(request)
        if self.config.CACHE_ENABLED:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                cache_hit = True
                return cached

        # 2. Build context
        ctx = QueryContext(
            domain="government_procurement",
            focus_areas=(request.context or {}).get("focus_areas", []),
            case_id=(request.context or {}).get("case_id"),
            user_roles=(request.context or {}).get("user_roles", []),
        )

        # 3. Process query
        processed = await self.qp.process_query(request.query, ctx)

        # 4. Get embedding
        query_text = processed.get("expanded") or processed.get("cleaned")
        embedding = await self.embedding.generate_embedding(query_text)

        # 5. Search
        strategy = "hybrid"
        results: List[RetrievalResult] = []

        if request.use_hybrid:
            results = await self.hybrid.search(
                query=processed["expanded"],
                query_embedding=embedding,
                match_count=request.match_count * 2,
                match_threshold=request.match_threshold,
                category_filter=request.category_filter,
                active_only=request.active_only,
            )
        else:
            # Dense only
            results = await self.hybrid.vector.search(
                embedding,
                match_count=request.match_count * 2,
                match_threshold=request.match_threshold,
                category_filter=request.category_filter,
                active_only=request.active_only,
            )
            strategy = "dense"

        # 6. Rerank
        if request.rerank and self.config.RERANK_ENABLED:
            results = await self.reranker.rerank(
                query=request.query,
                results=results,
                top_k=self.config.RERANK_TOP_K,
            )

        # 7. Trim
        results = results[: request.match_count]

        # 8. Build response
        elapsed_ms = (time.monotonic() - start) * 1000
        response = RetrievalResponse(
            query=request.query,
            expanded_query=processed.get("expanded"),
            results=results,
            total_results=len(results),
            query_time_ms=round(elapsed_ms, 2),
            strategy_used=strategy,
            cache_hit=cache_hit,
            metadata={
                "match_threshold": request.match_threshold,
                "category_filter": request.category_filter,
                "rerank_applied": request.rerank and self.reranker.is_ready,
            },
        )

        # 9. Cache & metrics
        if self.config.CACHE_ENABLED and not cache_hit:
            await self._set_cache(cache_key, response)
        await self._record_metrics(response)

        return response

    # ------------------------------------------------------------------
    # Contextual retrieval
    # ------------------------------------------------------------------

    async def retrieve_with_context(
        self, request: ContextualRetrievalRequest,
    ) -> RetrievalResponse:
        """Retrieve policies using case signals and evidence as context."""

        query = self.qp.build_case_context_query(
            case_signals=request.case_signals,
            case_evidence=request.case_evidence,
            risk_score=request.risk_score,
            risk_tier=request.risk_tier,
        )

        if request.query_template:
            try:
                query = request.query_template.format(
                    query=query,
                    risk_score=request.risk_score,
                    risk_tier=request.risk_tier,
                )
            except KeyError:
                pass

        # Build category filter from context
        ctx = ContextBuilder.from_case_data(
            request.case_signals, request.case_evidence,
            request.risk_score, request.risk_tier,
        )
        category_filter = ContextBuilder.build_category_filter(
            ctx.focus_areas, request.include_policies,
        )

        retrieval_req = RetrievalRequest(
            query=query,
            query_type="case_based",
            match_count=request.match_count,
            category_filter=category_filter,
            use_hybrid=True,
            rerank=True,
        )

        return await self.retrieve(retrieval_req)

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_key(self, request: RetrievalRequest) -> str:
        data = {
            "q": request.query,
            "n": request.match_count,
            "t": request.match_threshold,
            "c": request.category_filter,
            "h": request.use_hybrid,
            "a": request.active_only,
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

    async def _get_cache(self, key: str) -> Optional[RetrievalResponse]:
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT results FROM retrieval_cache
                    WHERE query_hash = $1 AND expires_at > NOW()
                    """,
                    key,
                )
            if row:
                return RetrievalResponse(**row["results"])
        except Exception:
            logger.debug("Cache read failed")
        return None

    async def _set_cache(self, key: str, response: RetrievalResponse) -> None:
        try:
            expires = datetime.now(timezone.utc) + timedelta(
                seconds=self.config.CACHE_TTL_SECONDS,
            )
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO retrieval_cache (query_hash, query, results, expires_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (query_hash) DO UPDATE
                    SET results = $3, expires_at = $4
                    """,
                    key,
                    response.query,
                    json.dumps(response.model_dump(), default=str),
                    expires,
                )
        except Exception:
            logger.debug("Cache write failed")

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    async def _record_metrics(self, response: RetrievalResponse) -> None:
        try:
            sims = [r.similarity for r in response.results]
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO retrieval_metrics
                        (query_id, query_type, result_count,
                         avg_similarity, max_similarity, min_similarity,
                         latency_ms, cache_hit)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    response.request_id,
                    "general",
                    response.total_results,
                    sum(sims) / len(sims) if sims else 0.0,
                    max(sims) if sims else 0.0,
                    min(sims) if sims else 0.0,
                    response.query_time_ms,
                    response.cache_hit,
                )
        except Exception:
            logger.debug("Metrics write failed")
