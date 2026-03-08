ALTER TABLE accounts
ADD COLUMN IF NOT EXISTS last_payment_date DATE;
