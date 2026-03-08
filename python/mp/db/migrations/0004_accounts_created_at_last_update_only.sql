ALTER TABLE accounts
    ADD COLUMN IF NOT EXISTS last_update TIMESTAMPTZ;

UPDATE accounts
SET last_update = COALESCE(last_update, updated_at, created_at)
WHERE last_update IS NULL;

ALTER TABLE accounts
    DROP COLUMN IF EXISTS date_opened,
    DROP COLUMN IF EXISTS updated_at;
