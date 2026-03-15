CREATE TABLE IF NOT EXISTS audit_log_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trigger_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT audit_log_events_trigger_type_check
        CHECK (trigger_type IN ('user', 'cron', 'system'))
);

CREATE INDEX IF NOT EXISTS ix_audit_log_events_user_occurred_at
    ON audit_log_events(user_id, occurred_at DESC, id DESC);
