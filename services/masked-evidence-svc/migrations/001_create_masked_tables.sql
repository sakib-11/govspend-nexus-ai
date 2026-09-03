-- Masked Evidence Service — database schema
-- Run: psql -d govspend_masked -f migrations/001_create_masked_tables.sql

BEGIN;

-- Masked Transactions Table
CREATE TABLE IF NOT EXISTS masked_transactions (
    transaction_id UUID PRIMARY KEY,
    masked_data   JSONB NOT NULL DEFAULT '{}'::jsonb,
    tokens        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_masked_transactions_created
    ON masked_transactions (created_at);

-- Masked Cases Table
CREATE TABLE IF NOT EXISTS masked_cases (
    case_id          UUID PRIMARY KEY,
    transaction_id   UUID REFERENCES masked_transactions (transaction_id) ON DELETE SET NULL,
    masked_case_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    tokens           JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_score       NUMERIC(5,4) CHECK (risk_score >= 0 AND risk_score <= 1),
    tier             TEXT,
    jurisdiction_id  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_masked_cases_tier
    ON masked_cases (tier);
CREATE INDEX IF NOT EXISTS idx_masked_cases_jurisdiction
    ON masked_cases (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_masked_cases_created
    ON masked_cases (created_at);
CREATE INDEX IF NOT EXISTS idx_masked_cases_transaction
    ON masked_cases (transaction_id);

-- Token Mapping Table
CREATE TABLE IF NOT EXISTS token_mappings (
    token                TEXT PRIMARY KEY,
    raw_identifier_hash  TEXT NOT NULL,
    entity_type          TEXT NOT NULL,
    prefix               TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_token_mappings_hash
    ON token_mappings (raw_identifier_hash);
CREATE INDEX IF NOT EXISTS idx_token_mappings_entity
    ON token_mappings (entity_type);

-- Masked Evidence Table
CREATE TABLE IF NOT EXISTS masked_evidence (
    evidence_id   UUID PRIMARY KEY,
    case_id       UUID REFERENCES masked_cases (case_id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL,
    masked_data   JSONB NOT NULL DEFAULT '{}'::jsonb,
    tokens        JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_hash TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_masked_evidence_case
    ON masked_evidence (case_id);
CREATE INDEX IF NOT EXISTS idx_masked_evidence_type
    ON masked_evidence (evidence_type);
CREATE INDEX IF NOT EXISTS idx_masked_evidence_hash
    ON masked_evidence (evidence_hash);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_masked_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_masked_transactions_updated ON masked_transactions;
CREATE TRIGGER trg_masked_transactions_updated
    BEFORE UPDATE ON masked_transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_masked_timestamp();

DROP TRIGGER IF EXISTS trg_masked_cases_updated ON masked_cases;
CREATE TRIGGER trg_masked_cases_updated
    BEFORE UPDATE ON masked_cases
    FOR EACH ROW
    EXECUTE FUNCTION update_masked_timestamp();

COMMIT;
