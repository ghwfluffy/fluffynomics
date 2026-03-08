ALTER TABLE accounts
ADD COLUMN IF NOT EXISTS icon_type VARCHAR(16) NOT NULL DEFAULT 'Icon';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'accounts_icon_type_check'
    ) THEN
        ALTER TABLE accounts
        ADD CONSTRAINT accounts_icon_type_check
        CHECK (icon_type IN ('Letters', 'Gravatar', 'Icon'));
    END IF;
END $$;

UPDATE accounts
SET icon_type = 'Icon'
WHERE icon_type IS NULL;
