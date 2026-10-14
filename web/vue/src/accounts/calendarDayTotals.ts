interface CalendarAmount {
  dateIso: string
  signedAmountCents: number
}

/** Day colors represent all displayed income/outflows, including debt payments. */
export function calendarDayTotals(events: readonly CalendarAmount[]) {
  const totals = new Map<string, number>()
  for (const event of events) {
    totals.set(event.dateIso, (totals.get(event.dateIso) ?? 0) + event.signedAmountCents)
  }
  return totals
}

export function calendarDayToneClass(totalCents: number, hasEvents: boolean) {
  if (!hasEvents) return 'calendar-day-tone--none'
  const magnitude = Math.abs(totalCents)
  if (magnitude < 20_000) return 'calendar-day-tone--low'
  const sign = totalCents > 0 ? 'positive' : 'negative'
  return `calendar-day-tone--${sign}-${magnitude < 100_000 ? 'mid' : 'high'}`
}

/** Distinct payments and interest may share an account/date but not an event key. */
export function uniqueCalendarEvents<T extends { key: string }>(events: readonly T[]) {
  return Array.from(new Map(events.map((event) => [event.key, event])).values())
}
