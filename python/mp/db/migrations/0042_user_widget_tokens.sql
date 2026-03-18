ALTER TABLE users
    ADD COLUMN IF NOT EXISTS widget_token TEXT NULL,
    ADD COLUMN IF NOT EXISTS widget_last_accessed_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS widget_last_net_worth_cents INTEGER NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_widget_token
ON users(widget_token)
WHERE widget_token IS NOT NULL;
