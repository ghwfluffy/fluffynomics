<template>
  <div class="dashboard">
    <section class="cds--tile widgets">
      <h2>Insights Widgets</h2>
      <p>Placeholder area for trend charts, cashflow graphs, and forecasting widgets.</p>
      <div class="widget-grid">
        <div class="widget-slot">Net Worth Trend</div>
        <div class="widget-slot">Budget vs Actual</div>
        <div class="widget-slot">Debt Burn Down</div>
      </div>
    </section>

    <div class="action-row">
      <button
        ref="typePickerButton"
        class="cds--btn cds--btn--primary"
        type="button"
        @click="showTypePicker = !showTypePicker"
      >
        Add New Account
      </button>
      <div v-if="showTypePicker" class="type-picker" :style="{ width: `${typePickerWidth}px` }">
        <UnifiedDropdown
          auto-open
          :scrollable="false"
          menu-only
          placeholder="Select account type"
          :options="accountTypes"
          @update:modelValue="onAccountTypePicked"
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
          <div class="tile-balance" :class="balanceTone(section.key)">
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
              <button type="button" class="tile-menu-option tile-menu-option--danger" @click="deleteAccount(account.id)">
                Delete
              </button>
            </div>
          </div>
        </article>
      </div>

      <div v-else class="cds--tile empty-state">No accounts yet.</div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { errorMessage, request, snackbar } from '@/lib/api'
import BankField from '@/components/BankField.vue'
import DollarField from '@/components/DollarField.vue'
import PercentField from '@/components/PercentField.vue'
import RecurringPeriodField from '@/components/RecurringPeriodField.vue'
import UnifiedDropdown from '@/components/UnifiedDropdown.vue'

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
  last_update?: string
  balance_cents?: number
  usd_balance_cents?: number
  stock_positions?: Array<{ stock_id?: string; ticker?: string; quantity: string; last_price_cents?: number }>
  crypto_positions?: Array<{ ticker: string; quantity: string; exchange_rate_cents?: number }>
  cash_bills?: Array<{ denomination_cents: number; quantity: number }>
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

const makeCreateForm = (): CreateAccountPayload => ({
  account_number: '',
  name: '',
  type: 'checking',
  organization: '',
  icon_type: 'Icon',
  stock_positions: [],
  crypto_positions: [],
  cash_bills: [],
})

const accounts = ref<AccountPayload[]>([])
const organizations = ref<OrganizationSuggestion[]>([])
const iconChoices = ref<IconListItem[]>([])
const createDialog = ref(false)
const createForm = ref<CreateAccountPayload>(makeCreateForm())
const editingAccountId = ref<string | null>(null)
const deleteDialog = ref(false)
const pendingDeleteAccountId = ref<string | null>(null)
const updateDialog = ref(false)
const updatingAccount = ref<AccountPayload | null>(null)
const updateForm = ref({
  amountCents: 0,
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
const showTypePicker = ref(false)
const activeTileMenuId = ref<string | null>(null)
const typePickerButton = ref<HTMLElement | null>(null)
const iconFileInput = ref<HTMLInputElement | null>(null)
const typePickerWidth = ref(220)
const iconPickerDialog = ref(false)
const iconPickerDraftId = ref<string | undefined>(undefined)
const iconPickerDraftType = ref<'Letters' | 'Gravatar' | 'Icon'>('Icon')
const iconContextMenu = ref<{ open: boolean; x: number; y: number; iconId?: string }>({
  open: false,
  x: 0,
  y: 0,
})

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

const sections = computed<Section[]>(() =>
  sectionDefinitions.map((section) => ({
    ...section,
    accounts: accounts.value.filter((account) => section.types.includes(account.type)),
  })),
)

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
const showLastPaymentDateField = computed(
  () =>
    updateMode.value === 'dollars' &&
    ['line_of_credit', 'credit_card', 'loan'].includes(updatingAccount.value?.type || ''),
)
const showRewardsExpirationField = computed(
  () => updateMode.value === 'dollars' && updatingAccount.value?.type === 'rewards_card',
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
    return `Balance ${cents(computed)}`
  }
  return `Balance ${cents(account.balance_cents)}`
}

const balanceTone = (sectionKey: string) =>
  ['credit_cards', 'payables'].includes(sectionKey) ? 'balance-liability' : 'balance-asset'

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
  accounts.value = await request.get<AccountPayload[]>('/accounts')
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

const syncTypePickerWidth = () => {
  typePickerWidth.value = typePickerButton.value?.offsetWidth || 220
}

const closeCreateDialog = () => {
  createDialog.value = false
  editingAccountId.value = null
}

const openCreateDialog = (type: AccountType) => {
  showTypePicker.value = false
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
  updateForm.value.lastPaymentDate = account.last_payment_date?.slice(0, 10) || ''
  updateForm.value.expirationDate = account.expiration_date?.slice(0, 10) || ''
  updateDialog.value = true
}

const closeUpdateDialog = () => {
  updateDialog.value = false
  updatingAccount.value = null
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
  if (showTypePicker.value) {
    if (typePickerButton.value?.contains(target)) {
      return
    }
    const picker = document.querySelector('.type-picker')
    if (picker && picker.contains(target)) {
      return
    }
    showTypePicker.value = false
  }
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
}

onMounted(loadAccounts)
onMounted(loadOrganizations)
onMounted(loadIcons)
onMounted(async () => {
  await nextTick()
  syncTypePickerWidth()
  window.addEventListener('resize', syncTypePickerWidth)
  window.addEventListener('click', onWindowClick)
})
onUnmounted(() => {
  window.removeEventListener('resize', syncTypePickerWidth)
  window.removeEventListener('click', onWindowClick)
})

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
.dashboard {
  max-width: 1320px;
  margin: 0 auto;
  padding: 1.25rem;
}

.widgets {
  margin-bottom: 1.25rem;
}

.widgets h2 {
  margin: 0 0 0.4rem;
}

.widgets p {
  margin: 0 0 0.8rem;
  color: var(--cds-text-secondary);
}

.widget-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.widget-slot {
  border: 1px dashed var(--cds-border-subtle-01);
  min-height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: var(--cds-text-secondary);
  background: var(--cds-layer-hover);
}

.action-row {
  position: relative;
  margin-bottom: 1.25rem;
}

.type-picker {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 20;
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

.section-wrap {
  margin-bottom: 1.25rem;
}

.section-title {
  margin: 0 0 0.75rem;
}

.section-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.account-tile {
  min-height: 148px;
  border-radius: 12px;
  position: relative;
  padding-bottom: 2rem;
  padding-left: 2.3rem;
  padding-top: 0.62rem;
}

.tile-icon {
  position: absolute;
  left: 0.55rem;
  top: 0.7rem;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid var(--cds-border-subtle-01);
  object-fit: cover;
}

.tile-icon--empty {
  background: #e2e8f0;
}

.tile-rank-trigger {
  position: absolute;
  left: 0.35rem;
  top: 50%;
  transform: translateY(-50%);
  border: 0;
  background: transparent;
  color: var(--cds-text-secondary);
  font-size: 0.65rem;
  line-height: 1;
  padding: 0;
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  transition: opacity 120ms ease;
}

.tile-rank-trigger:hover,
.tile-rank-trigger:focus-visible {
  color: var(--cds-text-primary);
  outline: none;
}

.account-tile:hover .tile-rank-trigger,
.account-tile:focus-within .tile-rank-trigger {
  opacity: 1;
  pointer-events: auto;
}

.tile-rank-trigger--right {
  left: auto;
  right: 2rem;
}

.tile-update-clock {
  position: absolute;
  right: 0.75rem;
  top: 0.42rem;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid currentColor;
  cursor: default;
  display: inline-block;
}

.tile-link {
  position: absolute;
  right: 1.95rem;
  top: 0.42rem;
  text-decoration: none;
  width: 18px;
  height: 18px;
  border: 1px solid #64748b;
  border-radius: 3px;
  color: #111827;
  font-size: 0.75rem;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.tile-update-clock::before,
.tile-update-clock::after {
  content: '';
  position: absolute;
  background: currentColor;
  left: 50%;
  top: 50%;
  transform-origin: bottom center;
}

.tile-update-clock::before {
  width: 2px;
  height: 6px;
  transform: translate(-50%, -100%) rotate(0deg);
}

.tile-update-clock::after {
  width: 2px;
  height: 5px;
  transform: translate(-50%, -100%) rotate(60deg);
}

.clock-fresh {
  color: #16a34a;
}

.clock-recent {
  color: #2563eb;
}

.clock-aging {
  color: #111827;
}

.clock-stale {
  color: #b91c1c;
}

.tile-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--cds-text-primary);
  margin-top: 0.05rem;
  margin-bottom: 2px;
  line-height: 1.2;
}

.tile-sub {
  font-size: 0.87rem;
  color: var(--cds-text-secondary);
}

.tile-balance {
  margin-top: 10px;
  font-size: 1rem;
  font-weight: 700;
}

.balance-asset {
  color: #047857;
}

.balance-liability {
  color: #b91c1c;
}

.tile-type {
  margin-top: 6px;
  font-size: 0.78rem;
  color: var(--cds-text-secondary);
  text-transform: capitalize;
}

.tile-actions {
  position: absolute;
  right: 0.75rem;
  bottom: 0.6rem;
}

.tile-menu-trigger {
  border: 0;
  background: #000;
  color: #fff;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  padding: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.tile-menu-trigger:hover,
.tile-menu-trigger:focus-visible {
  background: #111827;
  outline: 2px solid #94a3b8;
  outline-offset: 1px;
}

.tile-menu-dots {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #fff;
  box-shadow:
    0 -6px 0 #fff,
    0 6px 0 #fff;
}

.tile-menu {
  position: absolute;
  right: 0;
  bottom: calc(100% + 4px);
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.16);
  min-width: 120px;
  overflow: hidden;
}

.tile-menu-option {
  display: block;
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--cds-text-primary);
  text-align: left;
  padding: 0.55rem 0.7rem;
  cursor: pointer;
}

.tile-menu-option:hover,
.tile-menu-option:focus-visible {
  background: #e0f2fe;
  outline: none;
}

.tile-menu-option--danger {
  color: #b91c1c;
}

.empty-state {
  color: var(--cds-text-secondary);
}

@media (max-width: 1200px) {
  .section-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .section-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .icon-grid-scroll {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .crypto-position-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .section-grid {
    grid-template-columns: 1fr;
  }

  .icon-grid-scroll {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
