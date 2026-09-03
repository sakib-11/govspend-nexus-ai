"""Models for duplicate and fuzzy detection."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class DuplicateMatchType(str, Enum):
    """Types of duplicate match results."""

    EXACT_HASH = "exact_hash"
    FUZZY_SIMILARITY = "fuzzy_similarity"
    PARTIAL_MATCH = "partial_match"
    NO_MATCH = "no_match"


class SimilarityMatch(BaseModel):
    """Individual similarity match result."""

    transaction_id: str
    vendor_id: str
    vendor_name: str
    document_number: str
    amount: float
    transaction_date: date
    similarity_score: float = Field(..., ge=0, le=1)
    match_type: DuplicateMatchType
    evidence: List[str]
    matched_fields: Dict[str, float]  # Field-level similarity scores


class DuplicateDetectionResult(BaseModel):
    """Complete duplicate detection result."""

    signal_value: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    match_type: DuplicateMatchType
    matches: List[SimilarityMatch]
    best_match: Optional[SimilarityMatch] = None
    duplicate_count: int = 0
    hash_duplicate: bool = False
    fuzzy_matches: List[SimilarityMatch] = Field(default_factory=list)

    # Detection metadata
    detection_methods_used: List[str]
    processing_time_ms: Optional[int] = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    # Evidence and recommendations
    evidence: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

    @field_validator("signal_value")
    @classmethod
    def validate_signal(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


class DuplicateSearchParams(BaseModel):
    """Parameters for duplicate search."""

    invoice_hash: str
    vendor_token: str
    vendor_name: str
    amount: float
    transaction_date: date
    document_text: Optional[str] = None
    document_number: Optional[str] = None
    line_items: Optional[List[Dict]] = None

    # Search parameters
    amount_tolerance: float = 0.02  # ±2%
    date_window_days: int = 30
    similarity_threshold: float = 0.85
    max_results: int = 10
    include_soft_deleted: bool = False


class FuzzyMatchCandidate(BaseModel):
    """Candidate for fuzzy matching."""

    transaction_id: str
    vendor_token: str
    vendor_name: str
    document_number: str
    invoice_hash: str
    amount: float
    transaction_date: date
    document_text: Optional[str] = None
    line_items: Optional[List[Dict]] = None
    created_at: datetime

    # Pre-computed similarities
    text_similarity: Optional[float] = None
    vendor_similarity: Optional[float] = None
    amount_similarity: Optional[float] = None
    date_similarity: Optional[float] = None

    # Combined score
    combined_score: Optional[float] = None
