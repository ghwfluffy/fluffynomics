TRUNCATE TABLE net_worth_daily_snapshot;

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
        ) AS previous_value_cents,
        CASE
            WHEN a.type IN ('credit_card', 'line_of_credit', 'loan') THEN -1
            ELSE 1
        END AS sign_multiplier
    FROM account_value_history h
    JOIN accounts a ON a.id = h.account_id
),
event_deltas AS (
    SELECT
        user_id,
        snapshot_date,
        recorded_at,
        ((value_cents - COALESCE(previous_value_cents, 0)) * sign_multiplier) AS delta_cents
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
FROM daily_last;
