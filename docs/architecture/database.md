# Database Architecture

## Engine + Ownership

- PostgreSQL (dockerized via `docker-compose.yml`)
- App schema managed by migration files in `python/mp/db/migrations/`
- ORM models in `python/mp/schema/*.py`

## Source of Truth

- Use SQL migrations + ORM models as the schema source of truth.
- `init.sql` is bootstrap-only and should not carry evolving app table DDL.

## Migration System

Startup upgrader: `python/mp/db/upgrade.py`

On boot it:
- ensures `app_config` table exists,
- uses `app_config.key='dbversion'` for current revision,
- applies missing migrations in numeric order,
- updates `dbversion` after each migration.

No `db_migrations.json` file is used.

## Recent Schema Intent (Important)

### Accounts timestamps

Account timestamp semantics are intentionally split:
- `created_at`: creation time
- `last_update`: business-value refresh time

`last_update` is updated by the value-update API flow (`PUT /accounts/{id}/value`), not generic metadata edits.

### Account ranking

- `accounts.rank` is `DOUBLE PRECISION` (float).
- New account rank defaults to top (`max(rank)+1` per user).
- Reordering UI sets rank directly via API.

### Account icons + organizations

- `icon_assets` table stores normalized PNG bytes with:
  - `id` (UUID)
  - `hash` (SHA-256, unique for dedupe)
  - `created_by_user_id` (nullable; null for built-in defaults)
  - `png_data` (bytea)
- `organizations` table stores canonical org names and optional default icon mapping.
- `default_icons` table stores generic default icon presets (`key`, `label`, `icon_id`) not tied to organizations.
- `accounts.icon_id` references `icon_assets.id`.
- `accounts.icon_type` is enum-like constrained text: `Letters`, `Gravatar`, `Icon`.
  - for `Letters`/`Gravatar`, `accounts.icon_id` is expected to be null and icon bytes are generated on demand
- `accounts.last_payment_date` stores the most recently recorded payment date for payable accounts (`line_of_credit`, `credit_card`, `loan`).
- Cash balances should be treated as derived from `account_cash_denominations` quantities (not an independently authored static `accounts.balance_cents` value).
- Hash dedupe rule: identical uploaded icon content should reuse existing `icon_assets` row.

### User-scoped uniqueness

- Stocks uniqueness is per user:
  - unique constraint on `(user_id, ticker, exchange)`
- This avoids cross-user collisions during example-data seeding.

## Key Tables (Current)

- `users`
- `accounts`
- `icon_assets`
- `organizations`
- `default_icons`
- `stocks`
- `account_stock_positions`
- `account_crypto_positions`
- `account_cash_denominations`
- `app_config`
- `pending_payments`
- `contracts`

## Example Data Contract

- `users.example_data` controls whether sample data should exist.
- `python/mp/sample_data.py` is part of the product experience, not test-only helper.
- When adding schema/features/account types, update sample seeding with representative records.
- Keep sample data varied where UX depends on state (for example varied `last_update` ages for clock-status colors).
- For defaults-driven UX, keep startup default loaders aligned with DB schema (example: organization defaults + icons).

## Migration Discipline

When changing schema:
- add a new migration file (next numeric prefix),
- update ORM/Pydantic models,
- update affected API handlers,
- update docs in `docs/architecture/*.md`.
