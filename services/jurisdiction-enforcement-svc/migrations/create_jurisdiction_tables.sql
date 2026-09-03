-- Jurisdictions Table
CREATE TABLE IF NOT EXISTS jurisdictions (
    jurisdiction_id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    level TEXT NOT NULL,
    parent_id TEXT,
    ancestors TEXT[] DEFAULT '{}',
    descendants TEXT[] DEFAULT '{}',
    depth INTEGER DEFAULT 0,
    jurisdiction_type TEXT NOT NULL,
    allowed_access JSONB DEFAULT '{}',
    default_access TEXT DEFAULT 'no_access',
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    FOREIGN KEY (parent_id) REFERENCES jurisdictions(jurisdiction_id),
    INDEX idx_jurisdictions_parent (parent_id),
    INDEX idx_jurisdictions_level (level),
    INDEX idx_jurisdictions_code (code),
    INDEX idx_jurisdictions_active (is_active)
);

-- User Jurisdictions Table
CREATE TABLE IF NOT EXISTS user_jurisdictions (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    jurisdiction_id TEXT NOT NULL REFERENCES jurisdictions(jurisdiction_id),
    access_level TEXT NOT NULL,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    assigned_by TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    
    UNIQUE (user_id, jurisdiction_id),
    INDEX idx_user_jurisdictions_user (user_id),
    INDEX idx_user_jurisdictions_jurisdiction (jurisdiction_id),
    INDEX idx_user_jurisdictions_active (is_active)
);

-- Resource Jurisdictions Table
CREATE TABLE IF NOT EXISTS resource_jurisdictions (
    id BIGSERIAL PRIMARY KEY,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    jurisdiction_id TEXT NOT NULL REFERENCES jurisdictions(jurisdiction_id),
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    assigned_by TEXT,
    metadata JSONB DEFAULT '{}',
    
    UNIQUE (resource_type, resource_id, jurisdiction_id),
    INDEX idx_resource_jurisdictions_resource (resource_type, resource_id),
    INDEX idx_resource_jurisdictions_jurisdiction (jurisdiction_id)
);

-- Cross-Jurisdiction Requests Table
CREATE TABLE IF NOT EXISTS cross_jurisdiction_requests (
    request_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_jurisdiction TEXT NOT NULL,
    target_jurisdiction TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    reason TEXT,
    requested_by TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    status TEXT DEFAULT 'pending',
    approved_by TEXT,
    approved_at TIMESTAMP WITH TIME ZONE,
    approved BOOLEAN DEFAULT FALSE,
    approval_reason TEXT,
    conditions JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_cross_requests_user (user_id),
    INDEX idx_cross_requests_status (status)
);

-- Jurisdiction Audit Logs Table
CREATE TABLE IF NOT EXISTS jurisdiction_audit_logs (
    request_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    resource_jurisdiction TEXT NOT NULL,
    user_jurisdictions TEXT[] NOT NULL,
    action TEXT NOT NULL,
    allowed BOOLEAN NOT NULL,
    reason TEXT NOT NULL,
    matching_jurisdictions TEXT[],
    hierarchy_check JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_audit_user (user_id),
    INDEX idx_audit_timestamp (timestamp),
    INDEX idx_audit_allowed (allowed),
    INDEX idx_audit_resource (resource_type, resource_id)
);

-- Function to update updated_at
CREATE OR REPLACE FUNCTION update_jurisdiction_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_jurisdiction_timestamp
    BEFORE UPDATE ON jurisdictions
    FOR EACH ROW
    EXECUTE FUNCTION update_jurisdiction_timestamp();

-- Insert default jurisdictions
INSERT INTO jurisdictions (jurisdiction_id, code, name, level, depth, jurisdiction_type) VALUES
('jur-001', 'US', 'United States', 'federal', 0, 'geographic'),
('jur-002', 'US-CA', 'California', 'state', 1, 'geographic'),
('jur-003', 'US-CA-SF', 'San Francisco', 'city', 2, 'geographic'),
('jur-004', 'US-NY', 'New York', 'state', 1, 'geographic'),
('jur-005', 'US-CA-LA', 'Los Angeles', 'city', 2, 'geographic'),
('jur-006', 'FED-AUDIT', 'Federal Audit', 'agency', 1, 'organizational'),
('jur-007', 'CA-AUDIT', 'California Audit', 'agency', 2, 'organizational');

-- Update parent relationships
UPDATE jurisdictions SET parent_id = 'jur-001' WHERE jurisdiction_id IN ('jur-002', 'jur-004', 'jur-006');
UPDATE jurisdictions SET parent_id = 'jur-002' WHERE jurisdiction_id IN ('jur-003', 'jur-005', 'jur-007');

-- Update ancestors and descendants
-- Note: In production, you'd use a recursive CTE or stored procedure