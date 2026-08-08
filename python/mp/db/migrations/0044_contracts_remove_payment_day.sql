UPDATE contracts
SET payment_period = json_build_object(
    'kind', 'monthly_day',
    'day', payment_day
)::TEXT
WHERE (payment_period IS NULL OR btrim(payment_period) = '')
  AND payment_day BETWEEN 1 AND 31;

UPDATE contracts
SET payment_period = NULL
WHERE payment_period IS NOT NULL
  AND btrim(payment_period) = '';

UPDATE contracts
SET payment_period = CASE lower(btrim(payment_period))
    WHEN 'daily' THEN '{"kind":"daily_weekdays","weekdays":[0,1,2,3,4,5,6]}'
    WHEN 'weekly' THEN '{"kind":"weekly_weekday","weekday":0}'
    WHEN 'biweekly' THEN '{"kind":"biweekly_weekday","weekday":0,"start_date":"2025-01-06"}'
    WHEN 'monthly' THEN '{"kind":"monthly_day","day":1}'
    WHEN 'yearly' THEN '{"kind":"yearly_month_day","month":1,"day":1}'
END
WHERE lower(btrim(payment_period)) IN (
    'daily', 'weekly', 'biweekly', 'monthly', 'yearly'
);

ALTER TABLE contracts
DROP COLUMN IF EXISTS payment_day;
