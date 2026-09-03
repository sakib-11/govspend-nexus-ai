-- RAG Retriever Service — database schema
-- Run: psql -d govspend_policies -f migrations/001_create_retrieval_tables.sql

BEGIN;

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ======================================================================
-- 1. Policy Documents
-- ======================================================================
CREATE TABLE IF NOT EXISTS policy_documents (
    document_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'general',
    source        TEXT,
    content_hash  TEXT,
    is_active     BOOLEAN DEFAULT TRUE,
    metadata      JSONB DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_policy_docs_category ON policy_documents (category);
CREATE INDEX IF NOT EXISTS idx_policy_docs_active ON policy_documents (is_active);

-- ======================================================================
-- 2. Policy Chunks (with vector embeddings)
-- ======================================================================
CREATE TABLE IF NOT EXISTS policy_chunks (
    chunk_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID REFERENCES policy_documents (document_id) ON DELETE CASCADE,
    content       TEXT NOT NULL,
    chunk_index   INTEGER DEFAULT 0,
    embedding     VECTOR(1536),
    search_vector TSVECTOR,
    metadata      JSONB DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON policy_chunks (document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_search ON policy_chunks USING GIN (search_vector);

-- HNSW index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON policy_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ======================================================================
-- 3. Retrieval Cache
-- ======================================================================
CREATE TABLE IF NOT EXISTS retrieval_cache (
    cache_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash  TEXT NOT NULL UNIQUE,
    query       TEXT NOT NULL,
    results     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cache_hash ON retrieval_cache (query_hash);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON retrieval_cache (expires_at);

-- ======================================================================
-- 4. Retrieval Metrics
-- ======================================================================
CREATE TABLE IF NOT EXISTS retrieval_metrics (
    metric_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id        TEXT NOT NULL,
    query_type      TEXT NOT NULL,
    result_count    INTEGER,
    avg_similarity  FLOAT,
    max_similarity  FLOAT,
    min_similarity  FLOAT,
    latency_ms      FLOAT,
    cache_hit       BOOLEAN DEFAULT FALSE,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON retrieval_metrics (timestamp);
CREATE INDEX IF NOT EXISTS idx_metrics_query ON retrieval_metrics (query_id);

-- ======================================================================
-- 5. Retrieval Feedback
-- ======================================================================
CREATE TABLE IF NOT EXISTS retrieval_feedback (
    feedback_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id        TEXT NOT NULL,
    chunk_id        UUID NOT NULL,
    relevance_score FLOAT,
    user_id         TEXT,
    feedback_type   TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_query ON retrieval_feedback (query_id);
CREATE INDEX IF NOT EXISTS idx_feedback_chunk ON retrieval_feedback (chunk_id);

-- ======================================================================
-- 6. Query Synonyms
-- ======================================================================
CREATE TABLE IF NOT EXISTS query_synonyms (
    synonym_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term        TEXT NOT NULL,
    synonym     TEXT NOT NULL,
    category    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (term, synonym)
);

CREATE INDEX IF NOT EXISTS idx_synonym_term ON query_synonyms (term);

-- ======================================================================
-- 7. Seed domain synonyms
-- ======================================================================
INSERT INTO query_synonyms (term, synonym, category) VALUES
('procurement', 'purchasing', 'domain'),
('procurement', 'acquisition', 'domain'),
('fraud', 'misconduct', 'domain'),
('fraud', 'irregularity', 'domain'),
('audit', 'review', 'domain'),
('audit', 'examination', 'domain'),
('compliance', 'adherence', 'domain'),
('compliance', 'conformance', 'domain'),
('vendor', 'supplier', 'domain'),
('vendor', 'contractor', 'domain'),
('invoice', 'bill', 'domain'),
('invoice', 'charge', 'domain'),
('price', 'cost', 'domain'),
('price', 'rate', 'domain'),
('duplicate', 'copy', 'domain'),
('duplicate', 'repeat', 'domain'),
('anomaly', 'outlier', 'domain'),
('anomaly', 'deviation', 'domain')
ON CONFLICT (term, synonym) DO NOTHING;

-- ======================================================================
-- 8. Auto-update trigger
-- ======================================================================
CREATE OR REPLACE FUNCTION update_policy_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_policy_docs_updated ON policy_documents;
CREATE TRIGGER trg_policy_docs_updated
    BEFORE UPDATE ON policy_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_policy_timestamp();

COMMIT;
