"""Crypto models for hashing and tokenization."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class HashAlgorithm(str, Enum):
    SHA256 = "SHA-256"
    SHA384 = "SHA-384"
    SHA512 = "SHA-512"

class TokenPrefix(str, Enum):
    VENDOR = "VEND"
    TRANSACTION = "TXN"
    DOCUMENT = "DOC"
    USER = "USR"
    DEPARTMENT = "DEPT"

class HashResult(BaseModel):
    """Result of hashing operation."""
    algorithm: HashAlgorithm
    digest: str
    hex_digest: str
    base64_digest: str
    timestamp: datetime = Field(default_factory=datetime.now)
    input_length: int
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TokenResult(BaseModel):
    """Result of tokenization operation."""
    original_value: str
    token: str
    prefix: TokenPrefix
    algorithm: str = "HMAC-SHA256"
    encoding: str = "Base32"
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocumentHashResult(BaseModel):
    """Result of document hashing."""
    invoice_doc_hash: str
    algorithm: str = "SHA-256"
    content_length: int
    content_preview: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class VerificationResult(BaseModel):
    """Result of verification operation."""
    verified: bool
    original_value: Optional[str] = None
    token: Optional[str] = None
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
