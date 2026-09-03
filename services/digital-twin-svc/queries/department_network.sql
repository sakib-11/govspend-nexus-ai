-- Department Network Query
-- Traverses from a department to its vendors, tenders, and officials

WITH RECURSIVE dept_network AS (
    SELECT
        d.department_id AS node_id,
        'department'    AS node_type,
        d.name          AS node_label,
        NULL::TEXT       AS parent_id,
        0               AS depth

    FROM departments d
    WHERE d.department_id = $1

    UNION ALL

    -- Vendors through transactions
    SELECT
        v.vendor_id,
        'vendor',
        v.name,
        g.node_id,
        g.depth + 1

    FROM dept_network g
    JOIN transactions t ON t.department_id = g.node_id
    JOIN vendors v ON v.token = t.vendor_token
    WHERE g.depth < $2

    UNION ALL

    -- Tenders
    SELECT
        te.tender_id::TEXT,
        'tender',
        te.title,
        g.node_id,
        g.depth + 1

    FROM dept_network g
    JOIN tenders te ON te.department_id = g.node_id
    WHERE g.depth < $2

    UNION ALL

    -- Officials through transactions
    SELECT
        o.official_id::TEXT,
        'official',
        o.name,
        g.node_id,
        g.depth + 1

    FROM dept_network g
    JOIN transactions t ON t.department_id = g.node_id
    JOIN officials o ON o.official_id = t.approved_by
    WHERE g.depth < $2 AND t.approved_by IS NOT NULL
),

deduped AS (
    SELECT DISTINCT ON (node_id)
        node_id, node_type, node_label, parent_id, depth
    FROM dept_network
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
                        WHEN 'department' THEN 25
                        WHEN 'vendor'     THEN 20
                        WHEN 'tender'     THEN 16
                        WHEN 'official'   THEN 15
                        ELSE 12
                     END,
            'color', CASE n.node_type
                        WHEN 'department' THEN '#4CAF50'
                        WHEN 'vendor'     THEN '#2196F3'
                        WHEN 'tender'     THEN '#9C27B0'
                        WHEN 'official'   THEN '#F44336'
                        ELSE '#9E9E9E'
                     END
        )
    ) AS nodes
FROM deduped n;
