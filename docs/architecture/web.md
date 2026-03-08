# Web Architecture

## Stack

- Vue 3 + TypeScript + Vite
- Carbon CSS base styles (`@carbon/styles`)
- Axios wrapper in `web/vue/src/lib/api.ts`

## Core Pages

- Landing + login/register: `web/vue/src/auth/LandingPage.vue`
- Authenticated shell/header: `web/vue/src/AppShell.vue`
- Dashboard/accounts: `web/vue/src/accounts/AccountsPage.vue`
- Dashboard/contracts: `web/vue/src/accounts/ContractsTab.vue`

## Design System Direction

- Base visual language is Carbon.
- Prefer reusable shared components over page-local one-offs.
- Current shared form primitives:
  - `web/vue/src/components/BankField.vue`
  - `web/vue/src/components/DollarField.vue`
  - `web/vue/src/components/RecurringPeriodField.vue`
  - `web/vue/src/components/UnifiedDropdown.vue`
  - `web/vue/src/components/AddTypePickerButton.vue` (right-aligned add button + type dropdown)

Shared tile visual definitions now live in:
- `web/vue/src/accounts/sharedTile.css`

Both account and contract tiles should consume that shared stylesheet instead of redefining tile layout/styles independently.

## Dropdown Consistency Rule

Use `UnifiedDropdown` for dropdown/combobox-style menus (account type picker, organization fuzzy search, recurring period type selector). This keeps:
- hover behavior,
- width/overflow behavior,
- option rendering,
- searchable/custom entry behavior,
consistent across the app.

Use `AddTypePickerButton.vue` for right-aligned "Add ..." flows that open a type-selection dropdown from the action button. This is now shared by Accounts and Contracts tabs.

Organization fuzzy search sources organizations from `GET /organizations` (not only local account state) so defaults and known icons are available immediately.

## Dashboard Interaction Patterns

In `AccountsPage.vue`:

- Account tiles grouped by section (cash, securities, hard assets, etc.).
- Tile action menu contains:
  - `Edit`
  - `Update`
  - `History`
  - `Delete`
- Update flow:
  - opens custom modal
  - calls `PUT /accounts/{id}/value`
  - intended to refresh business values and drive `last_update`
  - for `cash` accounts, update modal edits bill quantities (`$1,$2,$5,$10,$20,$50,$100`) instead of static balance input
  - cash balance shown on tile is derived from bill quantities
  - for crypto accounts, update modal supports multiple ticker rows with quantity + exchange rate
  - crypto tile balance is derived from sum(quantity * exchange_rate)
- History flow:
  - opens history modal from tile menu
  - fetches `GET /accounts/{id}/history`
  - renders value-over-time line chart
- Delete flow uses custom confirm modal (no browser `alert/confirm`).
- Account create/edit modal supports icon upload:
  - uploads to `POST /icons`
  - stores returned `icon_id` on account payload
  - stores `icon_type` on account (`Icon`, `Letters`, `Gravatar`)
  - deterministic generated options are rendered directly from:
    - `GET /icons/lettered/{organization}`
    - `GET /icons/gravatar/{organization}`
  - selecting an organization auto-applies known icon where available
  - users can choose from icon library via `GET /icons` (defaults + their uploads)
  - generic defaults are available via backend default icon catalog (`GET /default-icons`) for consistent fallback choices
  - right-click on a user-uploaded icon in the picker opens delete action (`DELETE /icons/{id}`)
  - all account types expose an editable `url` field near the bottom of the modal
  - account tiles show a hyperlink icon when URL is present; opening uses a new browser tab

## Ranking / Reorder UX

- Accounts expose float `rank` from API.
- Tile controls:
  - `◀` moves one slot left (not shown on first tile in section)
  - `▶` moves one slot right (not shown on last tile in section)
- Frontend computes a new rank between neighboring ranks and calls `PUT /accounts/{id}/rank`.

Contracts use the same float-rank strategy within each category section and call `PUT /contracts/{id}/rank`.

## Contracts Tile Parity

Contracts intentionally mirror account tile UX:
- grouped sections (by category),
- left/right rank arrows,
- icon + organization + last4 identity rows,
- link icon and update-age clock badge,
- bottom-right three-dot menu for edit/delete.
- `Update` action owns payment-timing lifecycle fields (`last_payment_date`, `expiration_date`), while the main edit modal omits them.
- Expired contracts (`expiration_date` before today) are rendered in a trailing `Expired` section after active grouped sections.
- active contracts are grouped by `type + category` (example: `Incoming Work`, `Payment Digital`).

Contract create/edit also mirrors account create/edit patterns:
- organization fuzzy dropdown from `/organizations`,
- icon selection/upload from `/icons` and generated icon variants,
- immutable type selected before modal opens.

## Next-Payment Early-Pay Logic

Contracts and payable accounts use the same intent:
- if a recorded payment is newer than the expected prior scheduled payment but still before the upcoming scheduled payment, treat it as an **early payment** and move “next payment” forward by one extra cycle.

Implementation references:
- Accounts: `computePaymentDates()` in `web/vue/src/accounts/AccountsPage.vue`
- Contracts: `nextPaymentDate()` in `web/vue/src/accounts/ContractsTab.vue`

Keep this behavior consistent across future scheduling/forecasting UI so “next payment” does not incorrectly show the already-covered upcoming cycle.

## Last-Update Visual Indicator

Each tile shows a top-right clock indicator with tooltip `last update: <Month dayOrdinal>`.

Color mapping:
- `< 7 days`: green
- `7-30 days`: blue
- `30-90 days`: black
- `> 90 days` or missing: red

## Icon Rendering

- Tile icons are rendered from `/api/icons/{icon_id}`.
- Accounts without icon use neutral placeholder.
- Keep icon usage consistent: prefer organization default icon reuse before new uploads.

## Money Input Behavior

`DollarField.vue` uses cents-safe input behavior:
- terminal-style digit entry when typing normally
- selection replacement behavior when text is highlighted (typing replaces selection)
- supports fine editing of cents and dollars without invalid currency states.

## Serving / Proxy

- Built web app served by NGINX (`web/Dockerfile`, `web/nginx.conf`).
- API requests should go through `/api/*` via NGINX proxy.
