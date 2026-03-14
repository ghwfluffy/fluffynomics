CREATE TABLE IF NOT EXISTS investments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    destination_account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    amount_cents BIGINT NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    general_frequency TEXT,
    last_invested_date DATE,
    next_investment_date DATE,
    next_date_is_static BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_investments_user_id
    ON investments(user_id);

CREATE INDEX IF NOT EXISTS idx_investments_user_next
    ON investments(user_id, next_investment_date);
