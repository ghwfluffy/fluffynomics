ALTER TABLE accounts
    ADD COLUMN IF NOT EXISTS rank DOUBLE PRECISION NOT NULL DEFAULT 0;

WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at ASC, id ASC) AS new_rank
    FROM accounts
)
UPDATE accounts AS a
SET rank = ranked.new_rank::DOUBLE PRECISION
FROM ranked
WHERE a.id = ranked.id;
