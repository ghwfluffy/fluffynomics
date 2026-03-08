# API Architecture

## Stack

- Framework: FastAPI (`python/main.py`)
- ORM + models: SQLAlchemy + Pydantic (`python/mp/schema/*.py`)
- DB dependency export: `python/mp/db/__init__.py` (`get_db`)

## Router Layout

- `mp.api.auth` mounted at `/auth`
- `mp.api.accounts` mounted at `/`

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
- `POST /accounts`
- `PUT /accounts/{account_id}`
- `PUT /accounts/{account_id}/value`
  - dedicated “value update” endpoint used by dashboard Update modal
  - updates balance/position values only
  - sets `accounts.last_update = now()`
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

Stocks are user-scoped. DB uniqueness is per user (`user_id, ticker, exchange`).

## Ownership + Access Control

- Accounts/stocks are always filtered by authenticated `user_id`.
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
