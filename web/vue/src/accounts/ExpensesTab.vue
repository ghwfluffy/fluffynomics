<template>
  <section class="section-wrap">
    <div class="top-controls">
      <ViewModeToggle v-model="viewMode" />
    </div>
    <div v-if="viewMode !== 'table'" class="action-row">
      <button class="cds--btn cds--btn--primary mp-add-btn" type="button" @click="openCreate">Add Expense</button>
    </div>

    <template v-if="viewMode !== 'table'">
      <section v-for="section in sections" :key="section.key" class="section-wrap">
        <CollapsibleSectionHeader
          :title="section.label"
          :collapsed="isExpenseSectionCollapsed(section)"
          :collapsible="section.key === 'legacy'"
          @toggle="toggleExpenseSection(section)"
        />
        <div
          v-if="!isExpenseSectionCollapsed(section) && section.items.length"
          class="section-grid"
          :class="{ 'section-grid--icons': viewMode === 'icons' }"
        >
          <article
            v-for="item in section.items"
            :key="item.id"
            class="cds--tile account-tile"
            :class="{
              'account-tile--icon': viewMode === 'icons',
              'account-tile--icon-expanded': viewMode === 'icons' && isExpenseIconExpanded(item.id),
            }"
          >
            <button
              v-if="viewMode === 'icons'"
              class="icon-card-trigger"
              type="button"
              :aria-expanded="isExpenseIconExpanded(item.id) ? 'true' : 'false'"
              :aria-label="`${isExpenseIconExpanded(item.id) ? 'Collapse' : 'Expand'} ${item.name}`"
              @click="toggleExpenseIconExpanded(item.id)"
            >
              <img v-if="expenseIconUrl(item)" :src="expenseIconUrl(item)" class="icon-card-icon" alt="" />
              <div v-else class="icon-card-icon icon-card-icon--empty" aria-hidden="true"></div>
            </button>
            <template v-else>
              <img v-if="expenseIconUrl(item)" :src="expenseIconUrl(item)" class="tile-icon" alt="Expense icon" />
              <div v-else class="tile-icon tile-icon--empty" />
            </template>
            <div v-if="viewMode === 'icons'" class="icon-card-balance balance-liability">
              {{ cents(item.estimated_amount_cents) }}
            </div>
            <template v-if="viewMode === 'tiles' || isExpenseIconExpanded(item.id)">
              <div :class="viewMode === 'icons' ? 'icon-card-details' : ''">
                <div class="tile-title">{{ item.name }}</div>
                <div class="tile-sub">Last: {{ formatDate(item.last_expensed_date) }}</div>
                <div class="tile-sub">Next: {{ formatDate(item.next_expensed_date) }}</div>
                <div class="tile-balance balance-liability">Est. {{ cents(item.estimated_amount_cents) }}</div>
                <div class="tile-type">{{ frequencyLabel(item.general_frequency) }}<span v-if="!item.enabled"> • Disabled</span></div>
              </div>
              <div class="tile-actions">
                <button class="tile-menu-trigger" type="button" aria-label="Expense menu" @click.stop="toggleMenu(item.id)">
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
        <div v-else-if="!isExpenseSectionCollapsed(section)" class="cds--tile empty-state">No expenses yet.</div>
      </section>
    </template>

    <section v-else class="section-wrap">
      <div class="cds--data-table-container">
        <div class="table-toolbar-row">
          <DataTableControls
            v-model="tableFilter"
            placeholder="Filter expenses"
            :filters="expenseColumnFilters"
            @update:filter="onExpenseColumnFilterUpdate"
          />
          <button class="cds--btn cds--btn--primary mp-add-btn" type="button" @click="openCreate">Add Expense</button>
        </div>
        <table class="cds--data-table cds--data-table--md">
          <thead>
            <tr>
              <th></th>
              <th><button class="sort-btn" type="button" @click="setSort('name')">Name</button></th>
              <th><button class="sort-btn" type="button" @click="setSort('category')">Category</button></th>
              <th><button class="sort-btn" type="button" @click="setSort('estimated')">Estimated</button></th>
              <th><button class="sort-btn" type="button" @click="setSort('frequency')">Frequency</button></th>
              <th><button class="sort-btn" type="button" @click="setSort('last')">Last</button></th>
              <th><button class="sort-btn" type="button" @click="setSort('next')">Next</button></th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in filteredExpenses" :key="item.id">
              <td class="table-icon-cell">
                <img v-if="expenseIconUrl(item)" :src="expenseIconUrl(item)" class="table-icon" alt="Expense icon" />
                <div v-else class="table-icon table-icon--empty"></div>
              </td>
              <td>{{ item.name }}</td>
              <td>{{ expenseCategoryLabel(item) }}</td>
              <td>{{ cents(item.estimated_amount_cents) }}</td>
              <td>{{ frequencyLabel(item.general_frequency) }}</td>
              <td>{{ formatDate(item.last_expensed_date) }}</td>
              <td>{{ formatDate(item.next_expensed_date) }}</td>
              <td class="table-actions-cell">
                <div class="table-overflow-menu">
                  <button class="tile-menu-trigger table-menu-trigger" type="button" aria-label="Expense menu" @click.stop="toggleMenu(item.id)">
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
        <h3>{{ editingId ? 'Edit Expense' : 'Create Expense' }}</h3>
        <form class="form-grid" @submit.prevent="saveExpense">
          <BankField v-model="form.name" label="Name" required />
          <UnifiedDropdown v-model="form.category" label="Category" searchable allow-custom required :options="categoryOptions" />

          <DollarField v-model="form.estimated_amount_cents" label="Estimated Amount" />
          <UnifiedDropdown v-model="form.linked_account_id" label="Linked Account" searchable required :options="accountDropdownOptions" />
          <div class="icon-picker">
            <label class="bank-label">Expense Icon</label>
            <div class="icon-picker-row">
              <img v-if="selectedFormIconUrl" :src="selectedFormIconUrl" class="icon-preview" alt="Selected icon" />
              <div v-else class="icon-preview icon-preview--empty" />
              <button type="button" class="cds--btn cds--btn--ghost icon-upload-btn" @click="openIconPickerModal">Choose Icon</button>
              <input ref="iconFileInput" class="icon-upload-input" type="file" accept="image/*" @change="uploadExpenseIcon" />
              <button type="button" class="cds--btn cds--btn--ghost icon-upload-btn" @click="openIconUploadPicker">Upload New</button>
            </div>
          </div>

          <RecurringPeriodField v-model="form.general_frequency" label="Frequency" />
          <div class="date-row">
            <BankField v-model="form.last_expensed_date" label="Last Expensed Date" type="date" />
            <div class="next-date-field">
              <BankField v-model="form.next_expensed_date" label="Next Expensed Date" type="date" />
              <button type="button" class="cds--btn cds--btn--ghost clear-next-btn" @click="clearNextExpensedDate">Clear Next Date</button>
            </div>
          </div>
          <BankField v-model="form.notes" class="notes-field" label="Notes" multiline />

          <div class="modal-actions">
            <button class="cds--btn cds--btn--ghost" type="button" @click="closeDialog">Cancel</button>
            <button class="cds--btn cds--btn--primary" type="submit">{{ editingId ? 'Save Changes' : 'Create Expense' }}</button>
          </div>
        </form>
      </section>
    </div>

    <div v-if="iconPickerDialog" class="modal-backdrop">
      <section class="icon-modal-card cds--tile">
        <h3>Choose Icon</h3>
        <div class="generated-icon-actions">
          <button type="button" class="cds--btn cds--btn--secondary" @click="selectGeneratedIcon('Letters')">Use Letters Icon</button>
          <button type="button" class="cds--btn cds--btn--secondary" @click="selectGeneratedIcon('Gravatar')">Use Gravatar Style</button>
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
            @click="selectCatalogIcon(icon.id)"
          >
            <img :src="iconUrl(icon.id)" class="icon-preview" alt="Icon choice" />
          </button>
        </div>
        <div class="icon-modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="cancelIconPickerModal">Cancel</button>
          <button class="cds--btn cds--btn--primary" type="button" @click="acceptIconPickerModal">Accept</button>
        </div>
      </section>
    </div>

    <div v-if="deleteId" class="modal-backdrop">
      <section class="confirm-card cds--tile">
        <h3>Delete Expense</h3>
        <p>Are you sure you want to delete this expense?</p>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="deleteId = null">Cancel</button>
          <button class="cds--btn cds--btn--danger" type="button" @click="confirmDelete">Delete</button>
        </div>
      </section>
    </div>

    <div v-if="updateDialog" class="modal-backdrop">
      <section class="confirm-card cds--tile">
        <h3>Update Expense</h3>
        <div class="form-grid form-grid--single">
          <div class="bank-field">
            <label class="bank-label">Enabled</label>
            <label class="check-row"><input v-model="updateForm.enabled" type="checkbox" /> <span>Enabled</span></label>
          </div>
          <div class="date-row date-row--update">
            <BankField v-model="updateForm.last_expensed_date" label="Last Expensed Date" type="date" />
            <div class="next-date-field">
              <BankField v-model="updateForm.next_expensed_date" label="Next Expensed Date" type="date" />
              <button type="button" class="cds--btn cds--btn--ghost clear-next-btn" @click="updateForm.next_expensed_date = ''">
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
import ViewModeToggle from '@/components/ViewModeToggle.vue'
import DataTableControls from '@/components/DataTableControls.vue'
import BankField from '@/components/BankField.vue'
import DollarField from '@/components/DollarField.vue'
import RecurringPeriodField from '@/components/RecurringPeriodField.vue'
import UnifiedDropdown from '@/components/UnifiedDropdown.vue'
import CollapsibleSectionHeader from '@/components/CollapsibleSectionHeader.vue'

interface Expense {
  id: string
  name: string
  category: string
  notes?: string
  linked_account_id?: string
  icon_id?: string
  icon_type: 'Letters' | 'Gravatar' | 'Icon'
  estimated_amount_cents: number
  enabled: boolean
  general_frequency?: string
  last_expensed_date?: string
  next_expensed_date?: string
  next_date_is_static: boolean
}

interface IconListItem {
  id: string
  is_default?: boolean
}

interface LinkedAccount {
  id: string
  name: string
  type: string
}

interface ExpenseSection {
  key: string
  label: string
  items: Expense[]
}

const props = withDefaults(defineProps<{ viewMode?: 'tiles' | 'icons' | 'table' }>(), {
  viewMode: 'icons',
})
const emit = defineEmits<{ (event: 'update:viewMode', value: 'tiles' | 'icons' | 'table'): void }>()

const viewMode = computed({
  get: () => props.viewMode,
  set: (value: 'tiles' | 'icons' | 'table') => emit('update:viewMode', value),
})

const expenses = ref<Expense[]>([])
const linkedAccounts = ref<LinkedAccount[]>([])
const iconChoices = ref<IconListItem[]>([])
const tableFilter = ref('')
const categoryFilterValues = ref<string[]>([])
const enabledFilterValues = ref<string[]>([])
const sortKey = ref<'name' | 'category' | 'estimated' | 'frequency' | 'last' | 'next'>('category')
const sortDir = ref<'asc' | 'desc'>('asc')
const dialogOpen = ref(false)
const deleteId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const activeMenuId = ref<string | null>(null)
const expandedExpenseIconIds = ref<Set<string>>(new Set())
const legacyExpensesSectionOpen = ref(false)
const updateDialog = ref(false)
const updatingId = ref<string | null>(null)
const iconFileInput = ref<HTMLInputElement | null>(null)
const iconPickerDialog = ref(false)
const iconPickerDraftId = ref<string | undefined>(undefined)
const iconPickerDraftType = ref<'Letters' | 'Gravatar' | 'Icon'>('Letters')

const form = ref({
  name: '',
  category: 'Living',
  notes: '',
  linked_account_id: '',
  icon_id: '',
  icon_type: 'Letters' as 'Letters' | 'Gravatar' | 'Icon',
  estimated_amount_cents: 0,
  enabled: true,
  general_frequency: '',
  last_expensed_date: '',
  next_expensed_date: '',
})

const categoryOptions = ['Living', 'Entertainment', 'Health', 'Digital', 'Financial', 'Work', 'Family'].map((value) => ({
  label: value,
  value,
}))
const accountDropdownOptions = computed(() =>
  linkedAccounts.value.map((account) => ({
    label: `${account.name} (${account.type.replaceAll('_', ' ')})`,
    value: account.id,
  })),
)

const expenseCategoryLabel = (item: Expense) => (item.enabled ? item.category : `Disabled ${item.category}`)

const expenseCategorySortValue = (item: Expense) => `${item.enabled ? '0' : '1'}:${item.category.toLowerCase()}`

const sections = computed<ExpenseSection[]>(() => {
  const byCat = new Map<string, Expense[]>()
  const legacyItems: Expense[] = []
  for (const item of expenses.value) {
    if (!item.enabled) {
      legacyItems.push(item)
      continue
    }
    const arr = byCat.get(item.category) || []
    arr.push(item)
    byCat.set(item.category, arr)
  }
  const grouped = Array.from(byCat.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([label, items]) => ({
      key: label,
      label,
      items,
    }))
  if (legacyItems.length) {
    grouped.push({
      key: 'legacy',
      label: 'Legacy',
      items: legacyItems,
    })
  }
  return grouped
})

const isExpenseSectionCollapsed = (section: ExpenseSection) => section.key === 'legacy' && !legacyExpensesSectionOpen.value

const toggleExpenseSection = (section: ExpenseSection) => {
  if (section.key !== 'legacy') {
    return
  }
  legacyExpensesSectionOpen.value = !legacyExpensesSectionOpen.value
}

const isExpenseIconExpanded = (expenseId: string) => expandedExpenseIconIds.value.has(expenseId)

const toggleExpenseIconExpanded = (expenseId: string) => {
  const next = new Set(expandedExpenseIconIds.value)
  if (next.has(expenseId)) {
    next.delete(expenseId)
  } else {
    next.add(expenseId)
  }
  expandedExpenseIconIds.value = next
}

const filteredExpenses = computed(() => {
  const needle = tableFilter.value.trim().toLowerCase()
  const filtered = expenses.value.filter((item) => {
    const matchesNeedle =
      !needle ||
      [item.name, item.category, expenseCategoryLabel(item), frequencyLabel(item.general_frequency), formatDate(item.last_expensed_date), formatDate(item.next_expensed_date)]
        .join(' ')
        .toLowerCase()
        .includes(needle)
    if (!matchesNeedle) {
      return false
    }
    if (categoryFilterValues.value.length && !categoryFilterValues.value.includes(item.category)) {
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
        ? a.name
        : sortKey.value === 'category'
          ? expenseCategorySortValue(a)
          : sortKey.value === 'estimated'
            ? a.estimated_amount_cents
            : sortKey.value === 'frequency'
              ? frequencyLabel(a.general_frequency)
              : sortKey.value === 'last'
                ? new Date(`${(a.last_expensed_date || '1900-01-01').slice(0, 10)}T00:00:00`).getTime()
                : new Date(`${(a.next_expensed_date || '1900-01-01').slice(0, 10)}T00:00:00`).getTime()
    const bv =
      sortKey.value === 'name'
        ? b.name
        : sortKey.value === 'category'
          ? expenseCategorySortValue(b)
          : sortKey.value === 'estimated'
            ? b.estimated_amount_cents
            : sortKey.value === 'frequency'
              ? frequencyLabel(b.general_frequency)
              : sortKey.value === 'last'
                ? new Date(`${(b.last_expensed_date || '1900-01-01').slice(0, 10)}T00:00:00`).getTime()
                : new Date(`${(b.next_expensed_date || '1900-01-01').slice(0, 10)}T00:00:00`).getTime()
    if (typeof av === 'number' && typeof bv === 'number') {
      return sortDir.value === 'asc' ? av - bv : bv - av
    }
    return sortDir.value === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av))
  })
})

const expenseCategoryOptions = computed(() =>
  Array.from(new Set(expenses.value.map((item) => item.category))).sort((a, b) => a.localeCompare(b)),
)
const expenseEnabledOptions = ['Enabled', 'Disabled']
const expenseColumnFilters = computed(() => [
  { key: 'category', label: 'Category', options: expenseCategoryOptions.value, selected: categoryFilterValues.value },
  { key: 'enabled', label: 'Status', options: expenseEnabledOptions, selected: enabledFilterValues.value },
])

const onExpenseColumnFilterUpdate = (payload: { key: string; selected: string[] }) => {
  if (payload.key === 'category') {
    categoryFilterValues.value = payload.selected
    return
  }
  if (payload.key === 'enabled') {
    enabledFilterValues.value = payload.selected
  }
}

const setSort = (key: typeof sortKey.value) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortKey.value = key
  sortDir.value = 'asc'
}

const cents = (value?: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format((value || 0) / 100)

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

const iconUrl = (iconId?: string) => (iconId ? `/api/icons/${iconId}` : '')
const generatedIconUrl = (iconType: 'Letters' | 'Gravatar', seed: string) =>
  iconType === 'Letters'
    ? `/api/icons/lettered/${encodeURIComponent(seed || 'Expense')}`
    : `/api/icons/gravatar/${encodeURIComponent(seed || 'Expense')}`

const resolveIconUrl = (iconId?: string, iconType?: 'Letters' | 'Gravatar' | 'Icon', seed?: string) => {
  if (iconType === 'Letters' || iconType === 'Gravatar') {
    return generatedIconUrl(iconType, seed || 'Expense')
  }
  return iconUrl(iconId)
}

const expenseIconUrl = (item: Expense) => resolveIconUrl(item.icon_id, item.icon_type, item.category || item.name)
const selectedFormIconUrl = computed(() =>
  resolveIconUrl(form.value.icon_id || undefined, form.value.icon_type, form.value.category || form.value.name),
)

const resetForm = () => {
  form.value = {
    name: '',
    category: 'Living',
    notes: '',
    linked_account_id: linkedAccounts.value[0]?.id || '',
    icon_id: '',
    icon_type: 'Letters',
    estimated_amount_cents: 0,
    enabled: true,
    general_frequency: '',
    last_expensed_date: '',
    next_expensed_date: '',
  }
}

const loadExpenses = async () => {
  expenses.value = await request.get<Expense[]>('/expenses')
}

const loadAccounts = async () => {
  linkedAccounts.value = await request.get<LinkedAccount[]>('/accounts')
}

const loadIcons = async () => {
  iconChoices.value = await request.get<IconListItem[]>('/icons')
}

const openCreate = () => {
  resetForm()
  editingId.value = null
  dialogOpen.value = true
}

const openEdit = (item: Expense) => {
  form.value = {
    name: item.name,
    category: item.category,
    notes: item.notes || '',
    linked_account_id: item.linked_account_id || '',
    icon_id: item.icon_id || '',
    icon_type: item.icon_type,
    estimated_amount_cents: item.estimated_amount_cents || 0,
    enabled: item.enabled ?? true,
    general_frequency: item.general_frequency || '',
    last_expensed_date: item.last_expensed_date || '',
    next_expensed_date: item.next_expensed_date || '',
  }
  editingId.value = item.id
  dialogOpen.value = true
  activeMenuId.value = null
}

const closeDialog = () => {
  dialogOpen.value = false
  editingId.value = null
}

const openIconPickerModal = () => {
  iconPickerDraftId.value = form.value.icon_id || undefined
  iconPickerDraftType.value = form.value.icon_type
  iconPickerDialog.value = true
}

const cancelIconPickerModal = () => {
  iconPickerDialog.value = false
}

const selectNoIcon = () => {
  iconPickerDraftType.value = 'Icon'
  iconPickerDraftId.value = undefined
}

const selectCatalogIcon = (iconId: string) => {
  iconPickerDraftType.value = 'Icon'
  iconPickerDraftId.value = iconId
}

const selectGeneratedIcon = (kind: 'Letters' | 'Gravatar') => {
  iconPickerDraftType.value = kind
  iconPickerDraftId.value = undefined
}

const acceptIconPickerModal = () => {
  form.value.icon_type = iconPickerDraftType.value
  form.value.icon_id = iconPickerDraftType.value === 'Icon' ? iconPickerDraftId.value || '' : ''
  iconPickerDialog.value = false
}

const openIconUploadPicker = () => {
  iconFileInput.value?.click()
}

const uploadExpenseIcon = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) {
    return
  }
  const body = new FormData()
  body.append('icon', file)
  const created = await request.post<{ icon_id: string }>('/icons', body)
  await loadIcons()
  form.value.icon_type = 'Icon'
  form.value.icon_id = created.icon_id
  target.value = ''
}

const clearNextExpensedDate = () => {
  form.value.next_expensed_date = ''
}

const saveExpense = async () => {
  const payload = {
    ...form.value,
    linked_account_id: form.value.linked_account_id || null,
    notes: form.value.notes || null,
    icon_id: form.value.icon_type === 'Icon' ? form.value.icon_id || null : null,
    general_frequency: form.value.general_frequency || null,
    last_expensed_date: form.value.last_expensed_date || null,
    next_expensed_date: form.value.next_expensed_date || null,
    next_date_is_static: Boolean(form.value.next_expensed_date),
    enabled: form.value.enabled,
  }
  if (editingId.value) {
    await request.put(`/expenses/${editingId.value}`, payload)
  } else {
    await request.post('/expenses', payload)
  }
  closeDialog()
  await loadExpenses()
}

const openDelete = (id: string) => {
  deleteId.value = id
  activeMenuId.value = null
}

const updateForm = ref({
  enabled: true,
  last_expensed_date: '',
  next_expensed_date: '',
})

const openUpdate = (item: Expense) => {
  updateForm.value = {
    enabled: item.enabled ?? true,
    last_expensed_date: item.last_expensed_date || '',
    next_expensed_date: item.next_expensed_date || '',
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
  if (!updatingId.value) {
    return
  }
  await request.put(`/expenses/${updatingId.value}`, {
    enabled: updateForm.value.enabled,
    last_expensed_date: updateForm.value.last_expensed_date || null,
    next_expensed_date: updateForm.value.next_expensed_date || null,
    next_date_is_static: Boolean(updateForm.value.next_expensed_date),
  })
  closeUpdateDialog()
  await loadExpenses()
}

const openFromCalendar = async (expenseId: string, action: 'edit' | 'update') => {
  let item = expenses.value.find((entry) => entry.id === expenseId)
  if (!item) {
    await loadExpenses()
    item = expenses.value.find((entry) => entry.id === expenseId)
  }
  if (!item) {
    return false
  }
  if (action === 'edit') {
    openEdit(item)
  } else {
    openUpdate(item)
  }
  return true
}

const confirmDelete = async () => {
  if (!deleteId.value) {
    return
  }
  await request.delete(`/expenses/${deleteId.value}`)
  deleteId.value = null
  await loadExpenses()
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
  if (iconPickerDialog.value) {
    cancelIconPickerModal()
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

onMounted(loadExpenses)
onMounted(loadAccounts)
onMounted(loadIcons)
onMounted(() => window.addEventListener('click', onWindowClick))
onMounted(() => window.addEventListener('keydown', onWindowKeyDown))
onUnmounted(() => window.removeEventListener('click', onWindowClick))
onUnmounted(() => window.removeEventListener('keydown', onWindowKeyDown))

defineExpose({
  openFromCalendar,
})
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
  object-fit: cover;
}

.table-icon--empty {
  background: #e2e8f0;
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

.icon-picker {
  display: flex;
  flex-direction: column;
}

.notes-field {
  grid-column: 1 / -1;
}

.icon-picker-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bank-label {
  display: block;
  margin-bottom: 6px;
  font-size: 0.75rem;
  color: var(--cds-text-secondary);
  font-weight: 600;
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

.section-wrap {
  margin-bottom: 1.25rem;
}

.section-title {
  margin: 0 0 0.75rem;
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

  .icon-grid-scroll {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .icon-grid-scroll {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
