DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'account_transfers'
          AND column_name = 'credit_card_account_id'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'account_transfers'
          AND column_name = 'destination_account_id'
    ) THEN
        ALTER TABLE account_transfers
            RENAME COLUMN credit_card_account_id TO destination_account_id;
    END IF;
END $$;

ALTER TABLE account_transfers
    ADD COLUMN IF NOT EXISTS destination_account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS current_balance_cents INTEGER NULL,
    ADD COLUMN IF NOT EXISTS pending_balance_cents INTEGER NULL,
    ADD COLUMN IF NOT EXISTS transfer_kind TEXT NOT NULL DEFAULT 'standard';

UPDATE account_transfers
SET transfer_kind = 'credit_card_payment'
WHERE transfer_kind IS NULL
   OR btrim(transfer_kind) = '';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'account_transfers_transfer_kind_check'
    ) THEN
        ALTER TABLE account_transfers
            ADD CONSTRAINT account_transfers_transfer_kind_check
            CHECK (transfer_kind IN ('standard', 'credit_card_payment'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_account_transfers_user_effective
    ON account_transfers(user_id, effective_at);

CREATE INDEX IF NOT EXISTS idx_account_transfers_user_source
    ON account_transfers(user_id, source_account_id);

CREATE INDEX IF NOT EXISTS idx_account_transfers_user_destination
    ON account_transfers(user_id, destination_account_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_account_transfers_active_credit_card_payment
    ON account_transfers(destination_account_id)
    WHERE transfer_kind = 'credit_card_payment' AND applied_at IS NULL;
