"""Retrieval routes — REST API for RAG search, contextual search, and feedback."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status

from models.retrieval import (
    ContextualRetrievalRequest,
    RetrievalFeedback,
    RetrievalRequest,
    RetrievalResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/retrieval", tags=["retrieval"])


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_service(request: Request, name: str) -> Any:
    svc = getattr(request.app.state, name, None)
    if svc is None:
        raise HTTPException(status_code=503, detail=f"Service {name} unavailable")
    return svc


def _require_auth(request: Request) -> Any:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def _require_admin(request: Request) -> Any:
    user = _require_auth(request)
    roles = [r.value if hasattr(r, "value") else str(r) for r in getattr(user, "roles", [])]
    if "super_admin" not in roles and "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# ------------------------------------------------------------------
# Search endpoints
# ------------------------------------------------------------------

@router.post("/search", response_model=RetrievalResponse)
async def search_policies(body: RetrievalRequest, request: Request) -> RetrievalResponse:
    """Search for relevant policy chunks using hybrid retrieval."""
    _require_auth(request)
    retriever = _get_service(request, "retriever_service")

    try:
        return await retriever.retrieve(body)
    except Exception as exc:
        logger.exception("Search failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval failed: {exc}",
        )


@router.post("/contextual", response_model=RetrievalResponse)
async def contextual_search(
    body: ContextualRetrievalRequest, request: Request,
) -> RetrievalResponse:
    """Search with case context (signals + evidence)."""
    _require_auth(request)
    retriever = _get_service(request, "retriever_service")

    try:
        return await retriever.retrieve_with_context(body)
    except Exception as exc:
        logger.exception("Contextual search failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Contextual retrieval failed: {exc}",
        )


@router.get("/search/quick", response_model=RetrievalResponse)
async def quick_search(
    request: Request,
    query: str = Query(..., min_length=1, max_length=5000),
    match_count: int = Query(default=5, ge=1, le=20),
) -> RetrievalResponse:
    """Quick search endpoint for testing / prototyping."""
    _require_auth(request)
    retriever = _get_service(request, "retriever_service")

    req = RetrievalRequest(query=query, match_count=match_count, use_hybrid=True, rerank=True)
    try:
        return await retriever.retrieve(req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# Feedback
# ------------------------------------------------------------------

@router.post("/feedback")
async def submit_feedback(body: RetrievalFeedback, request: Request) -> Dict[str, str]:
    """Submit relevance feedback for a retrieval result."""
    user = _require_auth(request)
    db_pool = _get_service(request, "db_pool")

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO retrieval_feedback
                    (query_id, chunk_id, relevance_score, user_id, feedback_type, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                body.query_id,
                body.chunk_id,
                body.relevance_score,
                getattr(user, "user_id", "anonymous"),
                body.feedback_type,
                body.metadata,
            )
        return {"status": "feedback recorded"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# Admin: stats & cache
# ------------------------------------------------------------------

@router.get("/stats")
async def get_retrieval_stats(
    request: Request,
    days: int = Query(default=7, ge=1, le=365),
) -> Dict[str, Any]:
    """Get retrieval performance statistics (admin only)."""
    _require_admin(request)
    db_pool = _get_service(request, "db_pool")

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)                       AS total_queries,
                    AVG(latency_ms)                AS avg_latency,
                    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS cache_hits,
                    AVG(result_count)              AS avg_results,
                    MAX(latency_ms)                AS max_latency
                FROM retrieval_metrics
                WHERE timestamp > NOW() - make_interval(days => $1)
                """,
                days,
            )
        return dict(row) if row else {}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cache/clear")
async def clear_cache(request: Request) -> Dict[str, str]:
    """Clear all cached retrieval results (admin only)."""
    _require_admin(request)
    db_pool = _get_service(request, "db_pool")

    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM retrieval_cache")
        return {"status": "cache cleared"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
