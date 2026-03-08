ALTER TABLE contracts
ALTER COLUMN linked_account_id DROP NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'contracts_linked_account_id_fkey'
    ) THEN
        ALTER TABLE contracts DROP CONSTRAINT contracts_linked_account_id_fkey;
    END IF;
END $$;

ALTER TABLE contracts
ADD CONSTRAINT contracts_linked_account_id_fkey
FOREIGN KEY (linked_account_id) REFERENCES accounts(id) ON DELETE SET NULL;

ALTER TABLE expenses
ALTER COLUMN linked_account_id DROP NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'expenses_linked_account_id_fkey'
    ) THEN
        ALTER TABLE expenses DROP CONSTRAINT expenses_linked_account_id_fkey;
    END IF;
END $$;

ALTER TABLE expenses
ADD CONSTRAINT expenses_linked_account_id_fkey
FOREIGN KEY (linked_account_id) REFERENCES accounts(id) ON DELETE SET NULL;
