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

    <div v-if="createDialog" class="modal-backdrop" @click.self="closeCreateDialog">
      <section class="modal-card cds--tile">
        <h3>{{ modalTitle }} {{ selectedTypeLabel || 'Account' }}</h3>
        <form class="form-grid" @submit.prevent="submitCreateAccount">
          <BankField v-model="createForm.name" label="Account Name" required />
          <BankField v-model="createForm.account_number" label="Account Number" required />

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

          <template v-if="needsFee">
            <DollarField v-model="createForm.fee_amount_cents" label="Fee Amount" />
            <RecurringPeriodField v-model="createForm.fee_period" label="Fee Period" />
          </template>

          <div v-if="needsRouting">
            <BankField v-model="createForm.routing_number" label="Routing Number" />
          </div>

          <template v-if="needsApy">
            <BankField v-model="createForm.apy_bps" label="APY (bps)" type="number" />
            <BankField v-model="createForm.compound_period" label="Compound Period" :options="compoundPeriodOptions" />
          </template>

          <template v-if="needsApr">
            <BankField v-model="createForm.apr_bps" label="APR (bps)" type="number" />
            <BankField
              v-if="needsCompoundPeriod"
              v-model="createForm.compound_period"
              label="Compound Period"
              :options="compoundPeriodOptions"
            />
            <BankField v-if="needsBillingDay" v-model="createForm.billing_day" label="Billing Day" type="number" />
            <BankField v-if="needsPaymentDay" v-model="createForm.payment_day" label="Payment Day" type="number" />
          </template>

          <template v-if="needsExpiration">
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

          <div class="modal-actions">
            <button class="cds--btn cds--btn--ghost" type="button" @click="closeCreateDialog">Cancel</button>
            <button class="cds--btn cds--btn--primary" type="submit">{{ submitLabel }}</button>
          </div>
        </form>
      </section>
    </div>

    <div v-if="deleteDialog" class="modal-backdrop" @click.self="closeDeleteDialog">
      <section class="confirm-card cds--tile">
        <h3>Delete Account</h3>
        <p>Are you sure you want to delete this account? This action cannot be undone.</p>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="closeDeleteDialog">Cancel</button>
          <button class="cds--btn cds--btn--danger" type="button" @click="confirmDeleteAccount">Delete</button>
        </div>
      </section>
    </div>

    <div v-if="iconPickerDialog" class="modal-backdrop" @click.self="cancelIconPickerModal">
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

    <div v-if="updateDialog" class="modal-backdrop" @click.self="closeUpdateDialog">
      <section class="confirm-card cds--tile">
        <h3>Update {{ updatingAccount?.name }}</h3>
        <p>{{ updateDescription }}</p>

        <div class="form-grid form-grid--single">
          <DollarField
            v-if="updateMode === 'dollars'"
            v-model="updateForm.amountCents"
            :label="updateAmountLabel"
          />
          <template v-else>
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
          <div class="tile-title">{{ account.name }}</div>
          <div class="tile-sub">{{ account.organization || 'Unknown organization' }}</div>
          <div class="tile-sub">•••• {{ last4(account.account_number) }}</div>
          <div class="tile-balance" :class="balanceTone(section.key)">
            {{ balanceLabel(account) }}
          </div>
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
  last_update?: string
  balance_cents?: number
  usd_balance_cents?: number
  stock_positions?: Array<{ stock_id: string; quantity: string }>
  crypto_positions?: Array<{ ticker: string; quantity: string }>
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
  balance_cents?: number
  fee_amount_cents?: number
  fee_period?: string
  routing_number?: string
  apy_bps?: number
  compound_period?: string
  apr_bps?: number
  billing_day?: number
  payment_day?: number
  expiration_date?: string
  cvc?: string
  usd_balance_cents?: number
  retirement_account_type?: string
  payment_amount_cents?: number
  icon_id?: string
  icon_type: 'Letters' | 'Gravatar' | 'Icon'
  stock_positions: Array<{ stock_id: string; quantity: string }>
  crypto_positions: Array<{ ticker: string; quantity: string }>
  cash_bills: Array<{ denomination_cents: number; quantity: number }>
}

interface OrganizationSuggestion {
  name: string
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
const retirementTypes = ['roth', 'simple', '401k']
const compoundPeriodOptions = compoundPeriods.map((value) => ({ label: value, value }))
const retirementTypeOptions = retirementTypes.map((value) => ({ label: value, value }))

const needsBalance = computed(() =>
  ['checking', 'savings', 'line_of_credit', 'credit_card', 'retirement', 'loan', 'rewards_card'].includes(
    createForm.value.type,
  ),
)
const needsFee = computed(() =>
  ['checking', 'savings', 'line_of_credit', 'credit_card'].includes(createForm.value.type),
)
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
const updateMode = computed<'dollars' | 'quantity'>(() =>
  ['stocks_account', 'crypto_wallet'].includes(updatingAccount.value?.type || '') ? 'quantity' : 'dollars',
)
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
  if (updatingAccount.value.type === 'stocks_account') {
    return 'Update the quantity for the first stock position on this account.'
  }
  return 'Update the quantity for the first crypto position on this account.'
})

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

const last4 = (value: string) => value.slice(-4)

const cents = (value?: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format((value || 0) / 100)

const balanceLabel = (account: AccountPayload) => {
  if (account.type === 'stocks_account') {
    return `${account.stock_positions?.length || 0} stock positions`
  }
  if (account.type === 'crypto_wallet') {
    return `${account.crypto_positions?.length || 0} crypto positions`
  }
  if (account.type === 'crypto_exchange') {
    return `USD ${cents(account.usd_balance_cents)}`
  }
  return `Balance ${cents(account.balance_cents)}`
}

const balanceTone = (sectionKey: string) =>
  ['credit_cards', 'payables'].includes(sectionKey) ? 'balance-liability' : 'balance-asset'

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
    const firstPosition = account.stock_positions?.[0]
    if (!firstPosition) {
      errorMessage.value = 'No stock position to update. Use Edit to add one first.'
      snackbar.value = true
      return
    }
    updateForm.value.quantity = firstPosition.quantity || '0'
    updateForm.value.ticker = ''
  } else if (account.type === 'crypto_wallet') {
    const firstPosition = account.crypto_positions?.[0]
    updateForm.value.quantity = firstPosition?.quantity || '0'
    updateForm.value.ticker = firstPosition?.ticker || ''
  } else if (account.type === 'crypto_exchange') {
    updateForm.value.amountCents = account.usd_balance_cents || 0
  } else {
    updateForm.value.amountCents = account.balance_cents || 0
  }
  updateDialog.value = true
}

const closeUpdateDialog = () => {
  updateDialog.value = false
  updatingAccount.value = null
}

const isValidQuantity = (value: string) => /^-?\d+(\.\d+)?$/.test(value.trim())

const submitUpdateValue = async () => {
  if (!updatingAccount.value) {
    return
  }
  const account = updatingAccount.value
  const payload: Record<string, unknown> = {}

  if (updateMode.value === 'dollars') {
    if (account.type === 'crypto_exchange') {
      payload.usd_balance_cents = updateForm.value.amountCents
    } else {
      payload.balance_cents = updateForm.value.amountCents
    }
  } else if (account.type === 'stocks_account') {
    if (!isValidQuantity(updateForm.value.quantity)) {
      errorMessage.value = 'Quantity must be a valid number'
      snackbar.value = true
      return
    }
    const stockPositions = (account.stock_positions || []).map((position, index) =>
      index === 0 ? { ...position, quantity: updateForm.value.quantity.trim() } : position,
    )
    payload.stock_positions = stockPositions
  } else if (account.type === 'crypto_wallet') {
    if (!isValidQuantity(updateForm.value.quantity)) {
      errorMessage.value = 'Quantity must be a valid number'
      snackbar.value = true
      return
    }
    const ticker = updateForm.value.ticker.trim().toUpperCase()
    if (!ticker) {
      errorMessage.value = 'Ticker is required for crypto quantity updates'
      snackbar.value = true
      return
    }
    const cryptoPositions = [...(account.crypto_positions || [])]
    if (cryptoPositions.length) {
      cryptoPositions[0] = {
        ...cryptoPositions[0],
        ticker,
        quantity: updateForm.value.quantity.trim(),
      }
    } else {
      cryptoPositions.push({
        ticker,
        quantity: updateForm.value.quantity.trim(),
      })
    }
    payload.crypto_positions = cryptoPositions
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
  padding-left: 2.1rem;
}

.tile-icon {
  position: absolute;
  left: 0.55rem;
  top: 0.65rem;
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
  top: 0.6rem;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid currentColor;
  cursor: default;
  display: inline-block;
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
  height: 5px;
  transform: translate(-50%, -100%) rotate(0deg);
}

.tile-update-clock::after {
  width: 2px;
  height: 4px;
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
  margin-bottom: 2px;
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
