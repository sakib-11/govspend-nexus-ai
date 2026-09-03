from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import uuid

class ValidationSeverity(str, Enum):
    """Validation severity levels"""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class ValidationStatus(str, Enum):
    """Validation status"""
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    GROUNDED = "grounded"
    UNGROUNDED = "ungrounded"
    MASKED = "masked"

class CitationStatus(str, Enum):
    """Citation validation status"""
    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"
    MISSING = "missing"

class GroundingCheck(BaseModel):
    """Individual grounding check result"""
    check_id: str
    claim_type: str  # evidence, policy, detector
    claim_value: str
    is_grounded: bool
    source_id: Optional[str] = None
    source_type: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    details: Dict[str, Any] = Field(default_factory=dict)
    status: ValidationStatus = ValidationStatus.UNGROUNDED

class CitationValidation(BaseModel):
    """Citation validation result"""
    citation_id: str
    citation_type: str  # evidence, policy
    reference_id: str
    reference_text: str
    exists_in_bundle: bool
    exists_in_corpus: bool
    is_valid: bool
    status: CitationStatus
    validation_details: Dict[str, Any] = Field(default_factory=dict)

class ExplanationValidationResult(BaseModel):
    """Complete validation result"""
    
    # Core
    validation_id: str = Field(default_factory=lambda: f"val-{uuid.uuid4().hex[:12]}")
    explanation_id: str
    case_id: str
    
    # Status
    status: ValidationStatus
    grounding_score: float = Field(ge=0.0, le=1.0)
    citation_coverage: float = Field(ge=0.0, le=1.0)
    
    # Checks
    schema_valid: bool
    citations_valid: bool
    evidence_valid: bool
    policy_valid: bool
    detector_names_valid: bool
    
    # Details
    grounding_checks: List[GroundingCheck] = Field(default_factory=list)
    citation_validations: List[CitationValidation] = Field(default_factory=list)
    
    # Issues
    critical_issues: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    # Masked content
    original_content: Optional[str] = None
    masked_content: Optional[str] = None
    rephrased_content: Optional[str] = None
    
    # Metadata
    validated_at: datetime = Field(default_factory=datetime.now)
    validation_time_ms: float = 0.0
    version: str = "1.0"

class ValidationRequest(BaseModel):
    """Request to validate an explanation"""
    explanation_id: str
    case_id: str
    content: Dict[str, Any]  # The explanation JSON
    evidence_bundle: Dict[str, Any]
    retrieved_policies: List[Dict[str, Any]]
    signals: List[Dict[str, Any]]
    
    # Options
    strict_mode: bool = True
    mask_ungrounded: bool = True
    rephrase_ungrounded: bool = True

class MaskingResult(BaseModel):
    """Result of masking ungrounded claims"""
    original_sentence: str
    masked_sentence: str
    is_grounded: bool
    grounding_issues: List[str] = Field(default_factory=list)
    masked_terms: List[str] = Field(default_factory=list)