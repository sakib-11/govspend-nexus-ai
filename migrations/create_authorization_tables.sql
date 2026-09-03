-- Authorization Audit Logs Table
CREATE TABLE IF NOT EXISTS authorization_audit_logs (
    audit_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_id TEXT,
    resource_jurisdiction TEXT,
    user_roles TEXT[] DEFAULT '{}',
    user_permissions TEXT[] DEFAULT '{}',
    user_jurisdictions TEXT[] DEFAULT '{}',
    permission_checks_passed INTEGER DEFAULT 0,
    permission_checks_failed INTEGER DEFAULT 0,
    jurisdiction_checks_passed INTEGER DEFAULT 0,
    jurisdiction_checks_failed INTEGER DEFAULT 0,
    ip_address TEXT,
    user_agent TEXT,
    session_id TEXT,
    allowed BOOLEAN DEFAULT FALSE,
    message TEXT,
    details JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    response_time_ms NUMERIC(10,3),
    
    INDEX idx_auth_audit_user (user_id),
    INDEX idx_auth_audit_timestamp (timestamp),
    INDEX idx_auth_audit_resource (resource_type, action),
    INDEX idx_auth_audit_jurisdiction (resource_jurisdiction),
    INDEX idx_auth_audit_decision (decision)
);

-- Authorization Policies Table
CREATE TABLE IF NOT EXISTS authorization_policies (
    policy_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    version TEXT NOT NULL DEFAULT '1.0',
    permission_rules JSONB DEFAULT '[]',
    jurisdiction_rules JSONB DEFAULT '[]',
    role_rules JSONB DEFAULT '[]',
    allow_overrides JSONB DEFAULT '[]',
    deny_overrides JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT,
    
    INDEX idx_auth_policies_active (is_active)
);

-- Function to update updated_at
CREATE OR REPLACE FUNCTION update_auth_policy_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_auth_policy_timestamp
    BEFORE UPDATE ON authorization_policies
    FOR EACH ROW
    EXECUTE FUNCTION update_auth_policy_timestamp();

-- Insert default authorization policy
INSERT INTO authorization_policies (
    policy_id, name, description, version,
    permission_rules, jurisdiction_rules, role_rules,
    allow_overrides, deny_overrides, is_active, created_by
) VALUES (
    'default-policy',
    'Default Authorization Policy',
    'Default policy for GovSpend Nexus AI',
    '1.0',
    '[
        {"resource": "transaction", "action": "view", "roles": ["auditor_level_1", "auditor_level_2", "auditor_level_3"]},
        {"resource": "transaction", "action": "update", "roles": ["auditor_level_2", "auditor_level_3"]},
        {"resource": "case", "action": "close", "roles": ["approver", "admin", "super_admin"]},
        {"resource": "evidence", "action": "export", "roles": ["auditor_level_3", "admin", "super_admin"]}
    ]'::jsonb,
    '[
        {"rule": "user_jurisdiction_must_match_resource", "enabled": true}
    ]'::jsonb,
    '[
        {"role": "super_admin", "all_permissions": true}
    ]'::jsonb,
    '[
        {"condition": "emergency_override", "grant": true}
    ]'::jsonb,
    '[
        {"condition": "suspected_fraud", "deny": true}
    ]'::jsonb,
    TRUE,
    'system'
);