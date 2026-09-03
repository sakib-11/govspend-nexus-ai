from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class EmbeddingRequest(BaseModel):
    """Request to generate embeddings"""
    texts: List[str]
    model: str = "text-embedding-ada-002"
    batch_size: int = 20

class EmbeddingResponse(BaseModel):
    """Response with embeddings"""
    embeddings: List[List[float]]
    model: str
    total_tokens: int
    processing_time_ms: float

class SearchQuery(BaseModel):
    """Search query for policy retrieval"""
    query: str
    query_embedding: Optional[List[float]] = None
    match_threshold: float = 0.7
    match_count: int = 10
    category_filter: Optional[List[str]] = None
    active_only: bool = True
    include_metadata: bool = True

class SearchResult(BaseModel):
    """Search result from vector store"""
    chunk_id: str
    document_id: str
    content: str
    similarity: float
    document_title: str
    document_category: str
    metadata: Dict[str, Any]
