"""Prompt models — request, response, templates, and LLM I/O schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ======================================================================
# Enums
# ======================================================================

class PromptType(str, Enum):
    """Types of prompts."""

    SYSTEM = "system"
    USER = "user"
    FEW_SHOT = "few_shot"
    CONTEXTUAL = "contextual"
    EXPLANATION = "explanation"


class RiskTier(str, Enum):
    """Risk tier for prompt style selection."""

    HIGH = "HIGH"
    BORDERLINE = "BORDERLINE"
    LOW = "LOW"


class CitationType(str, Enum):
    """Type of citation reference."""

    EVIDENCE = "evidence"
    POLICY = "policy"


# ======================================================================
# Core models
# ======================================================================

class PromptTemplate(BaseModel):
    """Prompt template with variables and versioning."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    template_id: str = Field(default_factory=lambda: f"tmpl-{uuid4().hex[:8]}")
    name: str
    description: Optional[str] = None
    prompt_type: PromptType
    template: str
    variables: List[str] = Field(default_factory=list)
    version: str = "1.0"
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    """Citation for evidence or policy reference."""

    citation_type: CitationType
    reference_id: str
    reference_text: str
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.0)
    location: Optional[str] = None


class ExplanationPoint(BaseModel):
    """Individual explanation point with citations."""

    point_number: int = Field(ge=1)
    detector_name: str
    sentence: str = Field(min_length=10)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: List[str] = Field(default_factory=list)
    policy_references: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    reasoning: Optional[str] = None


# ======================================================================
# LLM I/O
# ======================================================================

class LLMInput(BaseModel):
    """Structured input for the LLM."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    case_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_tier: RiskTier
    evidence_bundle: Dict[str, Any] = Field(default_factory=dict)
    retrieved_policies: List[Dict[str, Any]] = Field(default_factory=list)
    signals: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMOutput(BaseModel):
    """Structured output from the LLM with citations and grounding."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    summary: str = Field(min_length=10)
    confidence: float = Field(ge=0.0, le=1.0)
    explanations: List[ExplanationPoint] = Field(min_length=1)
    grounding_score: float = Field(ge=0.0, le=1.0)
    citations_used: int = Field(ge=0, default=0)
    total_evidence: int = Field(ge=0, default=0)
    total_policies: int = Field(ge=0, default=0)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ======================================================================
# Request / Response DTOs
# ======================================================================

class PromptRequest(BaseModel):
    """Request to generate a prompt for the LLM."""

    llm_input: LLMInput
    template_name: Optional[str] = None
    include_few_shot: bool = True
    custom_instructions: Optional[str] = None
    max_explanations: int = Field(default=10, ge=1, le=20)


class PromptResponse(BaseModel):
    """Response with generated prompt and metadata."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    system_prompt: str
    user_prompt: str
    prompt_id: str = Field(default_factory=lambda: f"prompt-{uuid4().hex[:8]}")
    token_count: int = 0
    estimated_cost: float = 0.0
    template_used: str = "default"
    variables_used: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Validation result for LLM input or output."""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    grounding_score: float = 0.0
    citation_coverage: float = 0.0
    missing_evidence: List[str] = Field(default_factory=list)
    missing_policies: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class ValidateOutputRequest(BaseModel):
    """Request body for output validation."""

    output_data: Dict[str, Any]
    input_data: Optional[Dict[str, Any]] = None
