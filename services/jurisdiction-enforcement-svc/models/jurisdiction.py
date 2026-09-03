from enum import Enum
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, validator
from uuid import uuid4

class JurisdictionLevel(str, Enum):
    """Jurisdiction hierarchy levels"""
    FEDERAL = "federal"
    STATE = "state"
    REGION = "region"
    COUNTY = "county"
    CITY = "city"
    AGENCY = "agency"
    DEPARTMENT = "department"
    CUSTOM = "custom"

class JurisdictionType(str, Enum):
    """Types of jurisdictions"""
    GEOGRAPHIC = "geographic"
    ORGANIZATIONAL = "organizational"
    FUNCTIONAL = "functional"
    HYBRID = "hybrid"

class JurisdictionAccess(str, Enum):
    """Jurisdiction access types"""
    FULL = "full"          # Can access all resources in jurisdiction
    LIMITED = "limited"    # Can access only specific resources
    READ_ONLY = "read_only"  # Can only read, not modify
    NO_ACCESS = "no_access"  # No access

class Jurisdiction(BaseModel):
    """Jurisdiction model with hierarchy support"""
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
    
    jurisdiction_id: str = Field(default_factory=lambda: f"jur-{uuid4().hex[:12]}")
    code: str  # e.g., "US-CA-001"
    name: str
    description: Optional[str] = None
    
    # Hierarchy
    level: JurisdictionLevel
    parent_id: Optional[str] = None
    ancestors: List[str] = Field(default_factory=list)  # Full path from root
    descendants: List[str] = Field(default_factory=list)
    depth: int = 0
    
    # Type
    jurisdiction_type: JurisdictionType = JurisdictionType.GEOGRAPHIC
    
    # Access control
    allowed_access: Dict[str, JurisdictionAccess] = Field(default_factory=dict)
    default_access: JurisdictionAccess = JurisdictionAccess.NO_ACCESS
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    
    # Status
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @validator('ancestors')
    def validate_ancestors(cls, v, values):
        """Validate ancestors path"""
        if not v:
            return v
        
        # Ensure ancestors are valid jurisdiction IDs
        # In production, you'd validate against database
        return v
    
    def is_ancestor_of(self, jurisdiction: 'Jurisdiction') -> bool:
        """Check if this jurisdiction is an ancestor of another"""
        return self.jurisdiction_id in jurisdiction.ancestors
    
    def is_descendant_of(self, jurisdiction: 'Jurisdiction') -> bool:
        """Check if this jurisdiction is a descendant of another"""
        return jurisdiction.jurisdiction_id in self.ancestors
    
    def get_access(self, user_id: str) -> JurisdictionAccess:
        """Get access level for a user"""
        return self.allowed_access.get(user_id, self.default_access)

class UserJurisdiction(BaseModel):
    """User's jurisdiction assignments"""
    user_id: str
    jurisdiction_id: str
    access_level: JurisdictionAccess
    assigned_at: datetime = Field(default_factory=datetime.now)
    assigned_by: Optional[str] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    
    # Audit
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ResourceJurisdiction(BaseModel):
    """Jurisdiction assignment for a resource"""
    resource_type: str  # case, transaction, evidence, etc.
    resource_id: str
    jurisdiction_id: str
    assigned_at: datetime = Field(default_factory=datetime.now)
    assigned_by: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class JurisdictionEnforcementRequest(BaseModel):
    """Request for jurisdiction enforcement"""
    user_id: str
    user_jurisdictions: List[str]  # User's allowed jurisdiction IDs
    resource_type: str
    resource_id: str
    resource_jurisdiction: str
    action: str  # read, write, delete, etc.
    context: Dict[str, Any] = Field(default_factory=dict)

class JurisdictionEnforcementResult(BaseModel):
    """Result of jurisdiction enforcement"""
    request_id: str = Field(default_factory=lambda: f"req-{uuid4().hex[:12]}")
    user_id: str
    resource_type: str
    resource_id: str
    resource_jurisdiction: str
    allowed: bool
    reason: str
    matching_jurisdictions: List[str] = Field(default_factory=list)
    hierarchy_check: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Audit
    audit_id: Optional[str] = None

class CrossJurisdictionRequest(BaseModel):
    """Request for cross-jurisdiction access"""
    user_id: str
    source_jurisdiction: str
    target_jurisdiction: str
    resource_type: str
    resource_id: str
    reason: str
    requested_by: str
    expires_at: Optional[datetime] = None

class CrossJurisdictionApproval(BaseModel):
    """Approval for cross-jurisdiction access"""
    request_id: str
    approved_by: str
    approved_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    approved: bool
    reason: Optional[str] = None
    conditions: Dict[str, Any] = Field(default_factory=dict)