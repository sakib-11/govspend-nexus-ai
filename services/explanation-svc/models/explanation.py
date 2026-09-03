"""Explanation models — structured AI explanations with citations and LLM metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ======================================================================
# Enums
# ======================================================================

class ExplanationStatus(str, Enum):
    """Lifecycle states for explanation generation."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    VALIDATED = "validated"
    FAILED = "failed"
    FALLBACK = "fallback"


# ======================================================================
# Core models
# ======================================================================

class Citation(BaseModel):
    """A citation reference within an explanation."""

    citation_type: str  # evidence | policy
    reference_id: str
    reference_text: str
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.0)
    location: Optional[str] = None


class ExplanationPoint(BaseModel):
    """Individual explanation point with citations."""

    point_number: int = Field(ge=1)
    detector_name: str
    sentence: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: List[str] = Field(default_factory=list)
    policy_references: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    reasoning: Optional[str] = None

    @field_validator("sentence")
    @classmethod
    def validate_sentence(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError("Sentence must be at least 10 characters")
        return v


# ======================================================================
# Request / Response
# ======================================================================

class ExplanationRequest(BaseModel):
    """Request for explanation generation."""

    case_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_tier: str = "LOW"
    evidence_bundle: Dict[str, Any] = Field(default_factory=dict)
    retrieved_policies: List[Dict[str, Any]] = Field(default_factory=list)
    signals: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Options
    max_explanations: int = Field(default=10, ge=1, le=20)
    include_citations: bool = True
    validation_strictness: Optional[str] = None


class ExplanationResponse(BaseModel):
    """Complete explanation response with LLM and validation metadata."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    # Core
    explanation_id: str = Field(default_factory=lambda: f"exp-{uuid4().hex[:12]}")
    case_id: str
    transaction_id: str

    # Content
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    explanations: List[ExplanationPoint] = Field(default_factory=list)
    grounding_score: float = Field(ge=0.0, le=1.0, default=0.0)

    # Metadata
    citations_used: int = 0
    total_evidence: int = 0
    total_policies: int = 0
    status: ExplanationStatus = ExplanationStatus.COMPLETED

    # LLM metadata
    llm_model: str = ""
    llm_provider: str = ""
    generation_time_ms: float = 0.0
    token_count: int = 0

    # Validation
    validated: bool = False
    validation_attempts: int = 0
    validation_errors: List[str] = Field(default_factory=list)

    # Timestamps
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    validated_at: Optional[datetime] = None

    # Fallback
    is_fallback: bool = False
    fallback_reason: Optional[str] = None


class ExplanationValidationResult(BaseModel):
    """Validation result for an explanation."""

    is_valid: bool
    grounding_score: float = 0.0
    confidence_score: float = 0.0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    missing_policies: List[str] = Field(default_factory=list)
    uncited_sentences: List[int] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


# ======================================================================
# Internal LLM models
# ======================================================================

class LLMRequest(BaseModel):
    """Internal LLM request."""

    system_prompt: str
    user_prompt: str
    temperature: float = 0.3
    max_tokens: int = 2000
    top_p: float = 0.9


class LLMResponse(BaseModel):
    """Internal LLM response."""

    content: str
    model: str
    provider: str
    token_count: int = 0
    processing_time_ms: float = 0.0
    raw_response: Optional[Dict[str, Any]] = None
