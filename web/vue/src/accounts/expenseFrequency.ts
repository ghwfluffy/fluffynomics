const weekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const monthLabels = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const formatExpenseFrequency = (raw?: string) => {
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
      return `Yearly (${monthLabels[month] || month} ${day})`
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
      return `Every ${interval} year${interval === 1 ? '' : 's'} (${monthLabels[month] || month} ${day})`
    }
    if (kind === 'weekly_weekday') {
      const weekday = Number(parsed.weekday)
      return `Weekly (${weekdayLabels[weekday] || 'Day'})`
    }
    if (kind === 'biweekly_weekday') {
      const weekday = Number(parsed.weekday)
      return `Every 2 weeks (${weekdayLabels[weekday] || 'Day'})`
    }
    if (kind === 'every_n_weeks_weekday') {
      const interval = Math.max(1, Number(parsed.interval_weeks || 1))
      const weekday = Number(parsed.weekday)
      return `Every ${interval} weeks (${weekdayLabels[weekday] || 'Day'})`
    }
    if (kind === 'daily_weekdays') {
      return 'Daily'
    }
  } catch {
    return 'Custom'
  }
  return 'Custom'
}
