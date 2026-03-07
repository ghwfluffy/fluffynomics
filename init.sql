-- Setup user
--CREATE USER ghw WITH PASSWORD 'supersecure';
--CREATE DATABASE budget OWNER ghw;
GRANT ALL PRIVILEGES ON DATABASE budget TO ghw;
GRANT ALL ON ALL TABLES IN SCHEMA public TO ghw;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO ghw;

-- Connect to target database
--\c budget;

-- Bootstrap-only setup. App schema is managed by SQL migrations in
-- python/mp/db/migrations and applied at API startup.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
