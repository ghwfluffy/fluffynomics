# Database Architecture

## Engine + Ownership

- PostgreSQL (dockerized via `docker-compose.yml`)
- App schema managed by migration files in `python/mp/db/migrations/`
- ORM models in `python/mp/schema/*.py`
- Local filesystem backup target directory: `./backups` (mounted into backup worker container)

## Operational Backups

- `docker-compose.yml` includes a `db-backup` worker service that runs `pg_dump` nightly.
- Backup files are timestamped gzip dumps in `./backups`, named like:
  - `pgdump-<db>-YYYYMMDDTHHMMSSZ.sql.gz`
- Nightly schedule controls:
  - `BACKUP_HOUR_UTC` (default `02`)
  - `BACKUP_MINUTE_UTC` (default `00`)
- Retention controls:
  - `BACKUP_RETENTION` default `100` newest files retained.
- Ownership controls:
  - backup worker container runs as `BACKUP_UID:BACKUP_GID` (default `1000:1000`)
  - backup files are written directly with that ownership (no per-file `chown` step)
- Immediate run trigger:
  - API endpoint `POST /backups/run-now` writes a trigger file consumed by backup worker.

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
- `account_crypto_positions.exchange_rate_cents` stores per-ticker USD exchange rate used for derived crypto account value.
  - update flows propagate same ticker rate across all of a user's crypto holdings.
- `stocks.last_price_cents` stores user-scoped price metadata for stock tickers.
- `account_value_history` stores value snapshots (`value_cents`, `recorded_at`) for account history graphs.
- `net_worth_daily_snapshot` stores one net-worth snapshot per user per day.
  - unique key: `(user_id, snapshot_date)`
  - on multiple same-day updates, the row is updated to latest net worth.
  - liability account types (`credit_card`, `line_of_credit`, `loan`) are signed negative in net-worth math.
- Hash dedupe rule: identical uploaded icon content should reuse existing `icon_assets` row.
- SVG import rule for built-in defaults:
  - many icon sets use `stroke=\"currentColor\"`; converting without setting color can produce fully transparent PNGs.
  - when generating PNG defaults from SVG, set an explicit stroke/fill color before rasterization and verify output is non-empty.
  - a quick sanity check is file size and `identify -verbose` histogram (not all-alpha).

### Contracts parity fields

Contracts now carry tile-parity fields to match account dashboard interactions:
- `organization` (text),
- `icon_id` (nullable FK to `icon_assets`),
- `icon_type` (`Letters|Gravatar|Icon`),
- `rank` (`DOUBLE PRECISION` float for in-section ordering).
- `expiration_date` (`DATE`, default `2099-01-01`) for lifecycle grouping (active vs expired).

Contracts remain user-scoped (`contracts.user_id`) and are grouped by category in web UI. Ranking is applied within category sections.
Current UI grouping is by `type + category` for active contracts, plus a trailing `Expired` section based on `expiration_date < today`.

### Architecture Decision: Snapshot Consistency Model

- `net_worth_daily_snapshot` is updated synchronously when account value history is recorded from account update flows.
- Snapshot granularity is intentionally **daily latest-value**:
  - multiple updates in one day overwrite the same `(user_id, snapshot_date)` row,
  - no separate end-of-day batch job is required.
- Tradeoff: this is not a market-close canonical EOD ledger; it is an operational product snapshot optimized for:
  - low-latency dashboard reads,
  - deterministic backup/restore behavior,
  - bounded query cost for long-lived users.

### Contract postings ledger

- `contract_postings` is append-only posting history for automatic contract execution.
- Key rule: unique `(contract_id, effective_date)` ensures idempotent apply behavior.
- Posting records store signed `delta_cents` and `applied_at`.
- Automatic execution updates account balances and advances `contracts.last_payment_date`.

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
- `account_value_history`
- `net_worth_daily_snapshot`
- `app_config`
- `pending_payments`
- `contracts`
- `contract_postings`
- `expenses`

### Expenses table intent

- `expenses` stores user-scoped budgeting estimates (not account balances).
- `expenses.linked_account_id` is intentionally nullable with `ON DELETE SET NULL` so deleting an account never deletes expense definitions.
- `next_date_is_static` distinguishes fixed next date from derived next date.
- `general_frequency` is stored as recurring-period JSON for derivation math.
- automatic expense simulation mutates linked account balances on due dates:
  - liability-linked expenses increase liability balances
  - asset-linked expenses decrease balances
  - these deltas are included in account `as_of_date` projection and net-worth forecast endpoints

### Cross-table delete policy

- Non-tightly-coupled references must not use cascade deletion.
- Current examples:
  - `contracts.linked_account_id -> accounts.id` uses `ON DELETE SET NULL`.
  - `expenses.linked_account_id -> accounts.id` uses `ON DELETE SET NULL`.
- Tightly-coupled child data may still cascade (for example account positions/history tied directly to account lifecycle).

### User profile fields

- `users.avatar_icon_id` (nullable FK -> `icon_assets.id`, `ON DELETE SET NULL`)
- `users.last_login_at` (nullable timestamp)
- `users.password_changed_at` (nullable timestamp)
- `users.failed_password_attempts` (non-null integer, default `0`)
- `users.password_lockout_until` (nullable timestamp for short lockout window)
- `users.is_admin` (non-null boolean, default `false`)
  - first registered user is assigned admin privileges

## Data Portability Replace Semantics

Import/restore (`POST /data/import`) is intentionally modeled as:
- deserialize package JSON,
- migrate payload schema to current version,
- replace existing user-scoped rows with fresh inserts.

Current replace order removes user rows from:
- `expenses`
- `contracts`
  - cascades `contract_postings` by contract foreign key
- `account_value_history`
- `net_worth_daily_snapshot`
- `accounts` (cascades account positions/denominations)
- `stocks`

Then new rows are inserted with remapped IDs per import run.

Icon handling during import:
- imported icon records are looked up by `icon_assets.hash` first (global dedupe),
- existing matching hash rows are reused,
- missing hashes create new rows,
- imported account/contract/expense `icon_id` references are remapped to resolved icon rows.

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
- update data portability serializer/import migrator in `python/mp/api/data_portability.py` so export packages remain complete and older package versions can be upgraded,
- update docs in `docs/architecture/*.md`.
