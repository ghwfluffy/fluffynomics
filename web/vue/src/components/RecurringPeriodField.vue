<template>
  <div class="period-field">
    <label class="bank-label">{{ label }}</label>
    <div class="period-box">
      <span class="period-text">{{ summary }}</span>
      <button class="cds--btn cds--btn--ghost" type="button" @click="dialogOpen = true">Edit</button>
    </div>

    <div v-if="dialogOpen" class="modal-backdrop" @click.self="dialogOpen = false">
      <section class="modal-card cds--tile">
        <h3 class="modal-title">Recurring Period</h3>
        <div class="modal-grid">
          <UnifiedDropdown v-model="kindValue" label="Period Type" :options="kindOptions" />

          <div v-if="draft.kind === 'monthly_day'" class="cds--form-item">
            <label class="cds--label">Day of Month</label>
            <input v-model.number="draft.day" class="cds--text-input" type="number" min="1" max="31" />
          </div>

          <template v-if="draft.kind === 'twice_monthly'">
            <div class="cds--form-item">
              <label class="cds--label">First Day</label>
              <input v-model.number="draft.day_1" class="cds--text-input" type="number" min="1" max="31" />
            </div>
            <div class="cds--form-item">
              <label class="cds--label">Second Day</label>
              <input v-model.number="draft.day_2" class="cds--text-input" type="number" min="1" max="31" />
            </div>
          </template>

          <template v-if="draft.kind === 'yearly_month_day'">
            <div class="cds--form-item">
              <label class="cds--label">Month</label>
              <select v-model.number="draft.month" class="cds--select-input">
                <option v-for="month in monthOptions" :key="month.value" :value="month.value">{{ month.label }}</option>
              </select>
            </div>
            <div class="cds--form-item">
              <label class="cds--label">Day</label>
              <input v-model.number="draft.day" class="cds--text-input" type="number" min="1" max="31" />
            </div>
          </template>

          <template v-if="draft.kind === 'every_n_months_day'">
            <div class="cds--form-item">
              <label class="cds--label">Every N Months</label>
              <input v-model.number="draft.interval_months" class="cds--text-input" type="number" min="1" max="120" />
            </div>
            <div class="cds--form-item">
              <label class="cds--label">Day</label>
              <input v-model.number="draft.day" class="cds--text-input" type="number" min="1" max="31" />
            </div>
            <div class="cds--form-item">
              <label class="cds--label">Start Date</label>
              <input v-model="draft.start_date" class="cds--text-input" type="date" />
            </div>
          </template>

          <template v-if="draft.kind === 'every_n_years_month_day'">
            <div class="cds--form-item">
              <label class="cds--label">Every N Years</label>
              <input v-model.number="draft.interval_years" class="cds--text-input" type="number" min="1" max="100" />
            </div>
            <div class="cds--form-item">
              <label class="cds--label">Month</label>
              <select v-model.number="draft.month" class="cds--select-input">
                <option v-for="month in monthOptions" :key="month.value" :value="month.value">{{ month.label }}</option>
              </select>
            </div>
            <div class="cds--form-item">
              <label class="cds--label">Day</label>
              <input v-model.number="draft.day" class="cds--text-input" type="number" min="1" max="31" />
            </div>
            <div class="cds--form-item">
              <label class="cds--label">Start Date</label>
              <input v-model="draft.start_date" class="cds--text-input" type="date" />
            </div>
          </template>

          <div v-if="draft.kind === 'daily_weekdays'" class="weekday-grid">
            <button
              v-for="weekday in weekdayOptions"
              :key="weekday.value"
              type="button"
              class="weekday-btn"
              :class="{ 'weekday-btn--active': selectedWeekdays.has(weekday.value) }"
              @click="toggleWeekday(weekday.value)"
            >
              {{ weekday.label }}
            </button>
          </div>

          <div v-if="draft.kind === 'weekly_weekday'" class="cds--form-item">
            <label class="cds--label">Weekday</label>
            <select v-model.number="draft.weekday" class="cds--select-input">
              <option v-for="weekday in weekdayOptions" :key="weekday.value" :value="weekday.value">{{ weekday.label }}</option>
            </select>
          </div>

          <template v-if="draft.kind === 'biweekly_weekday'">
            <div class="cds--form-item">
              <label class="cds--label">Weekday</label>
              <select v-model.number="draft.weekday" class="cds--select-input">
                <option v-for="weekday in weekdayOptions" :key="weekday.value" :value="weekday.value">{{ weekday.label }}</option>
              </select>
            </div>
            <div class="cds--form-item">
              <label class="cds--label">Start Date</label>
              <input v-model="draft.start_date" class="cds--text-input" type="date" />
            </div>
          </template>

          <template v-if="draft.kind === 'every_n_weeks_weekday'">
            <div class="cds--form-item">
              <label class="cds--label">Every N Weeks</label>
              <input v-model.number="draft.interval_weeks" class="cds--text-input" type="number" min="1" max="520" />
            </div>
            <div class="cds--form-item">
              <label class="cds--label">Weekday</label>
              <select v-model.number="draft.weekday" class="cds--select-input">
                <option v-for="weekday in weekdayOptions" :key="weekday.value" :value="weekday.value">{{ weekday.label }}</option>
              </select>
            </div>
            <div class="cds--form-item">
              <label class="cds--label">Start Date</label>
              <input v-model="draft.start_date" class="cds--text-input" type="date" />
            </div>
          </template>
        </div>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" @click="dialogOpen = false">Cancel</button>
          <button class="cds--btn cds--btn--primary" type="button" @click="saveDraft">Save</button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import UnifiedDropdown from '@/components/UnifiedDropdown.vue'

type RecurringKind =
  | 'monthly_day'
  | 'monthly_last_day'
  | 'twice_monthly'
  | 'every_n_months_day'
  | 'yearly_month_day'
  | 'every_n_years_month_day'
  | 'daily_weekdays'
  | 'weekly_weekday'
  | 'biweekly_weekday'
  | 'every_n_weeks_weekday'

interface RecurringPayload {
  kind: RecurringKind
  day?: number
  day_1?: number
  day_2?: number
  month?: number
  interval_months?: number
  interval_years?: number
  interval_weeks?: number
  weekdays?: number[]
  weekday?: number
  start_date?: string
}

const props = defineProps<{
  modelValue?: string
  label: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
}>()

const dialogOpen = ref(false)
const draft = ref<RecurringPayload>({
  kind: 'monthly_day',
  day: 1,
})

const kindOptions = [
  { label: 'Monthly on a day', value: 'monthly_day' },
  { label: 'Monthly on last day', value: 'monthly_last_day' },
  { label: 'Twice monthly', value: 'twice_monthly' },
  { label: 'Every N months', value: 'every_n_months_day' },
  { label: 'Yearly on month/day', value: 'yearly_month_day' },
  { label: 'Every N years', value: 'every_n_years_month_day' },
  { label: 'Daily on weekdays', value: 'daily_weekdays' },
  { label: 'Weekly on weekday', value: 'weekly_weekday' },
  { label: 'Every 2 weeks', value: 'biweekly_weekday' },
  { label: 'Every N weeks', value: 'every_n_weeks_weekday' },
]

const kindValue = computed<string | undefined>({
  get: () => draft.value.kind,
  set: (next) => {
    if (!next) {
      return
    }
    draft.value.kind = next as RecurringKind
  },
})

const weekdayOptions = [
  { label: 'Monday', value: 0 },
  { label: 'Tuesday', value: 1 },
  { label: 'Wednesday', value: 2 },
  { label: 'Thursday', value: 3 },
  { label: 'Friday', value: 4 },
  { label: 'Saturday', value: 5 },
  { label: 'Sunday', value: 6 },
]

const monthOptions = [
  { label: 'January', value: 1 },
  { label: 'February', value: 2 },
  { label: 'March', value: 3 },
  { label: 'April', value: 4 },
  { label: 'May', value: 5 },
  { label: 'June', value: 6 },
  { label: 'July', value: 7 },
  { label: 'August', value: 8 },
  { label: 'September', value: 9 },
  { label: 'October', value: 10 },
  { label: 'November', value: 11 },
  { label: 'December', value: 12 },
]

const parseOrDefault = (raw: string | undefined): RecurringPayload => {
  if (!raw) {
    return { kind: 'monthly_day', day: 1 }
  }
  try {
    return JSON.parse(raw) as RecurringPayload
  } catch {
    return { kind: 'monthly_day', day: 1 }
  }
}

watch(
  () => props.modelValue,
  (next) => {
    draft.value = parseOrDefault(next)
  },
  { immediate: true },
)

const selectedWeekdays = computed(() => new Set(draft.value.weekdays || []))

const summary = computed(() => {
  const period = draft.value
  if (period.kind === 'monthly_day') {
    return `Monthly on the ${ordinal(period.day || 1)}`
  }
  if (period.kind === 'monthly_last_day') {
    return 'Monthly on the last day of the month'
  }
  if (period.kind === 'twice_monthly') {
    return `Twice monthly on the ${ordinal(period.day_1 || 1)} and ${ordinal(period.day_2 || 15)}`
  }
  if (period.kind === 'yearly_month_day') {
    const monthName = monthOptions.find((item) => item.value === period.month)?.label || 'January'
    return `Yearly on ${monthName} ${ordinal(period.day || 1)}`
  }
  if (period.kind === 'every_n_months_day') {
    const interval = Math.max(1, Number(period.interval_months || 1))
    return `Every ${interval} month${interval === 1 ? '' : 's'} on the ${ordinal(period.day || 1)}`
  }
  if (period.kind === 'every_n_years_month_day') {
    const interval = Math.max(1, Number(period.interval_years || 1))
    const monthName = monthOptions.find((item) => item.value === period.month)?.label || 'January'
    return `Every ${interval} year${interval === 1 ? '' : 's'} on ${monthName} ${ordinal(period.day || 1)}`
  }
  if (period.kind === 'daily_weekdays') {
    const symbols = (period.weekdays || [])
      .slice()
      .sort((a, b) => a - b)
      .map((weekday) => ['M', 'T', 'W', 'R', 'F', 'S', 'U'][weekday])
      .join('')
    return `Daily on ${symbols || 'MTWRF'}`
  }
  const weekdayName = weekdayOptions.find((item) => item.value === period.weekday)?.label || 'Monday'
  if (period.kind === 'biweekly_weekday') {
    return `Every 2 weeks on ${weekdayName}`
  }
  if (period.kind === 'every_n_weeks_weekday') {
    const interval = Math.max(1, Number(period.interval_weeks || 1))
    return `Every ${interval} weeks on ${weekdayName}`
  }
  return `Weekly on ${weekdayName}`
})

const toggleWeekday = (value: number) => {
  const next = new Set(draft.value.weekdays || [])
  if (next.has(value)) {
    next.delete(value)
  } else {
    next.add(value)
  }
  draft.value.weekdays = [...next].sort((a, b) => a - b)
}

const saveDraft = () => {
  if (draft.value.kind === 'daily_weekdays' && (!draft.value.weekdays || !draft.value.weekdays.length)) {
    draft.value.weekdays = [0, 1, 2, 3, 4]
  }
  if (draft.value.kind === 'biweekly_weekday') {
    if (draft.value.weekday === undefined) {
      draft.value.weekday = 0
    }
    if (!draft.value.start_date) {
      draft.value.start_date = new Date().toISOString().slice(0, 10)
    }
  }
  if (draft.value.kind === 'every_n_weeks_weekday') {
    draft.value.interval_weeks = Math.max(1, Number(draft.value.interval_weeks || 1))
    if (draft.value.weekday === undefined) {
      draft.value.weekday = 0
    }
    if (!draft.value.start_date) {
      draft.value.start_date = new Date().toISOString().slice(0, 10)
    }
  }
  if (draft.value.kind === 'every_n_months_day') {
    draft.value.interval_months = Math.max(1, Number(draft.value.interval_months || 1))
    draft.value.day = Math.max(1, Math.min(31, Number(draft.value.day || 1)))
    if (!draft.value.start_date) {
      draft.value.start_date = new Date().toISOString().slice(0, 10)
    }
  }
  if (draft.value.kind === 'every_n_years_month_day') {
    draft.value.interval_years = Math.max(1, Number(draft.value.interval_years || 1))
    draft.value.month = Math.max(1, Math.min(12, Number(draft.value.month || 1)))
    draft.value.day = Math.max(1, Math.min(31, Number(draft.value.day || 1)))
    if (!draft.value.start_date) {
      draft.value.start_date = new Date().toISOString().slice(0, 10)
    }
  }
  emit('update:modelValue', JSON.stringify(draft.value))
  dialogOpen.value = false
}

const ordinal = (value: number) => {
  const number = Math.max(1, Math.min(31, value))
  if (number >= 11 && number <= 13) {
    return `${number}th`
  }
  const suffixByDigit: Record<number, string> = {
    1: 'st',
    2: 'nd',
    3: 'rd',
  }
  const suffix = suffixByDigit[number % 10] || 'th'
  return `${number}${suffix}`
}
</script>

<style scoped>
.period-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bank-label {
  font-size: 0.75rem;
  color: var(--cds-text-secondary);
  font-weight: 600;
}

.period-box {
  border: 1px solid var(--cds-border-strong-01);
  border-radius: 0;
  background: var(--cds-layer);
  padding: 8px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.period-text {
  font-size: 0.92rem;
  color: var(--cds-text-primary);
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 1200;
}

.modal-card {
  width: min(640px, 100%);
  padding: 14px;
}

.modal-title {
  margin: 0 0 10px;
}

.modal-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.weekday-grid {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.weekday-btn {
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  color: var(--cds-text-primary);
  padding: 7px 10px;
  cursor: pointer;
}

.weekday-btn--active {
  border-color: var(--cds-link-primary);
  background: #e8f4ff;
}

.modal-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 720px) {
  .modal-grid {
    grid-template-columns: 1fr;
  }
}
</style>
