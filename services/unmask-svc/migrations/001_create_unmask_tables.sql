-- Unmask Service — database schema
-- Run: psql -d govspend_unmask -f migrations/001_create_unmask_tables.sql

BEGIN;

-- ======================================================================
-- 1. Unmask Requests Table
-- ======================================================================
CREATE TABLE IF NOT EXISTS unmask_requests (
    request_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id           UUID NOT NULL,
    entity_type       TEXT NOT NULL,
    entity_token      TEXT NOT NULL,
    reason            TEXT NOT NULL,
    requested_by      TEXT NOT NULL,
    requested_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status            TEXT NOT NULL DEFAULT 'pending',
    approved_by       TEXT,
    approved_at       TIMESTAMPTZ,
    unmasked_by       TEXT,
    unmasked_at       TIMESTAMPTZ,
    viewed_by         TEXT,
    viewed_at         TIMESTAMPTZ,
    expired_at        TIMESTAMPTZ,
    rejection_reason  TEXT,
    jurisdiction_id   TEXT NOT NULL DEFAULT 'unknown',
    mfa_verified      BOOLEAN DEFAULT FALSE,
    mfa_verified_at   TIMESTAMPTZ,
    unmasked_data     JSONB,
    data_checksum     TEXT,
    metadata          JSONB DEFAULT '{}'::jsonb,
    version           INTEGER DEFAULT 1,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_unmask_status ON unmask_requests (status);
CREATE INDEX IF NOT EXISTS idx_unmask_requested_by ON unmask_requests (requested_by);
CREATE INDEX IF NOT EXISTS idx_unmask_case ON unmask_requests (case_id);
CREATE INDEX IF NOT EXISTS idx_unmask_entity ON unmask_requests (entity_type, entity_token);
CREATE INDEX IF NOT EXISTS idx_unmask_jurisdiction ON unmask_requests (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_unmask_expires ON unmask_requests (expired_at);
CREATE INDEX IF NOT EXISTS idx_unmask_created ON unmask_requests (created_at);

-- ======================================================================
-- 2. Unmask Audit Log (Tamper-Evident Hash Chain)
-- ======================================================================
CREATE TABLE IF NOT EXISTS unmask_audit_log (
    audit_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID REFERENCES unmask_requests (request_id) ON DELETE CASCADE,
    action          TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    from_status     TEXT,
    to_status       TEXT,
    details         JSONB DEFAULT '{}'::jsonb,
    ip_address      TEXT,
    user_agent      TEXT,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    previous_hash   TEXT NOT NULL,
    current_hash    TEXT NOT NULL,
    payload_hash    TEXT NOT NULL,
    signature       TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_request ON unmask_audit_log (request_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON unmask_audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON unmask_audit_log (timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON unmask_audit_log (action);

-- ======================================================================
-- 3. MFA Verification Table
-- ======================================================================
CREATE TABLE IF NOT EXISTS mfa_verifications (
    verification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID REFERENCES unmask_requests (request_id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,
    method          TEXT NOT NULL DEFAULT 'totp',
    code_hash       TEXT NOT NULL,
    attempts        INTEGER DEFAULT 0,
    verified        BOOLEAN DEFAULT FALSE,
    verified_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mfa_request ON mfa_verifications (request_id);
CREATE INDEX IF NOT EXISTS idx_mfa_user ON mfa_verifications (user_id);
CREATE INDEX IF NOT EXISTS idx_mfa_expires ON mfa_verifications (expires_at);

-- ======================================================================
-- 4. MFA Backup Codes
-- ======================================================================
CREATE TABLE IF NOT EXISTS mfa_backup_codes (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    code_hash   TEXT NOT NULL,
    used        BOOLEAN DEFAULT FALSE,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, code_hash)
);

CREATE INDEX IF NOT EXISTS idx_backup_user ON mfa_backup_codes (user_id);

-- ======================================================================
-- 5. Unmask Access Log
-- ======================================================================
CREATE TABLE IF NOT EXISTS unmask_access_log (
    access_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID REFERENCES unmask_requests (request_id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,
    action          TEXT NOT NULL,
    data_accessed   TEXT[],
    data_hash       TEXT,
    ip_address      TEXT,
    user_agent      TEXT,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_access_request ON unmask_access_log (request_id);
CREATE INDEX IF NOT EXISTS idx_access_user ON unmask_access_log (user_id);
CREATE INDEX IF NOT EXISTS idx_access_timestamp ON unmask_access_log (timestamp);

-- ======================================================================
-- 6. Rate Limiting Table
-- ======================================================================
CREATE TABLE IF NOT EXISTS unmask_rate_limit (
    id            SERIAL PRIMARY KEY,
    user_id       TEXT NOT NULL,
    action        TEXT NOT NULL,
    count         INTEGER DEFAULT 1,
    window_start  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rate_user ON unmask_rate_limit (user_id);
CREATE INDEX IF NOT EXISTS idx_rate_action ON unmask_rate_limit (action);
CREATE INDEX IF NOT EXISTS idx_rate_window ON unmask_rate_limit (window_start);

-- ======================================================================
-- 7. Auto-update updated_at trigger
-- ======================================================================
CREATE OR REPLACE FUNCTION update_unmask_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_unmask_requests_updated ON unmask_requests;
CREATE TRIGGER trg_unmask_requests_updated
    BEFORE UPDATE ON unmask_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_unmask_timestamp();

-- ======================================================================
-- 8. Hash chain trigger for audit log
-- ======================================================================
CREATE OR REPLACE FUNCTION calculate_unmask_hash_chain()
RETURNS TRIGGER AS $$
DECLARE
    prev_hash TEXT;
    hash_data TEXT;
BEGIN
    SELECT current_hash INTO prev_hash
    FROM unmask_audit_log
    ORDER BY timestamp DESC, audit_id DESC
    LIMIT 1;

    NEW.previous_hash := COALESCE(
        prev_hash,
        '0000000000000000000000000000000000000000000000000000000000000000'
    );

    hash_data := CONCAT(
        NEW.previous_hash,
        NEW.action,
        NEW.user_id,
        COALESCE(NEW.request_id::TEXT, ''),
        NEW.timestamp::TEXT,
        NEW.payload_hash,
        COALESCE(NEW.from_status, ''),
        COALESCE(NEW.to_status, '')
    );

    NEW.current_hash := ENCODE(DIGEST(hash_data::bytea, 'sha256'), 'hex');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_unmask_audit_hash ON unmask_audit_log;
CREATE TRIGGER trg_unmask_audit_hash
    BEFORE INSERT ON unmask_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION calculate_unmask_hash_chain();

-- ======================================================================
-- 9. Self-approval prevention trigger
-- ======================================================================
CREATE OR REPLACE FUNCTION check_unmask_self_approval()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'approved' AND NEW.approved_by = NEW.requested_by THEN
        RAISE EXCEPTION 'Self-approval is not allowed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_self_approval ON unmask_requests;
CREATE TRIGGER trg_prevent_self_approval
    BEFORE UPDATE ON unmask_requests
    FOR EACH ROW
    WHEN (NEW.status = 'approved' AND NEW.approved_by = NEW.requested_by)
    EXECUTE FUNCTION check_unmask_self_approval();

COMMIT;
