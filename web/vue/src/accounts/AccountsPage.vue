<template>
  <div class="dashboard">
    <div class="cds--tabs" role="navigation" aria-label="Dashboard Sections">
      <ul class="cds--tabs__nav" role="tablist">
        <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': activeTab === 'overview' }" role="presentation">
          <button
            id="tab-overview"
            class="cds--tabs__nav-link"
            role="tab"
            type="button"
            :aria-selected="activeTab === 'overview'"
            aria-controls="panel-overview"
            @click="activeTab = 'overview'"
          >
            Overview
          </button>
        </li>
        <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': activeTab === 'accounts' }" role="presentation">
          <button
            id="tab-accounts"
            class="cds--tabs__nav-link"
            role="tab"
            type="button"
            :aria-selected="activeTab === 'accounts'"
            aria-controls="panel-accounts"
            @click="activeTab = 'accounts'"
          >
            Accounts
          </button>
        </li>
        <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': activeTab === 'contracts' }" role="presentation">
          <button
            id="tab-contracts"
            class="cds--tabs__nav-link"
            role="tab"
            type="button"
            :aria-selected="activeTab === 'contracts'"
            aria-controls="panel-contracts"
            @click="activeTab = 'contracts'"
          >
            Contracts
          </button>
        </li>
        <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': activeTab === 'expenses' }" role="presentation">
          <button
            id="tab-expenses"
            class="cds--tabs__nav-link"
            role="tab"
            type="button"
            :aria-selected="activeTab === 'expenses'"
            aria-controls="panel-expenses"
            @click="activeTab = 'expenses'"
          >
            Expenses
          </button>
        </li>
        <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': activeTab === 'calendar' }" role="presentation">
          <button
            id="tab-calendar"
            class="cds--tabs__nav-link"
            role="tab"
            type="button"
            :aria-selected="activeTab === 'calendar'"
            aria-controls="panel-calendar"
            @click="activeTab = 'calendar'"
          >
            Calendar
          </button>
        </li>
      </ul>
    </div>

    <section v-if="activeTab === 'overview'" id="panel-overview" class="cds--tile widgets" role="tabpanel" aria-labelledby="tab-overview">
      <div class="widget-toolbar">
        <div class="forecast-popover-wrap">
          <button
            class="cds--btn cds--btn--ghost widget-forecast-toggle"
            type="button"
            @click.stop="showForecastControls = !showForecastControls"
          >
            Set Forecast Date
          </button>
          <div v-if="showForecastControls" class="forecast-popover" @click.stop>
            <div class="forecast-row">
              <BankField v-model="forecastDate" label="Forecast Date" type="date" />
              <button class="cds--btn cds--btn--ghost" type="button" @click="clearForecastDate">Use Today</button>
            </div>
          </div>
        </div>
      </div>
      <div class="widget-grid">
        <article class="widget-slot widget-card">
          <div class="widget-card-head">
            <h3>Portfolio Mix</h3>
            <span class="widget-card-hint">Hover slices for type and percent</span>
          </div>
          <div class="widget-donut-row">
            <VChart class="widget-donut-echart" :option="mixChartOption" autoresize />
          </div>
        </article>
        <article class="widget-slot widget-card">
          <h3>Net Change (Last 30 Days)</h3>
          <div class="widget-kpi" :class="hasPast30SnapshotData ? deltaClass(netChangePast30) : 'delta-muted'">
            {{ hasPast30SnapshotData ? signedCents(netChangePast30) : 'No data' }}
          </div>
          <p class="widget-subtext">Compared to 30 days before {{ widgetAnchorLabel }}</p>
        </article>
        <article class="widget-slot widget-card">
          <h3>Net Change (Next 30 Days)</h3>
          <div
            class="widget-kpi-hover-wrap"
            @mouseenter="showNext30Breakdown = true"
            @mouseleave="showNext30Breakdown = false"
            @focusin="showNext30Breakdown = true"
            @focusout="showNext30Breakdown = false"
          >
            <div class="widget-kpi" :class="deltaClass(netChangeNext30)" tabindex="0">{{ signedCents(netChangeNext30) }}</div>
            <div v-if="showNext30Breakdown" class="widget-kpi-popout">
              <div class="widget-kpi-popout-title">Included Changes</div>
              <div v-if="next30BreakdownBusy" class="widget-kpi-popout-empty">Loading…</div>
              <div v-else-if="next30BreakdownItems.length === 0" class="widget-kpi-popout-empty">No projected postings.</div>
              <ul v-else class="widget-kpi-popout-list">
                <li v-for="item in next30BreakdownItems" :key="item.key">
                  <span>{{ item.dateLabel }} • {{ item.label }}</span>
                  <strong :class="deltaClass(item.netDeltaCents)">{{ signedCents(item.netDeltaCents) }}</strong>
                </li>
              </ul>
            </div>
          </div>
          <p class="widget-subtext">Forecast from {{ widgetAnchorLabel }} using automatic contracts</p>
        </article>
      </div>
      <div class="widget-trend">
        <article class="widget-slot widget-card widget-card--wide">
          <div class="widget-trend-head">
            <h3 class="widget-trend-title">
              <span>Current Net Worth: {{ cents(currentNetWorthCents) }}</span>
              <span v-if="widgetLoading" class="widget-trend-status">Updating…</span>
            </h3>
          </div>
          <VChart class="widget-trend-echart" :option="trendChartOption" autoresize />
        </article>
      </div>
      <div class="widget-derived-grid">
        <article class="widget-slot widget-card">
          <h3>Projected Net-Worth Flow</h3>
          <p class="widget-subtext">Contracts + expenses forecast</p>
          <ul class="widget-rate-list">
            <li v-for="row in projectedRateRows" :key="`proj-${row.key}`">
              <span>{{ row.label }}</span>
              <strong :class="deltaClass(row.valueCents)">{{ formatDollarRate(row.valueCents) }}</strong>
            </li>
          </ul>
        </article>
        <article class="widget-slot widget-card">
          <h3>Historical Net-Worth Flow</h3>
          <p class="widget-subtext">{{ historicalWindowLabel }}</p>
          <ul class="widget-rate-list">
            <li v-for="row in historicalRateRows" :key="`hist-${row.key}`">
              <span>{{ row.label }}</span>
              <strong :class="deltaClass(row.valueCents)">{{ formatDollarRate(row.valueCents) }}</strong>
            </li>
          </ul>
        </article>
        <article class="widget-slot widget-card">
          <h3>Historical Acceleration</h3>
          <p class="widget-subtext">Change in $/month trend over {{ historicalWindowWeeks }} week{{ historicalWindowWeeks === 1 ? '' : 's' }}</p>
          <div class="widget-kpi" :class="deltaClass(historicalAccelerationCentsPerMonth2)">
            {{ formatDollarPerMonthSquared(historicalAccelerationCentsPerMonth2) }}
          </div>
        </article>
      </div>
    </section>

    <section v-if="activeTab === 'calendar'" id="panel-calendar" class="cds--tile calendar-panel" role="tabpanel" aria-labelledby="tab-calendar">
      <div class="calendar-toolbar">
        <button class="cds--btn cds--btn--ghost" type="button" @click="goToPreviousCalendarMonth">Previous</button>
        <h3>{{ calendarMonthLabel }}</h3>
        <button class="cds--btn cds--btn--ghost" type="button" @click="goToNextCalendarMonth">Next</button>
      </div>
      <div class="calendar-grid">
        <div v-for="weekday in calendarWeekdayLabels" :key="weekday" class="calendar-weekday">{{ weekday }}</div>
        <div
          v-for="cell in calendarCells"
          :key="cell.key"
          class="calendar-day-cell"
          :class="{ 'calendar-day-cell--outside': !cell.inMonth, 'calendar-day-cell--today': cell.isToday }"
        >
          <div class="calendar-day-number">{{ cell.dayNumber }}</div>
          <div class="calendar-day-events">
            <button
              v-for="event in cell.events.slice(0, 3)"
              :key="event.key"
              type="button"
              class="calendar-event-chip"
              :class="calendarEventToneClass(event)"
              @click="openCalendarEvent(event)"
            >
              <span class="calendar-event-chip-name">{{ event.label }}</span>
              <span class="calendar-event-chip-amount">{{ signedCents(event.signedAmountCents) }}</span>
            </button>
            <div v-if="cell.events.length > 3" class="calendar-more-events">+{{ cell.events.length - 3 }} more</div>
          </div>
        </div>
      </div>
      <div class="calendar-upcoming">
        <h4>Upcoming This Month</h4>
        <div v-if="calendarUpcomingEvents.length === 0" class="calendar-upcoming-empty">No events in this month.</div>
        <div v-else class="calendar-upcoming-table-wrap">
          <table class="calendar-upcoming-table">
            <thead>
              <tr>
                <th>Date / Event</th>
                <th>Type</th>
                <th>Amount</th>
                <th>Running Total</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="event in calendarUpcomingEventsWithRunning"
                :key="`up-${event.key}`"
                class="calendar-upcoming-row"
                @click="openCalendarEvent(event)"
              >
                <td>{{ event.dateLabel }} • {{ event.title }}</td>
                <td class="calendar-upcoming-type">{{ event.kindLabel }}</td>
                <td :class="deltaClass(event.signedAmountCents)">{{ signedCents(event.signedAmountCents) }}</td>
                <td :class="deltaClass(event.runningTotalCents)">{{ signedCents(event.runningTotalCents) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <div v-if="activeTab === 'accounts'" id="panel-accounts" role="tabpanel" aria-labelledby="tab-accounts">
      <div class="top-controls">
        <ViewModeToggle v-model="dashboardViewMode" />
      </div>
      <div v-if="dashboardViewMode === 'tiles'">
        <AddTypePickerButton
          button-label="Add New Account"
          placeholder="Select account type"
          :options="accountTypes"
          @select="onAccountTypePicked"
        />
      </div>
    </div>

    <div v-if="createDialog" class="modal-backdrop">
      <section class="modal-card cds--tile">
        <h3>{{ modalTitle }} {{ selectedTypeLabel || 'Account' }}</h3>
        <form class="form-grid" @submit.prevent="submitCreateAccount">
          <BankField v-model="createForm.name" label="Account Name" required />
          <BankField v-model="createForm.account_number" label="Account Number" required />

          <div v-if="needsRouting" class="column-spacer" aria-hidden="true"></div>
          <BankField v-if="needsRouting" v-model="createForm.routing_number" label="Routing Number" />

          <div v-if="createForm.type === 'credit_card'" class="column-spacer" aria-hidden="true"></div>
          <div v-if="createForm.type === 'credit_card'" class="field-row-inline">
            <BankField v-model="createForm.expiration_date" label="Expiration Date" type="date" />
            <BankField v-model="createForm.cvc" label="CVC" />
          </div>

          <UnifiedDropdown
            v-model="createForm.organization"
            label="Organization"
            placeholder="Type or select organization"
            searchable
            allow-custom
            required
            :options="organizationDropdownOptions"
          />
          <div class="icon-picker">
            <label class="bank-label">Account Icon</label>
            <div class="icon-picker-row">
              <img
                v-if="selectedFormIconUrl"
                :src="selectedFormIconUrl"
                class="icon-preview"
                alt="Selected icon"
              />
              <div v-else class="icon-preview icon-preview--empty" />
              <button type="button" class="cds--btn cds--btn--ghost icon-upload-btn" @click="openIconPickerModal">
                Choose Icon
              </button>
              <input ref="iconFileInput" class="icon-upload-input" type="file" accept="image/*" @change="uploadAccountIcon" />
              <button type="button" class="cds--btn cds--btn--ghost icon-upload-btn" @click="openIconUploadPicker">
                Upload New
              </button>
            </div>
          </div>

          <div v-if="needsBalance">
            <DollarField v-model="createForm.balance_cents" label="Balance" />
          </div>
          <div v-if="needsMaxCredit">
            <DollarField v-model="createForm.max_credit_cents" label="Max Credit" />
          </div>
          <div v-if="needsRewardsBalance">
            <DollarField v-model="createForm.rewards_balance_cents" label="Rewards Balance" />
          </div>

          <div v-if="needsFee" class="fee-row">
            <DollarField v-model="createForm.fee_amount_cents" label="Fee Amount" />
            <RecurringPeriodField v-if="showFeePeriod" v-model="createForm.fee_period" label="Fee Period" />
          </div>

          <div v-if="needsApy" class="field-row">
            <PercentField v-model="createForm.apy_bps" label="APY" />
            <BankField
              v-model="createForm.compound_period"
              label="Compound Period"
              :options="compoundPeriodOptions"
            />
          </div>

          <template v-if="needsApr && !needsCompoundPeriod">
            <PercentField v-model="createForm.apr_bps" label="APR" />
          </template>
          <div v-if="needsApr && needsCompoundPeriod" class="field-row">
            <PercentField v-model="createForm.apr_bps" label="APR" />
            <BankField
              v-model="createForm.compound_period"
              label="Compound Period"
              :options="compoundPeriodOptions"
            />
          </div>

          <div v-if="needsBillingDay || needsPaymentDay" class="field-row">
            <BankField v-if="needsBillingDay" v-model="createForm.billing_day" label="Billing Day" type="number" />
            <BankField v-if="needsPaymentDay" v-model="createForm.payment_day" label="Payment Day" type="number" />
          </div>

          <template v-if="needsExpiration && createForm.type !== 'credit_card'">
            <BankField v-model="createForm.expiration_date" label="Expiration Date" type="date" />
            <BankField v-if="needsCvc" v-model="createForm.cvc" label="CVC" />
          </template>

          <div v-if="createForm.type === 'crypto_exchange'">
            <DollarField v-model="createForm.usd_balance_cents" label="USD Balance" />
          </div>

          <div v-if="createForm.type === 'retirement'">
            <BankField
              v-model="createForm.retirement_account_type"
              label="Retirement Account Type"
              :options="retirementTypeOptions"
            />
          </div>

          <div v-if="createForm.type === 'loan'">
            <DollarField v-model="createForm.payment_amount_cents" label="Payment Amount" />
          </div>

          <div class="field-row">
            <BankField v-model="createForm.url" label="Account URL" type="url" />
          </div>
          <label class="check-row"><input v-model="createForm.closed" type="checkbox" /> <span>Closed Account</span></label>
          <BankField v-model="createForm.notes" class="notes-field" label="Notes" multiline />

          <div class="modal-actions">
            <button class="cds--btn cds--btn--ghost" type="button" @click="closeCreateDialog">Cancel</button>
            <button class="cds--btn cds--btn--primary" type="submit">{{ submitLabel }}</button>
          </div>
        </form>
      </section>
    </div>

    <div v-if="deleteDialog" class="modal-backdrop">
      <section class="confirm-card cds--tile">
        <h3>Delete Account</h3>
        <p>Are you sure you want to delete this account? This action cannot be undone.</p>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="closeDeleteDialog">Cancel</button>
          <button class="cds--btn cds--btn--danger" type="button" @click="confirmDeleteAccount">Delete</button>
        </div>
      </section>
    </div>

    <div v-if="iconPickerDialog" class="modal-backdrop">
      <section class="icon-modal-card cds--tile">
        <h3>Choose Icon</h3>
        <div class="generated-icon-actions">
          <button
            type="button"
            class="cds--btn cds--btn--secondary"
            @click="selectGeneratedIcon('Letters')"
          >
            Use Letters Icon
          </button>
          <button
            type="button"
            class="cds--btn cds--btn--secondary"
            @click="selectGeneratedIcon('Gravatar')"
          >
            Use Gravatar Style
          </button>
        </div>
        <div class="icon-grid-scroll">
          <button
            type="button"
            class="icon-choice icon-choice--none"
            :class="{ 'icon-choice--selected': iconPickerDraftType === 'Icon' && !iconPickerDraftId }"
            title="No icon"
            @click="selectNoIcon"
          >
            None
          </button>
          <button
            v-for="icon in iconChoices"
            :key="icon.id"
            type="button"
            class="icon-choice"
            :class="{ 'icon-choice--selected': iconPickerDraftId === icon.id }"
            :title="icon.is_default ? 'Default icon' : 'Uploaded icon'"
            @click="selectCatalogIcon(icon.id)"
            @contextmenu.prevent="openIconContextMenu($event, icon)"
          >
            <img :src="iconUrl(icon.id)" class="icon-preview" alt="Icon choice" />
          </button>
        </div>
        <div
          v-if="iconContextMenu.open"
          class="icon-context-menu"
          :style="{ left: `${iconContextMenu.x}px`, top: `${iconContextMenu.y}px` }"
        >
          <button type="button" class="icon-context-menu-item" @click="deleteContextIcon">Delete icon</button>
        </div>
        <div class="icon-modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="cancelIconPickerModal">Cancel</button>
          <button class="cds--btn cds--btn--primary" type="button" @click="acceptIconPickerModal">Accept</button>
        </div>
      </section>
    </div>

    <div v-if="updateDialog" class="modal-backdrop">
      <section
        class="confirm-card cds--tile"
        :class="{ 'confirm-card--wide': updateMode === 'crypto_positions' || updateMode === 'stock_positions' }"
      >
        <h3>Update {{ updatingAccount?.name }}</h3>
        <p>{{ updateDescription }}</p>

        <div class="form-grid form-grid--single">
          <DollarField
            v-if="updateMode === 'dollars'"
            v-model="updateForm.amountCents"
            :label="updateAmountLabel"
          />
          <DollarField
            v-if="showRewardsBalanceField"
            v-model="updateForm.rewardsCents"
            label="Rewards Balance"
          />
          <div v-else-if="updateMode === 'cash_bills'" class="cash-bills-grid">
            <BankField v-model="updateForm.cashBills[100]" label="$1 bills" type="number" />
            <BankField v-model="updateForm.cashBills[200]" label="$2 bills" type="number" />
            <BankField v-model="updateForm.cashBills[500]" label="$5 bills" type="number" />
            <BankField v-model="updateForm.cashBills[1000]" label="$10 bills" type="number" />
            <BankField v-model="updateForm.cashBills[2000]" label="$20 bills" type="number" />
            <BankField v-model="updateForm.cashBills[5000]" label="$50 bills" type="number" />
            <BankField v-model="updateForm.cashBills[10000]" label="$100 bills" type="number" />
          </div>
          <div v-else-if="updateMode === 'crypto_positions'" class="crypto-positions-editor">
            <div v-if="updatingAccount?.type === 'crypto_exchange'" class="crypto-usd-balance">
              <DollarField v-model="updateForm.amountCents" label="USD Cash Balance" />
            </div>
            <div v-for="(position, index) in updateForm.cryptoPositions" :key="`cp-${index}`" class="crypto-position-row">
              <BankField v-model="position.ticker" label="Ticker" />
              <BankField v-model="position.quantity" label="Quantity" />
              <DollarField v-model="position.exchange_rate_cents" label="Exchange Rate (USD)" />
              <button
                type="button"
                class="cds--btn cds--btn--ghost crypto-remove-btn"
                @click="removeCryptoPosition(index)"
                :disabled="updateForm.cryptoPositions.length <= 1"
              >
                Remove
              </button>
            </div>
            <button type="button" class="cds--btn cds--btn--secondary crypto-add-btn" @click="addCryptoPosition">
              Add Ticker
            </button>
          </div>
          <div v-else-if="updateMode === 'stock_positions'" class="crypto-positions-editor">
            <DollarField
              v-if="updatingAccount?.type === 'stocks_account'"
              v-model="updateForm.amountCents"
              label="USD Cash Balance"
            />
            <div v-for="(position, index) in updateForm.stockPositions" :key="`sp-${index}`" class="crypto-position-row">
              <BankField v-model="position.ticker" label="Ticker" />
              <BankField v-model="position.quantity" label="Quantity" />
              <DollarField v-model="position.last_price_cents" label="Price Per Share (USD)" />
              <button
                type="button"
                class="cds--btn cds--btn--ghost crypto-remove-btn"
                @click="removeStockPosition(index)"
              >
                Remove
              </button>
            </div>
            <button type="button" class="cds--btn cds--btn--secondary crypto-add-btn" @click="addStockPosition">
              Add Ticker
            </button>
          </div>
          <BankField
            v-if="showLastPaymentDateField"
            v-model="updateForm.lastPaymentDate"
            label="Last Payment Date"
            type="date"
          />
          <BankField
            v-if="showRewardsExpirationField"
            v-model="updateForm.expirationDate"
            label="Expiration Date"
            type="date"
          />
          <template v-else-if="updateMode === 'quantity'">
            <BankField v-model="updateForm.quantity" label="Quantity" />
            <BankField v-if="updatingAccount?.type === 'crypto_wallet'" v-model="updateForm.ticker" label="Ticker" />
          </template>
        </div>

        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="closeUpdateDialog">Cancel</button>
          <button class="cds--btn cds--btn--primary" type="button" @click="submitUpdateValue">Save</button>
        </div>
      </section>
    </div>

    <template v-if="activeTab === 'accounts' && dashboardViewMode === 'tiles'">
      <section v-for="section in sections" :key="section.key" class="section-wrap">
        <h2 class="section-title">{{ section.title }}</h2>
        <div v-if="section.accounts.length" class="section-grid">
          <article v-for="(account, index) in section.accounts" :key="account.id" class="cds--tile account-tile">
            <img v-if="accountIconUrl(account)" :src="accountIconUrl(account)" class="tile-icon" alt="Account icon" />
            <div v-else class="tile-icon tile-icon--empty" />
            <button
              v-if="index > 0"
              class="tile-rank-trigger"
              type="button"
              title="Move left"
              @click="moveAccountLeft(section, index, $event)"
            >
              ◀
            </button>
            <button
              v-if="index < section.accounts.length - 1"
              class="tile-rank-trigger tile-rank-trigger--right"
              type="button"
              title="Move right"
              @click="moveAccountRight(section, index, $event)"
            >
              ▶
            </button>
            <span
              v-if="!account.closed"
              class="tile-update-clock"
              :class="lastUpdateTone(account)"
              :title="lastUpdateTooltip(account)"
              aria-label="Last update status"
            />
            <a
              v-if="account.url?.trim()"
              class="tile-link"
              :href="normalizedAccountUrl(account.url)"
              target="_blank"
              rel="noopener noreferrer"
              title="Open account link"
              @click.stop
            >
              ↗
            </a>
            <div class="tile-title">{{ account.name }}</div>
            <div class="tile-sub">{{ account.organization || 'Unknown organization' }}</div>
            <div class="tile-sub">•••• {{ last4(account.account_number) }}</div>
            <div class="tile-balance" :class="balanceTone(account, section.key)">
              {{ balanceLabel(account) }}
            </div>
            <div v-if="paymentSummary(account)" class="tile-sub">{{ paymentSummary(account) }}</div>
            <div class="tile-type">{{ account.type.replaceAll('_', ' ') }}</div>
            <div class="tile-actions">
              <button
                class="tile-menu-trigger"
                type="button"
                aria-label="Account menu"
                @click.stop="toggleTileMenu(account.id)"
              >
                <span class="tile-menu-dots" aria-hidden="true"></span>
              </button>
              <div v-if="activeTileMenuId === account.id" class="tile-menu">
                <button type="button" class="tile-menu-option" @click="startEditAccount(account)">Edit</button>
                <button type="button" class="tile-menu-option" @click="openUpdateDialog(account)">Update</button>
                <button type="button" class="tile-menu-option" @click="openHistoryDialog(account)">History</button>
                <button type="button" class="tile-menu-option tile-menu-option--danger" @click="deleteAccount(account.id)">
                  Delete
                </button>
              </div>
            </div>
          </article>
        </div>
        <div v-else class="cds--tile empty-state">No accounts yet.</div>
      </section>
    </template>

    <section v-if="activeTab === 'accounts' && dashboardViewMode === 'table'" class="section-wrap">
      <div class="cds--data-table-container">
        <div class="table-toolbar-row">
          <DataTableControls
            v-model="accountsTableFilter"
            placeholder="Filter accounts"
            :filters="accountsColumnFilters"
            @update:filter="onAccountsColumnFilterUpdate"
          />
          <AddTypePickerButton
            inline
            button-label="Add New Account"
            placeholder="Select account type"
            :options="accountTypes"
            @select="onAccountTypePicked"
          />
        </div>
        <table class="cds--data-table cds--data-table--md">
          <thead>
            <tr>
              <th></th>
              <th><button class="sort-btn" type="button" @click="setAccountsSort('section')">Section</button></th>
              <th><button class="sort-btn" type="button" @click="setAccountsSort('name')">Name</button></th>
              <th><button class="sort-btn" type="button" @click="setAccountsSort('organization')">Organization</button></th>
              <th><button class="sort-btn" type="button" @click="setAccountsSort('last4')">Last 4</button></th>
              <th><button class="sort-btn" type="button" @click="setAccountsSort('type')">Type</button></th>
              <th><button class="sort-btn" type="button" @click="setAccountsSort('balance')">Balance</button></th>
              <th><button class="sort-btn" type="button" @click="setAccountsSort('last_update')">Last Update</button></th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="account in accountsTableRows" :key="account.id">
              <td class="table-icon-cell">
                <img v-if="accountIconUrl(account)" :src="accountIconUrl(account)" class="table-icon" alt="Account icon" />
                <div v-else class="table-icon table-icon--empty" aria-hidden="true"></div>
              </td>
              <td>{{ sectionTitleByType(account.type) }}</td>
              <td>{{ account.name }}</td>
              <td>{{ account.organization || 'Unknown' }}</td>
              <td>•••• {{ last4(account.account_number) }}</td>
              <td>{{ account.type.replaceAll('_', ' ') }}</td>
              <td>{{ balanceLabel(account).replace('Balance ', '') }}</td>
              <td>{{ formatLastUpdate(account.last_update) }}</td>
              <td class="table-actions-cell">
                <div class="table-overflow-menu">
                  <button class="tile-menu-trigger table-menu-trigger" type="button" aria-label="Account menu" @click.stop="toggleTileMenu(account.id)">
                    <span aria-hidden="true">⋮</span>
                  </button>
                  <div v-if="activeTileMenuId === account.id" class="tile-menu table-menu-list">
                    <button type="button" class="tile-menu-option" @click="startEditAccount(account)">Edit</button>
                    <button type="button" class="tile-menu-option" @click="openUpdateDialog(account)">Update</button>
                    <button type="button" class="tile-menu-option" @click="openHistoryDialog(account)">History</button>
                    <button type="button" class="tile-menu-option tile-menu-option--danger" @click="deleteAccount(account.id)">Delete</button>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="historyDialog" class="modal-backdrop">
      <section class="confirm-card cds--tile confirm-card--wide">
        <h3>History - {{ historyAccount?.name }}</h3>
        <div class="history-chart-wrap">
          <svg viewBox="0 0 760 260" class="history-chart" role="img" aria-label="Account value history">
            <line x1="50" y1="210" x2="730" y2="210" class="history-axis" />
            <line x1="50" y1="20" x2="50" y2="210" class="history-axis" />
            <line
              v-for="tick in historyYTicks"
              :key="`y-grid-${tick.value}`"
              x1="50"
              :y1="tick.y"
              x2="730"
              :y2="tick.y"
              class="history-grid"
            />
            <text
              v-for="tick in historyYTicks"
              :key="`y-label-${tick.value}`"
              x="44"
              :y="tick.y + 4"
              class="history-y-label"
              text-anchor="end"
            >
              {{ cents(tick.value) }}
            </text>
            <line
              v-for="tick in historyXTicks"
              :key="`x-grid-${tick.key}`"
              :x1="tick.x"
              y1="20"
              :x2="tick.x"
              y2="210"
              class="history-grid history-grid--vertical"
            />
            <text
              v-for="tick in historyXTicks"
              :key="`x-label-${tick.key}`"
              :x="tick.x"
              y="226"
              class="history-x-label"
              text-anchor="middle"
            >
              {{ tick.label }}
            </text>
            <polyline v-if="historyPolyline" :points="historyPolyline" class="history-line" />
            <circle
              v-for="point in historyChartPoints"
              :key="point.key"
              :cx="point.x"
              :cy="point.y"
              r="3"
              class="history-dot"
            />
          </svg>
          <div v-if="!historyItems.length" class="history-empty">No history yet.</div>
        </div>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="closeHistoryDialog">Close</button>
        </div>
      </section>
    </div>

    <ContractsTab
      v-if="activeTab === 'contracts'"
      ref="contractsTabRef"
      id="panel-contracts"
      role="tabpanel"
      aria-labelledby="tab-contracts"
      :accounts="accounts"
      :forecast-date="forecastDate"
      v-model:view-mode="dashboardViewMode"
    />

    <ExpensesTab
      v-if="activeTab === 'expenses'"
      ref="expensesTabRef"
      id="panel-expenses"
      role="tabpanel"
      aria-labelledby="tab-expenses"
      v-model:view-mode="dashboardViewMode"
    />

    <div v-if="calendarEventDialogOpen && selectedCalendarEvent" class="modal-backdrop">
      <section class="confirm-card cds--tile">
        <h3>{{ selectedCalendarEvent.title }}</h3>
        <p>{{ selectedCalendarEvent.dateLabel }} • {{ selectedCalendarEvent.kindLabel }}</p>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="closeCalendarEventDialog">Close</button>
          <button class="cds--btn cds--btn--secondary" type="button" @click="runCalendarEventAction('edit')">Edit</button>
          <button class="cds--btn cds--btn--primary" type="button" @click="runCalendarEventAction('update')">Update</button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { errorMessage, request, snackbar } from '@/lib/api'
import { currentUser } from '@/lib/auth'
import BankField from '@/components/BankField.vue'
import DollarField from '@/components/DollarField.vue'
import PercentField from '@/components/PercentField.vue'
import RecurringPeriodField from '@/components/RecurringPeriodField.vue'
import UnifiedDropdown from '@/components/UnifiedDropdown.vue'
import AddTypePickerButton from '@/components/AddTypePickerButton.vue'
import ViewModeToggle from '@/components/ViewModeToggle.vue'
import DataTableControls from '@/components/DataTableControls.vue'
import ContractsTab from '@/accounts/ContractsTab.vue'
import ExpensesTab from '@/accounts/ExpensesTab.vue'
import VChart, { THEME_KEY } from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, PieChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { provide } from 'vue'

use([PieChart, LineChart, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])
provide(THEME_KEY, 'light')

type AccountType =
  | 'checking'
  | 'savings'
  | 'cash'
  | 'line_of_credit'
  | 'credit_card'
  | 'stocks_account'
  | 'crypto_exchange'
  | 'crypto_wallet'
  | 'retirement'
  | 'loan'
  | 'rewards_card'

interface AccountPayload {
  id: string
  rank: number
  icon_id?: string
  icon_type?: 'Letters' | 'Gravatar' | 'Icon'
  account_number: string
  name: string
  type: AccountType
  organization?: string
  url?: string
  payment_day?: number
  last_payment_date?: string
  expiration_date?: string
  closed?: boolean
  last_update?: string
  balance_cents?: number
  max_credit_cents?: number
  rewards_balance_cents?: number
  fee_amount_cents?: number
  fee_period?: string
  usd_balance_cents?: number
  stock_positions?: Array<{ stock_id?: string; ticker?: string; quantity: string; last_price_cents?: number }>
  crypto_positions?: Array<{ ticker: string; quantity: string; exchange_rate_cents?: number }>
  cash_bills?: Array<{ denomination_cents: number; quantity: number }>
}

interface ContractCalendarPayload {
  id: string
  name: string
  type: 'income' | 'payment' | 'transfer'
  amount_cents: number
  linked_account_id?: string
  linked_wallet?: 'paypal' | 'google_pay'
  source_account_id?: string
  payment_period?: string
  payment_day?: number
  expiration_date?: string
}

interface ExpenseCalendarPayload {
  id: string
  name: string
  estimated_amount_cents: number
  enabled?: boolean
  general_frequency?: string
  next_expensed_date?: string
}

interface ContractRunPostingPayload {
  contract_id: string
  effective_date: string
  delta_cents: number
  status?: string
  reason?: string | null
}

interface ExpenseRunPostingPayload {
  expense_id: string
  account_id: string
  effective_date: string
  delta_cents: number
  status?: string
  reason?: string | null
}

interface ContractRunPreviewPayload {
  postings: ContractRunPostingPayload[]
  expense_postings: ExpenseRunPostingPayload[]
}

interface NetChangeBreakdownItem {
  key: string
  dateLabel: string
  label: string
  netDeltaCents: number
}

type RateRow = {
  key: string
  label: string
  valueCents: number
}

type CalendarEventKind = 'fee' | 'contract' | 'expense'

type CalendarEventAction = 'edit' | 'update'

interface CalendarEventItem {
  key: string
  kind: CalendarEventKind
  kindLabel: string
  sourceId: string
  title: string
  label: string
  dateIso: string
  dateLabel: string
  signedAmountCents: number
}

type ContractsTabExpose = {
  openFromCalendar: (contractId: string, action: CalendarEventAction) => Promise<boolean>
}

type ExpensesTabExpose = {
  openFromCalendar: (expenseId: string, action: CalendarEventAction) => Promise<boolean>
}

interface Section {
  key: string
  title: string
  types: AccountType[]
  accounts: AccountPayload[]
}

interface CreateAccountPayload {
  account_number: string
  name: string
  type: AccountType
  organization?: string
  url?: string
  balance_cents?: number
  fee_amount_cents?: number
  fee_period?: string
  routing_number?: string
  apy_bps?: number
  compound_period?: string
  apr_bps?: number
  billing_day?: number
  payment_day?: number
  last_payment_date?: string
  expiration_date?: string
  closed?: boolean
  max_credit_cents?: number
  rewards_balance_cents?: number
  cvc?: string
  usd_balance_cents?: number
  retirement_account_type?: string
  payment_amount_cents?: number
  icon_id?: string
  icon_type: 'Letters' | 'Gravatar' | 'Icon'
  stock_positions: Array<{ stock_id?: string; ticker?: string; exchange?: string; quantity: string; last_price_cents?: number }>
  crypto_positions: Array<{ ticker: string; quantity: string; exchange_rate_cents?: number }>
  cash_bills: Array<{ denomination_cents: number; quantity: number }>
}

interface OrganizationSuggestion {
  name: string
  url?: string
  icon_id?: string
  is_default: boolean
}

interface IconListItem {
  id: string
  hash: string
  is_default: boolean
  created_by_me: boolean
}

interface AccountHistoryPoint {
  value_cents: number
  recorded_at: string
}

interface NetWorthHistoryPoint {
  value_cents: number
  snapshot_date: string
}

interface NetWorthForecastPoint {
  value_cents: number
  snapshot_date: string
}

const makeCreateForm = (): CreateAccountPayload => ({
  account_number: '',
  name: '',
  type: 'checking',
  organization: '',
  closed: false,
  icon_type: 'Icon',
  stock_positions: [],
  crypto_positions: [],
  cash_bills: [],
})

const accounts = ref<AccountPayload[]>([])
const activeTab = ref<'overview' | 'accounts' | 'contracts' | 'expenses' | 'calendar'>('overview')
const forecastDate = ref<string>('')
const showForecastControls = ref(false)
const dashboardViewMode = ref<'tiles' | 'table'>('tiles')
const widgetLoading = ref(false)
const next30BreakdownBusy = ref(false)
const showNext30Breakdown = ref(false)
const next30BreakdownItems = ref<NetChangeBreakdownItem[]>([])
const hasPast30SnapshotData = ref(false)
const netWorthAnchorCents = ref(0)
const netWorthPast30Cents = ref(0)
const netWorthNext30Cents = ref(0)
const trendSnapshots = ref<Array<{ key: string; label: string; value_cents: number; forecast: boolean }>>([])
const projectedNetWorthDailyRateCents = ref(0)
const historicalNetWorthDailyRateCents = ref(0)
const historicalAccelerationCentsPerMonth2 = ref(0)
const historicalWindowWeeks = ref(0)
let widgetRequestToken = 0
const accountsTableFilter = ref('')
const accountsSortKey = ref<'section' | 'name' | 'organization' | 'last4' | 'type' | 'balance' | 'last_update'>('section')
const accountsSortDir = ref<'asc' | 'desc'>('asc')
const accountsSectionValues = ref<string[]>([])
const accountsOrganizationValues = ref<string[]>([])
const accountsTypeValues = ref<string[]>([])
const organizations = ref<OrganizationSuggestion[]>([])
const iconChoices = ref<IconListItem[]>([])
const createDialog = ref(false)
const createForm = ref<CreateAccountPayload>(makeCreateForm())
const editingAccountId = ref<string | null>(null)
const deleteDialog = ref(false)
const pendingDeleteAccountId = ref<string | null>(null)
const updateDialog = ref(false)
const updatingAccount = ref<AccountPayload | null>(null)
const historyDialog = ref(false)
const historyAccount = ref<AccountPayload | null>(null)
const historyItems = ref<AccountHistoryPoint[]>([])
const updateForm = ref({
  amountCents: 0,
  rewardsCents: 0,
  quantity: '0',
  ticker: '',
  lastPaymentDate: '',
  expirationDate: '',
  stockPositions: [{ ticker: '', quantity: '0', last_price_cents: 0 }] as Array<{
    stock_id?: string
    ticker: string
    quantity: string
    last_price_cents: number
  }>,
  cryptoPositions: [{ ticker: '', quantity: '0', exchange_rate_cents: 0 }] as Array<{
    ticker: string
    quantity: string
    exchange_rate_cents: number
  }>,
  cashBills: {
    100: 0,
    200: 0,
    500: 0,
    1000: 0,
    2000: 0,
    5000: 0,
    10000: 0,
  } as Record<number, number>,
})
const activeTileMenuId = ref<string | null>(null)
const iconFileInput = ref<HTMLInputElement | null>(null)
const contractsTabRef = ref<ContractsTabExpose | null>(null)
const expensesTabRef = ref<ExpensesTabExpose | null>(null)
const iconPickerDialog = ref(false)
const iconPickerDraftId = ref<string | undefined>(undefined)
const iconPickerDraftType = ref<'Letters' | 'Gravatar' | 'Icon'>('Icon')
const iconContextMenu = ref<{ open: boolean; x: number; y: number; iconId?: string }>({
  open: false,
  x: 0,
  y: 0,
})
const now = new Date()
const calendarMonthAnchor = ref<Date>(new Date(now.getFullYear(), now.getMonth(), 1))
const calendarContracts = ref<ContractCalendarPayload[]>([])
const calendarExpenses = ref<ExpenseCalendarPayload[]>([])
const calendarEventDialogOpen = ref(false)
const selectedCalendarEvent = ref<CalendarEventItem | null>(null)

const accountTypes = [
  { label: 'Checking', value: 'checking' },
  { label: 'Savings', value: 'savings' },
  { label: 'Cash', value: 'cash' },
  { label: 'Line of Credit', value: 'line_of_credit' },
  { label: 'Credit Card', value: 'credit_card' },
  { label: 'Stocks Account', value: 'stocks_account' },
  { label: 'Crypto Exchange', value: 'crypto_exchange' },
  { label: 'Crypto Wallet', value: 'crypto_wallet' },
  { label: 'Retirement', value: 'retirement' },
  { label: 'Loan', value: 'loan' },
  { label: 'Rewards Card', value: 'rewards_card' },
]

const sectionDefinitions: Array<Omit<Section, 'accounts'>> = [
  { key: 'cash', title: 'Cash Accounts', types: ['checking', 'savings', 'cash'] },
  {
    key: 'securities',
    title: 'Marketable Securities',
    types: ['stocks_account', 'crypto_exchange', 'crypto_wallet'],
  },
  { key: 'hard_assets', title: 'Hard Assets', types: ['retirement'] },
  { key: 'credit_cards', title: 'Credit Cards', types: ['credit_card'] },
  { key: 'payables', title: 'Payables', types: ['loan', 'line_of_credit'] },
  { key: 'rewards', title: 'Rewards', types: ['rewards_card'] },
  { key: 'closed', title: 'Closed Accounts', types: [] },
]

const compoundPeriods = ['daily', 'monthly']
const retirementTypes = [
  { value: 'roth', label: 'Roth' },
  { value: 'simple', label: 'SIMPLE' },
  { value: '401k', label: '401(k)' },
]
const compoundPeriodOptions = compoundPeriods.map((value) => ({ label: value, value }))
const retirementTypeOptions = retirementTypes

const needsBalance = computed(() =>
  ['checking', 'savings', 'line_of_credit', 'credit_card', 'retirement', 'loan', 'rewards_card', 'stocks_account'].includes(
    createForm.value.type,
  ),
)
const needsFee = computed(() =>
  ['checking', 'savings', 'line_of_credit', 'credit_card'].includes(createForm.value.type),
)
const showFeePeriod = computed(() => needsFee.value && (createForm.value.fee_amount_cents || 0) !== 0)
const needsRouting = computed(() => ['checking', 'savings'].includes(createForm.value.type))
const needsApy = computed(() => createForm.value.type === 'savings')
const needsApr = computed(() => ['line_of_credit', 'credit_card', 'loan'].includes(createForm.value.type))
const needsCompoundPeriod = computed(() =>
  ['line_of_credit', 'credit_card', 'loan'].includes(createForm.value.type),
)
const needsBillingDay = computed(() => ['line_of_credit', 'credit_card'].includes(createForm.value.type))
const needsPaymentDay = computed(() => ['line_of_credit', 'credit_card', 'loan'].includes(createForm.value.type))
const needsExpiration = computed(() => ['credit_card', 'rewards_card'].includes(createForm.value.type))
const needsCvc = computed(() => createForm.value.type === 'credit_card')
const needsMaxCredit = computed(() => ['line_of_credit', 'credit_card', 'rewards_card'].includes(createForm.value.type))
const needsRewardsBalance = computed(() => ['credit_card', 'rewards_card'].includes(createForm.value.type))

const sections = computed<Section[]>(() =>
  sectionDefinitions.map((section) => ({
    ...section,
    accounts:
      section.key === 'closed'
        ? accounts.value.filter((account) => account.closed)
        : accounts.value.filter((account) => !account.closed && section.types.includes(account.type)),
  })),
)

const sectionTitleForAccount = (account: AccountPayload) =>
  account.closed ? 'Closed Accounts' : sectionTitleByType(account.type)

const accountsSectionOptions = computed(() =>
  Array.from(new Set(accounts.value.map((account) => sectionTitleForAccount(account)))).sort((a, b) => a.localeCompare(b)),
)
const accountsOrganizationOptions = computed(() =>
  Array.from(new Set(accounts.value.map((account) => account.organization || 'Unknown'))).sort((a, b) => a.localeCompare(b)),
)
const accountsTypeOptions = computed(() =>
  Array.from(new Set(accounts.value.map((account) => account.type.replaceAll('_', ' ')))).sort((a, b) => a.localeCompare(b)),
)

const accountsColumnFilters = computed(() => [
  { key: 'section', label: 'Section', options: accountsSectionOptions.value, selected: accountsSectionValues.value },
  {
    key: 'organization',
    label: 'Organization',
    options: accountsOrganizationOptions.value,
    selected: accountsOrganizationValues.value,
  },
  { key: 'type', label: 'Type', options: accountsTypeOptions.value, selected: accountsTypeValues.value },
])

const accountsTableRows = computed(() => {
  const needle = accountsTableFilter.value.trim().toLowerCase()
  const rows = accounts.value.filter((account) => {
    if (!needle) {
      return true
    }
    const haystack = [
      sectionTitleForAccount(account),
      account.name,
      account.organization || '',
      account.account_number,
      account.type,
      balanceLabel(account),
      formatLastUpdate(account.last_update),
    ]
      .join(' ')
      .toLowerCase()
    return haystack.includes(needle)
  })
  const filteredByColumns = rows.filter((account) => {
    const section = sectionTitleForAccount(account)
    const organization = account.organization || 'Unknown'
    const typeLabel = account.type.replaceAll('_', ' ')
    if (accountsSectionValues.value.length && !accountsSectionValues.value.includes(section)) {
      return false
    }
    if (accountsOrganizationValues.value.length && !accountsOrganizationValues.value.includes(organization)) {
      return false
    }
    if (accountsTypeValues.value.length && !accountsTypeValues.value.includes(typeLabel)) {
      return false
    }
    return true
  })
  const sorted = [...filteredByColumns].sort((a, b) => {
    const key = accountsSortKey.value
    const av =
      key === 'section'
        ? sectionTitleForAccount(a)
        : key === 'name'
          ? a.name
          : key === 'organization'
            ? a.organization || ''
            : key === 'last4'
              ? last4(a.account_number)
              : key === 'type'
                ? a.type
                : key === 'balance'
                  ? tableBalanceCents(a)
                  : new Date(a.last_update || 0).getTime()
    const bv =
      key === 'section'
        ? sectionTitleForAccount(b)
        : key === 'name'
          ? b.name
          : key === 'organization'
            ? b.organization || ''
            : key === 'last4'
              ? last4(b.account_number)
              : key === 'type'
                ? b.type
                : key === 'balance'
                  ? tableBalanceCents(b)
                  : new Date(b.last_update || 0).getTime()
    if (typeof av === 'number' && typeof bv === 'number') {
      return accountsSortDir.value === 'asc' ? av - bv : bv - av
    }
    return accountsSortDir.value === 'asc'
      ? String(av).localeCompare(String(bv))
      : String(bv).localeCompare(String(av))
  })
  return sorted
})

const setAccountsSort = (key: typeof accountsSortKey.value) => {
  if (accountsSortKey.value === key) {
    accountsSortDir.value = accountsSortDir.value === 'asc' ? 'desc' : 'asc'
    return
  }
  accountsSortKey.value = key
  accountsSortDir.value = 'asc'
}

const onAccountsColumnFilterUpdate = (payload: { key: string; selected: string[] }) => {
  if (payload.key === 'section') {
    accountsSectionValues.value = payload.selected
    return
  }
  if (payload.key === 'organization') {
    accountsOrganizationValues.value = payload.selected
    return
  }
  if (payload.key === 'type') {
    accountsTypeValues.value = payload.selected
  }
}

const sectionTitleByType = (type: AccountType) =>
  sectionDefinitions.find((section) => section.types.includes(type))?.title || 'Other'

const accountTypeLabel = (type: AccountType) =>
  ({
    checking: 'Checking',
    savings: 'Savings',
    cash: 'Cash',
    line_of_credit: 'Line of Credit',
    credit_card: 'Credit Card',
    stocks_account: 'Stocks Account',
    crypto_exchange: 'Crypto Exchange',
    crypto_wallet: 'Crypto Wallet',
    retirement: 'Retirement',
    loan: 'Loan',
    rewards_card: 'Rewards Card',
  })[type]

const isLiabilityAccountType = (type?: string) => ['credit_card', 'line_of_credit', 'loan'].includes(String(type || ''))

const netWorthContributionCents = (account: AccountPayload) => {
  const rewards = accountRewardsCents(account)
  const baseValue = tableBalanceCents(account) - rewards
  if (isLiabilityAccountType(account.type)) {
    return -Math.abs(baseValue) + rewards
  }
  return baseValue + rewards
}

const currentNetWorthCents = computed(() =>
  accounts.value.reduce((sum, account) => sum + netWorthContributionCents(account), 0),
)
const netChangePast30 = computed(() => netWorthAnchorCents.value - netWorthPast30Cents.value)
const netChangeNext30 = computed(() => netWorthNext30Cents.value - netWorthAnchorCents.value)

const widgetAnchorDate = computed(() => parseDateOnly(forecastDate.value) || new Date())
const widgetAnchorLabel = computed(() =>
  widgetAnchorDate.value.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
)

const mixPalette = ['#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd', '#17becf', '#e377c2', '#bcbd22', '#8c564b', '#7f7f7f', '#3366cc']

const mixSlices = computed(() => {
  const totals = new Map<string, number>()
  for (const account of accounts.value) {
    const isLiability = isLiabilityAccountType(account.type)
    const key = isLiability ? 'Rewards' : accountTypeLabel(account.type)
    const value = isLiability ? accountRewardsCents(account) : Math.abs(tableBalanceCents(account))
    totals.set(key, (totals.get(key) || 0) + value)
  }
  const nonZeroEntries = Array.from(totals.entries()).filter(([, value]) => value > 0)
  const total = nonZeroEntries.reduce((sum, [, value]) => sum + value, 0) || 1
  return nonZeroEntries
    .sort((a, b) => b[1] - a[1])
    .map(([label, value], index) => ({
      key: label,
      label,
      value_cents: value,
      percent: Math.round((value / total) * 100),
      color: mixPalette[index % mixPalette.length],
    }))
})

const mixChartOption = computed(() => ({
  color: mixSlices.value.map((item) => item.color),
  tooltip: {
    trigger: 'item',
    formatter: (params: { name: string; value: number; percent: number }) =>
      `${params.name}<br/>Value: ${cents(params.value)} (${params.percent}%)`,
  },
  legend: { show: false },
  series: [
    {
      type: 'pie',
      radius: ['52%', '74%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      label: { show: false },
      labelLine: { show: false },
      itemStyle: {
        borderColor: '#ffffff',
        borderWidth: 2,
      },
      data: mixSlices.value.map((slice) => ({
        name: slice.label,
        value: slice.value_cents,
      })),
    },
  ],
}))

const trendScale = computed(() => {
  if (!trendSnapshots.value.length) {
    return { min: 0, max: 1 }
  }
  const maxRaw = Math.max(0, ...trendSnapshots.value.map((item) => item.value_cents))
  const paddedMax = Math.max(1, maxRaw * 1.02)
  const step = Math.max(1, Math.ceil(paddedMax / 4 / 10000) * 10000)
  return { min: 0, max: step * 4 }
})

const trendChartOption = computed(() => {
  const { min, max } = trendScale.value
  const yMin = min / 100
  const yMax = max / 100
  return {
    grid: { left: 78, right: 20, top: 14, bottom: 36 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: Array<{ axisValue: string; data: number }>) => {
        const first = params?.[0]
        if (!first) {
          return ''
        }
        return `${first.axisValue}<br/>Net Worth: ${cents(Math.round(first.data * 100))}`
      },
    },
    xAxis: {
      type: 'category',
      data: trendSnapshots.value.map((item) => item.label),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#94a3b8' } },
      axisLabel: { color: '#64748b', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      min: yMin,
      max: yMax,
      splitNumber: 4,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#94a3b8' } },
      splitLine: { lineStyle: { color: '#e2e8f0' } },
      axisLabel: {
        color: '#64748b',
        fontSize: 9,
        formatter: (value: number) => cents(Math.round(value * 100)),
      },
    },
    series: [
      {
        type: 'line',
        data: trendSnapshots.value.map((item) => item.value_cents / 100),
        showSymbol: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2.25, color: '#0f62fe' },
        itemStyle: {
          color: (params: { dataIndex: number }) =>
            trendSnapshots.value[params.dataIndex]?.forecast ? '#f59e0b' : '#0f62fe',
        },
        emphasis: { focus: 'series' },
      },
    ],
  }
})

const selectedTypeLabel = computed(() => accountTypes.find((item) => item.value === createForm.value.type)?.label)
const modalTitle = computed(() => (editingAccountId.value ? 'Edit' : 'Create'))
const submitLabel = computed(() => (editingAccountId.value ? 'Save Changes' : 'Create'))
const updateMode = computed<'dollars' | 'quantity' | 'cash_bills' | 'crypto_positions' | 'stock_positions'>(() => {
  const type = updatingAccount.value?.type || ''
  if (type === 'cash') {
    return 'cash_bills'
  }
  if (type === 'stocks_account') {
    return 'stock_positions'
  }
  if (['crypto_wallet', 'crypto_exchange'].includes(type)) {
    return 'crypto_positions'
  }
  return 'dollars'
})
const updateAmountLabel = computed(() =>
  updatingAccount.value?.type === 'crypto_exchange' ? 'USD Balance' : 'Balance',
)
const updateDescription = computed(() => {
  if (!updatingAccount.value) {
    return ''
  }
  if (updateMode.value === 'dollars') {
    return 'Update the current account balance amount.'
  }
  if (updateMode.value === 'cash_bills') {
    return 'Update bill quantities. Cash balance is calculated from bill counts.'
  }
  if (updateMode.value === 'crypto_positions') {
    return 'Update crypto tickers, quantities, and exchange rates.'
  }
  if (updateMode.value === 'stock_positions') {
    return 'Update stock tickers, quantities, and share prices.'
  }
  return 'Update the quantity for the first crypto position on this account.'
})

const HISTORY_LEFT = 50
const HISTORY_TOP = 20
const HISTORY_WIDTH = 680
const HISTORY_HEIGHT = 190

const niceCeil = (value: number) => {
  if (value <= 0) {
    return 10000
  }
  const exponent = Math.floor(Math.log10(value))
  const magnitude = 10 ** exponent
  const normalized = value / magnitude
  const nice =
    normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  return nice * magnitude
}

const historyScale = computed(() => {
  if (!historyItems.value.length) {
    return { minValue: 0, maxValue: 10000, minTime: 0, maxTime: 1 }
  }
  const values = historyItems.value.map((item) => Math.max(0, item.value_cents || 0))
  const maxValue = niceCeil(Math.max(...values) * 1.02)
  const times = historyItems.value
    .map((item) => new Date(item.recorded_at).getTime())
    .filter((t) => Number.isFinite(t))
  const minTime = times.length ? Math.min(...times) : 0
  const maxTime = times.length ? Math.max(...times) : minTime + 1
  return { minValue: 0, maxValue, minTime, maxTime: Math.max(maxTime, minTime + 1) }
})

const historyChartPoints = computed(() => {
  if (!historyItems.value.length) {
    return []
  }
  const { minValue, maxValue, minTime, maxTime } = historyScale.value
  const valueSpan = Math.max(1, maxValue - minValue)
  const timeSpan = Math.max(1, maxTime - minTime)
  return historyItems.value.map((item, index) => {
    const ts = new Date(item.recorded_at).getTime()
    const x = HISTORY_LEFT + ((ts - minTime) / timeSpan) * HISTORY_WIDTH
    const y = HISTORY_TOP + ((maxValue - item.value_cents) / valueSpan) * HISTORY_HEIGHT
    return {
      key: `${item.recorded_at}-${index}`,
      x,
      y,
    }
  })
})

const historyPolyline = computed(() => historyChartPoints.value.map((p) => `${p.x},${p.y}`).join(' '))
const historyYTicks = computed(() => {
  const maxValue = historyScale.value.maxValue
  const ticks = 4
  return Array.from({ length: ticks + 1 }, (_, idx) => {
    const value = (idx / ticks) * maxValue
    const y = HISTORY_TOP + ((maxValue - value) / Math.max(1, maxValue)) * HISTORY_HEIGHT
    return { value: Math.round(value), y }
  })
})
const historyXTicks = computed(() => {
  if (!historyItems.value.length) {
    return []
  }
  const start = new Date(historyScale.value.minTime)
  const end = new Date(historyScale.value.maxTime)
  const cursor = new Date(start.getFullYear(), start.getMonth(), 1)
  const result: Array<{ key: string; x: number; label: string }> = []
  while (cursor <= end) {
    const ts = cursor.getTime()
    const x =
      HISTORY_LEFT +
      ((ts - historyScale.value.minTime) /
        Math.max(1, historyScale.value.maxTime - historyScale.value.minTime)) *
        HISTORY_WIDTH
    result.push({
      key: `${cursor.getFullYear()}-${cursor.getMonth() + 1}`,
      x,
      label: cursor.toLocaleString('en-US', { month: 'short', year: '2-digit' }),
    })
    cursor.setMonth(cursor.getMonth() + 1)
  }
  return result
})
const showLastPaymentDateField = computed(
  () =>
    updateMode.value === 'dollars' &&
    ['line_of_credit', 'credit_card', 'loan'].includes(updatingAccount.value?.type || ''),
)
const showRewardsExpirationField = computed(
  () => updateMode.value === 'dollars' && updatingAccount.value?.type === 'rewards_card',
)
const showRewardsBalanceField = computed(
  () =>
    updateMode.value === 'dollars' &&
    ['credit_card', 'rewards_card'].includes(updatingAccount.value?.type || ''),
)

const organizationOptions = computed(() => organizations.value.map((item) => item.name))

const organizationDropdownOptions = computed(() =>
  organizationOptions.value.map((value) => ({
    label: value,
    value,
  })),
)

const organizationIconByName = computed(() => {
  const map = new Map<string, string>()
  for (const item of organizations.value) {
    if (item.icon_id) {
      map.set(item.name.toLowerCase(), item.icon_id)
    }
  }
  return map
})

const organizationUrlByName = computed(() => {
  const map = new Map<string, string>()
  for (const item of organizations.value) {
    if (item.url) {
      map.set(item.name.toLowerCase(), item.url)
    }
  }
  return map
})

const last4 = (value: string) => value.slice(-4)

const cents = (value?: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format((value || 0) / 100)

const signedCents = (value: number) => {
  const formatted = cents(Math.abs(value))
  if (value > 0) {
    return `+${formatted}`
  }
  if (value < 0) {
    return `-${formatted}`
  }
  return formatted
}

const formatDollarInteger = (valueCents: number) => {
  const dollars = Math.round(valueCents / 100)
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(dollars)
}

const formatDollarRate = (valueCents: number) => {
  const sign = valueCents > 0 ? '+' : valueCents < 0 ? '-' : ''
  return `${sign}${formatDollarInteger(Math.abs(valueCents))}`
}

const formatDollarPerMonthSquared = (valueCents: number) => {
  const sign = valueCents > 0 ? '+' : valueCents < 0 ? '-' : ''
  return `${sign}${formatDollarInteger(Math.abs(valueCents))}/month²`
}

const deltaClass = (value: number) => {
  if (value > 0) {
    return 'delta-positive'
  }
  if (value < 0) {
    return 'delta-negative'
  }
  return 'delta-neutral'
}

const intOrZero = (value: unknown) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? Math.round(parsed) : 0
}

const accountRewardsCents = (account: AccountPayload) => Math.max(0, account.rewards_balance_cents || 0)

const balanceLabel = (account: AccountPayload) => {
  if (account.type === 'stocks_account') {
    const total = (account.stock_positions || []).reduce((sum, position) => {
      const qty = Number.parseFloat(position.quantity || '0')
      const price = position.last_price_cents || 0
      if (!Number.isFinite(qty)) {
        return sum
      }
      return sum + Math.round(qty * price)
    }, 0)
    return `Balance ${cents(total + (account.balance_cents || 0))}`
  }
  if (account.type === 'crypto_wallet' || account.type === 'crypto_exchange') {
    const total = (account.crypto_positions || []).reduce((sum, position) => {
      const qty = Number.parseFloat(position.quantity || '0')
      const rateCents = position.exchange_rate_cents || 0
      if (!Number.isFinite(qty)) {
        return sum
      }
      return sum + Math.round(qty * rateCents)
    }, 0)
    const usdCash = account.type === 'crypto_exchange' ? account.usd_balance_cents || 0 : 0
    return `Balance ${cents(total + usdCash)}`
  }
  if (account.type === 'cash') {
    const computed = (account.cash_bills || []).reduce((sum, bill) => sum + bill.denomination_cents * bill.quantity, 0)
    return `Balance ${cents(computed + accountRewardsCents(account))}`
  }
  if (account.type === 'credit_card') {
    return `Balance ${cents(account.balance_cents || 0)}`
  }
  return `Balance ${cents((account.balance_cents || 0) + accountRewardsCents(account))}`
}

const tableBalanceCents = (account: AccountPayload) => {
  if (account.type === 'stocks_account') {
    const total = (account.stock_positions || []).reduce((sum, position) => {
      const qty = Number.parseFloat(position.quantity || '0')
      const price = position.last_price_cents || 0
      if (!Number.isFinite(qty)) {
        return sum
      }
      return sum + Math.round(qty * price)
    }, 0)
    return total + (account.balance_cents || 0)
  }
  if (account.type === 'crypto_wallet' || account.type === 'crypto_exchange') {
    const total = (account.crypto_positions || []).reduce((sum, position) => {
      const qty = Number.parseFloat(position.quantity || '0')
      const rateCents = position.exchange_rate_cents || 0
      if (!Number.isFinite(qty)) {
        return sum
      }
      return sum + Math.round(qty * rateCents)
    }, 0)
    return total + (account.type === 'crypto_exchange' ? account.usd_balance_cents || 0 : 0)
  }
  if (account.type === 'cash') {
    return (account.cash_bills || []).reduce((sum, bill) => sum + bill.denomination_cents * bill.quantity, 0) + accountRewardsCents(account)
  }
  return (account.balance_cents || 0) + accountRewardsCents(account)
}

const localIsoDate = (value: Date) => {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const shiftDays = (base: Date, days: number) => {
  const moved = new Date(base)
  moved.setDate(moved.getDate() + days)
  return moved
}

const getNetWorthAsOf = async (asOf: Date) => {
  const snapshot = await request.get<AccountPayload[]>('/accounts', { params: { as_of_date: localIsoDate(asOf) } })
  return snapshot.reduce((sum, account) => sum + netWorthContributionCents(account), 0)
}

const buildNext30Breakdown = (
  preview: ContractRunPreviewPayload,
  contracts: ContractCalendarPayload[],
  expenses: ExpenseCalendarPayload[],
) => {
  const todayIso = localIsoDate(new Date())
  const contractsById = new Map(contracts.map((item) => [item.id, item]))
  const expensesById = new Map(expenses.map((item) => [item.id, item]))
  const accountTypeById = new Map(accounts.value.map((item) => [item.id, item.type]))
  const resolveContractLinkedType = (contract?: ContractCalendarPayload) => {
    if (!contract) {
      return undefined
    }
    if (contract.linked_account_id) {
      return accountTypeById.get(contract.linked_account_id)
    }
    if (contract.linked_wallet === 'paypal') {
      return currentUser.value?.paypal_account_id
        ? accountTypeById.get(currentUser.value.paypal_account_id)
        : undefined
    }
    if (contract.linked_wallet === 'google_pay') {
      return currentUser.value?.google_pay_account_id
        ? accountTypeById.get(currentUser.value.google_pay_account_id)
        : undefined
    }
    return undefined
  }
  const rows: Array<{ key: string; dateIso: string; label: string; netDeltaCents: number }> = []

  for (const posting of preview.postings || []) {
    const dateIso = (posting.effective_date || '').slice(0, 10)
    if (!dateIso || dateIso <= todayIso || posting.status === 'skipped') {
      continue
    }
    const contract = contractsById.get(posting.contract_id)
    const label = contract?.name || 'Contract'
    let netDelta = intOrZero(posting.delta_cents)
    if (contract?.type === 'transfer') {
      const amount = intOrZero(contract.amount_cents)
      const sourceType = contract.source_account_id ? accountTypeById.get(contract.source_account_id) : undefined
      const linkedType = resolveContractLinkedType(contract)
      const sourceSign = isLiabilityAccountType(sourceType) ? -1 : 1
      const linkedSign = isLiabilityAccountType(linkedType) ? -1 : 1
      netDelta = (-amount * sourceSign) + (amount * linkedSign)
    } else {
      const linkedType = resolveContractLinkedType(contract)
      const linkedSign = isLiabilityAccountType(linkedType) ? -1 : 1
      netDelta = intOrZero(posting.delta_cents) * linkedSign
    }
    rows.push({
      key: `contract-${posting.contract_id}-${dateIso}-${rows.length}`,
      dateIso,
      label,
      netDeltaCents: netDelta,
    })
  }

  for (const posting of preview.expense_postings || []) {
    const dateIso = (posting.effective_date || '').slice(0, 10)
    if (!dateIso || dateIso <= todayIso || posting.status === 'skipped') {
      continue
    }
    const expense = expensesById.get(posting.expense_id)
    const label = expense?.name || 'Expense'
    const accountType = accountTypeById.get(posting.account_id)
    const accountSign = isLiabilityAccountType(accountType) ? -1 : 1
    rows.push({
      key: `expense-${posting.expense_id}-${dateIso}-${rows.length}`,
      dateIso,
      label,
      netDeltaCents: intOrZero(posting.delta_cents) * accountSign,
    })
  }

  rows.sort((a, b) => (a.dateIso === b.dateIso ? a.label.localeCompare(b.label) : a.dateIso.localeCompare(b.dateIso)))
  return rows.map((row) => ({
    key: row.key,
    dateLabel: new Date(`${row.dateIso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    label: row.label,
    netDeltaCents: row.netDeltaCents,
  }))
}

const loadWidgets = async () => {
  const runToken = ++widgetRequestToken
  widgetLoading.value = true
  next30BreakdownBusy.value = true
  try {
    const anchor = parseDateOnly(forecastDate.value) || new Date()
    const next30Target = shiftDays(anchor, 30)
    const [netWorthHistory, contracts, expenses, next30Preview, next30ForecastSeries] = await Promise.all([
      request.get<NetWorthHistoryPoint[]>('/accounts/net-worth/history'),
      request.get<ContractCalendarPayload[]>('/contracts'),
      request.get<ExpenseCalendarPayload[]>('/expenses'),
      request.post<ContractRunPreviewPayload>('/contracts/run', undefined, {
        params: { dry_run: true, through_date: localIsoDate(next30Target) },
      }),
      request.get<NetWorthForecastPoint[]>('/accounts/net-worth/forecast', {
        params: { through_date: localIsoDate(next30Target) },
      }),
    ])
    const forecastSeries =
      anchor.getTime() > Date.now()
        ? await request.get<NetWorthForecastPoint[]>('/accounts/net-worth/forecast', {
            params: { through_date: localIsoDate(anchor) },
          })
        : []
    if (runToken !== widgetRequestToken) {
      return
    }
    const historyPoints = [...netWorthHistory]
      .map((item) => ({ at: parseDateOnly(item.snapshot_date), value: intOrZero(item.value_cents) }))
      .filter((item): item is { at: Date; value: number } => item.at !== null)
      .sort((a, b) => a.at.getTime() - b.at.getTime())
    const lookupHistoryAsOf = (target: Date) => {
      let found: number | null = null
      for (const point of historyPoints) {
        if (point.at.getTime() <= target.getTime()) {
          found = point.value
        } else {
          break
        }
      }
      return found
    }
    const anchorFromHistory = lookupHistoryAsOf(anchor)
    const pastAnchorFromHistory = lookupHistoryAsOf(shiftDays(anchor, -30))

    hasPast30SnapshotData.value = anchorFromHistory !== null && pastAnchorFromHistory !== null
    netWorthAnchorCents.value = anchorFromHistory ?? currentNetWorthCents.value
    netWorthPast30Cents.value = pastAnchorFromHistory ?? netWorthAnchorCents.value
    netWorthNext30Cents.value = next30ForecastSeries.length
      ? intOrZero(next30ForecastSeries[next30ForecastSeries.length - 1].value_cents)
      : netWorthAnchorCents.value
    next30BreakdownItems.value = buildNext30Breakdown(next30Preview, contracts, expenses)

    const accountTypeById = new Map(accounts.value.map((item) => [item.id, item.type]))
    const resolveContractLinkedType = (contract: ContractCalendarPayload) => {
      if (contract.linked_account_id) {
        return accountTypeById.get(contract.linked_account_id)
      }
      if (contract.linked_wallet === 'paypal') {
        return currentUser.value?.paypal_account_id
          ? accountTypeById.get(currentUser.value.paypal_account_id)
          : undefined
      }
      if (contract.linked_wallet === 'google_pay') {
        return currentUser.value?.google_pay_account_id
          ? accountTypeById.get(currentUser.value.google_pay_account_id)
          : undefined
      }
      return undefined
    }
    const projectedAnnualCents =
      contracts.reduce((sum, contract) => {
        const annualOccurrences = annualOccurrencesFromRecurring(contract.payment_period, contract.payment_day)
        if (contract.type === 'transfer') {
          const amount = intOrZero(contract.amount_cents)
          const sourceType = contract.source_account_id ? accountTypeById.get(contract.source_account_id) : undefined
          const linkedType = resolveContractLinkedType(contract)
          const sourceSign = isLiabilityAccountType(sourceType) ? -1 : 1
          const linkedSign = isLiabilityAccountType(linkedType) ? -1 : 1
          return sum + ((-amount * sourceSign) + (amount * linkedSign)) * annualOccurrences
        }
        const linkedType = resolveContractLinkedType(contract)
        const linkedSign = isLiabilityAccountType(linkedType) ? -1 : 1
        const rawDelta = contract.type === 'income' ? intOrZero(contract.amount_cents) : -intOrZero(contract.amount_cents)
        const accountDelta = isLiabilityAccountType(linkedType) ? -rawDelta : rawDelta
        return sum + accountDelta * linkedSign * annualOccurrences
      }, 0) -
      expenses.reduce((sum, expense) => {
        if (expense.enabled === false) {
          return sum
        }
        const annualOccurrences = annualOccurrencesFromRecurring(expense.general_frequency)
        return sum + expense.estimated_amount_cents * annualOccurrences
      }, 0)
    projectedNetWorthDailyRateCents.value = Math.round(projectedAnnualCents / 365)

    const sortedHistory = [...netWorthHistory]
      .map((item) => ({ value_cents: item.value_cents, at: new Date(`${item.snapshot_date}T00:00:00`) }))
      .filter((item) => !Number.isNaN(item.at.getTime()))
      .sort((a, b) => a.at.getTime() - b.at.getTime())
    if (sortedHistory.length >= 2) {
      const end = sortedHistory[sortedHistory.length - 1].at
      const startCutoff = shiftDays(end, -365)
      const windowed = sortedHistory.filter((item) => item.at >= startCutoff)
      const first = windowed[0]
      const last = windowed[windowed.length - 1]
      const spanDays = Math.max(1, (last.at.getTime() - first.at.getTime()) / (1000 * 60 * 60 * 24))
      historicalWindowWeeks.value = Math.min(52, Math.max(1, Math.floor(spanDays / 7)))
      historicalNetWorthDailyRateCents.value = Math.round((last.value_cents - first.value_cents) / spanDays)

      if (windowed.length >= 4) {
        const midIndex = Math.floor(windowed.length / 2)
        const firstHalf = windowed.slice(0, midIndex + 1)
        const secondHalf = windowed.slice(midIndex)
        const fhStart = firstHalf[0]
        const fhEnd = firstHalf[firstHalf.length - 1]
        const shStart = secondHalf[0]
        const shEnd = secondHalf[secondHalf.length - 1]
        const firstHalfDays = Math.max(1, (fhEnd.at.getTime() - fhStart.at.getTime()) / (1000 * 60 * 60 * 24))
        const secondHalfDays = Math.max(1, (shEnd.at.getTime() - shStart.at.getTime()) / (1000 * 60 * 60 * 24))
        const slope1 = (fhEnd.value_cents - fhStart.value_cents) / firstHalfDays
        const slope2 = (shEnd.value_cents - shStart.value_cents) / secondHalfDays
        const mid1 = (fhStart.at.getTime() + fhEnd.at.getTime()) / 2
        const mid2 = (shStart.at.getTime() + shEnd.at.getTime()) / 2
        const slopeSpanDays = Math.max(1, (mid2 - mid1) / (1000 * 60 * 60 * 24))
        const accelerationPerDay2 = (slope2 - slope1) / slopeSpanDays
        const daysPerMonth = 365 / 12
        historicalAccelerationCentsPerMonth2.value = Math.round(accelerationPerDay2 * daysPerMonth * daysPerMonth)
      } else {
        historicalAccelerationCentsPerMonth2.value = 0
      }
    } else {
      historicalNetWorthDailyRateCents.value = 0
      historicalAccelerationCentsPerMonth2.value = 0
      historicalWindowWeeks.value = 0
    }

    const byMonth = new Map<string, { date: Date; value_cents: number }>()
    for (const point of netWorthHistory) {
      const date = new Date(`${point.snapshot_date}T00:00:00`)
      if (Number.isNaN(date.getTime())) {
        continue
      }
      const monthKey = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`
      byMonth.set(monthKey, { date, value_cents: point.value_cents })
    }
    const historical = Array.from(byMonth.values())
      .sort((a, b) => a.date.getTime() - b.date.getTime())
      .map((entry) => ({
        key: localIsoDate(entry.date),
        label: entry.date.toLocaleString('en-US', { month: 'short', year: '2-digit' }),
        value_cents: entry.value_cents,
        forecast: false,
      }))

    if (forecastSeries.length) {
      const byDay = new Map<string, { key: string; label: string; value_cents: number; forecast: boolean }>()
      for (const point of historical) {
        byDay.set(point.key, point)
      }
      for (const point of forecastSeries) {
        const parsed = new Date(`${point.snapshot_date}T00:00:00`)
        if (Number.isNaN(parsed.getTime())) {
          continue
        }
        const key = localIsoDate(parsed)
        const isFuture = parsed.getTime() > Date.now()
        byDay.set(key, {
          key,
          label: parsed.toLocaleString('en-US', { month: 'short', day: 'numeric' }),
          value_cents: point.value_cents,
          forecast: isFuture,
        })
      }
      trendSnapshots.value = Array.from(byDay.values()).sort((a, b) => new Date(a.key).getTime() - new Date(b.key).getTime())
      return
    }
    trendSnapshots.value = historical
  } finally {
    if (runToken === widgetRequestToken) {
      widgetLoading.value = false
      next30BreakdownBusy.value = false
    }
  }
}

const balanceTone = (account: AccountPayload, sectionKey: string) => {
  const amountCents = tableBalanceCents(account)
  if (amountCents === 0) {
    return 'delta-neutral'
  }
  if (['credit_cards', 'payables'].includes(sectionKey)) {
    return 'delta-negative'
  }
  return 'delta-positive'
}

const parseDateOnly = (raw?: string) => {
  if (!raw) {
    return null
  }
  const parsed = new Date(`${raw.slice(0, 10)}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }
  parsed.setHours(0, 0, 0, 0)
  return parsed
}

const startOfDay = (value: Date) => {
  const next = new Date(value)
  next.setHours(0, 0, 0, 0)
  return next
}

const startOfMonth = (value: Date) => new Date(value.getFullYear(), value.getMonth(), 1)

const addDays = (value: Date, days: number) => {
  const next = new Date(value)
  next.setDate(next.getDate() + days)
  return next
}

const parseRecurringPayload = (raw?: string) => {
  const trimmed = (raw || '').trim()
  if (!trimmed || !trimmed.startsWith('{')) {
    return null
  }
  try {
    return JSON.parse(trimmed) as Record<string, unknown>
  } catch {
    return null
  }
}

const annualOccurrencesFromRecurring = (raw?: string, fallbackDay?: number) => {
  const trimmed = (raw || '').trim()
  if (!trimmed) {
    return fallbackDay ? 12 : 0
  }
  const legacy = trimmed.toLowerCase()
  if (legacy === 'daily') {
    return 365
  }
  if (legacy === 'weekly') {
    return 52
  }
  if (legacy === 'biweekly') {
    return 26
  }
  if (legacy === 'monthly') {
    return 12
  }
  if (legacy === 'yearly') {
    return 1
  }
  const payload = parseRecurringPayload(trimmed)
  const kind = String(payload?.kind || '')
  if (kind === 'monthly_day' || kind === 'monthly_last_day') {
    return 12
  }
  if (kind === 'twice_monthly' || kind === 'semimonthly_days') {
    return 24
  }
  if (kind === 'yearly_month_day') {
    return 1
  }
  if (kind === 'every_n_months_day') {
    const intervalMonths = Math.max(1, Number(payload?.interval_months || 1))
    return 12 / intervalMonths
  }
  if (kind === 'every_n_years_month_day') {
    const intervalYears = Math.max(1, Number(payload?.interval_years || 1))
    return 1 / intervalYears
  }
  if (kind === 'weekly_weekday') {
    return 52
  }
  if (kind === 'biweekly_weekday') {
    return 26
  }
  if (kind === 'every_n_weeks_weekday') {
    const intervalWeeks = Math.max(1, Number(payload?.interval_weeks || 1))
    return 52 / intervalWeeks
  }
  if (kind === 'daily_weekdays') {
    if (Array.isArray(payload?.weekdays) && payload.weekdays.length) {
      return payload.weekdays.length * 52
    }
    return 5 * 52
  }
  return fallbackDay ? 12 : 0
}

const rateRowsFromDailyCents = (dailyCents: number): RateRow[] => {
  const multipliers: Array<{ key: string; label: string; multiplier: number }> = [
    { key: 'year', label: 'Per Year', multiplier: 365 },
    { key: 'month', label: 'Per Month', multiplier: 365 / 12 },
    { key: 'week', label: 'Per Week', multiplier: 7 },
    { key: 'day', label: 'Per Day', multiplier: 1 },
  ]
  return multipliers.map((item) => ({
    key: item.key,
    label: item.label,
    valueCents: Math.round(dailyCents * item.multiplier),
  }))
}

const monthLastDay = (year: number, monthZeroBased: number) => new Date(year, monthZeroBased + 1, 0).getDate()

const monthlyRecurringDate = (year: number, monthZeroBased: number, day: number) => {
  const safeDay = Math.min(Math.max(day, 1), monthLastDay(year, monthZeroBased))
  const value = new Date(year, monthZeroBased, safeDay)
  value.setHours(0, 0, 0, 0)
  return value
}

const addMonthsRecurring = (value: Date, months: number, day: number) =>
  monthlyRecurringDate(value.getFullYear(), value.getMonth() + months, day)

const recurringOnOrAfter = (
  anchor: Date,
  kind: string,
  payload: Record<string, unknown> | null,
  fallbackDay: number,
) => {
  const dayFromFallback = fallbackDay || 1
  const day = Number(payload?.day ?? dayFromFallback)
  if (kind === 'monthly_day') {
    const thisMonth = monthlyRecurringDate(anchor.getFullYear(), anchor.getMonth(), day)
    return thisMonth >= anchor ? thisMonth : monthlyRecurringDate(anchor.getFullYear(), anchor.getMonth() + 1, day)
  }
  if (kind === 'monthly_last_day') {
    const thisMonth = monthlyRecurringDate(anchor.getFullYear(), anchor.getMonth(), 31)
    return thisMonth >= anchor ? thisMonth : monthlyRecurringDate(anchor.getFullYear(), anchor.getMonth() + 1, 31)
  }
  if (kind === 'twice_monthly') {
    const d1 = Number(payload?.day_1 ?? 1)
    const d2 = Number(payload?.day_2 ?? 15)
    const days = [d1, d2].sort((a, b) => a - b)
    for (const d of days) {
      const candidate = monthlyRecurringDate(anchor.getFullYear(), anchor.getMonth(), d)
      if (candidate >= anchor) {
        return candidate
      }
    }
    return monthlyRecurringDate(anchor.getFullYear(), anchor.getMonth() + 1, days[0])
  }
  if (kind === 'yearly_month_day') {
    const month = Math.max(1, Math.min(12, Number(payload?.month ?? 1))) - 1
    const thisYear = monthlyRecurringDate(anchor.getFullYear(), month, day)
    return thisYear >= anchor ? thisYear : monthlyRecurringDate(anchor.getFullYear() + 1, month, day)
  }
  if (kind === 'every_n_months_day') {
    const intervalMonths = Math.max(1, Number(payload?.interval_months ?? 1))
    const startRaw = String(payload?.start_date || '')
    const startDate = startRaw ? startOfDay(new Date(`${startRaw}T00:00:00`)) : anchor
    let candidate = monthlyRecurringDate(startDate.getFullYear(), startDate.getMonth(), day)
    let guard = 0
    while (candidate < anchor && guard < 2400) {
      candidate = addMonthsRecurring(candidate, intervalMonths, day)
      guard += 1
    }
    return candidate
  }
  if (kind === 'every_n_years_month_day') {
    const intervalYears = Math.max(1, Number(payload?.interval_years ?? 1))
    const month = Math.max(1, Math.min(12, Number(payload?.month ?? 1))) - 1
    const startRaw = String(payload?.start_date || '')
    const startDate = startRaw ? startOfDay(new Date(`${startRaw}T00:00:00`)) : anchor
    let year = startDate.getFullYear()
    let candidate = monthlyRecurringDate(year, month, day)
    let guard = 0
    while (candidate < anchor && guard < 400) {
      year += intervalYears
      candidate = monthlyRecurringDate(year, month, day)
      guard += 1
    }
    return candidate
  }
  if (kind === 'daily_weekdays') {
    const weekdays = Array.isArray(payload?.weekdays) && payload?.weekdays.length ? (payload.weekdays as number[]) : [0, 1, 2, 3, 4]
    const allowed = new Set(weekdays)
    const probe = new Date(anchor)
    while (!allowed.has(probe.getDay() === 0 ? 6 : probe.getDay() - 1)) {
      probe.setDate(probe.getDate() + 1)
    }
    probe.setHours(0, 0, 0, 0)
    return probe
  }
  if (kind === 'weekly_weekday') {
    const weekday = Math.max(0, Math.min(6, Number(payload?.weekday ?? 0)))
    const jsWeekday = weekday === 6 ? 0 : weekday + 1
    const delta = (jsWeekday - anchor.getDay() + 7) % 7
    return addDays(anchor, delta)
  }
  if (kind === 'biweekly_weekday') {
    const weekday = Math.max(0, Math.min(6, Number(payload?.weekday ?? 0)))
    const jsWeekday = weekday === 6 ? 0 : weekday + 1
    const startRaw = String(payload?.start_date || '')
    const startDate = startRaw ? startOfDay(new Date(`${startRaw}T00:00:00`)) : anchor
    const base = new Date(startDate)
    const baseDelta = (jsWeekday - base.getDay() + 7) % 7
    base.setDate(base.getDate() + baseDelta)
    if (anchor <= base) {
      return startOfDay(base)
    }
    const daysSince = Math.floor((anchor.getTime() - base.getTime()) / (1000 * 60 * 60 * 24))
    const periods = Math.ceil(daysSince / 14)
    const result = new Date(base)
    result.setDate(result.getDate() + periods * 14)
    return startOfDay(result)
  }
  if (kind === 'every_n_weeks_weekday') {
    const weekday = Math.max(0, Math.min(6, Number(payload?.weekday ?? 0)))
    const intervalWeeks = Math.max(1, Number(payload?.interval_weeks ?? 1))
    const jsWeekday = weekday === 6 ? 0 : weekday + 1
    const startRaw = String(payload?.start_date || '')
    const startDate = startRaw ? startOfDay(new Date(`${startRaw}T00:00:00`)) : anchor
    const base = new Date(startDate)
    const baseDelta = (jsWeekday - base.getDay() + 7) % 7
    base.setDate(base.getDate() + baseDelta)
    if (anchor <= base) {
      return startOfDay(base)
    }
    const intervalDays = intervalWeeks * 7
    const daysSince = Math.floor((anchor.getTime() - base.getTime()) / (1000 * 60 * 60 * 24))
    const periods = Math.ceil(daysSince / intervalDays)
    const result = new Date(base)
    result.setDate(result.getDate() + periods * intervalDays)
    return startOfDay(result)
  }
  return null
}

const recurringNext = (
  current: Date,
  kind: string,
  payload: Record<string, unknown> | null,
  fallbackDay: number,
) => recurringOnOrAfter(addDays(current, 1), kind, payload, fallbackDay)

const recurringOccurrencesInMonth = (
  monthStart: Date,
  monthEnd: Date,
  kind: string,
  payload: Record<string, unknown> | null,
  fallbackDay: number,
) => {
  const results: Date[] = []
  let previousIso = ''
  let next = recurringOnOrAfter(monthStart, kind, payload, fallbackDay)
  let guard = 0
  while (next && next <= monthEnd && guard < 120) {
    const nextIso = formatCalendarDateIso(next)
    if (nextIso === previousIso) {
      break
    }
    results.push(next)
    previousIso = nextIso
    next = recurringNext(next, kind, payload, fallbackDay)
    guard += 1
  }
  return results
}

const calendarMonthLabel = computed(() =>
  calendarMonthAnchor.value.toLocaleDateString('en-US', { month: 'long', year: 'numeric' }),
)

const calendarWeekdayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const formatCalendarDateIso = (value: Date) => {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const monthStart = computed(() => startOfMonth(calendarMonthAnchor.value))
const monthEnd = computed(() => {
  const value = new Date(calendarMonthAnchor.value.getFullYear(), calendarMonthAnchor.value.getMonth() + 1, 0)
  value.setHours(0, 0, 0, 0)
  return value
})
const calendarGridStart = computed(() => addDays(monthStart.value, -monthStart.value.getDay()))
const calendarGridEnd = computed(() => addDays(calendarGridStart.value, 41))

const calendarEvents = computed<CalendarEventItem[]>(() => {
  const items: CalendarEventItem[] = []
  for (const account of accounts.value) {
    if (account.closed) {
      continue
    }
    if ((account.fee_amount_cents || 0) <= 0 || !account.fee_period?.trim()) {
      continue
    }
    const payload = parseRecurringPayload(account.fee_period)
    const kind = String(payload?.kind || '')
    if (!kind) {
      continue
    }
    const dates = recurringOccurrencesInMonth(calendarGridStart.value, calendarGridEnd.value, kind, payload, 1)
    for (const date of dates) {
      const dateIso = formatCalendarDateIso(date)
      items.push({
        key: `fee-${account.id}-${dateIso}`,
        kind: 'fee',
        kindLabel: 'Fee',
        sourceId: account.id,
        title: `${account.name} fee`,
        label: `${account.name} fee`,
        dateIso,
        dateLabel: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
        signedAmountCents: -Math.abs(account.fee_amount_cents || 0),
      })
    }
  }

  for (const contract of calendarContracts.value) {
    const payload = parseRecurringPayload(contract.payment_period)
    const kind = String(payload?.kind || (contract.payment_day ? 'monthly_day' : ''))
    if (!kind) {
      continue
    }
    const dates = recurringOccurrencesInMonth(
      calendarGridStart.value,
      calendarGridEnd.value,
      kind,
      payload,
      contract.payment_day || 1,
    )
    for (const date of dates) {
      const dateIso = formatCalendarDateIso(date)
      if (contract.expiration_date && contract.expiration_date.slice(0, 10) < dateIso) {
        continue
      }
      items.push({
        key: `contract-${contract.id}-${dateIso}`,
        kind: 'contract',
        kindLabel: 'Contract',
        sourceId: contract.id,
        title: contract.name,
        label: contract.name,
        dateIso,
        dateLabel: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
        signedAmountCents:
          contract.type === 'income'
            ? Math.abs(contract.amount_cents || 0)
            : contract.type === 'payment'
              ? -Math.abs(contract.amount_cents || 0)
              : 0,
      })
    }
  }

  for (const expense of calendarExpenses.value) {
    const raw = expense.next_expensed_date?.slice(0, 10)
    if (!raw || raw < formatCalendarDateIso(calendarGridStart.value) || raw > formatCalendarDateIso(calendarGridEnd.value)) {
      continue
    }
    const parsed = new Date(`${raw}T00:00:00`)
    if (Number.isNaN(parsed.getTime())) {
      continue
    }
    items.push({
      key: `expense-${expense.id}-${raw}`,
      kind: 'expense',
      kindLabel: 'Expense',
      sourceId: expense.id,
      title: expense.name,
      label: expense.name,
      dateIso: raw,
      dateLabel: parsed.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
      signedAmountCents: -Math.abs(expense.estimated_amount_cents || 0),
    })
  }
  const deduped = new Map<string, CalendarEventItem>()
  for (const item of items) {
    deduped.set(`${item.kind}:${item.sourceId}:${item.dateIso}`, item)
  }
  return Array.from(deduped.values()).sort((a, b) =>
    a.dateIso === b.dateIso ? a.label.localeCompare(b.label) : a.dateIso.localeCompare(b.dateIso),
  )
})

const calendarEventsByIso = computed(() => {
  const map = new Map<string, CalendarEventItem[]>()
  for (const event of calendarEvents.value) {
    const existing = map.get(event.dateIso) || []
    existing.push(event)
    map.set(event.dateIso, existing)
  }
  return map
})

const calendarCells = computed(() => {
  const month = monthStart.value
  const firstCell = calendarGridStart.value
  const todayIso = formatCalendarDateIso(new Date())
  const cells: Array<{ key: string; dayNumber: number; inMonth: boolean; isToday: boolean; events: CalendarEventItem[] }> = []
  for (let i = 0; i < 42; i += 1) {
    const day = addDays(firstCell, i)
    const dayIso = formatCalendarDateIso(day)
    cells.push({
      key: dayIso,
      dayNumber: day.getDate(),
      inMonth: day.getMonth() === month.getMonth() && day.getFullYear() === month.getFullYear(),
      isToday: dayIso === todayIso,
      events: calendarEventsByIso.value.get(dayIso) || [],
    })
  }
  return cells
})

const calendarUpcomingEvents = computed(() => {
  const startIso = formatCalendarDateIso(monthStart.value)
  const endIso = formatCalendarDateIso(monthEnd.value)
  return calendarEvents.value.filter((event) => event.dateIso >= startIso && event.dateIso <= endIso)
})

const calendarUpcomingEventsWithRunning = computed(() => {
  let running = 0
  return calendarUpcomingEvents.value.map((event) => {
    running += event.signedAmountCents
    return {
      ...event,
      runningTotalCents: running,
    }
  })
})

const calendarEventToneClass = (event: CalendarEventItem) => {
  const amount = event.signedAmountCents || 0
  if (amount >= 50_000) {
    return 'calendar-event-chip--positive-large'
  }
  if (amount >= 0) {
    return 'calendar-event-chip--positive-small'
  }
  const abs = Math.abs(amount)
  if (abs < 20_000) {
    return 'calendar-event-chip--negative-1'
  }
  if (abs < 100_000) {
    return 'calendar-event-chip--negative-2'
  }
  return 'calendar-event-chip--negative-3'
}

const projectedRateRows = computed(() => rateRowsFromDailyCents(projectedNetWorthDailyRateCents.value))
const historicalRateRows = computed(() => rateRowsFromDailyCents(historicalNetWorthDailyRateCents.value))
const historicalWindowLabel = computed(
  () => `Using ${historicalWindowWeeks.value} week${historicalWindowWeeks.value === 1 ? '' : 's'} of history`,
)

const lastDayOfMonth = (year: number, monthZeroBased: number) => new Date(year, monthZeroBased + 1, 0).getDate()

const monthlyDate = (year: number, monthZeroBased: number, paymentDay: number) => {
  const safeDay = Math.min(Math.max(paymentDay, 1), lastDayOfMonth(year, monthZeroBased))
  const date = new Date(year, monthZeroBased, safeDay)
  date.setHours(0, 0, 0, 0)
  return date
}

const plusMonths = (base: Date, count: number, paymentDay: number) =>
  monthlyDate(base.getFullYear(), base.getMonth() + count, paymentDay)

const computePaymentDates = (account: AccountPayload) => {
  if (!['line_of_credit', 'credit_card', 'loan'].includes(account.type)) {
    return null
  }
  const paymentDay = account.payment_day || 0
  if (paymentDay <= 0) {
    return null
  }
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const scheduledThisMonth = monthlyDate(today.getFullYear(), today.getMonth(), paymentDay)
  const mostRecentScheduled = scheduledThisMonth <= today ? scheduledThisMonth : plusMonths(scheduledThisMonth, -1, paymentDay)
  let nextScheduled = scheduledThisMonth > today ? scheduledThisMonth : plusMonths(scheduledThisMonth, 1, paymentDay)

  const recorded = parseDateOnly(account.last_payment_date)
  let effectiveLast = recorded
  if (today > mostRecentScheduled && (!effectiveLast || effectiveLast < mostRecentScheduled)) {
    effectiveLast = mostRecentScheduled
  }

  // If payment was made early (after last scheduled date but before/at upcoming schedule),
  // treat upcoming schedule as already handled and move to the following cycle.
  if (recorded && recorded > mostRecentScheduled && recorded <= nextScheduled) {
    nextScheduled = plusMonths(nextScheduled, 1, paymentDay)
  }
  return { last: effectiveLast, next: nextScheduled }
}

const formatPaymentDate = (date: Date | null) => {
  if (!date) {
    return 'Unknown'
  }
  const month = date.toLocaleString('en-US', { month: 'short' })
  return `${month} ${ordinal(date.getDate())}`
}

const paymentSummary = (account: AccountPayload) => {
  const dates = computePaymentDates(account)
  if (!dates) {
    return null
  }
  return `Last pay ${formatPaymentDate(dates.last)} • Next pay ${formatPaymentDate(dates.next)}`
}

const ordinal = (value: number) => {
  const mod100 = value % 100
  if (mod100 >= 11 && mod100 <= 13) {
    return `${value}th`
  }
  const mod10 = value % 10
  const suffix = mod10 === 1 ? 'st' : mod10 === 2 ? 'nd' : mod10 === 3 ? 'rd' : 'th'
  return `${value}${suffix}`
}

const formatLastUpdate = (raw?: string) => {
  if (!raw) {
    return 'Never'
  }
  const parsed = new Date(raw)
  if (Number.isNaN(parsed.getTime())) {
    return 'Unknown'
  }
  const month = parsed.toLocaleString('en-US', { month: 'long' })
  return `${month} ${ordinal(parsed.getDate())}`
}

const lastUpdateTooltip = (account: AccountPayload) => `last update: ${formatLastUpdate(account.last_update)}`

const lastUpdateTone = (account: AccountPayload) => {
  if (!account.last_update) {
    return 'clock-stale'
  }
  const parsed = new Date(account.last_update)
  if (Number.isNaN(parsed.getTime())) {
    return 'clock-stale'
  }
  const ageDays = (Date.now() - parsed.getTime()) / (1000 * 60 * 60 * 24)
  if (ageDays < 7) {
    return 'clock-fresh'
  }
  if (ageDays < 30) {
    return 'clock-recent'
  }
  if (ageDays < 90) {
    return 'clock-aging'
  }
  return 'clock-stale'
}

const loadAccounts = async () => {
  const params = forecastDate.value ? { as_of_date: forecastDate.value } : undefined
  accounts.value = await request.get<AccountPayload[]>('/accounts', { params })
  await loadWidgets()
}

const loadCalendarSources = async () => {
  const [contracts, expenses] = await Promise.all([
    request.get<ContractCalendarPayload[]>('/contracts'),
    request.get<ExpenseCalendarPayload[]>('/expenses'),
  ])
  calendarContracts.value = contracts
  calendarExpenses.value = expenses
}

const loadOrganizations = async () => {
  organizations.value = await request.get<OrganizationSuggestion[]>('/organizations')
}

const loadIcons = async () => {
  iconChoices.value = await request.get<IconListItem[]>('/icons')
}

const iconUrl = (iconId?: string) => (iconId ? `/api/icons/${iconId}` : '')
const normalizedAccountUrl = (raw?: string) => {
  const value = (raw || '').trim()
  if (!value) {
    return '#'
  }
  if (/^https?:\/\//i.test(value)) {
    return value
  }
  return `https://${value}`
}
const generatedIconUrl = (iconType: 'Letters' | 'Gravatar', organization?: string) => {
  const seed = (organization || '').trim() || 'Organization'
  const encoded = encodeURIComponent(seed)
  return iconType === 'Letters' ? `/api/icons/lettered/${encoded}` : `/api/icons/gravatar/${encoded}`
}
const resolveIconUrl = (iconId?: string, iconType?: 'Letters' | 'Gravatar' | 'Icon', organization?: string) => {
  if (iconType === 'Letters' || iconType === 'Gravatar') {
    return generatedIconUrl(iconType, organization)
  }
  return iconUrl(iconId)
}
const accountIconUrl = (account: AccountPayload) => resolveIconUrl(account.icon_id, account.icon_type || 'Icon', account.organization)
const selectedFormIconUrl = computed(() =>
  resolveIconUrl(createForm.value.icon_id, createForm.value.icon_type, createForm.value.organization || createForm.value.name),
)

const closeCreateDialog = () => {
  createDialog.value = false
  editingAccountId.value = null
}

const openCreateDialog = (type: AccountType) => {
  createForm.value = makeCreateForm()
  createForm.value.type = type
  editingAccountId.value = null
  createDialog.value = true
}

const onAccountTypePicked = (value: string | undefined) => {
  if (!value) {
    return
  }
  openCreateDialog(value as AccountType)
}

const validateCreateForm = (): boolean => {
  if (!createForm.value.account_number?.trim()) {
    errorMessage.value = 'Account number is required'
    snackbar.value = true
    return false
  }
  if (!createForm.value.name?.trim()) {
    errorMessage.value = 'Account name is required'
    snackbar.value = true
    return false
  }
  if (!createForm.value.organization?.trim()) {
    errorMessage.value = 'Organization is required'
    snackbar.value = true
    return false
  }
  return true
}

const submitCreateAccount = async () => {
  if (!validateCreateForm()) {
    return
  }
  if (editingAccountId.value) {
    await request.put(`/accounts/${editingAccountId.value}`, createForm.value)
  } else {
    await request.post('/accounts', createForm.value)
  }
  createDialog.value = false
  editingAccountId.value = null
  await loadAccounts()
  await loadOrganizations()
  await loadIcons()
}

const openIconUploadPicker = () => {
  iconFileInput.value?.click()
}

const openIconPickerModal = () => {
  iconPickerDraftId.value = createForm.value.icon_id
  iconPickerDraftType.value = createForm.value.icon_type || 'Icon'
  iconPickerDialog.value = true
}

const cancelIconPickerModal = () => {
  iconPickerDialog.value = false
  closeIconContextMenu()
}

const acceptIconPickerModal = () => {
  createForm.value.icon_id = iconPickerDraftType.value === 'Icon' ? iconPickerDraftId.value : undefined
  createForm.value.icon_type = iconPickerDraftType.value
  iconPickerDialog.value = false
}

const selectNoIcon = () => {
  iconPickerDraftId.value = undefined
  iconPickerDraftType.value = 'Icon'
}

const selectCatalogIcon = (iconId: string) => {
  iconPickerDraftId.value = iconId
  iconPickerDraftType.value = 'Icon'
  closeIconContextMenu()
}

const selectGeneratedIcon = async (variant: 'Letters' | 'Gravatar') => {
  iconPickerDraftType.value = variant
  iconPickerDraftId.value = undefined
  closeIconContextMenu()
}

const closeIconContextMenu = () => {
  iconContextMenu.value = { open: false, x: 0, y: 0 }
}

const openIconContextMenu = (event: MouseEvent, icon: IconListItem) => {
  if (!icon.created_by_me || icon.is_default) {
    return
  }
  iconContextMenu.value = {
    open: true,
    x: event.clientX,
    y: event.clientY,
    iconId: icon.id,
  }
}

const deleteContextIcon = async () => {
  const iconId = iconContextMenu.value.iconId
  if (!iconId) {
    closeIconContextMenu()
    return
  }
  await request.delete(`/icons/${iconId}`)
  if (createForm.value.icon_id === iconId && createForm.value.icon_type === 'Icon') {
    createForm.value.icon_id = undefined
  }
  if (iconPickerDraftId.value === iconId) {
    iconPickerDraftId.value = undefined
    iconPickerDraftType.value = 'Icon'
  }
  closeIconContextMenu()
  await loadIcons()
}

const uploadAccountIcon = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) {
    return
  }
  const form = new FormData()
  form.append('file', file)
  const uploaded = await request.post<{ id: string; hash: string }>('/icons', form)
  createForm.value.icon_id = uploaded.id
  createForm.value.icon_type = 'Icon'
  iconPickerDraftId.value = uploaded.id
  iconPickerDraftType.value = 'Icon'
  await loadIcons()
  input.value = ''
}

const toggleTileMenu = (accountId: string) => {
  activeTileMenuId.value = activeTileMenuId.value === accountId ? null : accountId
}

const startEditAccount = (account: AccountPayload) => {
  activeTileMenuId.value = null
  createForm.value = {
    ...makeCreateForm(),
    ...account,
    stock_positions: account.stock_positions || [],
    crypto_positions: account.crypto_positions || [],
  }
  createForm.value.icon_type = account.icon_type || 'Icon'
  editingAccountId.value = account.id
  createDialog.value = true
}

const deleteAccount = async (accountId: string) => {
  activeTileMenuId.value = null
  pendingDeleteAccountId.value = accountId
  deleteDialog.value = true
}

const closeDeleteDialog = () => {
  deleteDialog.value = false
  pendingDeleteAccountId.value = null
}

const confirmDeleteAccount = async () => {
  if (!pendingDeleteAccountId.value) {
    return
  }
  await request.delete(`/accounts/${pendingDeleteAccountId.value}`)
  closeDeleteDialog()
  await loadAccounts()
}

const openUpdateDialog = (account: AccountPayload) => {
  activeTileMenuId.value = null
  updatingAccount.value = account
  if (account.type === 'stocks_account') {
    const positions =
      account.stock_positions?.map((position) => ({
        stock_id: position.stock_id,
        ticker: position.ticker || '',
        quantity: position.quantity || '0',
        last_price_cents: position.last_price_cents || 0,
      })) || []
    updateForm.value.stockPositions = positions
    updateForm.value.amountCents = account.balance_cents || 0
  } else if (account.type === 'crypto_wallet' || account.type === 'crypto_exchange') {
    const positions =
      account.crypto_positions?.map((position) => ({
        ticker: position.ticker || '',
        quantity: position.quantity || '0',
        exchange_rate_cents: position.exchange_rate_cents || 0,
      })) || []
    updateForm.value.cryptoPositions = positions.length
      ? positions
      : [{ ticker: '', quantity: '0', exchange_rate_cents: 0 }]
    if (account.type === 'crypto_exchange') {
      updateForm.value.amountCents = account.usd_balance_cents || 0
    }
  } else if (account.type === 'cash') {
    const nextBills: Record<number, number> = { 100: 0, 200: 0, 500: 0, 1000: 0, 2000: 0, 5000: 0, 10000: 0 }
    for (const bill of account.cash_bills || []) {
      if (bill.denomination_cents in nextBills) {
        nextBills[bill.denomination_cents] = bill.quantity
      }
    }
    updateForm.value.cashBills = nextBills
  } else {
    updateForm.value.amountCents = account.balance_cents || 0
  }
  updateForm.value.rewardsCents = account.rewards_balance_cents || 0
  updateForm.value.lastPaymentDate = account.last_payment_date?.slice(0, 10) || ''
  updateForm.value.expirationDate = account.expiration_date?.slice(0, 10) || ''
  updateDialog.value = true
}

const closeUpdateDialog = () => {
  updateDialog.value = false
  updatingAccount.value = null
}

const openHistoryDialog = async (account: AccountPayload) => {
  activeTileMenuId.value = null
  historyAccount.value = account
  historyItems.value = await request.get<AccountHistoryPoint[]>(`/accounts/${account.id}/history`)
  historyDialog.value = true
}

const closeHistoryDialog = () => {
  historyDialog.value = false
  historyAccount.value = null
  historyItems.value = []
}

const goToPreviousCalendarMonth = async () => {
  calendarMonthAnchor.value = new Date(calendarMonthAnchor.value.getFullYear(), calendarMonthAnchor.value.getMonth() - 1, 1)
  await loadCalendarSources()
}

const goToNextCalendarMonth = async () => {
  calendarMonthAnchor.value = new Date(calendarMonthAnchor.value.getFullYear(), calendarMonthAnchor.value.getMonth() + 1, 1)
  await loadCalendarSources()
}

const openCalendarEvent = (event: CalendarEventItem) => {
  selectedCalendarEvent.value = event
  calendarEventDialogOpen.value = true
}

const closeCalendarEventDialog = () => {
  calendarEventDialogOpen.value = false
  selectedCalendarEvent.value = null
}

const runCalendarEventAction = async (action: CalendarEventAction) => {
  if (!selectedCalendarEvent.value) {
    return
  }
  const event = selectedCalendarEvent.value
  closeCalendarEventDialog()
  if (event.kind === 'fee') {
    const account = accounts.value.find((item) => item.id === event.sourceId)
    if (!account) {
      return
    }
    activeTab.value = 'accounts'
    if (action === 'edit') {
      startEditAccount(account)
    } else {
      openUpdateDialog(account)
    }
    return
  }
  if (event.kind === 'contract') {
    activeTab.value = 'contracts'
    await nextTick()
    await contractsTabRef.value?.openFromCalendar(event.sourceId, action)
    return
  }
  activeTab.value = 'expenses'
  await nextTick()
  await expensesTabRef.value?.openFromCalendar(event.sourceId, action)
}

const isValidQuantity = (value: string) => /^-?\d+(\.\d+)?$/.test(value.trim())

const addCryptoPosition = () => {
  updateForm.value.cryptoPositions.push({ ticker: '', quantity: '0', exchange_rate_cents: 0 })
}

const removeCryptoPosition = (index: number) => {
  if (updateForm.value.cryptoPositions.length <= 1) {
    return
  }
  updateForm.value.cryptoPositions.splice(index, 1)
}

const addStockPosition = () => {
  updateForm.value.stockPositions.push({ ticker: '', quantity: '0', last_price_cents: 0 })
}

const removeStockPosition = (index: number) => {
  updateForm.value.stockPositions.splice(index, 1)
}

const submitUpdateValue = async () => {
  if (!updatingAccount.value) {
    return
  }
  const account = updatingAccount.value
  const payload: Record<string, unknown> = {}

  if (updateMode.value === 'dollars') {
    if (showLastPaymentDateField.value && updateForm.value.lastPaymentDate) {
      const todayIso = new Date().toISOString().slice(0, 10)
      if (updateForm.value.lastPaymentDate > todayIso) {
        errorMessage.value = 'Last payment date cannot be in the future'
        snackbar.value = true
        return
      }
    }
    if (account.type === 'crypto_exchange') {
      payload.usd_balance_cents = updateForm.value.amountCents
    } else {
      payload.balance_cents = updateForm.value.amountCents
    }
    if (showLastPaymentDateField.value) {
      payload.last_payment_date = updateForm.value.lastPaymentDate || null
    }
    if (showRewardsExpirationField.value) {
      payload.expiration_date = updateForm.value.expirationDate || null
    }
    if (showRewardsBalanceField.value) {
      payload.rewards_balance_cents = updateForm.value.rewardsCents
    }
  } else if (updateMode.value === 'cash_bills') {
    payload.cash_bills = Object.entries(updateForm.value.cashBills).map(([denomination, quantity]) => ({
      denomination_cents: Number.parseInt(denomination, 10),
      quantity: Math.max(0, Math.floor(Number(quantity) || 0)),
    }))
  } else if (updateMode.value === 'stock_positions') {
    const cleaned: Array<{ stock_id?: string; ticker: string; quantity: string; last_price_cents: number }> = []
    for (const row of updateForm.value.stockPositions) {
      const ticker = row.ticker.trim().toUpperCase()
      const quantity = row.quantity.trim()
      const price = Math.max(0, row.last_price_cents || 0)
      if (!ticker && !quantity) {
        continue
      }
      if (!ticker) {
        errorMessage.value = 'Ticker is required for each stock position'
        snackbar.value = true
        return
      }
      if (!isValidQuantity(quantity)) {
        errorMessage.value = 'Quantity must be a valid number'
        snackbar.value = true
        return
      }
      cleaned.push({
        stock_id: row.stock_id,
        ticker,
        quantity,
        last_price_cents: price,
      })
    }
    payload.stock_positions = cleaned
    payload.balance_cents = updateForm.value.amountCents
  } else if (updateMode.value === 'crypto_positions') {
    const cleaned: Array<{ ticker: string; quantity: string; exchange_rate_cents: number }> = []
    for (const row of updateForm.value.cryptoPositions) {
      const ticker = row.ticker.trim().toUpperCase()
      const quantity = row.quantity.trim()
      const rate = Math.max(0, row.exchange_rate_cents || 0)
      if (!ticker && !quantity) {
        continue
      }
      if (!ticker) {
        errorMessage.value = 'Ticker is required for each crypto position'
        snackbar.value = true
        return
      }
      if (!isValidQuantity(quantity)) {
        errorMessage.value = 'Quantity must be a valid number'
        snackbar.value = true
        return
      }
      cleaned.push({ ticker, quantity, exchange_rate_cents: rate })
    }
    payload.crypto_positions = cleaned
    if (account.type === 'crypto_exchange') {
      payload.usd_balance_cents = updateForm.value.amountCents
    }
  }

  await request.put(`/accounts/${account.id}/value`, payload)
  closeUpdateDialog()
  await loadAccounts()
}

const moveAccountLeft = async (section: Section, index: number, event?: MouseEvent) => {
  ;(event?.currentTarget as HTMLButtonElement | null)?.blur()
  if (index <= 0) {
    return
  }
  const current = section.accounts[index]
  const left = section.accounts[index - 1]
  const leftOfLeft = section.accounts[index - 2]
  const newRank = leftOfLeft ? (left.rank + leftOfLeft.rank) / 2 : left.rank + 1
  await request.put(`/accounts/${current.id}/rank`, { rank: newRank })
  await loadAccounts()
}

const moveAccountRight = async (section: Section, index: number, event?: MouseEvent) => {
  ;(event?.currentTarget as HTMLButtonElement | null)?.blur()
  if (index >= section.accounts.length - 1) {
    return
  }
  const current = section.accounts[index]
  const right = section.accounts[index + 1]
  const rightOfRight = section.accounts[index + 2]
  const newRank = rightOfRight ? (right.rank + rightOfRight.rank) / 2 : right.rank - 1
  await request.put(`/accounts/${current.id}/rank`, { rank: newRank })
  await loadAccounts()
}

const onWindowClick = (event: MouseEvent) => {
  const target = event.target as Node
  if (activeTileMenuId.value) {
    const tileMenu = document.querySelector('.tile-menu')
    const tileMenuTrigger = document.querySelector('.tile-menu-trigger')
    if (tileMenu?.contains(target) || tileMenuTrigger?.contains(target)) {
      return
    }
    activeTileMenuId.value = null
  }
  if (iconContextMenu.value.open) {
    const iconMenu = document.querySelector('.icon-context-menu')
    if (iconMenu && iconMenu.contains(target)) {
      return
    }
    closeIconContextMenu()
  }
  if (showForecastControls.value) {
    const forecastPopover = document.querySelector('.forecast-popover-wrap')
    if (!forecastPopover?.contains(target)) {
      showForecastControls.value = false
    }
  }
}

const onWindowKeyDown = (event: KeyboardEvent) => {
  if (event.key !== 'Escape') {
    return
  }
  if (iconPickerDialog.value) {
    cancelIconPickerModal()
    return
  }
  if (calendarEventDialogOpen.value) {
    closeCalendarEventDialog()
    return
  }
  if (historyDialog.value) {
    closeHistoryDialog()
    return
  }
  if (updateDialog.value) {
    closeUpdateDialog()
    return
  }
  if (deleteDialog.value) {
    closeDeleteDialog()
    return
  }
  if (createDialog.value) {
    closeCreateDialog()
  }
}

const clearForecastDate = () => {
  forecastDate.value = ''
}

onMounted(loadAccounts)
onMounted(loadOrganizations)
onMounted(loadIcons)
onMounted(loadCalendarSources)
onMounted(async () => {
  window.addEventListener('click', onWindowClick)
  window.addEventListener('keydown', onWindowKeyDown)
})
onUnmounted(() => {
  window.removeEventListener('click', onWindowClick)
  window.removeEventListener('keydown', onWindowKeyDown)
})

watch(
  () => forecastDate.value,
  async () => {
    const anchor = parseDateOnly(forecastDate.value) || new Date()
    calendarMonthAnchor.value = startOfMonth(anchor)
    await loadAccounts()
  },
)

watch(
  () => activeTab.value,
  async (next) => {
    if (next === 'calendar') {
      await loadCalendarSources()
    }
  },
)

watch(
  () => createForm.value.organization,
  (next) => {
    if (createForm.value.icon_type !== 'Icon') {
      return
    }
    const key = next?.trim().toLowerCase()
    if (!key) {
      return
    }
    const iconId = organizationIconByName.value.get(key)
    if (iconId) {
      createForm.value.icon_id = iconId
      createForm.value.icon_type = 'Icon'
    }
    const orgUrl = organizationUrlByName.value.get(key)
    if (orgUrl) {
      createForm.value.url = orgUrl
    }
  },
)

watch(
  () => createForm.value.fee_amount_cents,
  (next) => {
    if ((next || 0) === 0) {
      createForm.value.fee_period = undefined
    }
  },
)
</script>

<style scoped>
@import './sharedTile.css';

.dashboard {
  max-width: 1320px;
  margin: 0 auto;
  padding: 1.25rem;
}

.widgets {
  margin-bottom: 1.25rem;
}

.widget-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0.45rem;
}

.forecast-popover-wrap {
  position: relative;
}

.forecast-popover {
  position: absolute;
  top: calc(100% + 0.4rem);
  right: 0;
  z-index: 30;
  min-width: 330px;
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.16);
  padding: 0.75rem;
}

.widget-forecast-toggle {
  min-height: 2rem;
  padding-inline: 0.6rem;
}

.top-controls {
  margin-top: 0.75rem;
  margin-bottom: 0.7rem;
}

.table-toolbar-row {
  display: flex;
  align-items: stretch;
  gap: 0.75rem;
  margin-bottom: 0.35rem;
}

.table-toolbar-row :deep(.toolbar-shell) {
  flex: 1;
}

.forecast-row {
  display: flex;
  align-items: end;
  gap: 0.6rem;
  max-width: 420px;
}

.widget-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.widget-slot {
  border: 1px solid var(--cds-border-subtle-01);
  background: #fff;
}

.widget-card {
  padding: 0.9rem;
}

.widget-card h3 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}

.widget-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.45rem;
}

.widget-card-head h3 {
  margin: 0;
}

.widget-card-hint {
  font-size: 0.72rem;
  color: var(--cds-text-secondary);
  white-space: nowrap;
}

.widget-subtext {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
  color: var(--cds-text-secondary);
}

.widget-kpi {
  font-size: 1.6rem;
  font-weight: 700;
}

.delta-positive {
  color: #047857;
}

.delta-negative {
  color: #b91c1c;
}

.delta-neutral {
  color: #334155;
}

.delta-muted {
  color: #64748b;
}

.widget-donut-row {
  min-height: 146px;
}

.widget-donut-echart {
  width: 100%;
  height: 146px;
}

.widget-trend {
  margin-top: 12px;
}

.widget-trend-head {
  margin-bottom: 2px;
}

.widget-trend-title {
  margin: 0;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.widget-card--wide {
  padding-bottom: 0.55rem;
}

.widget-trend-echart {
  width: 100%;
  height: 190px;
}

.widget-trend-status {
  font-size: 0.8rem;
  color: #475569;
  white-space: nowrap;
  font-weight: 500;
}

.widget-kpi-hover-wrap {
  position: relative;
  display: inline-block;
}

.widget-kpi-popout {
  position: absolute;
  left: 0;
  top: 100%;
  width: min(440px, 75vw);
  max-height: 230px;
  overflow: auto;
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.2);
  border-radius: 6px;
  padding: 8px 10px;
  z-index: 18;
}

.widget-kpi-popout-title {
  font-size: 0.74rem;
  font-weight: 700;
  margin-bottom: 5px;
  color: var(--cds-text-secondary);
}

.widget-kpi-popout-empty {
  font-size: 0.72rem;
  color: var(--cds-text-secondary);
}

.widget-kpi-popout-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
}

.widget-kpi-popout-list li {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  font-size: 0.72rem;
}

.widget-kpi-popout-list li span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.widget-derived-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 12px;
}

.widget-rate-list {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
  display: grid;
  gap: 6px;
}

.widget-rate-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 0.84rem;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.34);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 100;
}

.modal-card {
  width: min(820px, 100%);
  max-height: 90vh;
  overflow: auto;
  padding: 1rem;
}

.confirm-card {
  width: min(460px, 100%);
  padding: 1rem;
}

.confirm-card--wide {
  width: min(1080px, 100%);
}

.confirm-card h3 {
  margin: 0 0 0.5rem;
}

.confirm-card p {
  margin: 0 0 0.75rem;
  color: var(--cds-text-secondary);
}

.history-chart-wrap {
  border: 1px solid var(--cds-border-subtle-01);
  background: #fff;
  min-height: 260px;
  position: relative;
  overflow: hidden;
}

.history-chart {
  width: 100%;
  height: 260px;
  display: block;
}

.history-axis {
  stroke: #94a3b8;
  stroke-width: 1;
}

.history-grid {
  stroke: #e2e8f0;
  stroke-width: 1;
}

.history-grid--vertical {
  stroke-dasharray: 2 4;
}

.history-line {
  fill: none;
  stroke: #0f62fe;
  stroke-width: 2.5;
}

.history-dot {
  fill: #0f62fe;
}

.history-y-label,
.history-x-label {
  fill: #64748b;
  font-size: 10px;
}

.history-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--cds-text-secondary);
}

.table-actions-cell {
  position: relative;
  width: 1%;
}

.table-overflow-menu {
  position: relative;
  display: inline-flex;
}

.table-menu-trigger {
  min-width: 1.5rem;
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 4px;
  background: transparent;
  color: #161616;
  font-size: 1rem;
}

.table-menu-list {
  right: 0;
  left: auto;
  min-width: 9rem;
}

.table-icon-cell {
  width: 1%;
}

.table-icon {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid var(--cds-border-subtle-01);
  object-fit: cover;
}

.table-icon--empty {
  background: #e2e8f0;
}

.sort-btn {
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
  padding: 0;
}

.modal-card h3 {
  margin-top: 0;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.fee-row {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.field-row {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.field-row-inline {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.notes-field {
  grid-column: 1 / -1;
}

.cash-bills-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.crypto-positions-editor {
  display: grid;
  gap: 10px;
}

.crypto-usd-balance {
  max-width: 360px;
}

.crypto-position-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.1fr) minmax(260px, 1.6fr) minmax(220px, 1.2fr) auto;
  gap: 10px;
  align-items: end;
  min-width: 0;
}

.crypto-remove-btn {
  min-height: 2.5rem;
  white-space: nowrap;
}

.crypto-add-btn {
  justify-self: start;
}

.column-spacer {
  min-height: 1px;
}

.modal-actions {
  grid-column: 1 / -1;
  margin-top: 6px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.bank-field {
  position: relative;
}

.bank-label {
  display: block;
  margin-bottom: 6px;
  font-size: 0.75rem;
  color: var(--cds-text-secondary);
  font-weight: 600;
}

.icon-picker {
  display: flex;
  flex-direction: column;
}

.icon-picker-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.icon-choice {
  border: 1px solid var(--cds-border-subtle-01);
  background: #fff;
  border-radius: 6px;
  padding: 4px;
  cursor: pointer;
  min-height: 40px;
}

.icon-choice--selected {
  border-color: #0f62fe;
  box-shadow: 0 0 0 1px #0f62fe inset;
}

.icon-choice--none {
  min-width: 60px;
  height: 40px;
  font-size: 0.8rem;
}

.icon-upload-input {
  display: none;
}

.icon-upload-btn {
  min-height: 36px;
}

.icon-modal-card {
  width: min(760px, 100%);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  padding: 1rem;
}

.icon-modal-card h3 {
  margin: 0 0 0.75rem;
}

.generated-icon-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.icon-grid-scroll {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 320px;
  max-height: 520px;
  padding-right: 4px;
}

.icon-modal-actions {
  position: sticky;
  bottom: 0;
  margin-top: 12px;
  padding-top: 10px;
  background: #fff;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.icon-context-menu {
  position: fixed;
  z-index: 140;
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.16);
  min-width: 120px;
}

.icon-context-menu-item {
  border: 0;
  background: transparent;
  color: #b91c1c;
  width: 100%;
  text-align: left;
  padding: 0.55rem 0.7rem;
  cursor: pointer;
}

.icon-context-menu-item:hover,
.icon-context-menu-item:focus-visible {
  background: #fee2e2;
  outline: none;
}

.icon-preview {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid var(--cds-border-subtle-01);
  object-fit: cover;
}

.icon-preview--empty {
  background: #f1f5f9;
}

.calendar-panel {
  display: grid;
  gap: 14px;
}

.calendar-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.calendar-toolbar h3 {
  margin: 0;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  border: 1px solid var(--cds-border-subtle-01);
  border-bottom: 0;
}

.calendar-weekday {
  padding: 8px;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--cds-text-secondary);
  border-bottom: 1px solid var(--cds-border-subtle-01);
  border-right: 1px solid var(--cds-border-subtle-01);
}

.calendar-weekday:nth-child(7n) {
  border-right: 0;
}

.calendar-day-cell {
  min-height: 120px;
  padding: 6px;
  border-right: 1px solid var(--cds-border-subtle-01);
  border-bottom: 1px solid var(--cds-border-subtle-01);
  display: grid;
  gap: 6px;
  align-content: start;
  background: #f0f7ff;
  overflow: hidden;
}

.calendar-day-cell:nth-child(odd) {
  background: #e4f0ff;
}

.calendar-day-cell:nth-child(7n) {
  border-right: 0;
}

.calendar-day-cell--outside {
  background: #fffbea;
}

.calendar-day-cell--outside:nth-child(odd) {
  background: #fff7d6;
}

.calendar-day-cell.calendar-day-cell--today,
.calendar-day-cell.calendar-day-cell--today:nth-child(odd),
.calendar-day-cell.calendar-day-cell--today.calendar-day-cell--outside,
.calendar-day-cell.calendar-day-cell--today.calendar-day-cell--outside:nth-child(odd) {
  background: #bbf7d0;
}

.calendar-day-number {
  font-size: 0.84rem;
  font-weight: 600;
}

.calendar-day-events {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.calendar-event-chip {
  border: 0;
  border-radius: 4px;
  padding: 4px 6px;
  font-size: 0.73rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  overflow: hidden;
  text-align: left;
}

.calendar-event-chip-name {
  display: block;
  flex: 1 1 auto;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

.calendar-event-chip-amount {
  display: block;
  flex: 0 0 auto;
  margin-left: auto;
  white-space: nowrap;
  text-align: right;
}

.calendar-event-chip--positive-small {
  background: #bfdbfe;
  color: #1e3a8a;
}

.calendar-event-chip--positive-large {
  background: #86efac;
  color: #14532d;
}

.calendar-event-chip--negative-1 {
  background: #fecaca;
  color: #7f1d1d;
}

.calendar-event-chip--negative-2 {
  background: #fca5a5;
  color: #7f1d1d;
}

.calendar-event-chip--negative-3 {
  background: #ef4444;
  color: #ffffff;
}

.calendar-more-events {
  font-size: 0.72rem;
  color: var(--cds-text-secondary);
}

.calendar-upcoming {
  border-top: 1px solid var(--cds-border-subtle-01);
  padding-top: 10px;
}

.calendar-upcoming h4 {
  margin: 0 0 8px;
}

.calendar-upcoming-empty {
  color: var(--cds-text-secondary);
}

.calendar-upcoming-table-wrap {
  border: 1px solid var(--cds-border-subtle-01);
  border-radius: 6px;
  overflow: hidden;
}

.calendar-upcoming-table {
  width: 100%;
  border-collapse: collapse;
}

.calendar-upcoming-table th,
.calendar-upcoming-table td {
  border-bottom: 1px solid var(--cds-border-subtle-01);
  padding: 7px 9px;
  text-align: left;
  font-size: 0.84rem;
}

.calendar-upcoming-table th {
  background: var(--cds-layer-accent-01);
  font-weight: 600;
}

.calendar-upcoming-row {
  cursor: pointer;
}

.calendar-upcoming-row:hover {
  background: var(--cds-layer-hover);
}

.calendar-upcoming-type {
  color: var(--cds-text-secondary);
  font-size: 0.82rem;
}

.section-wrap {
  margin-bottom: 1.25rem;
}

.section-title {
  margin: 0 0 0.75rem;
}

.empty-state {
  color: var(--cds-text-secondary);
}

@media (max-width: 1200px) {
}

@media (max-width: 900px) {
  .table-toolbar-row {
    flex-wrap: wrap;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .widget-card-head {
    flex-wrap: wrap;
  }

  .widget-card-hint {
    white-space: normal;
  }

  .icon-grid-scroll {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .crypto-position-row {
    grid-template-columns: 1fr;
  }

  .calendar-grid {
    grid-template-columns: repeat(1, minmax(0, 1fr));
  }

  .calendar-weekday {
    display: none;
  }

  .calendar-day-cell {
    border-right: 0;
    min-height: 88px;
  }

  .calendar-day-cell--outside {
    display: none;
  }
}

@media (max-width: 640px) {
  .forecast-popover {
    min-width: min(330px, calc(100vw - 2.5rem));
    right: 0;
  }

  .forecast-row {
    flex-direction: column;
    align-items: stretch;
    max-width: none;
  }

  .icon-grid-scroll {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
