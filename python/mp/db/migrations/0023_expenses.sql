CREATE TABLE IF NOT EXISTS expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    icon_id UUID NULL REFERENCES icon_assets(id),
    icon_type VARCHAR(16) NOT NULL DEFAULT 'Icon',
    estimated_amount_cents INTEGER NOT NULL DEFAULT 0,
    general_frequency TEXT NULL,
    last_expensed_date DATE NULL,
    next_expensed_date DATE NULL,
    next_date_is_static BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_expenses_user_category
ON expenses(user_id, category, name);
