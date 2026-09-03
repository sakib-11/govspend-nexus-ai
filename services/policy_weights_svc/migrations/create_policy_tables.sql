-- Policy Weights Management Schema
-- Run: psql -d govspend -f create_policy_tables.sql

-- Weight Policies Table
CREATE TABLE IF NOT EXISTS weight_policies (
    policy_id           TEXT PRIMARY KEY,
    version             TEXT NOT NULL UNIQUE,
    weights             JSONB NOT NULL,
    weights_sum         DECIMAL(6,4) NOT NULL,
    name                TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'draft',
    calibration_type    TEXT,
    calibration_reason  TEXT,
    calibration_data    JSONB,
    performance_metrics JSONB,
    previous_version    TEXT,
    supersedes_version  TEXT,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    activated_at        TIMESTAMP WITH TIME ZONE,
    deactivated_at      TIMESTAMP WITH TIME ZONE,
    created_by          TEXT NOT NULL DEFAULT 'system',
    approved_by         TEXT,
    approved_at         TIMESTAMP WITH TIME ZONE,
    tags                TEXT[] DEFAULT '{}',
    metadata            JSONB DEFAULT '{}',

    CONSTRAINT valid_status CHECK (
        status IN ('draft', 'active', 'inactive', 'archived',
                   'pending_approval', 'rejected', 'superseded')
    )
);

-- Policy Audit Log Table
CREATE TABLE IF NOT EXISTS policy_audit_log (
    audit_id        TEXT PRIMARY KEY,
    policy_id       TEXT NOT NULL REFERENCES weight_policies(policy_id) ON DELETE CASCADE,
    version         TEXT NOT NULL,
    action          TEXT NOT NULL,
    old_state       JSONB,
    new_state       JSONB NOT NULL,
    changed_fields  TEXT[] DEFAULT '{}',
    performed_by    TEXT NOT NULL,
    performed_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address      TEXT,
    user_agent      TEXT,
    reason          TEXT
);

-- Calibration History Table
CREATE TABLE IF NOT EXISTS calibration_history (
    calibration_id      TEXT PRIMARY KEY,
    policy_id           TEXT NOT NULL REFERENCES weight_policies(policy_id) ON DELETE CASCADE,
    calibration_type    TEXT NOT NULL,
    reason              TEXT NOT NULL,
    data                JSONB,
    performance_before  JSONB,
    performance_after   JSONB,
    created_by          TEXT NOT NULL DEFAULT 'system',
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMP WITH TIME ZONE,
    evaluation_status   TEXT DEFAULT 'pending',
    evaluation_results  JSONB
);

-- Active Policy Tracking (singleton row)
CREATE TABLE IF NOT EXISTS active_policy (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    policy_id       TEXT NOT NULL REFERENCES weight_policies(policy_id),
    version         TEXT NOT NULL,
    activated_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    activated_by    TEXT NOT NULL DEFAULT 'system',
    CONSTRAINT single_active_policy CHECK (id = 1)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_policies_status ON weight_policies(status);
CREATE INDEX IF NOT EXISTS idx_policies_version ON weight_policies(version);
CREATE INDEX IF NOT EXISTS idx_policies_created_at ON weight_policies(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_policies_tags ON weight_policies USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_policies_metadata ON weight_policies USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_audit_policy ON policy_audit_log(policy_id);
CREATE INDEX IF NOT EXISTS idx_audit_performed_at ON policy_audit_log(performed_at DESC);
CREATE INDEX IF NOT EXISTS idx_calibration_policy ON calibration_history(policy_id);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_policy_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_policy_timestamp ON weight_policies;
CREATE TRIGGER update_policy_timestamp
    BEFORE UPDATE ON weight_policies
    FOR EACH ROW
    EXECUTE FUNCTION update_policy_updated_at();
