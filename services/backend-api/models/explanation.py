"""AI explanation models."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ExplanationPoint(BaseModel):
    """Individual explanation point with citations."""

    point_number: int
    detector_name: str
    sentence: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: List[str] = Field(default_factory=list)
    policy_references: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)


class CaseExplanation(BaseModel):
    """Complete case explanation with grounding."""

    case_id: str
    transaction_id: str
    explanations: List[ExplanationPoint]
    summary: str
    overall_confidence: float = Field(ge=0.0, le=1.0)
    grounding_score: float = Field(ge=0.0, le=1.0)
    evidence_count: int
    policy_count: int
    generated_at: str
    version: str = "1.0"
