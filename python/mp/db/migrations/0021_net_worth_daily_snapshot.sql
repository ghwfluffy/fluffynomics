CREATE TABLE IF NOT EXISTS net_worth_daily_snapshot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    value_cents INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_net_worth_daily_snapshot_user_day UNIQUE (user_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS ix_net_worth_daily_snapshot_user_day
ON net_worth_daily_snapshot(user_id, snapshot_date);

WITH ordered AS (
    SELECT
        h.user_id,
        h.account_id,
        h.recorded_at::date AS snapshot_date,
        h.recorded_at,
        h.value_cents,
        LAG(h.value_cents) OVER (
            PARTITION BY h.user_id, h.account_id
            ORDER BY h.recorded_at
        ) AS previous_value_cents
    FROM account_value_history h
),
event_deltas AS (
    SELECT
        user_id,
        snapshot_date,
        recorded_at,
        (value_cents - COALESCE(previous_value_cents, 0)) AS delta_cents
    FROM ordered
),
running_net AS (
    SELECT
        user_id,
        snapshot_date,
        recorded_at,
        SUM(delta_cents) OVER (
            PARTITION BY user_id
            ORDER BY recorded_at
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS net_worth_cents
    FROM event_deltas
),
daily_last AS (
    SELECT DISTINCT ON (user_id, snapshot_date)
        user_id,
        snapshot_date,
        net_worth_cents
    FROM running_net
    ORDER BY user_id, snapshot_date, recorded_at DESC
)
INSERT INTO net_worth_daily_snapshot (
    user_id,
    snapshot_date,
    value_cents,
    updated_at
)
SELECT
    user_id,
    snapshot_date,
    net_worth_cents::INTEGER,
    now()
FROM daily_last
ON CONFLICT (user_id, snapshot_date) DO UPDATE
SET
    value_cents = EXCLUDED.value_cents,
    updated_at = now();
