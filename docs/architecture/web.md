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
- Dashboard/expenses: `web/vue/src/accounts/ExpensesTab.vue`

Dashboard top-level tabs are now:
- `Overview` (widgets/forecast/trend)
- `Accounts`
- `Transfers`
- `Contracts`
- `Expenses`
- `Calendar`

`Overview` is the default tab on dashboard load.
On narrow screens, the desktop tab bar is replaced with a top-of-page section dropdown that drives the same dashboard tab state.

Calendar tab behavior:
- shows month view with previous/next month navigation.
- renders upcoming fee, contract, and expense events on day cells.
- clicking an event opens actions and supports `Edit` / `Update` using the same object flows as the source tab.
- on narrow screens, swaps to a compact month grid with day-level color coding by net change magnitude; tapping a day opens the exact event names and amounts for that date.

## Design System Direction

- Base visual language is Carbon.
- Use Carbon CSS framework widgets/patterns by default (`cds--*` components, Carbon structure/classes) rather than creating custom one-off controls when an equivalent Carbon pattern exists.
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

For account-selection inputs specifically (linked account, source account, wallet-backed account, credit-card payment funding account), prefer `UnifiedDropdown` with `searchable` enabled so large account lists stay usable.
When a searchable dropdown already has a selected option, opening it should still show the full option list until the user starts typing a different query.

Recurring period UI (`RecurringPeriodField.vue`) must support interval schedules in addition to base monthly/yearly:
- `every_n_months_day` (every N months on a day),
- `every_n_years_month_day` (every N years on month/day).

Use `AddTypePickerButton.vue` for right-aligned "Add ..." flows that open a type-selection dropdown from the action button. This is now shared by Accounts and Contracts tabs.

Forecast-date UX:
- Dashboard widgets live under the `Overview` tab and include a popover `Set Forecast Date` control (`AccountsPage.vue`).
- When set, frontend sends `as_of_date` in read calls:
  - `/accounts`
  - `/contracts`
- Clearing the date returns to live mode (today / persisted state).
- This is read-only simulation mode; write endpoints do not use forecast date.

View mode UX:
- Accounts/Contracts/Expenses share one `Tiles` / `Icons` / `Table` mode state.
- Toggling view mode in one tab applies to the other tabs for consistency.
- `Icons` is the default dashboard view mode.
- `Icons` mode shows compact icon-first cards with balance/value visible up front; clicking the icon expands that card into the same detail content/actions as the tile view.
- In tile mode, stale trailing sections stay collapsed by default behind `CollapsibleSectionHeader.vue`:
  - Accounts: `Closed Accounts`
  - Contracts: `Expired`
  - Expenses: `Legacy`

Expenses tab grouping:
- enabled expenses stay under their normal category labels.
- disabled expenses render in a trailing `Legacy` section in tile mode.
- the expenses table `Category` column and category sort should follow that same display grouping so tiles and table stay consistent.

Trend widget behavior:
- Net worth trend sources historical data from `GET /accounts/net-worth/history`.
- Endpoint returns daily snapshots; frontend should preserve daily points for normal recent-history ranges and only collapse to coarser monthly points once the history gets long enough to need bucketing.
- When forecast date is in the future, frontend also fetches `GET /accounts/net-worth/forecast` and merges intermediate forecast event points so trend shows each projected contract-impact step.
- This ensures trend expands to full available history instead of fixed recent-window snapshots.
- On desktop widths, the overview top widget grid holds four cards with the net-worth trend card first, followed by portfolio mix, last-30 change, and next-30 change.
- Overview trend header shows only the prorated `Net Worth` value.
- Hovering or focusing that net-worth value reveals a popover with `Current Net Worth`.
- That popover should also show an itemized signed `/day` breakdown for the actual live proration inputs that move the net-worth value: recurring contracts, recurring expenses, and account fees.
- `Current Net Worth` starts from account balances and includes in-progress accrual for non-automatic recurring contracts plus recurring expenses over their current cycles.
- `Current Net Worth` also includes in-progress recurring account-fee accrual over the current fee cycle.
- Displayed `Net Worth` adds automatic recurring contract accrual on top of that current-net-worth baseline.
- Proration smoothing rule: recurring contract/expense/fee accrual should be summed in fractional cents first and rounded once at the final displayed total, rather than rounding each line item independently.
- Early-payment proration rule: if a recurring contract is marked paid early for its upcoming scheduled occurrence, the next accrual cycle should begin immediately from that actual payment date rather than leaving a dead window until the old scheduled boundary.
- Exclusion rule: expired contracts, closed fee-bearing accounts, and disabled expenses must be excluded from both the live proration math and the overview summaries/rate widgets that explain that math.
- In live mode, the prorated value refreshes every 5 seconds; when a forecast date is set, proration is evaluated at that fixed date instead of live time.
- Overview also includes derived rate widgets under the trend chart:
  - projected net-worth flow from contracts + expenses + recurring account fees (`per year/month/week/day`, dollar-rounded),
  - historical 12-month net-worth flow rates (`per year/month/week/day`),
  - historical acceleration estimate (`$/month²`) derived from change in monthly slope over the historical window.
  - a net-worth projection bar chart for the anchor month/year plus the calculated `+1 year`, `+5 year`, and `+10 year` month/year targets.
  - a 60-day biggest-changes widget showing the first two positive events and first two negative events whose absolute value is at least `$1,000`, with each pair displayed in chronological order.
  - upcoming-change widgets merge simulation output with locally derived non-automatic recurring contract occurrences so manual contracts appear in both the 30-day breakdown and the 60-day biggest-changes card.
  - projection bars stay in chronological order, but their green fill shades are assigned by relative value from lightest (least value) to darkest (greatest value).
  - historical-widget labels should show the actual week window used for the calculation.

### Architecture Decision: Trend Merge Semantics

- Frontend treats historical and forecast series as distinct sources:
  - history = persisted reality snapshots,
  - forecast = simulated future path.
- Merge is date-keyed and time-ordered to produce one continuous chart line.
- This keeps UI logic simple and deterministic while allowing backend forecast logic to evolve without changing chart rendering contracts.

Organization fuzzy search sources organizations from `GET /organizations` (not only local account state) so defaults and known icons are available immediately.

Masked mode UX:
- Profile menu exposes a one-way `Masked Mode` action.
- Once enabled, masked mode stays active through page refreshes and cannot be turned off in-session; logout clears it.
- While active, account/contract-facing dollar amounts and account numbers render through deterministic fake values that preserve sign, ordering, and digit-scale for safe demos.
- Masked mode applies to chart geometry too, not only labels/tooltips, so net-worth/history/projection visuals do not leak the real scale.
- Masked mode is view-only for dashboard finance actions; account, contract, and expense create/edit/update/delete/reorder flows should refuse to open or submit until the user logs out and signs back in.

## Data Portability UX

`AppShell.vue` header uses a profile trigger (avatar + username) with a dropdown menu that provides:
- `Profile`
  - opens profile-management modal
  - uses Carbon tabs:
    - `Info`: avatar selection (icon library / upload / clear) + account-created/last-login/last-password-change info
    - `Password`: password change flow (`current password` + `new password`)
    - `Digital Wallets`: maps `PayPal` / `Google Pay` aliases to concrete accounts
    - `Delete Account`: requires current password + explicit confirmation checkbox, then permanently deletes the signed-in user account
- `Manage Users` (admin users only)
  - opens admin user-management modal with Carbon tabs:
    - `Users`
    - `Registration`
  - `Users` tab contains user table
  - signed-in admin cannot edit their own row from this view
  - supports per-user actions:
    - update password (opens modal with password + verify fields)
    - lock/unlock account
    - mark/unmark admin (checkbox-driven)
    - delete account (in-app confirmation modal, not browser alert/confirm)
  - `Registration` tab contains registration code CRUD
- `Administration` (admin users only)
  - opens admin modal for backup controls
  - supports:
    - trigger local scheduled backup immediately
    - download full-site backup (`.sql.gz`)
    - upload and restore full-site backup (`.sql.gz`)
- `Export Data`
  - opens modal with optional password
  - downloads a JSON package from `POST /data/export`
- `Import Data`
  - opens modal for package file selection + optional password
  - accepts both modern JSON export package files and legacy `.yml/.yaml` files
  - uploads package to `POST /data/import` with replace semantics
  - app reloads after successful import to refresh dashboard state
- `Logout`

Register form behavior:
- includes optional `Registration Code` input.
- first account can leave it blank.
- once users exist, backend requires a valid non-expired code.

Password is optional in both flows. It is required only for encrypted packages.

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
  - intended to refresh business values and drive `last_update`
  - default path calls `PUT /accounts/{id}/value`
  - for `cash` accounts, update modal edits bill quantities (`$1,$2,$5,$10,$20,$50,$100`) instead of static balance input
  - cash balance shown on tile is derived from bill quantities
  - for crypto accounts, update modal supports multiple ticker rows with quantity + exchange rate
  - crypto tile balance is derived from sum(quantity * exchange_rate)
  - for `stocks_account` accounts whose organization is exactly `Robinhood`, the update modal also exposes a statement-PDF import action
  - that import uploads a Robinhood PDF, replaces the stock positions from the statement, syncs brokerage/individual cash when present, and also updates the user's Robinhood crypto-exchange account when the PDF includes a `Cryptocurrencies` section
  - for accounts whose organization is exactly `Wells Fargo`, the update modal also exposes a PDF import action that syncs all Wells Fargo accounts found in the PDF by matching saved account-number last 4 values
  - for `credit_card` accounts, update modal switches to a queued-payment flow:
    - inputs `Current Balance`, `Pending Balance`, `Rewards Balance`, `Amount Paying`, and `Pay From`
    - calls `POST /accounts/{id}/queue-credit-card-payment`
    - `Amount Paying = 0` is valid and means “sync card balance only, no queued payment”
    - tile/table balances immediately render as if the queued payment has already reduced both the card and the funding account
    - update-form starting values must use the stored/imported account balance, not the transfer-adjusted display balance shown on tiles/icons
    - while a queued payment is active, the modal reopens with the queued values prefilled so the user can edit them
    - editing an active queued payment uses `PUT /accounts/{id}/queue-credit-card-payment` and reschedules settlement to the next business day at noon
    - setting `Amount Paying` to `0` while editing an active queued payment cancels it
  - every account update modal also shows a bottom `Transfers` section listing pending transfers where that account is either the source or destination
  - that section supports transfer CRUD in-place for supported direct-balance account types and uses short descriptions like transfer amount + counterpart account
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
- when masked mode is active, account-number displays (tile/table last-4 and related derived strings) must use masked values instead of the real account number

Transfers tab UX:
- `Transfers` is a dedicated dashboard tab for pending transfers.
- It lists queued credit-card payments and manual transfers together with source, destination, amount, completion timestamp, and transfer type.
- Transfer create/edit uses `/transfers` CRUD; credit-card payments stay special on the account update modal but can still be edited or deleted from the Transfers tab/account transfer section.
- Manual transfer create/edit defaults the completion timestamp server-side to next business day at noon when left blank.
- Standard manual transfers also expose an `Instant Deposit` checkbox; when enabled, the destination account reflects the transfer immediately while the source waits until completion.
- When transfer create is opened from an account update modal, that account should default as the destination; source-account dropdown ordering should prioritize checking accounts by rank before other eligible accounts.

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
- next-payment countdown text on tiles/tables should expose the exact scheduled date on hover,
- bottom-right three-dot menu for edit/delete.
- `Update` action owns payment-timing lifecycle fields (`last_payment_date`, `expiration_date`), while the main edit modal omits them.
- Update modal exposes an `Expired` checkbox; this is the supported manual-expiration control.
- Expired contracts (`expiration_date` before today) are rendered in a trailing `Expired` section after active grouped sections, collapsed by default.
- active contracts are grouped by `type + category` (example: `Incoming Work`, `Payment Digital`).

Contract create/edit also mirrors account create/edit patterns:
- organization fuzzy dropdown from `/organizations`,
- icon selection/upload from `/icons` and generated icon variants,
- immutable type selected before modal opens.
- linked target selector supports wallet aliases (`PayPal Wallet`, `Google Pay Wallet`) in addition to account IDs.
- `Payment Day` field is hidden and omitted from payload for week-based recurring periods (`weekly_weekday`, `biweekly_weekday`, `every_n_weeks_weekday`).
- masked mode should still show contract amounts/countdowns, but through the same deterministic fake-currency formatter used by the accounts dashboard

## Expenses UX

Expenses support CRUD in `ExpensesTab.vue` with:
- name,
- category,
- notes,
- linked account (required),
- icon selection (`Letters|Gravatar|Icon`),
- estimated amount,
- general frequency,
- last expensed date,
- next expensed date with static-vs-derived toggle.
- `Update` menu action edits only operational fields: `enabled`, `last expensed date`, `next expensed date`.

The tab supports both tile and table rendering and follows the same menu/modal patterns as accounts/contracts.
The create/edit expense modal must always expose linked-account selection so expense simulation can apply deltas to the intended account.
Disabled expenses stay editable/updateable in the `Legacy` tile section, which is collapsed by default.
When masked mode is active, expense amounts should render through the same fake-currency display layer and all expense mutations should stay locked.

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

## Agent Handoff Notes

- Before closing work that touches backend/frontend behavior, run:
  - `python/lint.sh`
  - `web/build.sh`
- Keep admin UX split:
  - `Administration` is backups-only.
  - `Manage Users` owns user operations and registration code CRUD.
- Use in-app Carbon-styled modals for destructive confirmations; do not add browser `alert`/`confirm`.
- API requests should go through `/api/*` via NGINX proxy.
- Edge rate limiting is enforced in `web/nginx.conf`:
  - stricter per-IP limits for `/api/auth/*` (brute-force/fuzz pressure),
  - broader per-IP request + connection limits for `/api/*`.
