ALTER TABLE account_crypto_positions
ADD COLUMN IF NOT EXISTS exchange_rate_cents BIGINT NOT NULL DEFAULT 0;
