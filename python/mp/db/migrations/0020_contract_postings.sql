CREATE TABLE IF NOT EXISTS contract_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    effective_date DATE NOT NULL,
    delta_cents BIGINT NOT NULL,
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (contract_id, effective_date)
);

CREATE INDEX IF NOT EXISTS ix_contract_postings_user_effective
    ON contract_postings(user_id, effective_date);
