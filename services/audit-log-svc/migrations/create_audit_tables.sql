-- Audit Entries Table
CREATE TABLE IF NOT EXISTS audit_entries (
    audit_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    event_version TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_roles TEXT[] DEFAULT '{}',
    user_jurisdictions TEXT[] DEFAULT '{}',
    session_id TEXT,
    ip_address TEXT,
    user_agent TEXT,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    resource_token TEXT,
    jurisdiction_id TEXT,
    action TEXT NOT NULL,
    action_details JSONB DEFAULT '{}',
    request_id TEXT NOT NULL,
    request_data JSONB,
    response_data JSONB,
    response_status INTEGER,
    error_message TEXT,
    error_stack TEXT,
    duration_ms NUMERIC(10,3),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP WITH TIME ZONE,
    verification_hash TEXT,

    -- Hash chain columns
    previous_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    data_hash TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    blockchain_hash TEXT
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_entries (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_entries (timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_entries (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_entries (resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_jurisdiction ON audit_entries (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_entries (action);
CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_entries (status);
CREATE INDEX IF NOT EXISTS idx_audit_verified ON audit_entries (verified);
CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_entries (request_id);
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_entries (session_id);
CREATE INDEX IF NOT EXISTS idx_audit_sequence ON audit_entries (sequence_number);
CREATE INDEX IF NOT EXISTS idx_audit_hash_chain ON audit_entries (previous_hash, current_hash);

-- Audit Chain State Table (singleton row)
CREATE TABLE IF NOT EXISTS audit_chain_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    last_sequence_number INTEGER DEFAULT 0,
    last_hash TEXT NOT NULL,
    total_entries INTEGER DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verified BOOLEAN DEFAULT FALSE,
    last_verification TIMESTAMP WITH TIME ZONE,
    CONSTRAINT single_row CHECK (id = 1)
);

-- Audit Verification History Table
CREATE TABLE IF NOT EXISTS audit_verification_history (
    verification_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL REFERENCES audit_entries(audit_id),
    verified BOOLEAN NOT NULL,
    chain_valid BOOLEAN NOT NULL,
    tampered BOOLEAN NOT NULL,
    previous_hash_valid BOOLEAN NOT NULL,
    data_hash_valid BOOLEAN NOT NULL,
    chain_sequence_valid BOOLEAN NOT NULL,
    verification_details JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit Anomalies Table
CREATE TABLE IF NOT EXISTS audit_anomalies (
    anomaly_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL REFERENCES audit_entries(audit_id),
    anomaly_type TEXT NOT NULL,
    description TEXT,
    severity TEXT NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_anomalies_audit ON audit_anomalies (audit_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_detected ON audit_anomalies (detected_at);
CREATE INDEX IF NOT EXISTS idx_anomalies_resolved ON audit_anomalies (resolved);
