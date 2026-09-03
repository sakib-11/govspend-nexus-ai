-- Hash Chain Entries Table
CREATE TABLE IF NOT EXISTS hash_chain_entries (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id UUID NOT NULL UNIQUE,
    sequence_number BIGSERIAL UNIQUE NOT NULL,
    previous_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    resource_token TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    merkle_root TEXT,
    merkle_path TEXT[],
    signature TEXT,
    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_hashchain_audit ON hash_chain_entries (audit_id);
CREATE INDEX IF NOT EXISTS idx_hashchain_hash ON hash_chain_entries (current_hash, previous_hash);
CREATE INDEX IF NOT EXISTS idx_hashchain_timestamp ON hash_chain_entries (timestamp);
CREATE INDEX IF NOT EXISTS idx_hashchain_actor ON hash_chain_entries (actor);
CREATE INDEX IF NOT EXISTS idx_hashchain_verified ON hash_chain_entries (verified);

-- Daily Snapshots Table
CREATE TABLE IF NOT EXISTS daily_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL UNIQUE,
    start_sequence BIGINT NOT NULL,
    end_sequence BIGINT NOT NULL,
    merkle_root TEXT NOT NULL,
    root_hash TEXT NOT NULL,
    total_entries INTEGER NOT NULL,
    snapshot_hash TEXT NOT NULL,
    external_reference TEXT,
    blockchain_tx_hash TEXT,
    notary_signature TEXT,
    notary_timestamp TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_snapshot_merkle ON daily_snapshots (merkle_root);
CREATE INDEX IF NOT EXISTS idx_snapshot_blockchain ON daily_snapshots (blockchain_tx_hash);

-- Merkle Tree Nodes Table
CREATE TABLE IF NOT EXISTS merkle_tree_nodes (
    node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID REFERENCES daily_snapshots(snapshot_id),
    node_hash TEXT NOT NULL,
    node_level INTEGER NOT NULL,
    node_index INTEGER NOT NULL,
    left_child_hash TEXT,
    right_child_hash TEXT,
    parent_hash TEXT,
    is_leaf BOOLEAN DEFAULT FALSE,
    leaf_entry_id UUID
);

CREATE INDEX IF NOT EXISTS idx_merkle_snapshot ON merkle_tree_nodes (snapshot_id);
CREATE INDEX IF NOT EXISTS idx_merkle_hash ON merkle_tree_nodes (node_hash);
CREATE INDEX IF NOT EXISTS idx_merkle_level ON merkle_tree_nodes (node_level);

-- External Notary Records Table
CREATE TABLE IF NOT EXISTS notary_records (
    record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID REFERENCES daily_snapshots(snapshot_id),
    notary_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    root_hash TEXT NOT NULL,
    signature TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verification_url TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_notary_snapshot ON notary_records (snapshot_id);
CREATE INDEX IF NOT EXISTS idx_notary_external ON notary_records (external_id);
CREATE INDEX IF NOT EXISTS idx_notary_type ON notary_records (notary_type);

-- Verification Audit Table
CREATE TABLE IF NOT EXISTS verification_audit (
    verification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID REFERENCES daily_snapshots(snapshot_id),
    verified_by TEXT,
    verification_type TEXT NOT NULL,
    result BOOLEAN NOT NULL,
    details JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verification_snapshot ON verification_audit (snapshot_id);
CREATE INDEX IF NOT EXISTS idx_verification_timestamp ON verification_audit (timestamp);
CREATE INDEX IF NOT EXISTS idx_verification_result ON verification_audit (result);

-- Function to calculate hash chain entry
CREATE OR REPLACE FUNCTION calculate_hash_chain_entry(
    p_audit_id UUID,
    p_actor TEXT,
    p_action TEXT,
    p_resource TEXT,
    p_payload_hash TEXT,
    p_timestamp TIMESTAMP WITH TIME ZONE
) RETURNS TABLE(
    sequence_number BIGINT,
    previous_hash TEXT,
    current_hash TEXT
) AS $$
DECLARE
    v_prev_hash TEXT;
    v_hash_data TEXT;
    v_sequence BIGINT;
BEGIN
    -- Get previous hash
    SELECT current_hash, sequence_number INTO v_prev_hash, v_sequence
    FROM hash_chain_entries
    ORDER BY sequence_number DESC
    LIMIT 1;
    
    -- If no previous entry, use genesis hash
    IF v_prev_hash IS NULL THEN
        v_prev_hash := '0000000000000000000000000000000000000000000000000000000000000000';
        v_sequence := 0;
    END IF;
    
    -- Calculate hash
    v_hash_data := CONCAT(
        v_prev_hash,
        p_actor,
        p_action,
        p_resource,
        p_payload_hash,
        p_timestamp::text
    );
    
    -- Return values
    RETURN QUERY SELECT 
        v_sequence + 1 AS sequence_number,
        v_prev_hash AS previous_hash,
        ENCODE(SHA256(v_hash_data::bytea), 'hex') AS current_hash;
END;
$$ LANGUAGE plpgsql;

-- Function to verify hash chain
CREATE OR REPLACE FUNCTION verify_hash_chain(
    p_start_sequence BIGINT DEFAULT NULL,
    p_end_sequence BIGINT DEFAULT NULL
) RETURNS TABLE(
    entry_id UUID,
    sequence_number BIGINT,
    is_valid BOOLEAN,
    error_message TEXT
) AS $$
DECLARE
    v_prev_hash TEXT;
    v_hash_data TEXT;
    v_computed_hash TEXT;
    v_entry RECORD;
BEGIN
    -- Get bounds
    IF p_start_sequence IS NULL THEN
        SELECT MIN(sequence_number) INTO p_start_sequence FROM hash_chain_entries;
    END IF;
    
    IF p_end_sequence IS NULL THEN
        SELECT MAX(sequence_number) INTO p_end_sequence FROM hash_chain_entries;
    END IF;
    
    -- Iterate through entries
    FOR v_entry IN 
        SELECT * FROM hash_chain_entries
        WHERE sequence_number BETWEEN p_start_sequence AND p_end_sequence
        ORDER BY sequence_number ASC
    LOOP
        -- Verify hash
        v_hash_data := CONCAT(
            v_entry.previous_hash,
            v_entry.actor,
            v_entry.action,
            v_entry.resource,
            v_entry.payload_hash,
            v_entry.timestamp::text
        );
        
        v_computed_hash := ENCODE(SHA256(v_hash_data::bytea), 'hex');
        
        IF v_computed_hash != v_entry.current_hash THEN
            RETURN QUERY SELECT 
                v_entry.entry_id,
                v_entry.sequence_number,
                FALSE,
                'Hash mismatch at sequence ' || v_entry.sequence_number::text;
        END IF;
        
        -- Check previous hash chain
        IF v_prev_hash IS NOT NULL AND v_entry.previous_hash != v_prev_hash THEN
            RETURN QUERY SELECT 
                v_entry.entry_id,
                v_entry.sequence_number,
                FALSE,
                'Chain break at sequence ' || v_entry.sequence_number::text;
        END IF;
        
        v_prev_hash := v_entry.current_hash;
    END LOOP;
    
    -- If we got here, chain is valid
    RETURN QUERY SELECT 
        NULL::UUID,
        NULL::BIGINT,
        TRUE,
        'Chain is valid'::TEXT;
END;
$$ LANGUAGE plpgsql;
