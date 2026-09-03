"""Shared Pydantic models for GovSpend Nexus AI"""
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
import json

# ============ Enums ============

class SignalType(str, Enum):
    PRICE_DEVIATION = "price_deviation"
    DUPLICATE_FUZZY = "duplicate_fuzzy"
    VENDOR_GRAPH_RISK = "vendor_graph_risk"
    TIMING_ANOMALY = "timing_anomaly"
    CONTRACT_SPLITTING = "contract_splitting"
    APPROVAL_VELOCITY = "approval_velocity"

class CaseStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"

class RiskTier(str, Enum):
    HIGH = "high"
    BORDERLINE = "borderline"
    LOW = "low"

class UnmaskStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class ActionType(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    RECALIBRATE = "recalibrate"
    UNMASK = "unmask"
    ESCALATE = "escalate"
    ASSIGN = "assign"

class EntityType(str, Enum):
    VENDOR = "vendor"
    OFFICIAL = "official"
    DEPARTMENT = "department"
    TRANSACTION = "transaction"

class SourceType(str, Enum):
    CPPP = "CPPP"
    GEM = "GeM"
    ERP = "ERP"
    MANUAL = "Manual"

# ============ Core Models ============

class Signal(BaseModel):
    """Detector output signal"""
    model_config = ConfigDict(use_enum_values=True)
    
    type: SignalType
    value: float = Field(ge=0, le=1, description="Signal strength [0,1]")
    confidence: float = Field(ge=0, le=1, description="Confidence in signal [0,1]")
    evidence_ref: List[str] = Field(default_factory=list, description="IDs of evidence records")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    def is_active(self, threshold: float = 0.15) -> bool:
        """Check if signal is active above threshold"""
        return self.value > threshold
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "type": self.type.value if isinstance(self.type, SignalType) else self.type,
            "value": self.value,
            "confidence": self.confidence,
            "evidence_ref": self.evidence_ref,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signal":
        """Create Signal from dictionary"""
        return cls(
            type=data.get("type"),
            value=data.get("value", 0.0),
            confidence=data.get("confidence", 0.0),
            evidence_ref=data.get("evidence_ref", []),
            metadata=data.get("metadata", {})
        )

class CanonicalTransaction(BaseModel):
    """Normalized transaction from L0 ingestion"""
    model_config = ConfigDict(use_enum_values=True)
    
    id: UUID = Field(default_factory=uuid4)
    invoice_doc_hash: str = Field(..., min_length=64, max_length=64)
    vendor_token: str
    department_id: str
    amount: float = Field(gt=0)
    unit_price: float = Field(gt=0)
    quantity: int = Field(gt=0)
    category: str
    region: str
    submitted_at: datetime
    approved_at: Optional[datetime] = None
    approver_token: Optional[str] = None
    source: SourceType
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v
    
    @validator('unit_price')
    def validate_unit_price(cls, v, values):
        if v <= 0:
            raise ValueError("Unit price must be greater than 0")
        return v
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        return v
    
    def get_amount_band(self) -> str:
        """Bucket amounts for peer comparison"""
        if self.amount < 10000:
            return "micro"
        elif self.amount < 100000:
            return "small"
        elif self.amount < 1000000:
            return "medium"
        else:
            return "large"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": str(self.id),
            "invoice_doc_hash": self.invoice_doc_hash,
            "vendor_token": self.vendor_token,
            "department_id": self.department_id,
            "amount": self.amount,
            "unit_price": self.unit_price,
            "quantity": self.quantity,
            "category": self.category,
            "region": self.region,
            "submitted_at": self.submitted_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approver_token": self.approver_token,
            "source": self.source.value if isinstance(self.source, SourceType) else self.source,
            "metadata": self.metadata
        }

class RiskScore(BaseModel):
    """Computed risk score"""
    model_config = ConfigDict(use_enum_values=True)
    
    id: UUID = Field(default_factory=uuid4)
    transaction_id: UUID
    score: float = Field(ge=0, le=1)
    tier: RiskTier
    confidence_factor: float = Field(ge=0, le=1)
    policy_weight_version: str = "v1.0"
    evidence_bundle_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "transaction_id": str(self.transaction_id),
            "score": self.score,
            "tier": self.tier.value if isinstance(self.tier, RiskTier) else self.tier,
            "confidence_factor": self.confidence_factor,
            "policy_weight_version": self.policy_weight_version,
            "evidence_bundle_id": str(self.evidence_bundle_id),
            "created_at": self.created_at.isoformat()
        }

class EvidenceBundle(BaseModel):
    """Evidence bundle for a case"""
    model_config = ConfigDict(use_enum_values=True)
    
    id: UUID = Field(default_factory=uuid4)
    risk_score_id: UUID
    signals: List[Signal]
    transaction: CanonicalTransaction
    vendor_token: str
    department_id: str
    benchmarks: Dict[str, Any] = Field(default_factory=dict)
    retrieved_policy_chunks: Optional[List[Dict[str, Any]]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "risk_score_id": str(self.risk_score_id),
            "signals": [s.to_dict() for s in self.signals],
            "transaction": self.transaction.to_dict(),
            "vendor_token": self.vendor_token,
            "department_id": self.department_id,
            "benchmarks": self.benchmarks,
            "retrieved_policy_chunks": self.retrieved_policy_chunks,
            "created_at": self.created_at.isoformat()
        }

class Case(BaseModel):
    """Audit case"""
    model_config = ConfigDict(use_enum_values=True)
    
    id: UUID = Field(default_factory=uuid4)
    risk_score_id: UUID
    status: CaseStatus = CaseStatus.OPEN
    assigned_auditor_id: Optional[UUID] = None
    jurisdiction_scope: str
    priority: int = Field(ge=1, le=5, default=3)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "risk_score_id": str(self.risk_score_id),
            "status": self.status.value if isinstance(self.status, CaseStatus) else self.status,
            "assigned_auditor_id": str(self.assigned_auditor_id) if self.assigned_auditor_id else None,
            "jurisdiction_scope": self.jurisdiction_scope,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes
        }

class UnmaskRequest(BaseModel):
    """Request to de-tokenize sensitive data"""
    model_config = ConfigDict(use_enum_values=True)
    
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    requester_id: UUID
    approver_id: Optional[UUID] = None
    entity_type: EntityType
    entity_token: str
    reason: str = Field(min_length=10, max_length=500)
    status: UnmaskStatus = UnmaskStatus.PENDING
    jurisdiction_scope: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "case_id": str(self.case_id),
            "requester_id": str(self.requester_id),
            "approver_id": str(self.approver_id) if self.approver_id else None,
            "entity_type": self.entity_type.value if isinstance(self.entity_type, EntityType) else self.entity_type,
            "entity_token": self.entity_token,
            "reason": self.reason,
            "status": self.status.value if isinstance(self.status, UnmaskStatus) else self.status,
            "jurisdiction_scope": self.jurisdiction_scope,
            "created_at": self.created_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "viewed_at": self.viewed_at.isoformat() if self.viewed_at else None
        }

class Explanation(BaseModel):
    """AI-generated explanation"""
    model_config = ConfigDict(use_enum_values=True)
    
    case_id: UUID
    rationale: str
    citations: List[Dict[str, Any]]
    grounding_rate: float = Field(ge=0, le=1, default=0.0)
    model_used: str
    tokens_used: int = Field(ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": str(self.case_id),
            "rationale": self.rationale,
            "citations": self.citations,
            "grounding_rate": self.grounding_rate,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at.isoformat()
        }

class Action(BaseModel):
    """Auditor action"""
    model_config = ConfigDict(use_enum_values=True)
    
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    auditor_id: UUID
    action: ActionType
    rationale: Optional[str] = Field(max_length=1000, default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "case_id": str(self.case_id),
            "auditor_id": str(self.auditor_id),
            "action": self.action.value if isinstance(self.action, ActionType) else self.action,
            "rationale": self.rationale,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }

# ============ MCP Tool Models ============

class MCPTool(BaseModel):
    """MCP Gateway tool contract"""
    model_config = ConfigDict(use_enum_values=True)
    
    name: str
    permission_tag: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    side_effects: List[str] = Field(default_factory=list)
    rate_limit: int = 60
    timeout: int = 30
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input against schema"""
        # In production, use jsonschema validation
        return True
    
    def validate_output(self, data: Dict[str, Any]) -> bool:
        """Validate output against schema"""
        return True

# ============ Request/Response Models ============

class CaseListResponse(BaseModel):
    cases: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int

class CaseDetailResponse(BaseModel):
    case: Dict[str, Any]
    risk_score: Dict[str, Any]
    evidence_bundle: Dict[str, Any]
    explanation: Optional[Dict[str, Any]] = None

class IngestRequest(BaseModel):
    file_content: str
    department_id: str
    region: str
    source: SourceType = SourceType.MANUAL
    
    @validator('file_content')
    def validate_file_content(cls, v):
        if len(v) < 10:
            raise ValueError("File content too short")
        return v

class IngestResponse(BaseModel):
    transaction_id: UUID
    status: str
    vendor_token: str
    message: str
    warnings: List[str] = Field(default_factory=list)

class UnmaskRequestModel(BaseModel):
    case_id: UUID
    entity_type: EntityType
    entity_token: str
    reason: str = Field(min_length=10, max_length=500)

class UnmaskResponse(BaseModel):
    request_id: UUID
    status: UnmaskStatus
    message: str

class AuditLogEntry(BaseModel):
    id: UUID
    prev_hash: str
    entry_hash: str
    actor_id: str
    action: str
    resource_token: Optional[str]
    payload_hash: str
    ts: datetime

# ============ Schema Validation Helpers ============

class SchemaValidator:
    """Helper class for schema validation"""
    
    @staticmethod
    def validate_transaction(data: Dict[str, Any]) -> bool:
        """Validate transaction data"""
        try:
            CanonicalTransaction(**data)
            return True
        except Exception:
            return False
    
    @staticmethod
    def validate_signal(data: Dict[str, Any]) -> bool:
        """Validate signal data"""
        try:
            Signal(**data)
            return True
        except Exception:
            return False
    
    @staticmethod
    def validate_risk_score(data: Dict[str, Any]) -> bool:
        """Validate risk score data"""
        try:
            RiskScore(**data)
            return True
        except Exception:
            return False
    
    @staticmethod
    def validate_case(data: Dict[str, Any]) -> bool:
        """Validate case data"""
        try:
            Case(**data)
            return True
        except Exception:
            return False
