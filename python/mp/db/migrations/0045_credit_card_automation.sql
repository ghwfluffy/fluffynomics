ALTER TABLE accounts
    ADD COLUMN minimum_payment_cents INTEGER CHECK (minimum_payment_cents >= 0),
    ADD COLUMN default_payment_account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    ADD COLUMN credit_card_processed_through DATE DEFAULT (CURRENT_DATE - 1);
-- Begin at deployment, never charge historical interest against today's balance.
UPDATE accounts SET credit_card_processed_through = CURRENT_DATE - 1;
