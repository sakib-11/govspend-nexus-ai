-- Vendor Graph Query with Recursive CTE
-- Finds all connected entities (transactions, departments, officials, tenders, invoices)
-- up to the specified depth starting from a vendor token.

WITH RECURSIVE vendor_network AS (
    -- Seed: the vendor node
    SELECT
        v.vendor_id   AS node_id,
        'vendor'      AS node_type,
        v.name        AS node_label,
        v.token       AS vendor_token,
        NULL::TEXT     AS parent_id,
        0             AS depth

    FROM vendors v
    WHERE v.token = $1

    UNION ALL

    -- Transactions linked to this vendor
    SELECT
        t.transaction_id::TEXT,
        'transaction',
        t.invoice_number,
        g.vendor_token,
        g.node_id,
        g.depth + 1

    FROM vendor_network g
    JOIN transactions t ON t.vendor_token = g.vendor_token
    WHERE g.depth < $2

    UNION ALL

    -- Departments linked through transactions
    SELECT
        d.department_id,
        'department',
        d.name,
        g.vendor_token,
        g.node_id,
        g.depth + 1

    FROM vendor_network g
    JOIN transactions t ON t.vendor_token = g.vendor_token
    JOIN departments d ON d.department_id = t.department_id
    WHERE g.depth < $2

    UNION ALL

    -- Officials linked to this vendor
    SELECT
        o.official_id::TEXT,
        'official',
        o.name,
        g.vendor_token,
        g.node_id,
        g.depth + 1

    FROM vendor_network g
    JOIN vendor_officials vo ON vo.vendor_token = g.vendor_token
    JOIN officials o ON o.official_id = vo.official_id
    WHERE g.depth < $2

    UNION ALL

    -- Tenders
    SELECT
        te.tender_id::TEXT,
        'tender',
        te.title,
        g.vendor_token,
        g.node_id,
        g.depth + 1

    FROM vendor_network g
    JOIN tenders te ON te.vendor_token = g.vendor_token
    WHERE g.depth < $2

    UNION ALL

    -- Invoices
    SELECT
        i.invoice_id::TEXT,
        'invoice',
        i.invoice_number,
        g.vendor_token,
        g.node_id,
        g.depth + 1

    FROM vendor_network g
    JOIN invoices i ON i.vendor_token = g.vendor_token
    WHERE g.depth < $2
),

-- Deduplicate: keep first occurrence of each node
deduped_nodes AS (
    SELECT DISTINCT ON (node_id)
        node_id, node_type, node_label, vendor_token, depth
    FROM vendor_network
    ORDER BY node_id, depth
),

-- Build edges from parent → child
edges AS (
    SELECT
        g1.parent_id AS source,
        g1.node_id   AS target,
        CASE
            WHEN g1.node_type = 'transaction'  THEN 'supplies'
            WHEN g1.node_type = 'department'   THEN 'contracted'
            WHEN g1.node_type = 'official'     THEN 'employs'
            WHEN g1.node_type = 'tender'       THEN 'related'
            WHEN g1.node_type = 'invoice'      THEN 'supplies'
            ELSE 'related'
        END AS edge_type,
        CASE
            WHEN g1.node_type = 'transaction'  THEN 'Submitted'
            WHEN g1.node_type = 'department'   THEN 'Contracts with'
            WHEN g1.node_type = 'official'     THEN 'Employs'
            WHEN g1.node_type = 'tender'       THEN 'Participates in'
            WHEN g1.node_type = 'invoice'      THEN 'Billed'
            ELSE 'Related to'
        END AS edge_label
    FROM vendor_network g1
    WHERE g1.parent_id IS NOT NULL
)

-- Return nodes as JSON
SELECT
    json_agg(
        jsonb_build_object(
            'id',    n.node_id,
            'type',  n.node_type,
            'label', n.node_label,
            'properties', jsonb_build_object(
                'vendor_token', n.vendor_token,
                'depth',        n.depth
            ),
            'size',  CASE n.node_type
                        WHEN 'vendor'      THEN 25
                        WHEN 'department'  THEN 20
                        WHEN 'official'    THEN 15
                        WHEN 'transaction' THEN 18
                        WHEN 'tender'      THEN 16
                        WHEN 'invoice'     THEN 14
                        ELSE 12
                     END,
            'color', CASE n.node_type
                        WHEN 'department'  THEN '#4CAF50'
                        WHEN 'vendor'      THEN '#2196F3'
                        WHEN 'official'    THEN '#F44336'
                        WHEN 'transaction' THEN '#FF9800'
                        WHEN 'tender'      THEN '#9C27B0'
                        WHEN 'invoice'     THEN '#795548'
                        ELSE '#9E9E9E'
                     END
        )
    ) AS nodes,
    json_agg(
        jsonb_build_object(
            'id',     e.source || '->' || e.target,
            'source', e.source,
            'target', e.target,
            'type',   e.edge_type,
            'label',  e.edge_label,
            'weight', 1.0
        )
    ) AS edges
FROM deduped_nodes n
LEFT JOIN edges e ON n.node_id = e.source OR n.node_id = e.target;
