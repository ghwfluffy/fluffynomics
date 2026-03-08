ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

WITH first_user AS (
    SELECT id
    FROM users
    ORDER BY created_at ASC, id ASC
    LIMIT 1
)
UPDATE users
SET is_admin = TRUE
WHERE id IN (SELECT id FROM first_user)
  AND NOT EXISTS (SELECT 1 FROM users WHERE is_admin IS TRUE);
