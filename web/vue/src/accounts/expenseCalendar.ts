import { addDays, parseDateOnly, parseRecurringPayload, recurringOnOrAfter } from './calendarRecurrence.ts'

interface ScheduledExpense {
  enabled?: boolean
  general_frequency?: string
  next_expensed_date?: string
}

// Keep legacy schedules aligned with the expense API and scheduler.
const legacyPeriods: Record<string, Record<string, unknown>> = {
  daily: { kind: 'daily_weekdays', weekdays: [0, 1, 2, 3, 4, 5, 6] },
  weekly: { kind: 'weekly_weekday', weekday: 0 },
  biweekly: { kind: 'biweekly_weekday', weekday: 0, start_date: '2025-01-06' },
  monthly: { kind: 'monthly_day', day: 1 },
  yearly: { kind: 'yearly_month_day', month: 1, day: 1 },
}

export const expenseOccurrencesInRange = (expense: ScheduledExpense, start: Date, end: Date): Date[] => {
  const first = parseDateOnly(expense.next_expensed_date)
  if (expense.enabled === false || !first || first > end) {
    return []
  }

  // The API has already skipped any occurrence covered by an early expense.
  // An explicit next date is honored once; subsequent dates follow the cadence.
  const dates = first >= start ? [first] : []
  const raw = (expense.general_frequency || '').trim()
  const payload = legacyPeriods[raw.toLowerCase()] || parseRecurringPayload(raw)
  const kind = String(payload?.kind || '')
  if (!kind) {
    return dates
  }

  let search = addDays(first, 1)
  if (search < start) {
    search = start
  }
  let next = recurringOnOrAfter(search, kind, payload, 1)
  while (next && next >= search && next <= end) {
    dates.push(next)
    search = addDays(next, 1)
    next = recurringOnOrAfter(search, kind, payload, 1)
  }
  return dates
}
