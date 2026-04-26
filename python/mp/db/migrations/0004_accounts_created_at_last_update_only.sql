ALTER TABLE accounts
    ADD COLUMN IF NOT EXISTS last_update TIMESTAMPTZ;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'accounts'
          AND column_name = 'updated_at'
    ) THEN
        UPDATE accounts
        SET last_update = COALESCE(last_update, updated_at, created_at)
        WHERE last_update IS NULL;
    ELSE
        UPDATE accounts
        SET last_update = COALESCE(last_update, created_at)
        WHERE last_update IS NULL;
    END IF;
END
$$;

ALTER TABLE accounts
    DROP COLUMN IF EXISTS date_opened,
    DROP COLUMN IF EXISTS updated_at;
