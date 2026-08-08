# API Architecture

## Stack

- Framework: FastAPI (`python/main.py`)
- ORM + models: SQLAlchemy + Pydantic (`python/mp/schema/*.py`)
- DB dependency export: `python/mp/db/__init__.py` (`get_db`)

## Router Layout

- `mp.api.auth` mounted at `/auth`
- `mp.api.admin` mounted at `/admin`
- `mp.api.accounts` mounted at `/`
- `mp.api.widgets` mounted at `/widgets`
- `mp.api.contracts` mounted at `/`
- `mp.api.data_portability` mounted at `/data`
- `mp.api.investments` mounted at `/`
- `mp.api.logs` mounted at `/`
- `mp.api.backups` mounted at `/backups`

## Auth + Session Model

- Registration/login/logout/me are in `python/mp/api/auth.py`.
- Default auth mode is local standalone auth. Setting `AUTH_MODE=oauth` enables central OAuth login through the configured `AUTH_BASE_URL`.
- OAuth mode keeps a local Fluffynomics session cookie after callback, but disables local password login, registration, password changes, profile avatar changes, user CRUD, and registration-code CRUD.
- Expired OAuth state callbacks redirect back to the landing page with an
  `oauth_error` query value. The web app removes that query and performs one
  automatic OAuth retry so a central Remember Me session can restore and finish
  the sign-in hop. Other OAuth failures, and a repeated expired-state callback,
  show a notification instead of leaving users on an API error response or
  redirect loop.
- `AUTH_BASE_URL` is the public browser/issuer base, while
  `OAUTH_SERVER_BASE_URL` can point backend token and userinfo calls at an
  internal auth API URL.
- First OAuth login links an existing unlinked local username when possible; otherwise it creates a local user linked by central issuer and subject.
- Public deployment pathing is configured with:
  - `PUBLIC_URL`: externally visible scheme/host/port used for public absolute URLs.
  - `APP_BASE_PATH`: externally visible app prefix, normalized to leading/trailing slash form (for example `/fluffynomics/`).
- FastAPI runs behind NGINX with external API URLs under `<APP_BASE_PATH>api/...`; NGINX strips that external prefix before proxying to FastAPI routers.
- Session cookies use `APP_BASE_PATH` as their cookie path so subpath deployments remain scoped to the mounted app prefix.
- `SESSION_COOKIE_NAME` and `SESSION_COOKIE_PATH` may be set explicitly to avoid same-host cookie collisions.
- Registration rule:
  - first account can register without a code.
  - once at least one user exists, `POST /auth/register` requires `registration_code`.
  - registration codes are looked up case-insensitively (normalized uppercase) and must exist + be unexpired.
- Profile updates are in `python/mp/api/auth.py` via `PUT /auth/profile`.
- Widget URL rotation is in `python/mp/api/auth.py` via `POST /auth/widget-url/regenerate`.
- Self account deletion is in `python/mp/api/auth.py` via `POST /auth/delete-account`.
- Session model is encrypted+signed token (Fernet) containing:
  - `user_id`
  - `expires_at`
- Token is accepted from:
  - cookie `mp_session`
  - `Authorization: Bearer <token>`
- In omnisite mode, the AI assistant can call selected read/write finance APIs
  with short-lived agent-scoped bearer tokens. Set
  `AGENT_INTEGRATION_TOKEN_SECRET` to the same ignored secret value used by the
  agent service. Agent tokens must be issued by `agent-service`, use audience
  `budget`, carry the current user's central OAuth subject, and include the
  exact allowed action scope such as `budget.list_accounts`. They map only to
  users that already have a central OAuth-linked local account and are not
  accepted for auth/admin/profile/backup APIs. Allowed scoped actions include
  account reads/value updates, net-worth history/forecast reads, transfer reads,
  investment/log reads, and contract/expense list/create/update/delete actions.
  Contract and expense write scopes exist so the agent can queue approved
  projection changes such as recurring subscriptions or observed spending
  patterns without broad API access.
- Login returns both:
  - cookie (set-cookie)
  - `session_token` in JSON for API clients
- User profile metadata exposed on auth user payload:
  - `avatar_icon_id`
  - `paypal_account_id`
  - `google_pay_account_id`
  - `widget_token`
  - `widget_last_accessed_at`
  - `widget_last_net_worth_cents`
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
  - widget URL rotation via `POST /auth/widget-url/regenerate`
- Widget URL rotation rule:
  - regenerating creates a new URL-safe random token for the signed-in user.
  - the old widget URL becomes invalid immediately.
  - widget hit-history fields are cleared when the token rotates so the next render starts from a fresh baseline.
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
  - returns daily projected points between today and `through_date`
  - liability account types are signed negative in the net-worth projection
  - also includes projected positive yield from savings APY and the implicit 5.5% monthly-compounded yield used for `stocks_account`, `investment_fund`, and `retirement`
  - recurring investments are projected as future source/destination balance moves, so they can change later yield growth even when the immediate net-worth delta is zero
- `POST /accounts`
- `PUT /accounts/{account_id}`
- `PUT /accounts/{account_id}/value`
  - dedicated “value update” endpoint used by dashboard Update modal
  - updates balance/position values only
  - `investment_fund` accounts are simple balance-based investment assets; they use `balance_cents` and do not carry per-holding stock positions
  - savings APY (`apy_bps` + `compound_period`) participates in forecast/proration calculations
  - for `line_of_credit`/`credit_card`/`loan`, can also set `last_payment_date`
  - `credit_card` accounts with an active queued payment reject direct `balance_cents` writes until the queued payment settles
  - for `cash` accounts, accepts `cash_bills` quantities and balance is derived from denominations
  - for crypto accounts, accepts multiple `crypto_positions` entries with `ticker`, `quantity`, and `exchange_rate_cents`
  - when crypto `exchange_rate_cents` is provided, backend propagates that rate to all holdings with same ticker for that user
  - sets `accounts.last_update = now()`
  - records an `account_value_history` point after each successful update
  - upserts one daily net-worth snapshot for the user (same day updates overwrite that day’s snapshot)
- `POST /accounts/{account_id}/import-robinhood-statement`
  - Robinhood-only helper for `stocks_account` update flow
  - accepts a monthly statement PDF upload and parses it with `pdfplumber`
  - supports both classic monthly statement PDFs and Robinhood account-summary PDFs
  - classic statements merge `Securities Held in Account` and `Loaned Securities` by ticker
  - account-summary PDFs parse both `Stocks` and `Cryptocurrencies` sections by symbol
  - replaces the stock account's positions using statement quantity plus derived per-share cents from statement equity/market value
  - updates stock-account cash from `Brokerage Cash Balance` or `Individual cash` when present
  - if the PDF includes cryptocurrencies, backend also looks up the user's Robinhood `crypto_exchange` account and replaces its crypto positions from the statement
- `POST /accounts/{account_id}/import-wells-fargo-statement`
  - Wells Fargo helper for account update flow
  - accepts a Wells Fargo account-summary PDF and parses account last-4 plus available/outstanding balances
  - matches user-owned Wells Fargo accounts by the last 4 digits of `account_number`
  - updates every uniquely matched direct-balance account from the PDF in one import pass
- Account-type upgrader:
  - migration `0038_accounts_investment_fund.sql` adds `investment_fund`
  - existing `stocks_account` rows whose organization starts with `Betterment` or `Acorns` are upgraded in place
  - upgrader preserves current total value by rolling stock-position market value into `balance_cents`, then clearing the per-stock holdings
- `POST /accounts/{account_id}/queue-credit-card-payment`
  - credit-card-only update flow used by the dashboard Update modal
  - payload captures `current_balance_cents`, `pending_balance_cents`, `rewards_balance_cents`, `payment_cents`, and `source_account_id`
  - stores the card balance as `current + pending` immediately, then creates a pending transfer with `effective_at = next business day at 12:00 local-API time`
  - settlement scheduling skips weekends and observed US bank holidays
  - if `payment_cents = 0`, it updates the card balance only and does not create a queued payment
  - account reads present balances as if the payment has already reduced both the credit card and the funding account, even before settlement
  - settlement is lazy: once `effective_at` is reached, the next account read/write applies the transfer into the underlying account balances and records value history
- `PUT /accounts/{account_id}/queue-credit-card-payment`
  - edits the active queued payment for that card using the same payload shape
  - updates the stored `current + pending` card balance immediately
  - resets the queue timer so settlement happens on the next business day at noon after the latest edit
  - if `payment_cents = 0`, the active queued payment is canceled and removed
- `GET /transfers`
  - lists active pending account transfers (manual transfers plus queued credit-card payments)
  - each row includes source account, destination account, amount, transfer kind, `instant_deposit`, queued time, and completion time
- `POST /transfers`
  - creates a manual pending transfer between two user-owned accounts with direct balance fields
  - supports `instant_deposit=true`, which credits the destination balance immediately while deferring only the source-side debit until `effective_at`
  - default completion time is next business day at noon when `effective_at` is omitted
- `PUT /transfers/{transfer_id}`
  - edits an active pending transfer
  - changing or deleting an instant-deposit transfer reverses/reapplies the already-posted destination-side balance effect as needed
  - credit-card-payment transfers keep their destination credit card, but funding account, amount, and completion time remain editable
- `DELETE /transfers/{transfer_id}`
  - deletes an active pending transfer
- `PUT /accounts/{account_id}/rank`
  - sets rank explicitly (float)
  - used by tile left/right reorder controls
- `DELETE /accounts/{account_id}`
- `GET /organizations`
  - returns organization suggestions (default organizations + user organizations)
- `GET /widgets/net-worth.png?token=...`
  - public PNG widget endpoint; does not require session auth
  - token is matched against `users.widget_token`
  - every successful hit renders a fresh `351x485` PNG containing prorated net worth, change since the previous hit, elapsed time between hits, and the branded cat artwork
  - successful hits persist `widget_last_accessed_at` and `widget_last_net_worth_cents` on the owning user row
- `GET /logs`
  - returns recent per-user audit-log events in newest-first order
  - each event includes:
    - `trigger_type` (`user`, `cron`, or `system`)
    - `event_type`
    - human-readable `message`
    - `occurred_at`
    - structured `details`
  - intended for the dashboard `Logs` tab
- Audit-log write rule:
  - log both explicit user mutations and automatic recurring/system balance changes
  - current covered flows include:
    - account create/update/delete
    - account value updates and statement imports
    - queued transfer / queued credit-card-payment create-update-delete-settle
    - contract / expense / investment create-update-delete
    - recurring contract / expense / investment application
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
  - early-payment rule: when `last_payment_date` is manually set after the previous scheduled occurrence but before the upcoming scheduled occurrence, the upcoming occurrence is treated as already covered and skipped by scheduler/forecast logic
  - payment contracts may set optional `next_payment_date` to replace exactly one upcoming scheduled occurrence without permanently changing the recurring cadence
- `PUT /contracts/{contract_id}/rank`
  - supports tile reorder behavior in category sections
- `DELETE /contracts/{contract_id}`
- `POST /contracts/run`
  - scheduler/manual engine endpoint
  - supports:
    - `dry_run` (default `true`)
    - `as_of_date` or `through_date`
  - dry-run returns planned postings without mutating balances
  - apply mode writes postings, updates balances, advances `last_payment_date`, records touched account value-history points, and refreshes the user’s daily net-worth snapshot
  - respects the same early-payment skip rule used by contract reads and projections
  - consumes one-off `next_payment_date` overrides for payment contracts; once the override occurrence is applied, backend clears it
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

Expense recurrence rule:
- when `last_expensed_date` is manually set after the previous scheduled occurrence but before the upcoming scheduled occurrence, the upcoming occurrence is treated as already covered and derived `next_expensed_date` skips to the following cycle.

## Investment API Behavior

Defined in `python/mp/api/investments.py`.

- `GET /investments`
- `POST /investments`
- `PUT /investments/{investment_id}`
- `DELETE /investments/{investment_id}`
- recurring investments move money from a checking source account into a destination account of type `savings`, `stocks_account`, `crypto_exchange`, `retirement`, or `investment_fund`
- `general_frequency` uses the same recurring-period JSON conventions as expenses/contracts
- `next_date_is_static=true` requires an explicit `next_investment_date`
- apply-time execution is handled by the shared recurring scheduler and updates both linked account balances/history
- future account reads and net-worth forecasts must include recurring-investment balance movement so destination-account yield can compound from those future contributions

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
- `GET /accounts`, `GET /accounts/{id}`, account history, and net-worth endpoints all lazily settle due pending transfers before responding so reads stay consistent with scheduled completion times.
- Any balance-changing event path that mutates persisted account values (manual account update, transfer settlement/instant-deposit posting, contract apply, expense apply, statement import) must also refresh the user’s daily net-worth snapshot; the snapshot table keeps only the latest value for a given day.

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
    - icons uploaded by the user plus icons referenced by user records
    - stocks
    - accounts (+ stock/crypto/cash sub-records)
    - contracts
    - contract postings ledger
    - expenses
    - account value history
    - net-worth daily snapshots
    - queued credit-card payments
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
- Export/import payload now also carries `investments`.
- If payload version is newer than server-supported version, import is rejected.
- Initial migration compatibility:
  - payloads with missing `schema_version` are treated as legacy v0 and upgraded to v1.
- Current payload schema version: `12`.
- Security metadata rule:
  - brute-force lockout state (`failed_password_attempts`, `password_lockout_until`) is intentionally not exported/imported and remains local runtime state.
- Digital-wallet link rule:
  - user wallet links (`paypal_account_id`, `google_pay_account_id`) and contract `linked_wallet` are exported/imported.
  - legacy YAML import also maps wallet-like payment-account aliases (for example `PayPal`, `Google Pay.*`, `gpay`) into contract `linked_wallet` when possible.
- Contract expiration rule:
  - modern export/import preserves `contracts.expiration_date` exactly; the far-future-to-expired cleanup is only for legacy YAML conversion.
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
  - app-local NGINX permits request bodies up to 25 MB for this endpoint while retaining the default body limit elsewhere
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
- Startup sync/seeding uses `python/mp/db/sample_data.py`.
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
