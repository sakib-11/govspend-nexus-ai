-- Secure Ledger Table (Encrypted at rest)
CREATE TABLE IF NOT EXISTS ledger_entries (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,
    entity_token TEXT NOT NULL,
    encrypted_data BYTEA NOT NULL,
    encryption_key_id TEXT NOT NULL,
    encryption_algorithm TEXT NOT NULL,
    iv BYTEA NOT NULL,
    auth_tag BYTEA NOT NULL,
    data_hash TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Indexes
    INDEX idx_ledger_entity (entity_type, entity_token),
    INDEX idx_ledger_created (created_at),
    INDEX idx_ledger_active (is_active),
    INDEX idx_ledger_key_id (encryption_key_id),
    CONSTRAINT unique_entity_token UNIQUE (entity_type, entity_token)
);

-- Audit Log Table (Tamper-Evident)
CREATE TABLE IF NOT EXISTS ledger_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id UUID REFERENCES ledger_entries(entry_id),
    action TEXT NOT NULL,
    user_id TEXT NOT NULL,
    service_name TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    details JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    previous_hash TEXT,
    current_hash TEXT,
    payload_hash TEXT,
    
    INDEX idx_audit_entry (entry_id),
    INDEX idx_audit_timestamp (timestamp),
    INDEX idx_audit_user (user_id),
    INDEX idx_audit_action (action)
);

-- Key Management Table
CREATE TABLE IF NOT EXISTS key_management (
    key_id TEXT PRIMARY KEY,
    key_version TEXT NOT NULL,
    key_type TEXT NOT NULL,
    key_metadata JSONB DEFAULT '{}',
    activated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    rotated_from TEXT,
    created_by TEXT,
    
    INDEX idx_key_active (is_active),
    INDEX idx_key_expires (expires_at)
);

-- Access Control Table
CREATE TABLE IF NOT EXISTS ledger_access_control (
    id SERIAL PRIMARY KEY,
    service_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    access_level TEXT NOT NULL, -- READ, WRITE, DELETE
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    granted_by TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE (service_name, entity_type)
);

-- Data Retention Policy Table
CREATE TABLE IF NOT EXISTS data_retention_policy (
    id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL UNIQUE,
    retention_days INTEGER NOT NULL,
    archive_enabled BOOLEAN DEFAULT FALSE,
    archive_location TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Function to update updated_at
CREATE OR REPLACE FUNCTION update_ledger_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_ledger_entries_timestamp
    BEFORE UPDATE ON ledger_entries
    FOR EACH ROW
    EXECUTE FUNCTION update_ledger_timestamp();

-- Function for hash chain
CREATE OR REPLACE FUNCTION calculate_hash_chain()
RETURNS TRIGGER AS $$
DECLARE
    prev_hash TEXT;
BEGIN
    -- Get previous hash
    SELECT current_hash INTO prev_hash 
    FROM ledger_audit_log 
    ORDER BY timestamp DESC 
    LIMIT 1;
    
    -- Set previous hash
    NEW.previous_hash := COALESCE(prev_hash, '0000000000000000000000000000000000000000000000000000000000000000');
    
    -- Calculate current hash
    NEW.current_hash := ENCODE(
        SHA256(
            CONCAT(
                NEW.previous_hash,
                NEW.action,
                NEW.user_id,
                NEW.entry_id::text,
                NEW.timestamp::text,
                NEW.payload_hash
            )::bytea
        ),
        'hex'
    );
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER calculate_audit_hash
    BEFORE INSERT ON ledger_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION calculate_hash_chain();

-- Insert default retention policies
INSERT INTO data_retention_policy (entity_type, retention_days) VALUES
('vendor', 3650),  -- 10 years
('official', 3650),
('transaction', 3650),
('invoice', 3650),
('user', 365);

-- Insert default access control
INSERT INTO ledger_access_control (service_name, entity_type, access_level) VALUES
('unmask-svc', 'vendor', 'READ'),
('unmask-svc', 'official', 'READ'),
('unmask-svc', 'transaction', 'READ'),
('unmask-svc', 'invoice', 'READ'),
('admin-svc', 'vendor', 'WRITE'),
('admin-svc', 'official', 'WRITE');
