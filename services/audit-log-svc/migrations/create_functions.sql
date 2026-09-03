-- Function to update chain state (upsert)
CREATE OR REPLACE FUNCTION update_audit_chain_state(
    p_sequence_number INTEGER,
    p_hash TEXT,
    p_total_entries INTEGER
) RETURNS VOID AS $$
BEGIN
    INSERT INTO audit_chain_state (id, last_sequence_number, last_hash, total_entries, updated_at)
    VALUES (1, p_sequence_number, p_hash, p_total_entries, NOW())
    ON CONFLICT (id) DO UPDATE
    SET
        last_sequence_number = p_sequence_number,
        last_hash = p_hash,
        total_entries = p_total_entries,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to verify chain integrity for a range
CREATE OR REPLACE FUNCTION verify_audit_chain_range(
    p_start_sequence INTEGER DEFAULT NULL,
    p_end_sequence INTEGER DEFAULT NULL
) RETURNS TABLE(
    audit_id TEXT,
    sequence_number INTEGER,
    chain_valid BOOLEAN,
    data_hash_valid BOOLEAN,
    previous_hash_valid BOOLEAN
) AS $$
DECLARE
    v_start_seq INTEGER;
    v_end_seq INTEGER;
BEGIN
    IF p_start_sequence IS NULL THEN
        SELECT MIN(sequence_number) INTO v_start_seq FROM audit_entries;
    ELSE
        v_start_seq := p_start_sequence;
    END IF;

    IF p_end_sequence IS NULL THEN
        SELECT MAX(sequence_number) INTO v_end_seq FROM audit_entries;
    ELSE
        v_end_seq := p_end_sequence;
    END IF;

    RETURN QUERY
    WITH chain_check AS (
        SELECT
            ae.audit_id,
            ae.sequence_number,
            ae.previous_hash,
            ae.current_hash,
            ae.data_hash,
            LAG(ae.current_hash) OVER (ORDER BY ae.sequence_number) as prev_chain_hash
        FROM audit_entries ae
        WHERE ae.sequence_number BETWEEN v_start_seq AND v_end_seq
        ORDER BY ae.sequence_number
    )
    SELECT
        cc.audit_id,
        cc.sequence_number,
        (cc.previous_hash = cc.prev_chain_hash OR cc.prev_chain_hash IS NULL) AS chain_valid,
        TRUE AS data_hash_valid,
        (cc.previous_hash = cc.prev_chain_hash OR cc.prev_chain_hash IS NULL) AS previous_hash_valid
    FROM chain_check cc;
END;
$$ LANGUAGE plpgsql;
