CREATE TABLE IF NOT EXISTS account_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    source_account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    destination_account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    current_balance_cents INTEGER NULL,
    pending_balance_cents INTEGER NULL,
    transfer_kind TEXT NOT NULL DEFAULT 'standard'
        CHECK (transfer_kind IN ('standard', 'credit_card_payment')),
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_at TIMESTAMPTZ NOT NULL,
    applied_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_account_transfers_user_effective
    ON account_transfers(user_id, effective_at);

CREATE INDEX IF NOT EXISTS idx_account_transfers_user_source
    ON account_transfers(user_id, source_account_id);

CREATE INDEX IF NOT EXISTS idx_account_transfers_user_destination
    ON account_transfers(user_id, destination_account_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_account_transfers_active_credit_card_payment
    ON account_transfers(destination_account_id)
    WHERE transfer_kind = 'credit_card_payment' AND applied_at IS NULL;

INSERT INTO account_transfers (
    user_id,
    source_account_id,
    destination_account_id,
    amount_cents,
    current_balance_cents,
    pending_balance_cents,
    transfer_kind,
    queued_at,
    effective_at,
    applied_at
)
SELECT
    q.user_id,
    q.source_account_id,
    q.credit_card_account_id,
    q.payment_cents,
    q.current_balance_cents,
    q.pending_balance_cents,
    'credit_card_payment',
    q.queued_at,
    q.effective_at,
    q.applied_at
FROM queued_credit_card_payments q
WHERE NOT EXISTS (
    SELECT 1
    FROM account_transfers t
    WHERE t.transfer_kind = 'credit_card_payment'
      AND t.user_id = q.user_id
      AND t.source_account_id = q.source_account_id
      AND t.destination_account_id = q.credit_card_account_id
      AND t.amount_cents = q.payment_cents
      AND t.queued_at = q.queued_at
);
