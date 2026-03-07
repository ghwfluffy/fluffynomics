CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    example_data BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_number TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (
        type IN (
            'checking',
            'savings',
            'cash',
            'line_of_credit',
            'credit_card',
            'stocks_account',
            'crypto_exchange',
            'crypto_wallet',
            'retirement',
            'loan',
            'rewards_card'
        )
    ),
    organization TEXT,
    url TEXT,
    notes TEXT,
    balance_cents BIGINT,
    fee_amount_cents BIGINT,
    fee_period TEXT,
    routing_number TEXT,
    apy_bps INT,
    compound_period TEXT,
    apr_bps INT,
    billing_day INT CHECK (billing_day BETWEEN 1 AND 31),
    payment_day INT CHECK (payment_day BETWEEN 1 AND 31),
    expiration_date DATE,
    cvc TEXT,
    usd_balance_cents BIGINT,
    retirement_account_type TEXT CHECK (
        retirement_account_type IN ('roth', 'simple', '401k')
    ),
    payment_amount_cents BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    exchange TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ticker, exchange)
);

CREATE TABLE IF NOT EXISTS account_stock_positions (
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    stock_id UUID NOT NULL REFERENCES stocks(id) ON DELETE RESTRICT,
    quantity NUMERIC(20, 8) NOT NULL,
    PRIMARY KEY (account_id, stock_id)
);

CREATE TABLE IF NOT EXISTS account_crypto_positions (
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    ticker VARCHAR(32) NOT NULL,
    quantity NUMERIC(38, 18) NOT NULL,
    PRIMARY KEY (account_id, ticker)
);

CREATE TABLE IF NOT EXISTS account_cash_denominations (
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    denomination_cents INT NOT NULL,
    quantity INT NOT NULL,
    PRIMARY KEY (account_id, denomination_cents)
);

CREATE TABLE IF NOT EXISTS pending_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    delta BIGINT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT,
    amount BIGINT,
    delta_amount BIGINT,
    frequency TEXT,
    last_payment DATE,
    next_payment DATE,
    automatic BOOLEAN,
    payment_account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    category TEXT,
    active BOOLEAN,
    url TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    start_date DATE,
    end_date DATE
);
