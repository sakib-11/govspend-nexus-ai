-- Official Network Query
-- Traverses from an official to their department, approved vendors, and transactions

WITH RECURSIVE official_network AS (
    SELECT
        o.official_id::TEXT AS node_id,
        'official'          AS node_type,
        o.name              AS node_label,
        NULL::TEXT           AS parent_id,
        0                   AS depth

    FROM officials o
    WHERE o.official_id = $1::uuid

    UNION ALL

    -- Department
    SELECT
        o.department_id,
        'department',
        d.name,
        g.node_id,
        g.depth + 1

    FROM official_network g
    JOIN officials o ON o.official_id = g.node_id::uuid
    JOIN departments d ON d.department_id = o.department_id
    WHERE g.depth < $2

    UNION ALL

    -- Vendors approved
    SELECT
        v.vendor_id,
        'vendor',
        v.name,
        g.node_id,
        g.depth + 1

    FROM official_network g
    JOIN transactions t ON t.approved_by = g.node_id::uuid
    JOIN vendors v ON v.token = t.vendor_token
    WHERE g.depth < $2

    UNION ALL

    -- Transactions approved
    SELECT
        t.transaction_id::TEXT,
        'transaction',
        t.invoice_number,
        g.node_id,
        g.depth + 1

    FROM official_network g
    JOIN transactions t ON t.approved_by = g.node_id::uuid
    WHERE g.depth < $2
),

deduped AS (
    SELECT DISTINCT ON (node_id)
        node_id, node_type, node_label, parent_id, depth
    FROM official_network
    ORDER BY node_id, depth
)

SELECT
    json_agg(
        jsonb_build_object(
            'id',    n.node_id,
            'type',  n.node_type,
            'label', n.node_label,
            'properties', jsonb_build_object('depth', n.depth),
            'size',  CASE n.node_type
                        WHEN 'official'     THEN 25
                        WHEN 'department'   THEN 20
                        WHEN 'vendor'       THEN 18
                        WHEN 'transaction'  THEN 14
                        ELSE 12
                     END,
            'color', CASE n.node_type
                        WHEN 'official'     THEN '#F44336'
                        WHEN 'department'   THEN '#4CAF50'
                        WHEN 'vendor'       THEN '#2196F3'
                        WHEN 'transaction'  THEN '#FF9800'
                        ELSE '#9E9E9E'
                     END
        )
    ) AS nodes
FROM deduped n;
