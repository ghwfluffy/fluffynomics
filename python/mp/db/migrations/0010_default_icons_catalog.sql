CREATE TABLE IF NOT EXISTS default_icons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(64) NOT NULL UNIQUE,
    label TEXT NOT NULL,
    icon_id UUID NOT NULL REFERENCES icon_assets(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
