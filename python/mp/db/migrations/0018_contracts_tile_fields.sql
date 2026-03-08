ALTER TABLE contracts
ADD COLUMN IF NOT EXISTS organization TEXT,
ADD COLUMN IF NOT EXISTS icon_id UUID REFERENCES icon_assets(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS icon_type VARCHAR(16) NOT NULL DEFAULT 'Icon',
ADD COLUMN IF NOT EXISTS rank DOUBLE PRECISION NOT NULL DEFAULT 0;

UPDATE contracts c
SET organization = a.organization
FROM accounts a
WHERE c.organization IS NULL
  AND c.linked_account_id = a.id;

WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, COALESCE(category, 'Financial')
            ORDER BY created_at ASC
        ) AS position
    FROM contracts
)
UPDATE contracts c
SET rank = ranked.position
FROM ranked
WHERE c.id = ranked.id
  AND (c.rank IS NULL OR c.rank = 0);
