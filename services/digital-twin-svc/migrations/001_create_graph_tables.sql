-- Digital Twin graph tables
-- Supports vendor/official/department/tender/invoice relationships

-- Node types for the graph
CREATE TABLE IF NOT EXISTS graph_nodes (
    node_id         TEXT PRIMARY KEY,
    node_type       TEXT NOT NULL CHECK (node_type IN ('vendor','department','official','tender','invoice','transaction','asset')),
    label           TEXT NOT NULL,
    properties      JSONB DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_graph_nodes_type ON graph_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_label ON graph_nodes(label);

-- Edges for the graph
CREATE TABLE IF NOT EXISTS graph_edges (
    edge_id         TEXT PRIMARY KEY DEFAULT ('edge-' || SUBSTR(MD5(RANDOM()::TEXT), 1, 8)),
    source_id       TEXT NOT NULL REFERENCES graph_nodes(node_id) ON DELETE CASCADE,
    target_id       TEXT NOT NULL REFERENCES graph_nodes(node_id) ON DELETE CASCADE,
    edge_type       TEXT NOT NULL CHECK (edge_type IN ('contracted','employs','owns','supplies','approves','related','part_of')),
    label           TEXT NOT NULL,
    weight          FLOAT DEFAULT 1.0,
    properties      JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_id, target_id, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_type ON graph_edges(edge_type);

-- Vendor network analysis cache
CREATE TABLE IF NOT EXISTS vendor_network_analysis (
    vendor_id       TEXT PRIMARY KEY,
    hhi             FLOAT DEFAULT 0.0,
    concentration   TEXT DEFAULT 'low',
    repeat_officials INT DEFAULT 0,
    connected_vendors INT DEFAULT 0,
    suspicious      JSONB DEFAULT '[]',
    computed_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Relationship strength tracking
CREATE TABLE IF NOT EXISTS relationship_strength (
    source_id       TEXT NOT NULL,
    target_id       TEXT NOT NULL,
    strength        FLOAT DEFAULT 0.0,
    transaction_count INT DEFAULT 0,
    total_amount    FLOAT DEFAULT 0.0,
    last_interaction TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}',
    PRIMARY KEY (source_id, target_id)
);

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_graph_node_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_graph_nodes_updated
    BEFORE UPDATE ON graph_nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_graph_node_timestamp();

-- Graph statistics view
CREATE OR REPLACE VIEW graph_statistics AS
SELECT
    (SELECT COUNT(*) FROM graph_nodes WHERE node_type = 'vendor') AS vendor_count,
    (SELECT COUNT(*) FROM graph_nodes WHERE node_type = 'department') AS department_count,
    (SELECT COUNT(*) FROM graph_nodes WHERE node_type = 'official') AS official_count,
    (SELECT COUNT(*) FROM graph_nodes WHERE node_type = 'tender') AS tender_count,
    (SELECT COUNT(*) FROM graph_nodes WHERE node_type = 'invoice') AS invoice_count,
    (SELECT COUNT(*) FROM graph_edges) AS total_edges,
    (SELECT COUNT(DISTINCT edge_type) FROM graph_edges) AS edge_type_count;
