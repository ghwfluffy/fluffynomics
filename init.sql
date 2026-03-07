-- Setup user
--CREATE USER ghw WITH PASSWORD 'supersecure';
--CREATE DATABASE budget OWNER ghw;
GRANT ALL PRIVILEGES ON DATABASE budget TO ghw;
GRANT ALL ON ALL TABLES IN SCHEMA public TO ghw;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO ghw;

-- Connect to target database
--\c budget;

-- Money accounts (checking, savings)
CREATE TABLE accounts (
    id INT NOT NULL,
    name VARCHAR,
    type VARCHAR,
    -- cents
    balance BIGINT,
    -- percentage points
    apr INT,
    url VARCHAR,
    notes VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,

    PRIMARY KEY (id)
);

-- Static one time withdrawals from accounts that haven't posted yet
CREATE TABLE pending_payments (
    id INT NOT NULL,
    -- accounts.id
    account_id INT NOT NULL,
    -- negative cents
    delta BIGINT,
    notes VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,

    PRIMARY KEY (id)
);

-- Contracts
CREATE TABLE contracts (
    id INT NOT NULL,
    name VARCHAR,
    -- cents (positive IE paycheck or negative IE bill)
    amount BIGINT,
    -- cents more or less than amount might occur this pay period
    delta_amount BIGINT,
    -- Week, %d Weeks, HalfMonth (15th and last day of month), Month, %d Months, Year, %d Years
    frequency VARCHAR,
    last_payment DATE,
    next_payment DATE,
    automatic BOOLEAN,
    -- accounts.id
    payment_account_id INT,
    category VARCHAR,
    active BOOLEAN,
    url VARCHAR,
    notes VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    start_date DATE,
    end_date DATE,

    PRIMARY KEY (id)
);

-- Credit accounts
CREATE TABLE payables (
    id INT NOT NULL,
    name VARCHAR,
    type VARCHAR,
    -- Max credit, cents
    credit BIGINT,
    last_payment DATE,
    next_payment DATE,
    -- percentage points
    apr INT,
    -- negative cents
    balance BIGINT,
    -- cents
    rewards BIGINT,
    url VARCHAR,
    notes VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,

    PRIMARY KEY (id)
);

-- Investment accounts (Acorns, Betterment, Retirement, etc)
CREATE TABLE funds (
    id INT NOT NULL,
    name VARCHAR,
    type VARCHAR,
    -- cents
    balance BIGINT,
    -- percentage points
    apr INT,
    url VARCHAR,
    notes VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,

    PRIMARY KEY (id)
);
