from typing import List, Dict, Any, Optional, Tuple
import os
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime
from models.policy import PolicyDocument, PolicyChunk, IngestionJob
from services.chunking_service import ChunkingService
from services.embedding_service import EmbeddingService
from services.vector_store import VectorStore
from services.metadata_service import MetadataService
from processors.pdf_processor import PDFProcessor
from processors.text_processor import TextProcessor
from processors.docx_processor import DocxProcessor
from processors.html_processor import HtmlProcessor
from config import PolicyIngestionConfig
import logging

logger = logging.getLogger(__name__)

class IngestionService:
    """Service for ingesting policy documents"""
    
    def __init__(
        self,
        db_pool,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        config: PolicyIngestionConfig
    ):
        self.db_pool = db_pool
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.metadata_service = MetadataService(config)
        self.config = config
        
        self.processors = {
            'pdf': PDFProcessor(config),
            'docx': DocxProcessor(config),
            'html': HtmlProcessor(config),
            'txt': TextProcessor(config),
            'md': TextProcessor(config)
        }
    
    async def ingest_file(
        self,
        file_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Ingest a single document file"""
        
        # Get file extension
        ext = Path(file_path).suffix.lower().replace('.', '')
        
        if ext not in self.config.supported_formats:
            raise ValueError(f"Unsupported file format: {ext}")
        
        # Get processor
        processor = self.processors.get(ext)
        if not processor:
            raise ValueError(f"No processor for format: {ext}")
        
        # Extract metadata using metadata service
        metadata = await self.metadata_service.extract_metadata(file_path, metadata or {})
        
        # Process the file
        processed = await processor.process(file_path, metadata)
        
        # Create document
        document = await self._create_document(processed, file_path, metadata)
        
        # Chunk the document
        chunks, sections = await self.chunking_service.chunk_document(
            str(document.document_id),
            processed["content"],
            metadata
        )
        
        # Generate embeddings
        texts = [chunk.content for chunk in chunks]
        embeddings = await self.embedding_service.generate_embeddings(texts)
        
        # Store chunks
        for chunk, embedding in zip(chunks, embeddings):
            await self.vector_store.store_chunk(chunk, embedding)
        
        # Store sections
        if sections:
            await self._store_sections(document.document_id, sections)
        
        return {
            "document": document,
            "chunks": len(chunks),
            "sections": len(sections),
            "embeddings": len(embeddings)
        }
    
    async def _create_document(
        self,
        processed: Dict[str, Any],
        file_path: str,
        metadata: Dict[str, Any]
    ) -> PolicyDocument:
        """Create document record"""
        
        # Extract metadata
        title = metadata.get('title') or Path(file_path).stem
        category = metadata.get('category', 'regulatory')
        source_type = Path(file_path).suffix.lower().replace('.', '')
        
        async with self.db_pool.acquire() as conn:
            # Check if document already exists by hash
            existing = await conn.fetchrow("""
                SELECT document_id FROM policy_documents
                WHERE file_hash = $1
            """, processed["file_hash"])
            
            if existing:
                logger.info(f"Document already exists: {existing['document_id']}")
                document = await self._get_document(existing['document_id'])
                return document
            
            # Insert document
            document_id = await conn.fetchval("""
                INSERT INTO policy_documents (
                    title, description, category, source_type,
                    file_path, file_hash, content_hash,
                    word_count, page_count, version,
                    effective_date, metadata
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                )
                RETURNING document_id
            """,
                title,
                metadata.get('description'),
                category,
                source_type,
                file_path,
                processed["file_hash"],
                hashlib.md5(processed["content"].encode()).hexdigest(),
                processed.get('word_count', 0),
                processed.get('page_count', 0),
                metadata.get('version', '1.0'),
                metadata.get('effective_date'),
                {**metadata, 'file_size': os.path.getsize(file_path)}
            )
            
            # Get the document
            document = await self._get_document(document_id)
            
            logger.info(f"Document created: {document_id}")
            return document
    
    async def _get_document(self, document_id: str) -> PolicyDocument:
        """Get document by ID"""
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM policy_documents
                WHERE document_id = $1
            """, document_id)
            
            if not row:
                return None
            
            return PolicyDocument(
                document_id=row['document_id'],
                title=row['title'],
                description=row['description'],
                category=row['category'],
                source_type=row['source_type'],
                source_url=row['source_url'],
                file_path=row['file_path'],
                file_hash=row['file_hash'],
                metadata=row['metadata'] or {},
                content_hash=row['content_hash'],
                language=row['language'],
                word_count=row['word_count'],
                page_count=row['page_count'],
                version=row['version'],
                effective_date=row['effective_date'],
                expiry_date=row['expiry_date'],
                is_active=row['is_active'],
                is_reviewed=row['is_reviewed'],
                reviewed_by=row['reviewed_by'],
                reviewed_at=row['reviewed_at'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
    
    async def _store_sections(self, document_id: str, sections: List):
        """Store document sections"""
        
        async with self.db_pool.acquire() as conn:
            for section in sections:
                await conn.execute("""
                    INSERT INTO policy_sections (
                        document_id, parent_section_id,
                        section_number, title, content,
                        level, path
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7
                    )
                """,
                    str(document_id),
                    str(section.parent_section_id) if section.parent_section_id else None,
                    section.section_number,
                    section.title,
                    section.content,
                    section.level,
                    section.path
                )
    
    async def ingest_directory(
        self,
        directory_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Ingest all documents in a directory"""
        
        results = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        # Get all supported files
        files = []
        for ext in self.config.supported_formats:
            files.extend(Path(directory_path).glob(f"*.{ext}"))
        
        results["total"] = len(files)
        
        for file_path in files:
            try:
                result = await self.ingest_file(str(file_path), metadata)
                results["success"] += 1
                logger.info(f"Successfully ingested: {file_path}")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "file": str(file_path),
                    "error": str(e)
                })
                logger.error(f"Failed to ingest {file_path}: {e}")
        
        return results
    
    async def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics"""
        
        async with self.db_pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_documents,
                    SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active_documents,
                    SUM(word_count) as total_words,
                    COUNT(DISTINCT category) as categories
                FROM policy_documents
            """)
            
            chunk_stats = await self.vector_store.get_stats()
            
            return {
                "documents": stats['total_documents'],
                "active_documents": stats['active_documents'],
                "total_words": stats['total_words'],
                "categories": stats['categories'],
                "chunks": chunk_stats['total_chunks']
            }
