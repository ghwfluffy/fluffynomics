ALTER TABLE expenses
ADD COLUMN IF NOT EXISTS linked_account_id UUID NULL REFERENCES accounts(id) ON DELETE SET NULL;

UPDATE expenses e
SET linked_account_id = a.id
FROM accounts a
WHERE e.user_id = a.user_id
  AND a.type IN ('checking', 'savings', 'stocks_account', 'crypto_exchange')
  AND e.linked_account_id IS NULL
  AND a.id = (
      SELECT a2.id
      FROM accounts a2
      WHERE a2.user_id = e.user_id
        AND a2.type IN ('checking', 'savings', 'stocks_account', 'crypto_exchange')
      ORDER BY a2.created_at ASC
      LIMIT 1
  );

ALTER TABLE expenses
ALTER COLUMN linked_account_id DROP NOT NULL;
