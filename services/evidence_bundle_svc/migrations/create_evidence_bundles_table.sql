-- Evidence Bundle Storage Schema
-- Run: psql -d govspend -f create_evidence_bundles_table.sql

-- Main bundles table — stores the full JSON blob plus denormalised columns
-- for fast filtering without deserialising the payload.
CREATE TABLE IF NOT EXISTS evidence_bundles (
    bundle_id           TEXT PRIMARY KEY,
    transaction_id      TEXT NOT NULL,
    version             TEXT NOT NULL DEFAULT '1.0',
    status              TEXT NOT NULL DEFAULT 'PENDING',
    bundle_format       TEXT NOT NULL DEFAULT 'JSON_EXTENDED',
    bundle_data         JSONB,
    weights_version     TEXT,
    risk_score          DECIMAL(5,4),
    risk_tier           TEXT,
    confidence_factor   DECIMAL(5,4),
    detector_types      TEXT[] DEFAULT '{}',
    evidence_count      INTEGER DEFAULT 0,
    size_bytes          INTEGER DEFAULT 0,
    storage_checksum    TEXT,
    tags                TEXT[] DEFAULT '{}',
    metadata            JSONB DEFAULT '{}',
    assembled_at        TIMESTAMP WITH TIME ZONE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    retrieved_at        TIMESTAMP WITH TIME ZONE,
    archived_at         TIMESTAMP WITH TIME ZONE
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_bundles_transaction
    ON evidence_bundles (transaction_id);
CREATE INDEX IF NOT EXISTS idx_bundles_status
    ON evidence_bundles (status);
CREATE INDEX IF NOT EXISTS idx_bundles_risk_tier
    ON evidence_bundles (risk_tier);
CREATE INDEX IF NOT EXISTS idx_bundles_assembled_at
    ON evidence_bundles (assembled_at DESC);
CREATE INDEX IF NOT EXISTS idx_bundles_created_at
    ON evidence_bundles (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bundles_tags
    ON evidence_bundles USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_bundles_detector_types
    ON evidence_bundles USING GIN (detector_types);
CREATE INDEX IF NOT EXISTS idx_bundles_metadata
    ON evidence_bundles USING GIN (metadata);

-- Individual evidence items — enables granular querying without
-- deserialising the full bundle JSON.
CREATE TABLE IF NOT EXISTS bundle_evidence_items (
    id              BIGSERIAL PRIMARY KEY,
    bundle_id       TEXT NOT NULL REFERENCES evidence_bundles(bundle_id) ON DELETE CASCADE,
    evidence_id     TEXT NOT NULL,
    source          TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    confidence      DECIMAL(5,4),
    relevance_score DECIMAL(5,4) DEFAULT 1.0,
    data            JSONB,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uq_evidence_bundle_id UNIQUE (bundle_id, evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_bundle
    ON bundle_evidence_items (bundle_id);
CREATE INDEX IF NOT EXISTS idx_evidence_source
    ON bundle_evidence_items (source);
CREATE INDEX IF NOT EXISTS idx_evidence_source_type
    ON bundle_evidence_items (source_type);

-- Auto-update updated_at on row modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_bundles_updated_at ON evidence_bundles;
CREATE TRIGGER update_bundles_updated_at
    BEFORE UPDATE ON evidence_bundles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
