CREATE TABLE IF NOT EXISTS queued_credit_card_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    credit_card_account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    source_account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    current_balance_cents INTEGER NOT NULL,
    pending_balance_cents INTEGER NOT NULL DEFAULT 0,
    payment_cents INTEGER NOT NULL,
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_at TIMESTAMPTZ NOT NULL,
    applied_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_queued_credit_card_payments_user_effective
    ON queued_credit_card_payments(user_id, effective_at)
    WHERE applied_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_queued_credit_card_payments_active_card
    ON queued_credit_card_payments(credit_card_account_id)
    WHERE applied_at IS NULL;
