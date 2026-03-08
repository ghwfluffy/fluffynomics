<template>
  <section class="section-wrap">
    <AddTypePickerButton
      button-label="Add Contract"
      placeholder="Select contract type"
      :options="contractTypeOptions"
      @select="onContractTypePicked"
    />

    <section v-for="section in sections" :key="section.key" class="section-wrap">
      <h2 class="section-title">{{ section.title }}</h2>
      <div v-if="section.contracts.length" class="section-grid">
        <article v-for="(contract, index) in section.contracts" :key="contract.id" class="cds--tile account-tile">
          <img v-if="contractIconUrl(contract)" :src="contractIconUrl(contract)" class="tile-icon" alt="Contract icon" />
          <div v-else class="tile-icon tile-icon--empty" />
          <button
            v-if="index > 0"
            class="tile-rank-trigger"
            type="button"
            title="Move left"
            @click="moveContractLeft(section, index, $event)"
          >
            ◀
          </button>
          <button
            v-if="index < section.contracts.length - 1"
            class="tile-rank-trigger tile-rank-trigger--right"
            type="button"
            title="Move right"
            @click="moveContractRight(section, index, $event)"
          >
            ▶
          </button>
          <img
            v-if="contract.automatic"
            src="/automatic.png"
            class="tile-automatic-icon"
            :title="nextPaymentTooltip(contract)"
            alt="Automatic contract"
          />
          <span
            v-else
            class="tile-update-clock"
            :class="lastUpdateTone(contract.updated_at)"
            :title="`last update: ${formatLastUpdate(contract.updated_at)}`"
            aria-label="Last update status"
          />
          <a
            v-if="contract.url?.trim()"
            class="tile-link"
            :href="normalizedUrl(contract.url)"
            target="_blank"
            rel="noopener noreferrer"
            title="Open contract link"
            @click.stop
          >
            ↗
          </a>
          <div class="tile-title">{{ contract.name }}</div>
          <div class="tile-sub">{{ contract.organization || 'Unknown organization' }}</div>
          <div class="tile-sub">{{ nextPaymentCountdownLabel(contract) }}</div>
          <div class="tile-balance" :class="contract.type === 'income' ? 'balance-asset' : 'balance-liability'">
            {{ contract.type === 'income' ? 'Amount' : 'Payment' }} {{ cents(contract.amount_cents) }}
          </div>
          <div class="tile-sub">{{ contractTypeLabel(contract.type) }} • {{ contract.automatic ? 'Automatic' : 'Manual' }}</div>
          <div class="tile-type">{{ accountNameById(contract.linked_account_id) }}</div>
          <div class="tile-actions">
            <button class="tile-menu-trigger" type="button" aria-label="Contract menu" @click.stop="toggleTileMenu(contract.id)">
              <span class="tile-menu-dots" aria-hidden="true"></span>
            </button>
            <div v-if="activeTileMenuId === contract.id" class="tile-menu">
              <button type="button" class="tile-menu-option" @click="startEditContract(contract)">Edit</button>
              <button type="button" class="tile-menu-option" @click="openUpdateDialog(contract)">Update</button>
              <button type="button" class="tile-menu-option tile-menu-option--danger" @click="openDeleteContract(contract.id)">
                Delete
              </button>
            </div>
          </div>
        </article>
      </div>
      <div v-else class="cds--tile empty-state">No contracts yet.</div>
    </section>

    <div v-if="contractDialog" class="modal-backdrop">
      <section class="modal-card cds--tile">
        <h3>{{ editingContractId ? 'Edit Contract' : 'Create Contract' }}</h3>
        <form class="form-grid" @submit.prevent="submitContract">
          <BankField v-model="contractForm.name" label="Contract Name" required />
          <BankField v-model="contractForm.account_number" label="Account Number" />
          <UnifiedDropdown
            v-model="contractForm.organization"
            label="Organization"
            placeholder="Type or select organization"
            searchable
            allow-custom
            required
            :options="organizationDropdownOptions"
          />
          <div class="icon-picker">
            <label class="bank-label">Contract Icon</label>
            <div class="icon-picker-row">
              <img v-if="selectedFormIconUrl" :src="selectedFormIconUrl" class="icon-preview" alt="Selected icon" />
              <div v-else class="icon-preview icon-preview--empty" />
              <button type="button" class="cds--btn cds--btn--ghost icon-upload-btn" @click="openIconPickerModal">
                Choose Icon
              </button>
              <input ref="iconFileInput" class="icon-upload-input" type="file" accept="image/*" @change="uploadIcon" />
              <button type="button" class="cds--btn cds--btn--ghost icon-upload-btn" @click="openIconUploadPicker">
                Upload New
              </button>
            </div>
          </div>
          <div class="contract-type-readonly">
            <label class="bank-label">Type</label>
            <div class="contract-type-readonly-value">{{ contractTypeLabel(contractForm.type) }}</div>
          </div>
          <div class="check-row">
            <input id="contract-auto" v-model="contractForm.automatic" type="checkbox" />
            <label for="contract-auto">Automatic</label>
          </div>
          <DollarField v-model="contractForm.amount_cents" label="Amount" />
          <UnifiedDropdown v-model="contractForm.linked_account_id" label="Linked Account" :options="accountDropdownOptions" />
          <div v-if="contractForm.type === 'transfer'">
            <UnifiedDropdown v-model="contractForm.source_account_id" label="Source Account" :options="accountDropdownOptions" />
          </div>
          <RecurringPeriodField v-model="contractForm.payment_period" label="Payment Period" />
          <BankField v-model="contractForm.payment_day" label="Payment Day" type="number" required />
          <UnifiedDropdown v-model="contractForm.category" label="Category" searchable allow-custom :options="categoryOptions" />
          <BankField v-model="contractForm.url" label="URL" type="url" />
          <BankField v-if="contractForm.type === 'payment'" v-model="contractForm.billing_day" label="Billing Day" type="number" />
          <BankField v-model="contractForm.notes" class="notes-field" label="Notes" multiline />
          <div class="modal-actions">
            <button class="cds--btn cds--btn--ghost" type="button" @click="closeContractDialog">Cancel</button>
            <button class="cds--btn cds--btn--primary" type="submit">{{ editingContractId ? 'Save Changes' : 'Create Contract' }}</button>
          </div>
        </form>
      </section>
    </div>

    <div v-if="deleteContractDialog" class="modal-backdrop">
      <section class="confirm-card cds--tile">
        <h3>Delete Contract</h3>
        <p>Are you sure you want to delete this contract? This action cannot be undone.</p>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="closeDeleteContractDialog">Cancel</button>
          <button class="cds--btn cds--btn--danger" type="button" @click="confirmDeleteContract">Delete</button>
        </div>
      </section>
    </div>

    <div v-if="updateDialog" class="modal-backdrop">
      <section class="confirm-card cds--tile">
        <h3>Update {{ updatingContract?.name }}</h3>
        <div class="form-grid form-grid--single">
          <BankField v-model="updateForm.last_payment_date" label="Last Payment Date" type="date" />
          <BankField v-model="updateForm.expiration_date" label="Expiration Date" type="date" />
        </div>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="closeUpdateDialog">Cancel</button>
          <button class="cds--btn cds--btn--primary" type="button" @click="submitUpdateDialog">Save</button>
        </div>
      </section>
    </div>

    <div v-if="iconPickerDialog" class="modal-backdrop">
      <section class="icon-modal-card cds--tile">
        <h3>Choose Icon</h3>
        <div class="generated-icon-actions">
          <button type="button" class="cds--btn cds--btn--secondary" @click="selectGeneratedIcon('Letters')">Use Letters Icon</button>
          <button type="button" class="cds--btn cds--btn--secondary" @click="selectGeneratedIcon('Gravatar')">
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
        <div v-if="iconContextMenu.open" class="icon-context-menu" :style="{ left: `${iconContextMenu.x}px`, top: `${iconContextMenu.y}px` }">
          <button type="button" class="icon-context-menu-item" @click="deleteContextIcon">Delete icon</button>
        </div>
        <div class="icon-modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="cancelIconPickerModal">Cancel</button>
          <button class="cds--btn cds--btn--primary" type="button" @click="acceptIconPickerModal">Accept</button>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { errorMessage, request, snackbar } from '@/lib/api'
import AddTypePickerButton from '@/components/AddTypePickerButton.vue'
import BankField from '@/components/BankField.vue'
import DollarField from '@/components/DollarField.vue'
import RecurringPeriodField from '@/components/RecurringPeriodField.vue'
import UnifiedDropdown from '@/components/UnifiedDropdown.vue'

interface AccountSummary {
  id: string
  name: string
  type: string
  account_number?: string
}

interface ContractPayload {
  id: string
  rank: number
  name: string
  type: 'income' | 'payment' | 'transfer'
  automatic: boolean
  amount_cents: number
  organization?: string
  icon_id?: string
  icon_type?: 'Letters' | 'Gravatar' | 'Icon'
  linked_account_id: string
  source_account_id?: string
  last_payment_date?: string
  payment_period?: string
  payment_day?: number
  expiration_date?: string
  notes?: string
  category?: string
  url?: string
  account_number?: string
  billing_day?: number
  updated_at?: string
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

type ContractForm = Omit<ContractPayload, 'id' | 'updated_at'> & { source_account_id?: string }

interface Section {
  key: string
  title: string
  contracts: ContractPayload[]
}

const props = defineProps<{ accounts: AccountSummary[]; forecastDate?: string }>()

const PRESET_CATEGORIES = ['Living', 'Entertainment', 'Health', 'Digital', 'Financial', 'Work', 'Family']

const makeContractForm = (): ContractForm => ({
  rank: 0,
  name: '',
  type: 'income',
  automatic: true,
  amount_cents: 0,
  organization: '',
  icon_id: undefined,
  icon_type: 'Icon',
  linked_account_id: '',
  source_account_id: undefined,
  last_payment_date: '',
  payment_period: '',
  payment_day: undefined,
  notes: '',
  category: 'Financial',
  url: '',
  account_number: '',
  billing_day: undefined,
})

const contracts = ref<ContractPayload[]>([])
const organizations = ref<OrganizationSuggestion[]>([])
const iconChoices = ref<IconListItem[]>([])
const contractDialog = ref(false)
const editingContractId = ref<string | null>(null)
const contractForm = ref<ContractForm>(makeContractForm())
const deleteContractDialog = ref(false)
const pendingDeleteContractId = ref<string | null>(null)
const updateDialog = ref(false)
const updatingContract = ref<ContractPayload | null>(null)
const updateForm = ref<{ last_payment_date?: string; expiration_date?: string }>({})
const activeTileMenuId = ref<string | null>(null)
const iconFileInput = ref<HTMLInputElement | null>(null)
const iconPickerDialog = ref(false)
const iconPickerDraftId = ref<string | undefined>(undefined)
const iconPickerDraftType = ref<'Letters' | 'Gravatar' | 'Icon'>('Icon')
const iconContextMenu = ref<{ open: boolean; x: number; y: number; iconId?: string }>({
  open: false,
  x: 0,
  y: 0,
})

const contractTypeOptions = [
  { label: 'Income', value: 'income' },
  { label: 'Payment', value: 'payment' },
  { label: 'Transfer', value: 'transfer' },
]

const accountDropdownOptions = computed(() =>
  props.accounts.map((account) => ({
    label: `${account.name} (${account.type.replaceAll('_', ' ')})`,
    value: account.id,
  })),
)

const isExpired = (contract: ContractPayload) => {
  if (!contract.expiration_date) {
    return false
  }
  const parsed = new Date(`${contract.expiration_date.slice(0, 10)}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) {
    return false
  }
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return parsed < today
}

const sections = computed<Section[]>(() => {
  const activeContracts = contracts.value.filter((contract) => !isExpired(contract))
  const expiredContracts = contracts.value.filter((contract) => isExpired(contract))
  const combos = new Set<string>()
  for (const contract of activeContracts) {
    combos.add(`${contract.type}::${contract.category || 'Financial'}`)
  }
  const grouped = Array.from(combos)
    .map((combo) => {
      const [type, category] = combo.split('::')
      return {
      key: combo,
      title: `${contractTypeGroupLabel(type)} ${category}`,
      contracts: activeContracts
        .filter((contract) => contract.type === type && (contract.category || 'Financial') === category)
        .sort((a, b) => b.rank - a.rank),
    }} )
    .filter((section) => section.contracts.length > 0)
    .sort((a, b) => a.title.localeCompare(b.title))
  if (expiredContracts.length) {
    grouped.push({
      key: 'expired',
      title: 'Expired',
      contracts: expiredContracts.sort((a, b) => b.rank - a.rank),
    })
  }
  return grouped
})

const categoryOptions = computed(() =>
  Array.from(new Set([...PRESET_CATEGORIES, ...contracts.value.map((c) => c.category || 'Financial')])).map((value) => ({
    label: value,
    value,
  })),
)

const organizationDropdownOptions = computed(() =>
  organizations.value.map((value) => ({
    label: value.name,
    value: value.name,
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

const selectedFormIconUrl = computed(() =>
  resolveIconUrl(contractForm.value.icon_id, contractForm.value.icon_type, contractForm.value.organization || contractForm.value.name),
)

const cents = (value?: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format((value || 0) / 100)

const normalizedUrl = (raw?: string) => (!raw?.trim() ? '#' : /^https?:\/\//i.test(raw) ? raw : `https://${raw}`)
const iconUrl = (iconId?: string) => (iconId ? `/api/icons/${iconId}` : '')
const generatedIconUrl = (iconType: 'Letters' | 'Gravatar', organization?: string) => {
  const seed = (organization || '').trim() || 'Organization'
  const encoded = encodeURIComponent(seed)
  return iconType === 'Letters' ? `/api/icons/lettered/${encoded}` : `/api/icons/gravatar/${encoded}`
}
const resolveIconUrl = (iconId?: string, iconType?: 'Letters' | 'Gravatar' | 'Icon', organization?: string) =>
  iconType === 'Letters' || iconType === 'Gravatar' ? generatedIconUrl(iconType, organization) : iconUrl(iconId)
const contractIconUrl = (contract: ContractPayload) => resolveIconUrl(contract.icon_id, contract.icon_type || 'Icon', contract.organization)
const contractTypeLabel = (type: string) => ({ income: 'Income', payment: 'Payment', transfer: 'Transfer' }[type] || type)
const contractTypeGroupLabel = (type: string) =>
  ({ income: 'Incoming', payment: 'Payment', transfer: 'Transfer' }[type] || type)
const accountNameById = (accountId?: string) => props.accounts.find((account) => account.id === accountId)?.name || 'Unknown account'

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

const startOfDay = (value: Date) => {
  const d = new Date(value)
  d.setHours(0, 0, 0, 0)
  return d
}

const lastDayOfMonth = (year: number, monthZeroBased: number) => new Date(year, monthZeroBased + 1, 0).getDate()

const clampMonthDay = (year: number, monthZeroBased: number, day: number) =>
  Math.min(Math.max(day, 1), lastDayOfMonth(year, monthZeroBased))

const monthlyDate = (year: number, monthZeroBased: number, day: number) =>
  startOfDay(new Date(year, monthZeroBased, clampMonthDay(year, monthZeroBased, day)))

const parseContractPeriod = (contract: ContractPayload) => {
  const raw = contract.payment_period?.trim()
  let payload: Record<string, unknown> | null = null
  if (raw) {
    try {
      payload = JSON.parse(raw) as Record<string, unknown>
    } catch {
      payload = null
    }
  }
  const kind = (payload?.kind as string | undefined) || (contract.payment_day ? 'monthly_day' : undefined)
  return { kind, payload }
}

const occurrenceOnOrAfter = (
  anchor: Date,
  kind: string,
  payload: Record<string, unknown> | null,
  fallbackDay: number,
) => {
  const dayFromContract = fallbackDay || 1
  const day = Number(payload?.day ?? dayFromContract)
  if (kind === 'monthly_day') {
    const thisMonth = monthlyDate(anchor.getFullYear(), anchor.getMonth(), day)
    return thisMonth >= anchor ? thisMonth : monthlyDate(anchor.getFullYear(), anchor.getMonth() + 1, day)
  }
  if (kind === 'monthly_last_day') {
    const thisMonth = monthlyDate(anchor.getFullYear(), anchor.getMonth(), 31)
    return thisMonth >= anchor ? thisMonth : monthlyDate(anchor.getFullYear(), anchor.getMonth() + 1, 31)
  }
  if (kind === 'twice_monthly') {
    const d1 = Number(payload?.day_1 ?? 1)
    const d2 = Number(payload?.day_2 ?? 15)
    const days = [d1, d2].sort((a, b) => a - b)
    for (const d of days) {
      const candidate = monthlyDate(anchor.getFullYear(), anchor.getMonth(), d)
      if (candidate >= anchor) {
        return candidate
      }
    }
    return monthlyDate(anchor.getFullYear(), anchor.getMonth() + 1, days[0])
  }
  if (kind === 'yearly_month_day') {
    const month = Math.max(1, Math.min(12, Number(payload?.month ?? 1))) - 1
    const thisYear = monthlyDate(anchor.getFullYear(), month, day)
    return thisYear >= anchor ? thisYear : monthlyDate(anchor.getFullYear() + 1, month, day)
  }
  if (kind === 'daily_weekdays') {
    const weekdays =
      Array.isArray(payload?.weekdays) && payload?.weekdays.length
        ? (payload.weekdays as number[])
        : [0, 1, 2, 3, 4]
    const allowed = new Set(weekdays)
    const probe = new Date(anchor)
    while (!allowed.has(probe.getDay() === 0 ? 6 : probe.getDay() - 1)) {
      probe.setDate(probe.getDate() + 1)
    }
    return startOfDay(probe)
  }
  if (kind === 'weekly_weekday') {
    const weekday = Math.max(0, Math.min(6, Number(payload?.weekday ?? 0)))
    const jsWeekday = weekday === 6 ? 0 : weekday + 1
    const delta = (jsWeekday - anchor.getDay() + 7) % 7
    const result = new Date(anchor)
    result.setDate(result.getDate() + delta)
    return startOfDay(result)
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
  return null
}

const previousOccurrenceBefore = (
  value: Date,
  kind: string,
  payload: Record<string, unknown> | null,
  fallbackDay: number,
) => {
  const current = startOfDay(value)
  const dayFromContract = fallbackDay || 1
  const day = Number(payload?.day ?? dayFromContract)
  if (kind === 'monthly_day') {
    return monthlyDate(current.getFullYear(), current.getMonth() - 1, day)
  }
  if (kind === 'monthly_last_day') {
    return monthlyDate(current.getFullYear(), current.getMonth() - 1, 31)
  }
  if (kind === 'twice_monthly') {
    const d1 = Number(payload?.day_1 ?? 1)
    const d2 = Number(payload?.day_2 ?? 15)
    const [low, high] = [d1, d2].sort((a, b) => a - b)
    const currentDay = current.getDate()
    const currentMonthHigh = monthlyDate(current.getFullYear(), current.getMonth(), high)
    if (currentDay === currentMonthHigh.getDate()) {
      return monthlyDate(current.getFullYear(), current.getMonth(), low)
    }
    return monthlyDate(current.getFullYear(), current.getMonth() - 1, high)
  }
  if (kind === 'yearly_month_day') {
    const month = Math.max(1, Math.min(12, Number(payload?.month ?? 1))) - 1
    return monthlyDate(current.getFullYear() - 1, month, day)
  }
  if (kind === 'daily_weekdays') {
    const weekdays =
      Array.isArray(payload?.weekdays) && payload?.weekdays.length
        ? (payload.weekdays as number[])
        : [0, 1, 2, 3, 4]
    const allowed = new Set(weekdays)
    const probe = new Date(current)
    probe.setDate(probe.getDate() - 1)
    while (!allowed.has(probe.getDay() === 0 ? 6 : probe.getDay() - 1)) {
      probe.setDate(probe.getDate() - 1)
    }
    return startOfDay(probe)
  }
  if (kind === 'weekly_weekday') {
    const probe = new Date(current)
    probe.setDate(probe.getDate() - 7)
    return startOfDay(probe)
  }
  if (kind === 'biweekly_weekday') {
    const probe = new Date(current)
    probe.setDate(probe.getDate() - 14)
    return startOfDay(probe)
  }
  const probe = new Date(current)
  probe.setDate(probe.getDate() - 1)
  return occurrenceOnOrAfter(startOfDay(probe), kind, payload, fallbackDay)
}

const advanceOccurrence = (
  value: Date,
  kind: string,
  payload: Record<string, unknown> | null,
  fallbackDay: number,
) => {
  const probe = new Date(value)
  probe.setDate(probe.getDate() + 1)
  return occurrenceOnOrAfter(startOfDay(probe), kind, payload, fallbackDay)
}

const nextPaymentDate = (contract: ContractPayload) => {
  const today = startOfDay(new Date())
  const { kind, payload } = parseContractPeriod(contract)
  const dayFromContract = contract.payment_day || 1
  if (!kind) {
    return null
  }
  let next = occurrenceOnOrAfter(today, kind, payload, dayFromContract)
  if (!next) {
    return null
  }

  const paidRaw = contract.last_payment_date?.slice(0, 10)
  if (paidRaw) {
    const paidDate = startOfDay(new Date(`${paidRaw}T00:00:00`))
    if (!Number.isNaN(paidDate.getTime())) {
      const expectedLast = previousOccurrenceBefore(next, kind, payload, dayFromContract)
      if (expectedLast && paidDate > expectedLast && paidDate < next) {
        const nextAfter = advanceOccurrence(next, kind, payload, dayFromContract)
        if (nextAfter) {
          next = nextAfter
        }
      }
    }
  }
  return next
}

const formatPaymentDate = (value: Date | null) => {
  if (!value) {
    return 'Unknown'
  }
  const month = value.toLocaleString('en-US', { month: 'long' })
  return `${month} ${ordinal(value.getDate())}`
}

const nextPaymentTooltip = (contract: ContractPayload) => `next payment: ${formatPaymentDate(nextPaymentDate(contract))}`

const nextPaymentCountdownLabel = (contract: ContractPayload) => {
  const next = nextPaymentDate(contract)
  if (!next) {
    return 'Next payment: Unknown'
  }
  const today = startOfDay(new Date())
  const target = startOfDay(next)
  const days = Math.max(0, Math.floor((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)))
  return `Next payment: ${days} day${days === 1 ? '' : 's'}`
}

const lastUpdateTone = (raw?: string) => {
  if (!raw) {
    return 'clock-stale'
  }
  const parsed = new Date(raw)
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

const loadContracts = async () => {
  const params = props.forecastDate ? { as_of_date: props.forecastDate } : undefined
  contracts.value = await request.get<ContractPayload[]>('/contracts', { params })
}
const loadOrganizations = async () => {
  organizations.value = await request.get<OrganizationSuggestion[]>('/organizations')
}
const loadIcons = async () => {
  iconChoices.value = await request.get<IconListItem[]>('/icons')
}

const onContractTypePicked = (value: string) => {
  contractForm.value = makeContractForm()
  contractForm.value.type = value as ContractForm['type']
  contractForm.value.linked_account_id = props.accounts[0]?.id || ''
  editingContractId.value = null
  contractDialog.value = true
}

const closeContractDialog = () => {
  contractDialog.value = false
  editingContractId.value = null
}

const startEditContract = (contract: ContractPayload) => {
  activeTileMenuId.value = null
  contractForm.value = {
    ...makeContractForm(),
    ...contract,
    icon_type: contract.icon_type || 'Icon',
    last_payment_date: '',
  }
  editingContractId.value = contract.id
  contractDialog.value = true
}

const validateContractForm = () => {
  if (!contractForm.value.name?.trim()) {
    errorMessage.value = 'Contract name is required'
    snackbar.value = true
    return false
  }
  if (!contractForm.value.organization?.trim()) {
    errorMessage.value = 'Organization is required'
    snackbar.value = true
    return false
  }
  if (!contractForm.value.linked_account_id) {
    errorMessage.value = 'Linked account is required'
    snackbar.value = true
    return false
  }
  if (!contractForm.value.payment_day || contractForm.value.payment_day < 1 || contractForm.value.payment_day > 31) {
    errorMessage.value = 'Payment day is required (1-31)'
    snackbar.value = true
    return false
  }
  if (contractForm.value.type === 'transfer' && !contractForm.value.source_account_id) {
    errorMessage.value = 'Source account is required for transfer contracts'
    snackbar.value = true
    return false
  }
  return true
}

const submitContract = async () => {
  if (!validateContractForm()) {
    return
  }
  const payload = {
    ...contractForm.value,
    account_number: contractForm.value.account_number?.trim(),
    organization: contractForm.value.organization?.trim(),
    last_payment_date: contractForm.value.last_payment_date || null,
    payment_period: contractForm.value.payment_period || null,
    notes: contractForm.value.notes || null,
    url: contractForm.value.url || null,
    billing_day: contractForm.value.billing_day || null,
    source_account_id: contractForm.value.type === 'transfer' ? contractForm.value.source_account_id || null : null,
  }
  if (editingContractId.value) {
    await request.put(`/contracts/${editingContractId.value}`, payload)
  } else {
    await request.post('/contracts', payload)
  }
  closeContractDialog()
  await loadContracts()
}

const moveContractLeft = async (section: Section, index: number, event?: MouseEvent) => {
  ;(event?.currentTarget as HTMLButtonElement | null)?.blur()
  if (index <= 0) {
    return
  }
  const current = section.contracts[index]
  const left = section.contracts[index - 1]
  const leftOfLeft = section.contracts[index - 2]
  const newRank = leftOfLeft ? (left.rank + leftOfLeft.rank) / 2 : left.rank + 1
  await request.put(`/contracts/${current.id}/rank`, { rank: newRank })
  await loadContracts()
}

const moveContractRight = async (section: Section, index: number, event?: MouseEvent) => {
  ;(event?.currentTarget as HTMLButtonElement | null)?.blur()
  if (index >= section.contracts.length - 1) {
    return
  }
  const current = section.contracts[index]
  const right = section.contracts[index + 1]
  const rightOfRight = section.contracts[index + 2]
  const newRank = rightOfRight ? (right.rank + rightOfRight.rank) / 2 : right.rank - 1
  await request.put(`/contracts/${current.id}/rank`, { rank: newRank })
  await loadContracts()
}

const toggleTileMenu = (contractId: string) => {
  activeTileMenuId.value = activeTileMenuId.value === contractId ? null : contractId
}

const openDeleteContract = (contractId: string) => {
  activeTileMenuId.value = null
  pendingDeleteContractId.value = contractId
  deleteContractDialog.value = true
}

const openUpdateDialog = (contract: ContractPayload) => {
  activeTileMenuId.value = null
  updatingContract.value = contract
  updateForm.value = {
    last_payment_date: contract.last_payment_date?.slice(0, 10) || '',
    expiration_date: contract.expiration_date?.slice(0, 10) || '',
  }
  updateDialog.value = true
}

const closeUpdateDialog = () => {
  updateDialog.value = false
  updatingContract.value = null
  updateForm.value = {}
}

const submitUpdateDialog = async () => {
  if (!updatingContract.value) {
    return
  }
  if (updateForm.value.last_payment_date) {
    const todayIso = new Date().toISOString().slice(0, 10)
    if (updateForm.value.last_payment_date > todayIso) {
      errorMessage.value = 'Last payment date cannot be in the future'
      snackbar.value = true
      return
    }
  }
  await request.put(`/contracts/${updatingContract.value.id}`, {
    last_payment_date: updateForm.value.last_payment_date || null,
    expiration_date: updateForm.value.expiration_date || null,
  })
  closeUpdateDialog()
  await loadContracts()
}

const closeDeleteContractDialog = () => {
  deleteContractDialog.value = false
  pendingDeleteContractId.value = null
}

const confirmDeleteContract = async () => {
  if (!pendingDeleteContractId.value) {
    return
  }
  await request.delete(`/contracts/${pendingDeleteContractId.value}`)
  closeDeleteContractDialog()
  await loadContracts()
}

const openIconUploadPicker = () => {
  iconFileInput.value?.click()
}

const openIconPickerModal = () => {
  iconPickerDraftId.value = contractForm.value.icon_id
  iconPickerDraftType.value = contractForm.value.icon_type || 'Icon'
  iconPickerDialog.value = true
}

const cancelIconPickerModal = () => {
  iconPickerDialog.value = false
  closeIconContextMenu()
}

const acceptIconPickerModal = () => {
  contractForm.value.icon_id = iconPickerDraftType.value === 'Icon' ? iconPickerDraftId.value : undefined
  contractForm.value.icon_type = iconPickerDraftType.value
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

const selectGeneratedIcon = (variant: 'Letters' | 'Gravatar') => {
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
  if (contractForm.value.icon_id === iconId && contractForm.value.icon_type === 'Icon') {
    contractForm.value.icon_id = undefined
  }
  if (iconPickerDraftId.value === iconId) {
    iconPickerDraftId.value = undefined
    iconPickerDraftType.value = 'Icon'
  }
  closeIconContextMenu()
  await loadIcons()
}

const uploadIcon = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) {
    return
  }
  const form = new FormData()
  form.append('file', file)
  const uploaded = await request.post<{ id: string; hash: string }>('/icons', form)
  contractForm.value.icon_id = uploaded.id
  contractForm.value.icon_type = 'Icon'
  iconPickerDraftId.value = uploaded.id
  iconPickerDraftType.value = 'Icon'
  await loadIcons()
  input.value = ''
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
}

onMounted(loadContracts)
onMounted(loadOrganizations)
onMounted(loadIcons)
onMounted(() => {
  window.addEventListener('click', onWindowClick)
})
onUnmounted(() => {
  window.removeEventListener('click', onWindowClick)
})

watch(
  () => props.forecastDate,
  async () => {
    await loadContracts()
  },
)

watch(
  () => contractForm.value.organization,
  (next) => {
    if (contractForm.value.icon_type !== 'Icon') {
      return
    }
    const key = next?.trim().toLowerCase()
    if (!key) {
      return
    }
    const iconId = organizationIconByName.value.get(key)
    if (iconId) {
      contractForm.value.icon_id = iconId
      contractForm.value.icon_type = 'Icon'
    }
    const orgUrl = organizationUrlByName.value.get(key)
    if (orgUrl && !contractForm.value.url) {
      contractForm.value.url = orgUrl
    }
  },
)
</script>

<style scoped>
@import './sharedTile.css';

.section-wrap {
  margin-top: 0.75rem;
}

.section-title {
  margin: 0 0 0.75rem;
}

.tile-automatic-icon {
  position: absolute;
  right: 0.75rem;
  top: 0.42rem;
  width: 18px;
  height: 18px;
  object-fit: contain;
}

.empty-state {
  color: var(--cds-text-secondary);
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

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.7rem;
}

.modal-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.4rem;
}

.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.contract-type-readonly {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bank-label {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #475569;
  font-weight: 700;
}

.contract-type-readonly-value {
  min-height: 2.5rem;
  display: flex;
  align-items: center;
  padding: 0 0.75rem;
  border-bottom: 1px solid var(--cds-border-strong-01);
}

.notes-field {
  grid-column: 1 / -1;
}

.icon-picker {
  align-self: end;
}

.icon-picker-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  justify-content: flex-start;
}

.icon-upload-input {
  display: none;
}

.icon-preview {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid var(--cds-border-subtle-01);
}

.icon-preview--empty {
  background: #e2e8f0;
}

.icon-modal-card {
  width: min(920px, 100%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.generated-icon-actions {
  display: flex;
  gap: 0.5rem;
}

.icon-grid-scroll {
  margin-top: 0.75rem;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 0.5rem;
  max-height: 58vh;
  overflow-y: auto;
}

.icon-choice {
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  min-height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-choice--none {
  font-size: 0.85rem;
}

.icon-choice--selected {
  border-color: #0f62fe;
  box-shadow: 0 0 0 1px #0f62fe;
}

.icon-context-menu {
  position: fixed;
  z-index: 120;
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
}

.icon-context-menu-item {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 0.55rem 0.75rem;
  text-align: left;
  cursor: pointer;
}

.icon-context-menu-item:hover {
  background: var(--cds-layer-hover);
}

.icon-modal-actions {
  margin-top: 0.75rem;
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

@media (max-width: 1000px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
