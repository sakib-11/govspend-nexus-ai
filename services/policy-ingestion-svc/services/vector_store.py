from typing import List, Dict, Any, Optional
import asyncpg
import json
import numpy as np
from models.policy import PolicyChunk
from models.embedding import SearchQuery, SearchResult
from config import PolicyIngestionConfig
import logging

logger = logging.getLogger(__name__)

class VectorStore:
    """Service for storing and searching vectors in PostgreSQL with pgvector"""
    
    def __init__(self, db_pool: asyncpg.Pool, config: PolicyIngestionConfig):
        self.db_pool = db_pool
        self.config = config
        self.dimension = config.vector_dimension
    
    async def store_chunk(
        self,
        chunk: PolicyChunk,
        embedding: List[float]
    ) -> bool:
        """Store a chunk with its embedding"""
        
        if len(embedding) != self.dimension:
            logger.warning(f"Embedding dimension mismatch: expected {self.dimension}, got {len(embedding)}")
            # Pad or truncate
            if len(embedding) > self.dimension:
                embedding = embedding[:self.dimension]
            else:
                embedding = embedding + [0.0] * (self.dimension - len(embedding))
        
        # Convert to PostgreSQL vector format
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO policy_chunks (
                    chunk_id, document_id, chunk_number,
                    content, content_hash, embedding,
                    start_position, end_position,
                    token_count, metadata
                ) VALUES (
                    $1, $2, $3, $4, $5, $6::vector, $7, $8, $9, $10
                )
                ON CONFLICT (chunk_id) DO UPDATE
                SET 
                    content = $4,
                    content_hash = $5,
                    embedding = $6::vector,
                    start_position = $7,
                    end_position = $8,
                    token_count = $9,
                    metadata = $10
            """,
                str(chunk.chunk_id),
                str(chunk.document_id),
                chunk.chunk_number,
                chunk.content,
                chunk.content_hash,
                embedding_str,
                chunk.start_position,
                chunk.end_position,
                chunk.token_count,
                json.dumps(chunk.metadata)
            )
            
            return True
    
    async def search(
        self,
        query: SearchQuery
    ) -> List[SearchResult]:
        """Search for similar chunks"""
        
        # Get query embedding if not provided
        if not query.query_embedding:
            # In production, generate embedding from query text
            from services.embedding_service import EmbeddingService
            embedding_service = EmbeddingService(self.config)
            embeddings = await embedding_service.generate_embeddings([query.query])
            query_embedding = embeddings[0] if embeddings else None
            
            if not query_embedding:
                return []
        else:
            query_embedding = query.query_embedding
        
        # Convert to vector format
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"
        
        # Build category filter
        category_filter = query.category_filter
        category_clause = ""
        if category_filter:
            category_filter_str = f"', '{'","'".join(category_filter)}"
            category_clause = f"AND pd.category IN ('{category_filter_str}')"
        
        # Execute search
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    pc.chunk_id,
                    pc.document_id,
                    pc.content,
                    1 - (pc.embedding <=> $1::vector) AS similarity,
                    pd.title AS document_title,
                    pd.category AS document_category,
                    pc.metadata
                FROM policy_chunks pc
                JOIN policy_documents pd ON pc.document_id = pd.document_id
                WHERE 
                    1 - (pc.embedding <=> $1::vector) > $2
                    AND (TRUE $3)
                    AND pd.is_active = $4
                ORDER BY pc.embedding <=> $1::vector
                LIMIT $5
            """,
                embedding_str,
                query.match_threshold,
                category_clause if category_filter else "",
                query.active_only,
                query.match_count
            )
        
        return [
            SearchResult(
                chunk_id=row['chunk_id'],
                document_id=row['document_id'],
                content=row['content'],
                similarity=float(row['similarity']),
                document_title=row['document_title'],
                document_category=row['document_category'],
                metadata=row['metadata'] or {}
            )
            for row in rows
        ]
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete all chunks for a document"""
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM policy_chunks
                WHERE document_id = $1
            """, document_id)
            
            return True
    
    async def get_chunk_count(self, document_id: str) -> int:
        """Get number of chunks for a document"""
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COUNT(*) FROM policy_chunks
                WHERE document_id = $1
            """, document_id)
            
            return row[0] if row else 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        
        async with self.db_pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_chunks,
                    COUNT(DISTINCT document_id) as total_documents,
                    AVG(token_count) as avg_tokens
                FROM policy_chunks
            """)
            
            return {
                "total_chunks": stats['total_chunks'],
                "total_documents": stats['total_documents'],
                "avg_tokens_per_chunk": float(stats['avg_tokens']) if stats['avg_tokens'] else 0,
                "embedding_dimension": self.dimension
            }
