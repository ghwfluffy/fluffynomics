ALTER TABLE contracts
ADD COLUMN IF NOT EXISTS user_id UUID,
ADD COLUMN IF NOT EXISTS name TEXT,
ADD COLUMN IF NOT EXISTS type TEXT,
ADD COLUMN IF NOT EXISTS automatic BOOLEAN,
ADD COLUMN IF NOT EXISTS amount_cents BIGINT,
ADD COLUMN IF NOT EXISTS linked_account_id UUID,
ADD COLUMN IF NOT EXISTS source_account_id UUID,
ADD COLUMN IF NOT EXISTS last_payment_date DATE,
ADD COLUMN IF NOT EXISTS payment_period TEXT,
ADD COLUMN IF NOT EXISTS payment_day INT,
ADD COLUMN IF NOT EXISTS notes TEXT,
ADD COLUMN IF NOT EXISTS category TEXT,
ADD COLUMN IF NOT EXISTS url TEXT,
ADD COLUMN IF NOT EXISTS account_number TEXT,
ADD COLUMN IF NOT EXISTS billing_day INT;

UPDATE contracts c
SET user_id = a.user_id
FROM accounts a
WHERE c.user_id IS NULL
  AND c.payment_account_id = a.id;

UPDATE contracts
SET user_id = (
    SELECT id
    FROM users
    ORDER BY created_at ASC
    LIMIT 1
)
WHERE user_id IS NULL;

UPDATE contracts
SET type = CASE
    WHEN lower(COALESCE(category, '')) = 'income' THEN 'income'
    WHEN lower(COALESCE(category, '')) = 'transfer' THEN 'transfer'
    ELSE 'payment'
END
WHERE type IS NULL;

UPDATE contracts
SET amount_cents = COALESCE(amount, 0)
WHERE amount_cents IS NULL;

UPDATE contracts
SET linked_account_id = payment_account_id
WHERE linked_account_id IS NULL;

UPDATE contracts
SET last_payment_date = last_payment
WHERE last_payment_date IS NULL;

UPDATE contracts
SET payment_period = frequency
WHERE payment_period IS NULL;

UPDATE contracts
SET automatic = COALESCE(automatic, TRUE)
WHERE automatic IS NULL;

UPDATE contracts
SET name = 'Contract'
WHERE name IS NULL OR btrim(name) = '';

UPDATE contracts
SET category = 'Financial'
WHERE category IS NULL OR btrim(category) = '';

DELETE FROM contracts
WHERE user_id IS NULL OR linked_account_id IS NULL;

ALTER TABLE contracts
ALTER COLUMN user_id SET NOT NULL,
ALTER COLUMN name SET NOT NULL,
ALTER COLUMN type SET NOT NULL,
ALTER COLUMN automatic SET NOT NULL,
ALTER COLUMN amount_cents SET NOT NULL,
ALTER COLUMN linked_account_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'contracts_user_id_fkey'
    ) THEN
        ALTER TABLE contracts
        ADD CONSTRAINT contracts_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'contracts_linked_account_id_fkey'
    ) THEN
        ALTER TABLE contracts
        ADD CONSTRAINT contracts_linked_account_id_fkey
        FOREIGN KEY (linked_account_id) REFERENCES accounts(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'contracts_source_account_id_fkey'
    ) THEN
        ALTER TABLE contracts
        ADD CONSTRAINT contracts_source_account_id_fkey
        FOREIGN KEY (source_account_id) REFERENCES accounts(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'contracts_type_check'
    ) THEN
        ALTER TABLE contracts
        ADD CONSTRAINT contracts_type_check
        CHECK (type IN ('income', 'payment', 'transfer'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_contracts_user_id ON contracts(user_id);
CREATE INDEX IF NOT EXISTS ix_contracts_linked_account_id ON contracts(linked_account_id);
