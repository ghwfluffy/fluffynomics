DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    FOR constraint_name IN
        SELECT c.conname
        FROM pg_constraint c
        WHERE c.conrelid = 'accounts'::regclass
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%%stocks_account%%'
          AND pg_get_constraintdef(c.oid) ILIKE '%%rewards_card%%'
    LOOP
        EXECUTE format('ALTER TABLE accounts DROP CONSTRAINT %%I', constraint_name);
    END LOOP;
END $$;

ALTER TABLE accounts
    ADD CONSTRAINT accounts_type_check
    CHECK (
        type IN (
            'checking',
            'savings',
            'cash',
            'line_of_credit',
            'credit_card',
            'stocks_account',
            'investment_fund',
            'crypto_exchange',
            'crypto_wallet',
            'retirement',
            'loan',
            'rewards_card'
        )
    );

WITH converted_accounts AS (
    SELECT
        a.id,
        COALESCE(a.balance_cents, 0) + COALESCE(
            (
                SELECT SUM(ROUND(asp.quantity * COALESCE(s.last_price_cents, 0))::BIGINT)
                FROM account_stock_positions asp
                JOIN stocks s ON s.id = asp.stock_id
                WHERE asp.account_id = a.id
            ),
            0
        ) AS total_value_cents
    FROM accounts a
    WHERE a.type = 'stocks_account'
      AND (
          LOWER(BTRIM(COALESCE(a.organization, ''))) LIKE 'betterment%%'
          OR LOWER(BTRIM(COALESCE(a.organization, ''))) LIKE 'acorns%%'
      )
)
UPDATE accounts a
SET type = 'investment_fund',
    balance_cents = converted_accounts.total_value_cents
FROM converted_accounts
WHERE a.id = converted_accounts.id;

DELETE FROM account_stock_positions asp
USING accounts a
WHERE asp.account_id = a.id
  AND a.type = 'investment_fund'
  AND (
      LOWER(BTRIM(COALESCE(a.organization, ''))) LIKE 'betterment%%'
      OR LOWER(BTRIM(COALESCE(a.organization, ''))) LIKE 'acorns%%'
  );
