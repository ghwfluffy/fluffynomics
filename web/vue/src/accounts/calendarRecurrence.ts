export const parseDateOnly = (raw?: string) => {
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

export const startOfDay = (value: Date) => {
  const next = new Date(value)
  next.setHours(0, 0, 0, 0)
  return next
}

export const startOfMonth = (value: Date) => new Date(value.getFullYear(), value.getMonth(), 1)

export const addDays = (value: Date, days: number) => {
  const next = new Date(value)
  next.setDate(next.getDate() + days)
  return next
}

export const parseRecurringPayload = (raw?: string) => {
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

const monthLastDay = (year: number, monthZeroBased: number) => new Date(year, monthZeroBased + 1, 0).getDate()

export const monthlyRecurringDate = (year: number, monthZeroBased: number, day: number) => {
  const safeDay = Math.min(Math.max(day, 1), monthLastDay(year, monthZeroBased))
  const value = new Date(year, monthZeroBased, safeDay)
  value.setHours(0, 0, 0, 0)
  return value
}

export const addMonthsRecurring = (value: Date, months: number, day: number) =>
  monthlyRecurringDate(value.getFullYear(), value.getMonth() + months, day)

// Recurrence intervals count calendar days, including 23/25-hour DST days.
const calendarDayNumber = (value: Date) =>
  Date.UTC(value.getFullYear(), value.getMonth(), value.getDate()) / (1000 * 60 * 60 * 24)

export const recurringOnOrAfter = (
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
    const daysSince = calendarDayNumber(anchor) - calendarDayNumber(base)
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
    const daysSince = calendarDayNumber(anchor) - calendarDayNumber(base)
    const periods = Math.ceil(daysSince / intervalDays)
    const result = new Date(base)
    result.setDate(result.getDate() + periods * intervalDays)
    return startOfDay(result)
  }
  return null
}

export const recurringNext = (
  current: Date,
  kind: string,
  payload: Record<string, unknown> | null,
  fallbackDay: number,
) => recurringOnOrAfter(addDays(current, 1), kind, payload, fallbackDay)

