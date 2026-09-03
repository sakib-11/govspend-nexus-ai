-- LLM Prompt Service — database schema
-- Run: psql -d govspend_llm -f migrations/001_create_prompt_tables.sql

BEGIN;

-- ======================================================================
-- 1. Prompt Templates
-- ======================================================================
CREATE TABLE IF NOT EXISTS prompt_templates (
    template_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    description   TEXT,
    prompt_type   TEXT NOT NULL DEFAULT 'system',
    template      TEXT NOT NULL,
    variables     TEXT[] DEFAULT '{}',
    version       TEXT DEFAULT '1.0',
    is_active     BOOLEAN DEFAULT TRUE,
    metadata      JSONB DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_templates_name ON prompt_templates (name);
CREATE INDEX IF NOT EXISTS idx_templates_type ON prompt_templates (prompt_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_templates_name_version ON prompt_templates (name, version);

-- ======================================================================
-- 2. Prompt History (audit trail of generated prompts)
-- ======================================================================
CREATE TABLE IF NOT EXISTS prompt_history (
    history_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id       TEXT NOT NULL,
    template_name   TEXT,
    system_prompt   TEXT NOT NULL,
    user_prompt     TEXT NOT NULL,
    token_count     INTEGER,
    estimated_cost  FLOAT,
    llm_input       JSONB,
    variables_used  JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_history_prompt_id ON prompt_history (prompt_id);
CREATE INDEX IF NOT EXISTS idx_history_created ON prompt_history (created_at);

-- ======================================================================
-- 3. Validation Results
-- ======================================================================
CREATE TABLE IF NOT EXISTS validation_results (
    validation_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id       TEXT,
    is_valid        BOOLEAN NOT NULL,
    errors          JSONB DEFAULT '[]',
    warnings        JSONB DEFAULT '[]',
    grounding_score FLOAT,
    citation_coverage FLOAT,
    missing_evidence  JSONB DEFAULT '[]',
    missing_policies  JSONB DEFAULT '[]',
    suggestions     JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_validation_prompt ON validation_results (prompt_id);
CREATE INDEX IF NOT EXISTS idx_validation_created ON validation_results (created_at);

-- ======================================================================
-- 4. Prompt Metrics
-- ======================================================================
CREATE TABLE IF NOT EXISTS prompt_metrics (
    metric_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id       TEXT,
    template_name   TEXT,
    token_count     INTEGER,
    estimated_cost  FLOAT,
    latency_ms      FLOAT,
    validation_passed BOOLEAN,
    grounding_score FLOAT,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON prompt_metrics (timestamp);

-- ======================================================================
-- 5. Auto-update trigger
-- ======================================================================
CREATE OR REPLACE FUNCTION update_prompt_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_templates_updated ON prompt_templates;
CREATE TRIGGER trg_templates_updated
    BEFORE UPDATE ON prompt_templates
    FOR EACH ROW
    EXECUTE FUNCTION update_prompt_timestamp();

COMMIT;
