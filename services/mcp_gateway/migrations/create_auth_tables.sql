-- ============================================================
-- MCP Gateway: Authentication & RBAC Schema
-- ============================================================

-- Users Table
CREATE TABLE IF NOT EXISTS mcp_users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    roles TEXT[] NOT NULL DEFAULT '{}',
    jurisdictions TEXT[] NOT NULL DEFAULT '{}',
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_methods TEXT[] DEFAULT '{}',
    active_session_id TEXT,
    last_login TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    is_locked BOOLEAN DEFAULT FALSE,
    failed_attempts INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_mcp_users_username ON mcp_users (username);
CREATE INDEX IF NOT EXISTS idx_mcp_users_email ON mcp_users (email);
CREATE INDEX IF NOT EXISTS idx_mcp_users_active ON mcp_users (is_active);

-- Sessions Table
CREATE TABLE IF NOT EXISTS mcp_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES mcp_users(user_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    ip_address TEXT,
    user_agent TEXT,
    device_id TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    mfa_verified BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_mcp_sessions_user ON mcp_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_mcp_sessions_expires ON mcp_sessions (expires_at);
CREATE INDEX IF NOT EXISTS idx_mcp_sessions_active ON mcp_sessions (is_active);

-- Audit Logs Table
CREATE TABLE IF NOT EXISTS mcp_audit_logs (
    audit_id TEXT PRIMARY KEY,
    user_id TEXT,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    details JSONB DEFAULT '{}',
    ip_address TEXT,
    user_agent TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    jurisdiction_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_mcp_audit_user ON mcp_audit_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_mcp_audit_action ON mcp_audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_mcp_audit_timestamp ON mcp_audit_logs (timestamp);
CREATE INDEX IF NOT EXISTS idx_mcp_audit_jurisdiction ON mcp_audit_logs (jurisdiction_id);

-- Jurisdictions Table
CREATE TABLE IF NOT EXISTS mcp_jurisdictions (
    jurisdiction_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    level TEXT NOT NULL,
    parent_id TEXT,
    code TEXT UNIQUE NOT NULL,
    region TEXT NOT NULL,
    country TEXT DEFAULT 'US',
    allowed_roles TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcp_jurisdictions_level ON mcp_jurisdictions (level);
CREATE INDEX IF NOT EXISTS idx_mcp_jurisdictions_parent ON mcp_jurisdictions (parent_id);

-- MFA Secrets Table
CREATE TABLE IF NOT EXISTS mcp_mfa_secrets (
    user_id TEXT PRIMARY KEY REFERENCES mcp_users(user_id),
    totp_secret TEXT,
    totp_enabled BOOLEAN DEFAULT FALSE,
    backup_codes TEXT[] DEFAULT '{}',
    phone_number TEXT,
    sms_enabled BOOLEAN DEFAULT FALSE,
    email_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Role Permissions Table
CREATE TABLE IF NOT EXISTS mcp_role_permissions (
    role TEXT PRIMARY KEY,
    permissions TEXT[] NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert Default Role Permissions
INSERT INTO mcp_role_permissions (role, permissions, description) VALUES
('read_only', ARRAY['view_transaction','view_detection','view_score','view_case','view_evidence'], 'Restricted read-only'),
('auditor_level_1', ARRAY['view_transaction','view_detection','view_score','view_case','view_evidence'], 'Basic read-only access'),
('data_analyst', ARRAY['view_transaction','view_detection','view_score','view_case','view_evidence','view_system_metrics'], 'Data analysis access'),
('reviewer', ARRAY['view_transaction','view_sensitive_transaction','view_detection','view_score','view_case','update_case','view_evidence','view_sensitive_evidence'], 'Case review access'),
('auditor_level_2', ARRAY['view_transaction','view_sensitive_transaction','view_detection','run_detection','view_score','view_case','create_case','update_case','view_evidence','view_sensitive_evidence'], 'Advanced read-write access'),
('auditor_level_3', ARRAY['view_transaction','view_sensitive_transaction','create_transaction','update_transaction','view_detection','run_detection','update_detection_config','view_score','update_score_weights','override_score','view_case','create_case','update_case','close_case','escalate_case','view_evidence','view_sensitive_evidence','export_evidence'], 'Full audit access'),
('compliance_officer', ARRAY['view_transaction','view_sensitive_transaction','view_detection','view_score','view_case','update_case','escalate_case','view_evidence','view_sensitive_evidence','view_audit_logs'], 'Compliance oversight'),
('approver', ARRAY['view_transaction','view_sensitive_transaction','view_detection','view_score','view_case','update_case','close_case','escalate_case','view_evidence','view_sensitive_evidence'], 'Approval authority'),
('admin', ARRAY['view_transaction','view_sensitive_transaction','create_transaction','update_transaction','delete_transaction','view_detection','run_detection','update_detection_config','view_score','update_score_weights','override_score','view_case','create_case','update_case','close_case','escalate_case','view_evidence','view_sensitive_evidence','export_evidence','manage_users','manage_roles','view_audit_logs','system_config','view_system_metrics'], 'System administrator'),
('super_admin', ARRAY['view_transaction','view_sensitive_transaction','create_transaction','update_transaction','delete_transaction','view_detection','run_detection','update_detection_config','view_score','update_score_weights','override_score','view_case','create_case','update_case','close_case','escalate_case','view_evidence','view_sensitive_evidence','export_evidence','manage_users','manage_roles','view_audit_logs','system_config','view_system_metrics','access_jurisdiction','cross_jurisdiction_view'], 'Full system access')
ON CONFLICT (role) DO NOTHING;

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION update_mcp_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_mcp_users_timestamp
    BEFORE UPDATE ON mcp_users
    FOR EACH ROW EXECUTE FUNCTION update_mcp_timestamp();

CREATE TRIGGER update_mcp_jurisdictions_timestamp
    BEFORE UPDATE ON mcp_jurisdictions
    FOR EACH ROW EXECUTE FUNCTION update_mcp_timestamp();
