-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS masked_evidence;
CREATE SCHEMA IF NOT EXISTS ledger;

-- Create users
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'ingestion_user') THEN
        CREATE USER ingestion_user WITH PASSWORD 'ingestion_pass';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'detection_user') THEN
        CREATE USER detection_user WITH PASSWORD 'detection_pass';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'scoring_user') THEN
        CREATE USER scoring_user WITH PASSWORD 'scoring_pass';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'gateway_user') THEN
        CREATE USER gateway_user WITH PASSWORD 'gateway_pass';
    END IF;
END $$;

-- Grant privileges
GRANT CONNECT ON DATABASE govspend TO ingestion_user, detection_user, scoring_user, gateway_user;
GRANT USAGE ON SCHEMA masked_evidence TO ingestion_user, detection_user, scoring_user, gateway_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA masked_evidence TO ingestion_user, detection_user, scoring_user, gateway_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA masked_evidence TO ingestion_user, detection_user, scoring_user, gateway_user;

-- Create tables
CREATE TABLE IF NOT EXISTS masked_evidence.transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_doc_hash VARCHAR(64) NOT NULL,
    vendor_token VARCHAR(50) NOT NULL,
    department_id VARCHAR(50) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    unit_price DECIMAL(15,2),
    quantity INTEGER,
    category VARCHAR(100),
    region VARCHAR(100),
    submitted_at TIMESTAMP NOT NULL,
    approved_at TIMESTAMP,
    approver_token VARCHAR(50),
    source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transactions_vendor ON masked_evidence.transactions(vendor_token);
CREATE INDEX idx_transactions_department ON masked_evidence.transactions(department_id);
CREATE INDEX idx_transactions_hash ON masked_evidence.transactions(invoice_doc_hash);

CREATE TABLE IF NOT EXISTS masked_evidence.signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL,
    signal_type VARCHAR(50) NOT NULL,
    value DECIMAL(3,2) NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    evidence_ref JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS masked_evidence.risk_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL,
    score DECIMAL(3,2) NOT NULL,
    tier VARCHAR(20) NOT NULL,
    confidence_factor DECIMAL(3,2) NOT NULL,
    policy_weight_version VARCHAR(20),
    evidence_bundle_id UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS masked_evidence.cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    risk_score_id UUID NOT NULL,
    status VARCHAR(20) DEFAULT 'open',
    assigned_auditor_id UUID,
    jurisdiction_scope VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS masked_evidence.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prev_hash VARCHAR(64) NOT NULL,
    entry_hash VARCHAR(64) NOT NULL UNIQUE,
    actor_id VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    resource_token VARCHAR(50),
    payload_hash VARCHAR(64),
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
