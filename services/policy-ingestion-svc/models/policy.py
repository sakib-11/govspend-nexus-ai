from typing import List, Optional, Dict, Any
from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, validator
from uuid import UUID, uuid4

class PolicyCategory(str, Enum):
    GFR = "gfr"
    PROCUREMENT = "procurement"
    PRIVACY = "privacy"
    AUDIT = "audit"
    FINANCIAL = "financial"
    COMPLIANCE = "compliance"
    REGULATORY = "regulatory"

class PolicyDocument(BaseModel):
    """Policy document model"""
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
    
    document_id: UUID = Field(default_factory=uuid4)
    title: str
    description: Optional[str] = None
    category: PolicyCategory
    source_type: str  # pdf, docx, txt, html, md
    source_url: Optional[str] = None
    file_path: Optional[str] = None
    file_hash: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    content_hash: Optional[str] = None
    language: str = "en"
    word_count: Optional[int] = None
    page_count: Optional[int] = None
    version: str = "1.0"
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    is_active: bool = True
    is_reviewed: bool = False
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class PolicyChunk(BaseModel):
    """Policy chunk with embedding"""
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
    
    chunk_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    chunk_number: int
    content: str
    content_hash: str
    embedding: Optional[List[float]] = None
    start_position: Optional[int] = None
    end_position: Optional[int] = None
    token_count: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

class PolicySection(BaseModel):
    """Policy section for hierarchical structure"""
    section_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    parent_section_id: Optional[UUID] = None
    section_number: Optional[str] = None
    title: str
    content: Optional[str] = None
    level: int = 0
    path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

class PolicyReference(BaseModel):
    """Cross-reference between policies"""
    reference_id: UUID = Field(default_factory=uuid4)
    from_document_id: UUID
    to_document_id: UUID
    reference_type: str  # cites, amends, supersedes, supplements
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

class IngestionJob(BaseModel):
    """Document ingestion job"""
    job_id: UUID = Field(default_factory=uuid4)
    job_type: str  # file, batch, url, directory
    status: str  # pending, running, completed, failed
    total_documents: int = 0
    processed_documents: int = 0
    total_chunks: int = 0
    processed_chunks: int = 0
    errors: Dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
