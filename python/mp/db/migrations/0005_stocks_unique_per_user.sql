ALTER TABLE stocks
    DROP CONSTRAINT IF EXISTS stocks_ticker_exchange_key;

ALTER TABLE stocks
    ADD CONSTRAINT stocks_user_ticker_exchange_key UNIQUE (user_id, ticker, exchange);
