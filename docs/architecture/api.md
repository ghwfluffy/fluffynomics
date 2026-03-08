# API Architecture

## Stack

- Framework: FastAPI (`python/main.py`)
- ORM + models: SQLAlchemy + Pydantic (`python/mp/schema/*.py`)
- DB dependency export: `python/mp/db/__init__.py` (`get_db`)

## Router Layout

- `mp.api.auth` mounted at `/auth`
- `mp.api.accounts` mounted at `/`
- `mp.api.contracts` mounted at `/`

## Auth + Session Model

- Registration/login/logout/me are in `python/mp/api/auth.py`.
- Session model is encrypted+signed token (Fernet) containing:
  - `user_id`
  - `expires_at`
- Token is accepted from:
  - cookie `mp_session`
  - `Authorization: Bearer <token>`
- Login returns both:
  - cookie (set-cookie)
  - `session_token` in JSON for API clients
- Session signing key:
  - from `SESSION_KEY` env var (preferred)
  - generated at startup if missing
  - warning is logged when using default `changeme`

## Account API Behavior

Defined in `python/mp/api/accounts.py`.

- `GET /accounts`
- `GET /accounts/{account_id}`
- `GET /accounts/{account_id}/history`
  - returns historical value points (`value_cents`, `recorded_at`) ordered by time
- `POST /accounts`
- `PUT /accounts/{account_id}`
- `PUT /accounts/{account_id}/value`
  - dedicated “value update” endpoint used by dashboard Update modal
  - updates balance/position values only
  - for `line_of_credit`/`credit_card`/`loan`, can also set `last_payment_date`
  - for `cash` accounts, accepts `cash_bills` quantities and balance is derived from denominations
  - for crypto accounts, accepts multiple `crypto_positions` entries with `ticker`, `quantity`, and `exchange_rate_cents`
  - when crypto `exchange_rate_cents` is provided, backend propagates that rate to all holdings with same ticker for that user
  - sets `accounts.last_update = now()`
  - records an `account_value_history` point after each successful update
- `PUT /accounts/{account_id}/rank`
  - sets rank explicitly (float)
  - used by tile left/right reorder controls
- `DELETE /accounts/{account_id}`
- `GET /organizations`
  - returns organization suggestions (default organizations + user organizations)
  - each suggestion includes optional `icon_id`
- `POST /icons`
  - uploads image, normalizes to small PNG, deduplicates by SHA-256 hash, returns icon UUID/hash
- `GET /icons/lettered/{organization_name}`
  - deterministic two-letter icon generated on demand from organization seed
- `GET /icons/gravatar/{organization_name}`
  - deterministic identicon-style icon generated on demand from organization seed
- `GET /icons`
  - lists selectable icons for current user (default icons + icons uploaded by current user)
  - ordering is stable and grouped as: generic defaults -> organization defaults -> user-uploaded
- `GET /default-icons`
  - lists generic default icon presets (`key`, `label`, `icon_id`) not tied to organizations
- `GET /icons/{icon_id}`
  - returns PNG bytes for tile/render usage
  - access is restricted to: default icons, user-owned icons, or icons referenced by user's accounts
- `DELETE /icons/{icon_id}`
  - deletes a user-owned uploaded icon
  - default icons and non-owned icons are not deletable

### Validation Rules (Current)

- Required on create/update identity:
  - `account_number`
  - `name`
  - `organization`
  - valid `type`
- `icon_type` enum on account is one of: `Letters`, `Gravatar`, `Icon`.
  - `Icon` uses persisted `icon_id` in `icon_assets`
  - `Letters`/`Gravatar` are generated at read-time and do not create DB icon records
- Type-specific fields are mostly optional unless directly required by a specialized endpoint flow.
- `fee_period` accepts structured recurring-period JSON and is schema-validated.

## Stock API Behavior

- `GET /stocks`
- `POST /stocks`
- `PUT /stocks/{stock_id}`
- `DELETE /stocks/{stock_id}`

Stock price propagation:
- `stocks.last_price_cents` is user-scoped market price metadata.
- Updating `last_price_cents` on one stock propagates to same-ticker stocks for that user.

Stocks are user-scoped. DB uniqueness is per user (`user_id, ticker, exchange`).

## Contract API Behavior

Defined in `python/mp/api/contracts.py`.

- `GET /contracts`
  - supports optional `as_of_date=YYYY-MM-DD` for simulation projection
- `POST /contracts`
- `PUT /contracts/{contract_id}`
  - contract `type` is immutable after create
- `PUT /contracts/{contract_id}/rank`
  - supports tile reorder behavior in category sections
- `DELETE /contracts/{contract_id}`
- `POST /contracts/run`
  - scheduler/manual engine endpoint
  - supports:
    - `dry_run` (default `true`)
    - `as_of_date` or `through_date`
  - dry-run returns planned postings without mutating balances
  - apply mode writes postings, updates balances, and advances `last_payment_date`

Validation + ownership rules:
- `name`, `organization`, and `linked_account_id` are required.
- `type` must be one of `income|payment|transfer`.
- `source_account_id` is required only for `transfer`.
- `payment_day` is required (`1..31`).
- `account_number` is optional for contracts.
- `linked_account_id` and `source_account_id` must belong to current user.
- `icon_type` follows account behavior (`Letters|Gravatar|Icon`).
- icon selection can infer default `icon_id` from matching organization if icon type is `Icon`.
- `expiration_date` defaults to `2099-01-01` when omitted.

Automatic execution model:
- Contract posting is idempotent using `contract_postings` unique `(contract_id, effective_date)`.
- Scheduler and apply runs reuse the same engine (`mp/contracts/engine.py`).
- Early-pay handling is applied when deriving first upcoming due date:
  - if `last_payment_date` falls between expected prior due and upcoming due, skip to next-next cycle.

Update-modal ownership:
- UI intentionally edits `last_payment_date` and `expiration_date` through contract `Update` flow (not the full editor), but API continues to accept either update path.

## Ownership + Access Control

- Accounts/stocks are always filtered by authenticated `user_id`.
- Contract reads/writes/runs are always filtered by authenticated `user_id`.
- Cross-user access is denied server-side even if IDs are known.

## Important Timestamp Semantics

For **accounts**:
- `created_at` = creation time (backend-managed)
- `last_update` = business value refresh time from Update modal endpoint (`/accounts/{id}/value`)
- Avoid conflating `last_update` with generic metadata edits.

## Example Data Contract

- Register supports `add_example_data`.
- Users store `example_data` boolean in DB.
- Startup sync/seeding uses `python/mp/sample_data.py`.
- When adding new account features/types, update sample data so opted-in users receive representative records.

## Organization/Icon Defaults

- Default organizations are bootstrapped from:
  - `python/organizations/organizations.yml`
  - PNG files in `python/organizations/`
- Generic default icon presets are bootstrapped from:
  - `python/organizations/generic_icons.yml`
  - PNG files in `python/organizations/`
- Startup loader `mp.organization_defaults.ensure_default_organizations_loaded()` ensures defaults are in DB.
- Account creation/update can infer `icon_id` from matching organization defaults when explicit icon is not provided.
- For uploaded/default catalog icons, `icon_type` should be `Icon`.
