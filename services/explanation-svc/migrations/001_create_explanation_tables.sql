-- Explanation Service — database schema
-- Run: psql -d govspend_explanations -f migrations/001_create_explanation_tables.sql

BEGIN;

-- ======================================================================
-- 1. Case Explanations
-- ======================================================================
CREATE TABLE IF NOT EXISTS case_explanations (
    explanation_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             TEXT NOT NULL,
    transaction_id      TEXT,
    summary             TEXT NOT NULL,
    confidence          FLOAT NOT NULL DEFAULT 0.0,
    explanations        JSONB NOT NULL DEFAULT '[]',
    grounding_score     FLOAT NOT NULL DEFAULT 0.0,
    citations_used      INTEGER DEFAULT 0,
    total_evidence      INTEGER DEFAULT 0,
    total_policies      INTEGER DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'completed',
    llm_model           TEXT,
    llm_provider        TEXT,
    generation_time_ms  FLOAT DEFAULT 0.0,
    token_count         INTEGER DEFAULT 0,
    validated           BOOLEAN DEFAULT FALSE,
    validation_attempts INTEGER DEFAULT 0,
    validation_errors   JSONB DEFAULT '[]',
    is_fallback         BOOLEAN DEFAULT FALSE,
    fallback_reason     TEXT,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    validated_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_explanations_case ON case_explanations (case_id);
CREATE INDEX IF NOT EXISTS idx_explanations_status ON case_explanations (status);
CREATE INDEX IF NOT EXISTS idx_explanations_generated ON case_explanations (generated_at);

-- ======================================================================
-- 2. Explanation Metrics
-- ======================================================================
CREATE TABLE IF NOT EXISTS explanation_metrics (
    metric_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    explanation_id      UUID,
    case_id             TEXT,
    llm_provider        TEXT,
    llm_model           TEXT,
    generation_time_ms  FLOAT,
    token_count         INTEGER,
    validation_passed   BOOLEAN,
    grounding_score     FLOAT,
    confidence_score    FLOAT,
    is_fallback         BOOLEAN DEFAULT FALSE,
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exp_metrics_timestamp ON explanation_metrics (timestamp);

-- ======================================================================
-- 3. Explanation Cache (for Redis-miss fallback)
-- ======================================================================
CREATE TABLE IF NOT EXISTS explanation_cache (
    cache_key   TEXT PRIMARY KEY,
    case_id     TEXT NOT NULL,
    response    JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_exp_cache_case ON explanation_cache (case_id);
CREATE INDEX IF NOT EXISTS idx_exp_cache_expires ON explanation_cache (expires_at);

COMMIT;
