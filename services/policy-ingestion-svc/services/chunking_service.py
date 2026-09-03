from typing import List, Dict, Any, Optional, Tuple
import re
import hashlib
from models.policy import PolicyChunk, PolicySection
from config import PolicyIngestionConfig
import logging

logger = logging.getLogger(__name__)

class ChunkingService:
    """Service for chunking policy documents"""
    
    def __init__(self, config: PolicyIngestionConfig):
        self.config = config
        self.chunk_size = config.chunk_size
        self.chunk_overlap = config.chunk_overlap
    
    async def chunk_document(
        self,
        document_id: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> Tuple[List[PolicyChunk], List[PolicySection]]:
        """Chunk a document into smaller pieces"""
        
        # Clean text
        cleaned_content = self._clean_text(content)
        
        # Extract sections
        sections = self._extract_sections(cleaned_content)
        
        # Chunk by sections and paragraphs
        chunks = []
        chunk_number = 0
        
        if sections:
            # Process sections
            for section in sections:
                section_chunks = self._chunk_text(
                    section.content,
                    section_id=section.section_id
                )
                
                for chunk_content in section_chunks:
                    chunks.append(self._create_chunk(
                        document_id,
                        chunk_number,
                        chunk_content,
                        metadata
                    ))
                    chunk_number += 1
        else:
            # Process entire document
            text_chunks = self._chunk_text(cleaned_content)
            
            for chunk_content in text_chunks:
                chunks.append(self._create_chunk(
                    document_id,
                    chunk_number,
                    chunk_content,
                    metadata
                ))
                chunk_number += 1
        
        logger.info(f"Created {len(chunks)} chunks for document {document_id}")
        return chunks, sections
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep structure
        text = re.sub(r'[^\w\s\.\,\;\!\?\-\"\']', ' ', text)
        
        # Normalize line breaks
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()
    
    def _extract_sections(self, content: str) -> List[PolicySection]:
        """Extract sections from document content"""
        
        sections = []
        
        # Common section patterns for policy documents
        patterns = [
            (r'Chapter\s+(\d+)[\.\s]+([^\n]+)', 'Chapter'),
            (r'Section\s+(\d+)[\.\s]+([^\n]+)', 'Section'),
            (r'Article\s+(\d+)[\.\s]+([^\n]+)', 'Article'),
            (r'(\d+)\.[\s]+([^\n]+)', 'Numbered'),
            (r'([A-Z][A-Z\s]+):', 'Heading')
        ]
        
        lines = content.split('\n')
        current_section = None
        section_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line is a section header
            is_header = False
            for pattern, section_type in patterns:
                match = re.match(pattern, line)
                if match:
                    # Save previous section
                    if current_section:
                        sections.append(PolicySection(
                            document_id=None,  # Will be set later
                            title=current_section[0],
                            content='\n'.join(section_content),
                            level=len(sections) + 1
                        ))
                    
                    # Start new section
                    if len(match.groups()) == 2:
                        section_number = match.group(1)
                        title = match.group(2)
                    else:
                        section_number = str(len(sections) + 1)
                        title = line
                    
                    current_section = (title, section_number)
                    section_content = []
                    is_header = True
                    break
            
            if not is_header and current_section:
                section_content.append(line)
        
        # Save last section
        if current_section and section_content:
            sections.append(PolicySection(
                document_id=None,
                title=current_section[0],
                content='\n'.join(section_content),
                level=len(sections) + 1
            ))
        
        return sections
    
    def _chunk_text(
        self,
        text: str,
        section_id: Optional[str] = None
    ) -> List[str]:
        """Split text into chunks with overlap"""
        
        if not text:
            return []
        
        chunks = []
        
        # Split by paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        current_chunk = []
        current_length = 0
        
        for paragraph in paragraphs:
            paragraph_length = len(paragraph)
            
            if current_length + paragraph_length > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append('\n\n'.join(current_chunk))
                
                # Keep overlap
                overlap = []
                overlap_length = 0
                for p in reversed(current_chunk):
                    if overlap_length + len(p) <= self.chunk_overlap:
                        overlap.insert(0, p)
                        overlap_length += len(p)
                    else:
                        break
                
                current_chunk = overlap
                current_length = overlap_length
            
            current_chunk.append(paragraph)
            current_length += paragraph_length
        
        # Save last chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        # Ensure minimum chunk size
        chunks = [c for c in chunks if len(c) > 100]
        
        return chunks
    
    def _create_chunk(
        self,
        document_id: str,
        chunk_number: int,
        content: str,
        metadata: Dict[str, Any]
    ) -> PolicyChunk:
        """Create a policy chunk"""
        
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        return PolicyChunk(
            document_id=document_id,
            chunk_number=chunk_number,
            content=content,
            content_hash=content_hash,
            token_count=len(content.split()),
            metadata=metadata or {},
            start_position=0,
            end_position=len(content)
        )
