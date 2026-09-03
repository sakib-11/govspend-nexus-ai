-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Policy Documents Table
CREATE TABLE IF NOT EXISTS policy_documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_url TEXT,
    file_path TEXT,
    file_hash TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    content_hash TEXT,
    language TEXT DEFAULT 'en',
    word_count INTEGER,
    page_count INTEGER,
    version TEXT DEFAULT '1.0',
    effective_date DATE,
    expiry_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    is_reviewed BOOLEAN DEFAULT FALSE,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_policy_category (category),
    INDEX idx_policy_file_hash (file_hash),
    INDEX idx_policy_active (is_active),
    INDEX idx_policy_created (created_at)
);

-- Policy Chunks Table (with pgvector)
CREATE TABLE IF NOT EXISTS policy_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES policy_documents(document_id),
    chunk_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding vector(1536),
    start_position INTEGER,
    end_position INTEGER,
    token_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_chunk_document (document_id),
    INDEX idx_chunk_number (chunk_number),
    INDEX idx_chunk_embedding (embedding vector_cosine_ops)
);

-- Policy Metadata Table
CREATE TABLE IF NOT EXISTS policy_metadata (
    metadata_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES policy_documents(document_id),
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE (document_id, key),
    INDEX idx_metadata_key (key),
    INDEX idx_metadata_value (value)
);

-- Policy Sections Table (for hierarchical structure)
CREATE TABLE IF NOT EXISTS policy_sections (
    section_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES policy_documents(document_id),
    parent_section_id UUID REFERENCES policy_sections(section_id),
    section_number TEXT,
    title TEXT NOT NULL,
    content TEXT,
    level INTEGER DEFAULT 0,
    path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_section_document (document_id),
    INDEX idx_section_parent (parent_section_id),
    INDEX idx_section_level (level)
);

-- Policy References (cross-references between policies)
CREATE TABLE IF NOT EXISTS policy_references (
    reference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_document_id UUID REFERENCES policy_documents(document_id),
    to_document_id UUID REFERENCES policy_documents(document_id),
    reference_type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE (from_document_id, to_document_id, reference_type),
    INDEX idx_reference_from (from_document_id),
    INDEX idx_reference_to (to_document_id)
);

-- Ingestion Job Table
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    total_documents INTEGER DEFAULT 0,
    processed_documents INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    processed_chunks INTEGER DEFAULT 0,
    errors JSONB DEFAULT '{}',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    
    INDEX idx_job_status (status),
    INDEX idx_job_started (started_at)
);

-- Function to update updated_at
CREATE OR REPLACE FUNCTION update_policy_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_policy_documents_timestamp
    BEFORE UPDATE ON policy_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_policy_timestamp();

-- Function to search policies by embedding
CREATE OR REPLACE FUNCTION search_policies(
    query_embedding vector(1536),
    match_threshold float,
    match_count int,
    category_filter text DEFAULT NULL,
    active_only boolean DEFAULT TRUE
)
RETURNS TABLE(
    chunk_id UUID,
    document_id UUID,
    content TEXT,
    similarity float,
    document_title TEXT,
    document_category TEXT,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pc.chunk_id,
        pc.document_id,
        pc.content,
        1 - (pc.embedding <=> query_embedding) AS similarity,
        pd.title AS document_title,
        pd.category AS document_category,
        pc.metadata
    FROM policy_chunks pc
    JOIN policy_documents pd ON pc.document_id = pd.document_id
    WHERE 
        (category_filter IS NULL OR pd.category = category_filter)
        AND (active_only = FALSE OR pd.is_active = TRUE)
        AND 1 - (pc.embedding <=> query_embedding) > match_threshold
    ORDER BY pc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
