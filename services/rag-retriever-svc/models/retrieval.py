"""Retrieval models — request, response, feedback, and context."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RetrievalRequest(BaseModel):
    """Request for retrieving relevant policy chunks."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    query: str = Field(..., min_length=1, max_length=5000)
    query_type: str = "general"  # general | specific | regulatory | case_based
    context: Optional[Dict[str, Any]] = None
    match_count: int = Field(default=10, ge=1, le=50)
    match_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    category_filter: Optional[List[str]] = None
    active_only: bool = True
    include_metadata: bool = True
    use_hybrid: bool = True
    query_expansion: bool = True
    rerank: bool = True
    case_context: Optional[Dict[str, Any]] = None


class RetrievalResult(BaseModel):
    """Individual retrieval result with scores from multiple retrievers."""

    chunk_id: str
    document_id: str
    content: str
    similarity: float
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    rerank_score: Optional[float] = None
    document_title: str = ""
    document_category: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    highlight: Optional[str] = None
    relevance_confidence: float = 0.0


class RetrievalResponse(BaseModel):
    """Complete retrieval response."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    request_id: str = Field(default_factory=lambda: f"req-{uuid4().hex[:12]}")
    query: str
    expanded_query: Optional[str] = None
    results: List[RetrievalResult] = Field(default_factory=list)
    total_results: int = 0
    query_time_ms: float = 0.0
    strategy_used: str = "hybrid"
    cache_hit: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextualRetrievalRequest(BaseModel):
    """Request for retrieval with case context."""

    case_signals: List[Dict[str, Any]] = Field(default_factory=list)
    case_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    risk_score: Optional[float] = None
    risk_tier: Optional[str] = None
    query_template: Optional[str] = None
    match_count: int = Field(default=10, ge=1, le=50)
    include_policies: bool = True


class RetrievalFeedback(BaseModel):
    """Feedback on retrieval quality."""

    query_id: str
    chunk_id: str
    relevance_score: float = Field(ge=-1.0, le=1.0)
    user_id: Optional[str] = None
    feedback_type: str  # positive | negative | neutral
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryContext(BaseModel):
    """Context for query processing."""

    domain: str = "government_procurement"
    jurisdiction: Optional[str] = None
    focus_areas: List[str] = Field(default_factory=list)
    case_id: Optional[str] = None
    user_roles: List[str] = Field(default_factory=list)
