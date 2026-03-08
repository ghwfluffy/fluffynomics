# API Architecture

## Stack

- Framework: FastAPI (`python/main.py`)
- ORM + models: SQLAlchemy + Pydantic (`python/mp/schema/*.py`)
- DB dependency export: `python/mp/db/__init__.py` (`get_db`)

## Router Layout

- `mp.api.auth` mounted at `/auth`
- `mp.api.admin` mounted at `/admin`
- `mp.api.accounts` mounted at `/`
- `mp.api.contracts` mounted at `/`
- `mp.api.data_portability` mounted at `/data`
- `mp.api.backups` mounted at `/backups`

## Auth + Session Model

- Registration/login/logout/me are in `python/mp/api/auth.py`.
- Registration rule:
  - first account can register without a code.
  - once at least one user exists, `POST /auth/register` requires `registration_code`.
  - registration codes are looked up case-insensitively (normalized uppercase) and must exist + be unexpired.
- Profile updates are in `python/mp/api/auth.py` via `PUT /auth/profile`.
- Self account deletion is in `python/mp/api/auth.py` via `POST /auth/delete-account`.
- Session model is encrypted+signed token (Fernet) containing:
  - `user_id`
  - `expires_at`
- Token is accepted from:
  - cookie `mp_session`
  - `Authorization: Bearer <token>`
- Login returns both:
  - cookie (set-cookie)
  - `session_token` in JSON for API clients
- User profile metadata exposed on auth user payload:
  - `avatar_icon_id`
  - `paypal_account_id`
  - `google_pay_account_id`
  - `last_login_at`
  - `password_changed_at`
- Login updates `last_login_at`.
- Password brute-force protection:
  - enforced on password-bearing auth flows (`POST /auth/login`, password-change branch of `PUT /auth/profile`)
  - threshold: `10` consecutive failed password attempts
  - lockout window: `30` seconds (`429` while locked)
  - successful password verification resets failed-attempt and lockout state
- Profile endpoint supports:
  - avatar selection/clearing (`avatar_icon_id`, using icon library/default ownership rules)
  - password change (`current_password`, `new_password`)
  - digital wallet links (`paypal_account_id`, `google_pay_account_id`) to owned accounts
- Account deletion endpoint (`POST /auth/delete-account`):
  - requires current authenticated session and `current_password`.
  - uses the same brute-force/lockout controls as login/password change.
  - permanently deletes user-owned data and then the user row.
  - clears auth session cookie on success.
- Session signing key:
  - from `SESSION_KEY` env var (preferred)
  - generated at startup if missing
  - warning is logged when using default `changeme`

## Account API Behavior

Defined in `python/mp/api/accounts.py`.

### Architecture Decision: Net-Worth Data Strategy

- Historical trend source is precomputed daily snapshots (`net_worth_daily_snapshot`) exposed via `GET /accounts/net-worth/history`.
- Forecast trend source is contract-event projection points via `GET /accounts/net-worth/forecast`.
- The API intentionally avoids full on-demand historical recomputation for every chart request because replaying long event streams does not scale predictably.
- Fallback replay from `account_value_history` exists only when snapshots are missing (bootstrap/backfill safety path).

- `GET /accounts`
- `GET /accounts/{account_id}`
- `GET /accounts/{account_id}/history`
  - returns historical value points (`value_cents`, `recorded_at`) ordered by time
- `GET /accounts/net-worth/history`
  - returns daily user net-worth snapshots (`snapshot_date`, `value_cents`)
  - primary source is `net_worth_daily_snapshot`
  - falls back to replaying `account_value_history` only when snapshots are empty
  - liability account types (`credit_card`, `line_of_credit`, `loan`) are treated as negative contributions
  - used for dashboard trend charts to expand as far back as recorded history exists
- `GET /accounts/net-worth/forecast?through_date=YYYY-MM-DD`
  - returns forecast net-worth datapoints between today and `through_date`
  - includes intermediate contract-effective dates (not only final target date)
  - liability account types are signed negative in the net-worth projection
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
  - upserts one daily net-worth snapshot for the user (same day updates overwrite that day’s snapshot)
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
  - recurring JSON supports monthly/yearly, plus interval forms: `every_n_months_day` and `every_n_years_month_day`.

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
  - liability-aware balance deltas:
    - for linked liability accounts (`credit_card`, `line_of_credit`, `loan`), non-transfer contract deltas are inverted at balance layer
    - this means `payment` contracts increase liability balances (more owed), while `income` contracts decrease liability balances

Validation + ownership rules:
- `name` and `organization` are required.
- exactly one linked target is required: `linked_account_id` or `linked_wallet`.
- `linked_wallet` allowed values: `paypal|google_pay`.
- `type` must be one of `income|payment|transfer`.
- `source_account_id` is required only for `transfer`.
- `transfer` cannot use `linked_wallet`; it must use concrete account IDs.
- `payment_day` is required (`1..31`).
- `account_number` is optional for contracts.
- `linked_account_id` and `source_account_id` must belong to current user.
- `icon_type` follows account behavior (`Letters|Gravatar|Icon`).
- icon selection can infer default `icon_id` from matching organization if icon type is `Icon`.

## Expense API Behavior

Defined in `python/mp/api/expenses.py`.

- `GET /expenses`
- `POST /expenses`
- `PUT /expenses/{expense_id}`
- `DELETE /expenses/{expense_id}`

Expense semantics:
- Fields: `name`, `category`, `notes`, `icon_id/icon_type`, `estimated_amount_cents`, `linked_account_id`, `general_frequency`, `last_expensed_date`, `next_expensed_date`, `next_date_is_static`.
- Includes `enabled` boolean so expenses can be turned off without deletion.
- Validation:
  - `name` and `category` are required.
  - `estimated_amount_cents >= 0`.
  - `linked_account_id` is required on create.
  - `icon_type` follows `Letters|Gravatar|Icon`.
  - `general_frequency` accepts recurring-period JSON (legacy keywords are tolerated).
- Next-date behavior:
  - if `next_date_is_static=true`, `next_expensed_date` is required and stored directly.
  - otherwise backend derives `next_expensed_date` from `last_expensed_date + general_frequency`.

Automatic execution model:
- Contract posting is idempotent using `contract_postings` unique `(contract_id, effective_date)`.
- Scheduler/apply runs execute both engines:
  - contracts: `mp/contracts/engine.py`
  - expenses: `mp/expenses/engine.py`
- Early-pay handling is applied when deriving first upcoming due date:
  - if `last_payment_date` falls between expected prior due and upcoming due, skip to next-next cycle.

Forecast/as-of behavior:
- `GET /accounts` and `GET /accounts/{id}` with `as_of_date` apply projected deltas from both contracts and expenses.
- `GET /accounts/net-worth/forecast` includes future deltas from both contracts and expenses.
- `POST /contracts/run` now executes both simulations for the target date and returns both posting sets.

Update-modal ownership:
- UI intentionally edits `last_payment_date` and `expiration_date` through contract `Update` flow (not the full editor), but API continues to accept either update path.

Deletion coupling rule:
- Account-linked objects that are not tightly coupled (`contracts.linked_account_id`, `expenses.linked_account_id`) do not cascade-delete with account deletion.
- Those references are nullable and use `ON DELETE SET NULL`; API should tolerate historical rows with a missing linked account and require relinking before normal execution semantics.

## Ownership + Access Control

- Accounts/stocks are always filtered by authenticated `user_id`.
- Contract reads/writes/runs are always filtered by authenticated `user_id`.
- Cross-user access is denied server-side even if IDs are known.

## Data Export / Import API

Defined in `python/mp/api/data_portability.py`.

- `POST /data/export`
  - builds a versioned JSON package of current user data:
    - user profile metadata (avatar + profile timestamps; excludes credentials)
    - icons referenced by user records
    - stocks
    - accounts (+ stock/crypto/cash sub-records)
    - contracts
    - contract postings ledger
    - expenses
    - account value history
    - net-worth daily snapshots
  - package envelope fields:
    - `format: "money-planner-export"`
    - `package_version: 1`
    - `encrypted: boolean`
  - optional password support:
    - when password is provided, payload is encrypted (`cipher: fernet`)
    - key derivation uses PBKDF2-SHA256 with intentionally high-hardness defaults:
      - large salt (`>=64` bytes, current export uses 128 bytes)
      - high iteration count (`1,500,000`)
- `POST /data/import`
  - accepts package envelope + optional password
  - decrypts (if needed), deserializes JSON, migrates payload schema to latest, then replaces user-scoped records via insert flow
  - also accepts legacy YAML/object imports (auto-detected by legacy keys like `assets`/`contracts`) and converts them into current payload schema before replace
  - legacy period mappings include `N Months` and `N Years`; `Half Month` maps to 15th and last day of month
  - legacy period mappings also include `Every N Weeks` (`every_n_weeks_weekday`); weekday is inferred from `nextPayment` when present
  - legacy default-org matching uses canonical-name containment with special aliases:
    - `WF` token matches `Wells Fargo`
    - `CitiCard` matches `Citibank`
    - longest-match scoring prevents generic card-brand collisions (for example `Wells Fargo Visa` resolves to `Wells Fargo`)
  - legacy org fallback:
    - if no default org match and account name contains `texas`, importer assigns the default `texas` generic icon
  - legacy closure rule:
    - payable/liability accounts with `nextPayment` more than 30 years in the future are imported as `closed=true`
    - contracts with `nextPayment` more than 30 years in the future are imported with an expired `expiration_date`
  - legacy import also writes a current-day net-worth snapshot after replace, computed from imported account balances using liability sign rules
  - currently supports only `replace_existing=true`
  - response returns imported object counts for each dataset class

### Export Payload Migration Contract

- Export payload includes `schema_version`.
- Import path must run migration steps until current `schema_version`.
- If payload version is newer than server-supported version, import is rejected.
- Initial migration compatibility:
  - payloads with missing `schema_version` are treated as legacy v0 and upgraded to v1.
- Current payload schema version: `4`.
- Security metadata rule:
  - brute-force lockout state (`failed_password_attempts`, `password_lockout_until`) is intentionally not exported/imported and remains local runtime state.
- Digital-wallet link rule:
  - user wallet links (`paypal_account_id`, `google_pay_account_id`) and contract `linked_wallet` are exported/imported.
- Schema-change rule:
  - backend schema/API changes that affect user data must update both:
    - DB migration/ORM model paths, and
    - data portability export/import serialization + migration logic.

## Backup API

Defined in `python/mp/api/backups.py`.

- `POST /backups/run-now`
  - admin-only endpoint that schedules an immediate local DB backup run
  - creates trigger file consumed by backup worker container
  - returns scheduling status
- `POST /backups/site/export`
  - admin-only endpoint that returns a full-site `pg_dump` as `.sql.gz`
  - format matches automated backup worker dump format
- `POST /backups/site/restore`
  - admin-only endpoint accepting uploaded backup payload
  - supports gzip SQL dumps (`.sql.gz`) and plain SQL dumps (`.sql`)
  - restores full site contents into the configured Postgres DB

## Admin API

Defined in `python/mp/api/admin.py`.

- `GET /admin/registration-codes`
  - admin-only list of all registration codes
- `POST /admin/registration-codes`
  - admin-only create
  - server generates a unique 32-character uppercase alphanumeric `code`
  - payload accepts:
    - `name` (required)
    - `expires_at` (optional)
- `PUT /admin/registration-codes/{code_id}`
  - admin-only update of `name` and/or `expires_at`
- `DELETE /admin/registration-codes/{code_id}`
  - admin-only removal
- `GET /admin/users`
  - admin-only list of users with role/lock/timestamp fields
- `PUT /admin/users/{user_id}/password`
  - admin-only password reset for target user
  - clears target lockout state
- `PUT /admin/users/{user_id}/lock`
  - admin-only lock/unlock toggle via `locked: bool`
- `PUT /admin/users/{user_id}/admin`
  - admin-only admin role toggle via `is_admin: bool`
  - rejects removing admin role from the last remaining admin
- `DELETE /admin/users/{user_id}`
  - admin-only user delete
  - rejects deleting the last remaining admin
  - rejects deleting self via admin endpoint (self-delete uses profile delete flow)

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
