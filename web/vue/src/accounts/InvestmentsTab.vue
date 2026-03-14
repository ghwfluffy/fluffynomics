<template>
  <section class="section-wrap">
    <div class="top-controls">
      <ViewModeToggle v-model="viewMode" />
    </div>
    <div v-if="viewMode !== 'table'" class="action-row">
      <button class="cds--btn cds--btn--primary mp-add-btn" type="button" @click="openCreate">Add Investment</button>
    </div>

    <template v-if="viewMode !== 'table'">
      <section v-for="section in sections" :key="section.key" class="section-wrap">
        <CollapsibleSectionHeader
          :title="section.label"
          :collapsed="isInvestmentSectionCollapsed(section)"
          :collapsible="section.key === 'legacy'"
          @toggle="toggleInvestmentSection(section)"
        />
        <div
          v-if="!isInvestmentSectionCollapsed(section) && section.items.length"
          class="section-grid"
          :class="{ 'section-grid--icons': viewMode === 'icons' }"
        >
          <article
            v-for="item in section.items"
            :key="item.id"
            class="cds--tile account-tile"
            :class="{
              'account-tile--icon': viewMode === 'icons',
              'account-tile--icon-expanded': viewMode === 'icons' && isInvestmentIconExpanded(item.id),
            }"
          >
            <button
              v-if="viewMode === 'icons'"
              class="icon-card-trigger"
              type="button"
              :aria-expanded="isInvestmentIconExpanded(item.id) ? 'true' : 'false'"
              :aria-label="`${isInvestmentIconExpanded(item.id) ? 'Collapse' : 'Expand'} ${investmentName(item)}`"
              @click="toggleInvestmentIconExpanded(item.id)"
            >
              <img
                v-if="investmentIconUrl(item)"
                :src="investmentIconUrl(item)"
                class="icon-card-icon"
                alt=""
              />
              <div v-else class="icon-card-icon icon-card-icon--empty" aria-hidden="true"></div>
            </button>
            <template v-else>
              <img v-if="investmentIconUrl(item)" :src="investmentIconUrl(item)" class="tile-icon" alt="Investment icon" />
              <div v-else class="tile-icon tile-icon--empty" />
            </template>
            <div v-if="viewMode === 'icons'" class="icon-card-balance balance-asset">
              {{ cents(item.amount_cents) }}
            </div>
            <template v-if="viewMode === 'tiles' || isInvestmentIconExpanded(item.id)">
              <div :class="viewMode === 'icons' ? 'icon-card-details' : ''">
                <div class="tile-title">{{ investmentName(item) }}</div>
                <div class="tile-sub">{{ sourceName(item.source_account_id) }} → {{ destinationName(item.destination_account_id) }}</div>
                <div class="tile-sub">Last: {{ formatDate(item.last_invested_date) }}</div>
                <div class="tile-sub">Next: {{ formatDate(item.next_investment_date) }}</div>
                <div class="tile-balance balance-asset">Amount {{ cents(item.amount_cents) }}</div>
                <div class="tile-type">
                  {{ frequencyLabel(item.general_frequency) }} • {{ destinationTypeLabel(item.destination_account_id) }}
                  <span v-if="!item.enabled"> • Disabled</span>
                </div>
              </div>
              <div class="tile-actions">
                <button class="tile-menu-trigger" type="button" aria-label="Investment menu" @click.stop="toggleMenu(item.id)">
                  <span class="tile-menu-dots" aria-hidden="true"></span>
                </button>
                <div v-if="activeMenuId === item.id" class="tile-menu">
                  <button type="button" class="tile-menu-option" @click="openEdit(item)">Edit</button>
                  <button type="button" class="tile-menu-option" @click="openUpdate(item)">Update</button>
                  <button type="button" class="tile-menu-option tile-menu-option--danger" @click="openDelete(item.id)">Delete</button>
                </div>
              </div>
            </template>
          </article>
        </div>
        <div v-else-if="!isInvestmentSectionCollapsed(section)" class="cds--tile empty-state">No investments yet.</div>
      </section>
    </template>

    <section v-else class="section-wrap">
      <div class="cds--data-table-container">
        <div class="table-toolbar-row">
          <DataTableControls
            v-model="tableFilter"
            placeholder="Filter investments"
            :filters="investmentColumnFilters"
            @update:filter="onInvestmentColumnFilterUpdate"
          />
          <button class="cds--btn cds--btn--primary mp-add-btn" type="button" @click="openCreate">Add Investment</button>
        </div>
        <table class="cds--data-table cds--data-table--md">
          <thead>
            <tr>
              <th></th>
              <th><button class="sort-btn" type="button" @click="setSort('name')">Name</button></th>
              <th><button class="sort-btn" type="button" @click="setSort('destination_type')">Destination Type</button></th>
              <th><button class="sort-btn" type="button" @click="setSort('amount')">Amount</button></th>
              <th><button class="sort-btn" type="button" @click="setSort('frequency')">Frequency</button></th>
              <th><button class="sort-btn" type="button" @click="setSort('last')">Last</button></th>
              <th><button class="sort-btn" type="button" @click="setSort('next')">Next</button></th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in filteredInvestments" :key="item.id">
              <td class="table-icon-cell">
                <img v-if="investmentIconUrl(item)" :src="investmentIconUrl(item)" class="table-icon" alt="Investment icon" />
                <div v-else class="table-icon table-icon--empty"></div>
              </td>
              <td>{{ investmentName(item) }}</td>
              <td>{{ investmentDestinationDisplay(item) }}</td>
              <td>{{ cents(item.amount_cents) }}</td>
              <td>{{ frequencyLabel(item.general_frequency) }}</td>
              <td>{{ formatDate(item.last_invested_date) }}</td>
              <td>{{ formatDate(item.next_investment_date) }}</td>
              <td class="table-actions-cell">
                <div class="table-overflow-menu">
                  <button class="tile-menu-trigger table-menu-trigger" type="button" aria-label="Investment menu" @click.stop="toggleMenu(item.id)">
                    <span aria-hidden="true">⋮</span>
                  </button>
                  <div v-if="activeMenuId === item.id" class="tile-menu table-menu-list">
                    <button type="button" class="tile-menu-option" @click="openEdit(item)">Edit</button>
                    <button type="button" class="tile-menu-option" @click="openUpdate(item)">Update</button>
                    <button type="button" class="tile-menu-option tile-menu-option--danger" @click="openDelete(item.id)">Delete</button>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="dialogOpen" class="modal-backdrop">
      <section class="modal-card cds--tile">
        <h3>{{ editingId ? 'Edit Investment' : 'Create Investment' }}</h3>
        <form class="form-grid" @submit.prevent="saveInvestment">
          <UnifiedDropdown v-model="form.source_account_id" label="Source Account" searchable required :options="sourceAccountOptions" />
          <UnifiedDropdown v-model="form.destination_account_id" label="Destination Account" searchable required :options="destinationAccountOptions" />
          <DollarField v-model="form.amount_cents" label="Amount" />
          <RecurringPeriodField v-model="form.general_frequency" label="Frequency" />
          <div class="date-row">
            <BankField v-model="form.last_invested_date" label="Last Invested Date" type="date" />
            <div class="next-date-field">
              <BankField v-model="form.next_investment_date" label="Next Investment Date" type="date" />
              <button type="button" class="cds--btn cds--btn--ghost clear-next-btn" @click="clearNextInvestmentDate">Clear Next Date</button>
            </div>
          </div>
          <div class="bank-field">
            <label class="bank-label">Enabled</label>
            <label class="check-row"><input v-model="form.enabled" type="checkbox" /> <span>Enabled</span></label>
          </div>

          <div class="modal-actions">
            <button class="cds--btn cds--btn--ghost" type="button" @click="closeDialog">Cancel</button>
            <button class="cds--btn cds--btn--primary" type="submit">{{ editingId ? 'Save Changes' : 'Create Investment' }}</button>
          </div>
        </form>
      </section>
    </div>

    <div v-if="deleteId" class="modal-backdrop">
      <section class="confirm-card cds--tile">
        <h3>Delete Investment</h3>
        <p>Are you sure you want to delete this investment?</p>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="deleteId = null">Cancel</button>
          <button class="cds--btn cds--btn--danger" type="button" @click="confirmDelete">Delete</button>
        </div>
      </section>
    </div>

    <div v-if="updateDialog" class="modal-backdrop">
      <section class="confirm-card cds--tile">
        <h3>Update Investment</h3>
        <div class="form-grid form-grid--single">
          <div class="bank-field">
            <label class="bank-label">Enabled</label>
            <label class="check-row"><input v-model="updateForm.enabled" type="checkbox" /> <span>Enabled</span></label>
          </div>
          <div class="date-row date-row--update">
            <BankField v-model="updateForm.last_invested_date" label="Last Invested Date" type="date" />
            <div class="next-date-field">
              <BankField v-model="updateForm.next_investment_date" label="Next Investment Date" type="date" />
              <button type="button" class="cds--btn cds--btn--ghost clear-next-btn" @click="updateForm.next_investment_date = ''">
                Clear Next Date
              </button>
            </div>
          </div>
        </div>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="closeUpdateDialog">Cancel</button>
          <button class="cds--btn cds--btn--primary" type="button" @click="saveUpdate">Save</button>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { request } from '@/lib/api'
import { formatMaskedCurrencyCents, guardMaskedMode } from '@/lib/maskedMode'
import ViewModeToggle from '@/components/ViewModeToggle.vue'
import DataTableControls from '@/components/DataTableControls.vue'
import BankField from '@/components/BankField.vue'
import DollarField from '@/components/DollarField.vue'
import RecurringPeriodField from '@/components/RecurringPeriodField.vue'
import UnifiedDropdown from '@/components/UnifiedDropdown.vue'
import CollapsibleSectionHeader from '@/components/CollapsibleSectionHeader.vue'

interface Investment {
  id: string
  source_account_id: string
  destination_account_id: string
  amount_cents: number
  enabled: boolean
  general_frequency?: string
  last_invested_date?: string
  next_investment_date?: string
  next_date_is_static: boolean
}

interface LinkedAccount {
  id: string
  name: string
  type: string
  rank: number
  icon_id?: string
  icon_type?: 'Letters' | 'Gravatar' | 'Icon'
  organization?: string
  closed?: boolean
}

interface InvestmentSection {
  key: string
  label: string
  items: Investment[]
}

const props = withDefaults(defineProps<{ accounts: LinkedAccount[]; viewMode?: 'tiles' | 'icons' | 'table' }>(), {
  viewMode: 'icons',
})
const emit = defineEmits<{
  (event: 'update:viewMode', value: 'tiles' | 'icons' | 'table'): void
  (event: 'changed'): void
}>()

const viewMode = computed({
  get: () => props.viewMode,
  set: (value: 'tiles' | 'icons' | 'table') => emit('update:viewMode', value),
})

const destinationTypeOrder = ['savings', 'investment_fund', 'stocks_account', 'retirement', 'crypto_exchange']
const destinationTypeLabels: Record<string, string> = {
  savings: 'Savings',
  investment_fund: 'Investment Funds',
  stocks_account: 'Stocks Accounts',
  retirement: 'Retirement',
  crypto_exchange: 'Crypto Exchange',
}

const investments = ref<Investment[]>([])
const tableFilter = ref('')
const destinationTypeFilterValues = ref<string[]>([])
const enabledFilterValues = ref<string[]>([])
const sortKey = ref<'name' | 'destination_type' | 'amount' | 'frequency' | 'last' | 'next'>('destination_type')
const sortDir = ref<'asc' | 'desc'>('asc')
const dialogOpen = ref(false)
const deleteId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const activeMenuId = ref<string | null>(null)
const expandedInvestmentIconIds = ref<Set<string>>(new Set())
const legacyInvestmentsSectionOpen = ref(false)
const updateDialog = ref(false)
const updatingId = ref<string | null>(null)

const form = ref({
  source_account_id: '',
  destination_account_id: '',
  amount_cents: 0,
  enabled: true,
  general_frequency: '',
  last_invested_date: '',
  next_investment_date: '',
})

const updateForm = ref({
  enabled: true,
  last_invested_date: '',
  next_investment_date: '',
})

const linkedAccounts = computed(() =>
  [...props.accounts]
    .filter((account) => !account.closed)
    .sort((a, b) => (Number(b.rank) || 0) - (Number(a.rank) || 0) || a.name.localeCompare(b.name)),
)

const sourceAccounts = computed(() => linkedAccounts.value.filter((account) => account.type === 'checking'))
const destinationAccounts = computed(() =>
  linkedAccounts.value
    .filter((account) => destinationTypeOrder.includes(account.type))
    .sort((a, b) => {
      const aIndex = destinationTypeOrder.indexOf(a.type)
      const bIndex = destinationTypeOrder.indexOf(b.type)
      return aIndex - bIndex || (Number(b.rank) || 0) - (Number(a.rank) || 0) || a.name.localeCompare(b.name)
    }),
)

const accountById = computed(() => new Map(linkedAccounts.value.map((account) => [account.id, account])))

const sourceAccountOptions = computed(() =>
  sourceAccounts.value.map((account) => ({
    label: account.name,
    value: account.id,
  })),
)

const destinationAccountOptions = computed(() =>
  destinationAccounts.value.map((account) => ({
    label: `${account.name} (${destinationTypeLabelFromType(account.type)})`,
    value: account.id,
  })),
)

const investmentName = (item: Investment) => `${destinationName(item.destination_account_id)} from ${sourceName(item.source_account_id)}`

const sourceName = (accountId?: string) => accountById.value.get(accountId || '')?.name || 'Unknown account'
const destinationName = (accountId?: string) => accountById.value.get(accountId || '')?.name || 'Unknown account'
const destinationType = (accountId?: string) => accountById.value.get(accountId || '')?.type || ''
const destinationTypeLabelFromType = (type: string) => destinationTypeLabels[type] || type.replaceAll('_', ' ')
const destinationTypeLabel = (accountId?: string) => destinationTypeLabelFromType(destinationType(accountId))
const investmentDestinationDisplay = (item: Investment) =>
  item.enabled ? destinationTypeLabel(item.destination_account_id) : `Disabled ${destinationTypeLabel(item.destination_account_id)}`

const iconUrl = (iconId?: string) => (iconId ? `/api/icons/${iconId}` : '')
const generatedIconUrl = (iconType: 'Letters' | 'Gravatar', seed: string) =>
  iconType === 'Letters'
    ? `/api/icons/lettered/${encodeURIComponent(seed || 'Investment')}`
    : `/api/icons/gravatar/${encodeURIComponent(seed || 'Investment')}`

const resolveIconUrl = (iconId?: string, iconType?: 'Letters' | 'Gravatar' | 'Icon', seed?: string) => {
  if (iconType === 'Letters' || iconType === 'Gravatar') {
    return generatedIconUrl(iconType, seed || 'Investment')
  }
  return iconUrl(iconId)
}

const investmentIconUrl = (item: Investment) => {
  const destination = accountById.value.get(item.destination_account_id)
  if (!destination) {
    return ''
  }
  return resolveIconUrl(destination.icon_id, destination.icon_type || 'Icon', destination.organization || destination.name)
}

const resetForm = () => {
  form.value = {
    source_account_id: sourceAccounts.value[0]?.id || '',
    destination_account_id: destinationAccounts.value[0]?.id || '',
    amount_cents: 0,
    enabled: true,
    general_frequency: '',
    last_invested_date: '',
    next_investment_date: '',
  }
}

const sections = computed<InvestmentSection[]>(() => {
  const grouped = destinationTypeOrder
    .map((type) => ({
      key: type,
      label: destinationTypeLabels[type] || type,
      items: investments.value.filter((item) => item.enabled && destinationType(item.destination_account_id) === type),
    }))
    .filter((section) => section.items.length > 0)
  const legacyItems = investments.value.filter((item) => !item.enabled)
  if (legacyItems.length) {
    grouped.push({
      key: 'legacy',
      label: 'Legacy',
      items: legacyItems,
    })
  }
  return grouped
})

const isInvestmentSectionCollapsed = (section: InvestmentSection) => section.key === 'legacy' && !legacyInvestmentsSectionOpen.value

const toggleInvestmentSection = (section: InvestmentSection) => {
  if (section.key !== 'legacy') {
    return
  }
  legacyInvestmentsSectionOpen.value = !legacyInvestmentsSectionOpen.value
}

const isInvestmentIconExpanded = (investmentId: string) => expandedInvestmentIconIds.value.has(investmentId)

const toggleInvestmentIconExpanded = (investmentId: string) => {
  const next = new Set(expandedInvestmentIconIds.value)
  if (next.has(investmentId)) {
    next.delete(investmentId)
  } else {
    next.add(investmentId)
  }
  expandedInvestmentIconIds.value = next
}

const destinationTypeOptions = computed(() =>
  Array.from(new Set(investments.value.map((item) => destinationTypeLabel(item.destination_account_id)))).sort((a, b) => a.localeCompare(b)),
)
const investmentEnabledOptions = ['Enabled', 'Disabled']
const investmentColumnFilters = computed(() => [
  { key: 'destination_type', label: 'Destination Type', options: destinationTypeOptions.value, selected: destinationTypeFilterValues.value },
  { key: 'enabled', label: 'Status', options: investmentEnabledOptions, selected: enabledFilterValues.value },
])

const onInvestmentColumnFilterUpdate = (payload: { key: string; selected: string[] }) => {
  if (payload.key === 'destination_type') {
    destinationTypeFilterValues.value = payload.selected
    return
  }
  if (payload.key === 'enabled') {
    enabledFilterValues.value = payload.selected
  }
}

const filteredInvestments = computed(() => {
  const needle = tableFilter.value.trim().toLowerCase()
  const filtered = investments.value.filter((item) => {
    const matchesNeedle =
      !needle ||
      [
        investmentName(item),
        sourceName(item.source_account_id),
        destinationName(item.destination_account_id),
        investmentDestinationDisplay(item),
        frequencyLabel(item.general_frequency),
        formatDate(item.last_invested_date),
        formatDate(item.next_investment_date),
      ]
        .join(' ')
        .toLowerCase()
        .includes(needle)
    if (!matchesNeedle) {
      return false
    }
    const typeLabel = destinationTypeLabel(item.destination_account_id)
    if (destinationTypeFilterValues.value.length && !destinationTypeFilterValues.value.includes(typeLabel)) {
      return false
    }
    const statusLabel = item.enabled ? 'Enabled' : 'Disabled'
    if (enabledFilterValues.value.length && !enabledFilterValues.value.includes(statusLabel)) {
      return false
    }
    return true
  })
  return [...filtered].sort((a, b) => {
    const av =
      sortKey.value === 'name'
        ? investmentName(a)
        : sortKey.value === 'destination_type'
          ? investmentDestinationDisplay(a)
          : sortKey.value === 'amount'
            ? a.amount_cents
            : sortKey.value === 'frequency'
              ? frequencyLabel(a.general_frequency)
              : sortKey.value === 'last'
                ? new Date(`${(a.last_invested_date || '1900-01-01').slice(0, 10)}T00:00:00`).getTime()
                : new Date(`${(a.next_investment_date || '1900-01-01').slice(0, 10)}T00:00:00`).getTime()
    const bv =
      sortKey.value === 'name'
        ? investmentName(b)
        : sortKey.value === 'destination_type'
          ? investmentDestinationDisplay(b)
          : sortKey.value === 'amount'
            ? b.amount_cents
            : sortKey.value === 'frequency'
              ? frequencyLabel(b.general_frequency)
              : sortKey.value === 'last'
                ? new Date(`${(b.last_invested_date || '1900-01-01').slice(0, 10)}T00:00:00`).getTime()
                : new Date(`${(b.next_investment_date || '1900-01-01').slice(0, 10)}T00:00:00`).getTime()
    if (typeof av === 'number' && typeof bv === 'number') {
      return sortDir.value === 'asc' ? av - bv : bv - av
    }
    return sortDir.value === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av))
  })
})

const setSort = (key: typeof sortKey.value) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortKey.value = key
  sortDir.value = 'asc'
}

const cents = (value?: number) => formatMaskedCurrencyCents(value)

const formatDate = (raw?: string) => {
  if (!raw) {
    return 'Auto'
  }
  const parsed = new Date(`${raw.slice(0, 10)}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) {
    return raw
  }
  return parsed.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const weekdayLabel = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const monthLabel = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const frequencyLabel = (raw?: string) => {
  const value = (raw || '').trim()
  if (!value) {
    return 'As needed'
  }
  if (!value.startsWith('{')) {
    return value
  }
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>
    const kind = String(parsed.kind || '')
    if (kind === 'monthly_day') {
      return `Monthly on day ${parsed.day}`
    }
    if (kind === 'monthly_last_day') {
      return 'Monthly on last day'
    }
    if (kind === 'semimonthly_days') {
      return `Twice monthly (${parsed.day_1}, ${parsed.day_2})`
    }
    if (kind === 'yearly_month_day') {
      const month = Number(parsed.month)
      const day = Number(parsed.day)
      return `Yearly (${monthLabel[month] || month} ${day})`
    }
    if (kind === 'every_n_months_day') {
      const interval = Math.max(1, Number(parsed.interval_months || 1))
      const day = Number(parsed.day || 1)
      return `Every ${interval} month${interval === 1 ? '' : 's'} (day ${day})`
    }
    if (kind === 'every_n_years_month_day') {
      const interval = Math.max(1, Number(parsed.interval_years || 1))
      const month = Number(parsed.month || 1)
      const day = Number(parsed.day || 1)
      return `Every ${interval} year${interval === 1 ? '' : 's'} (${monthLabel[month] || month} ${day})`
    }
    if (kind === 'weekly_weekday') {
      const weekday = Number(parsed.weekday)
      return `Weekly (${weekdayLabel[weekday] || 'Day'})`
    }
    if (kind === 'biweekly_weekday') {
      const weekday = Number(parsed.weekday)
      return `Every 2 weeks (${weekdayLabel[weekday] || 'Day'})`
    }
    if (kind === 'every_n_weeks_weekday') {
      const interval = Math.max(1, Number(parsed.interval_weeks || 1))
      const weekday = Number(parsed.weekday)
      return `Every ${interval} weeks (${weekdayLabel[weekday] || 'Day'})`
    }
    if (kind === 'daily_weekdays') {
      return 'Daily'
    }
  } catch {
    return 'Custom'
  }
  return 'Custom'
}

const loadInvestments = async () => {
  investments.value = await request.get<Investment[]>('/investments')
}

const notifyChanged = () => {
  emit('changed')
}

const openCreate = () => {
  if (guardMaskedMode('create investments')) {
    return
  }
  resetForm()
  editingId.value = null
  dialogOpen.value = true
}

const openEdit = (item: Investment) => {
  if (guardMaskedMode('edit investments')) {
    return
  }
  form.value = {
    source_account_id: item.source_account_id,
    destination_account_id: item.destination_account_id,
    amount_cents: item.amount_cents || 0,
    enabled: item.enabled ?? true,
    general_frequency: item.general_frequency || '',
    last_invested_date: item.last_invested_date || '',
    next_investment_date: item.next_investment_date || '',
  }
  editingId.value = item.id
  dialogOpen.value = true
  activeMenuId.value = null
}

const closeDialog = () => {
  dialogOpen.value = false
  editingId.value = null
}

const clearNextInvestmentDate = () => {
  form.value.next_investment_date = ''
}

const saveInvestment = async () => {
  if (guardMaskedMode(editingId.value ? 'edit investments' : 'create investments')) {
    return
  }
  const payload = {
    source_account_id: form.value.source_account_id,
    destination_account_id: form.value.destination_account_id,
    amount_cents: form.value.amount_cents,
    enabled: form.value.enabled,
    general_frequency: form.value.general_frequency || null,
    last_invested_date: form.value.last_invested_date || null,
    next_investment_date: form.value.next_investment_date || null,
    next_date_is_static: Boolean(form.value.next_investment_date),
  }
  if (editingId.value) {
    await request.put(`/investments/${editingId.value}`, payload)
  } else {
    await request.post('/investments', payload)
  }
  closeDialog()
  await loadInvestments()
  notifyChanged()
}

const openDelete = (id: string) => {
  if (guardMaskedMode('delete investments')) {
    return
  }
  deleteId.value = id
  activeMenuId.value = null
}

const openUpdate = (item: Investment) => {
  if (guardMaskedMode('update investments')) {
    return
  }
  updateForm.value = {
    enabled: item.enabled ?? true,
    last_invested_date: item.last_invested_date || '',
    next_investment_date: item.next_investment_date || '',
  }
  updatingId.value = item.id
  updateDialog.value = true
  activeMenuId.value = null
}

const closeUpdateDialog = () => {
  updateDialog.value = false
  updatingId.value = null
}

const saveUpdate = async () => {
  if (guardMaskedMode('update investments')) {
    return
  }
  if (!updatingId.value) {
    return
  }
  await request.put(`/investments/${updatingId.value}`, {
    enabled: updateForm.value.enabled,
    last_invested_date: updateForm.value.last_invested_date || null,
    next_investment_date: updateForm.value.next_investment_date || null,
    next_date_is_static: Boolean(updateForm.value.next_investment_date),
  })
  closeUpdateDialog()
  await loadInvestments()
  notifyChanged()
}

const confirmDelete = async () => {
  if (guardMaskedMode('delete investments')) {
    return
  }
  if (!deleteId.value) {
    return
  }
  await request.delete(`/investments/${deleteId.value}`)
  deleteId.value = null
  await loadInvestments()
  notifyChanged()
}

const toggleMenu = (id: string) => {
  activeMenuId.value = activeMenuId.value === id ? null : id
}

const onWindowClick = (event: MouseEvent) => {
  const target = event.target as Node
  if (activeMenuId.value) {
    const menu = document.querySelector('.tile-menu')
    const trigger = document.querySelector('.tile-menu-trigger')
    if (!menu?.contains(target) && !trigger?.contains(target)) {
      activeMenuId.value = null
    }
  }
}

const onWindowKeyDown = (event: KeyboardEvent) => {
  if (event.key !== 'Escape') {
    return
  }
  if (updateDialog.value) {
    closeUpdateDialog()
    return
  }
  if (deleteId.value) {
    deleteId.value = null
    return
  }
  if (dialogOpen.value) {
    closeDialog()
  }
}

onMounted(loadInvestments)
onMounted(() => window.addEventListener('click', onWindowClick))
onMounted(() => window.addEventListener('keydown', onWindowKeyDown))
onUnmounted(() => window.removeEventListener('click', onWindowClick))
onUnmounted(() => window.removeEventListener('keydown', onWindowKeyDown))
</script>

<style scoped>
@import './sharedTile.css';

.top-controls {
  margin-top: 0.75rem;
  margin-bottom: 0.7rem;
}

.action-row {
  margin-bottom: 1rem;
  display: flex;
  justify-content: flex-end;
}

.table-toolbar-row {
  display: flex;
  gap: 0.75rem;
  align-items: stretch;
  margin-bottom: 0.35rem;
}

.table-toolbar-row :deep(.toolbar-shell) {
  flex: 1;
}

.table-actions-cell {
  position: relative;
  width: 1%;
}

.sort-btn {
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
  padding: 0;
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
  width: min(760px, 100%);
  max-height: 90vh;
  overflow: auto;
  padding: 1rem;
}

.confirm-card {
  width: min(460px, 100%);
  padding: 1rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.form-grid--single {
  grid-template-columns: 1fr;
}

.next-date-field {
  display: grid;
  gap: 4px;
}

.date-row {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-items: start;
}

.date-row--update {
  margin-top: 2px;
}

.clear-next-btn {
  justify-self: start;
  min-height: 2rem;
}

.modal-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.bank-label {
  display: block;
  margin-bottom: 6px;
  font-size: 0.75rem;
  color: var(--cds-text-secondary);
  font-weight: 600;
}

.section-wrap {
  margin-bottom: 1.25rem;
}

.empty-state {
  color: var(--cds-text-secondary);
}

@media (max-width: 900px) {
  .table-toolbar-row {
    flex-wrap: wrap;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .date-row {
    grid-template-columns: 1fr;
  }
}
</style>
