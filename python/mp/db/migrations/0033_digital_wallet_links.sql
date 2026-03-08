ALTER TABLE users
ADD COLUMN IF NOT EXISTS paypal_account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS google_pay_account_id UUID REFERENCES accounts(id) ON DELETE SET NULL;

ALTER TABLE contracts
ADD COLUMN IF NOT EXISTS linked_wallet TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'contracts_linked_wallet_check'
    ) THEN
        ALTER TABLE contracts
        ADD CONSTRAINT contracts_linked_wallet_check
        CHECK (linked_wallet IS NULL OR linked_wallet IN ('paypal', 'google_pay'));
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS ix_users_paypal_account_id ON users(paypal_account_id);
CREATE INDEX IF NOT EXISTS ix_users_google_pay_account_id ON users(google_pay_account_id);
