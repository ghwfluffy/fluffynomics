import assert from 'node:assert/strict'
import { it } from 'node:test'
import { calendarDayTotals, calendarDayToneClass, uniqueCalendarEvents } from './calendarDayTotals.ts'

const day = '2026-10-13'
const event = (signedAmountCents, dateIso = day) => ({ dateIso, signedAmountCents })

it('colors -$10 and -$1000 red regardless of event order', () => {
  const events = [event(-1000), event(-100000)]
  for (const rows of [events, [...events].reverse()]) {
    const total = calendarDayTotals(rows).get(day)
    assert.equal(total, -101000)
    assert.equal(calendarDayToneClass(total, true), 'calendar-day-tone--negative-high')
  }
})

it('includes debt-payment outflows even when their net-worth impact is zero', () => {
  const total = calendarDayTotals([event(-1000), { ...event(-100000), netWorthDeltaCents: 0 }]).get(day)
  assert.equal(total, -101000)
  assert.equal(calendarDayToneClass(total, true), 'calendar-day-tone--negative-high')
})

it('nets income and all expenses on the day and keeps other dates separate', () => {
  const totals = calendarDayTotals([event(150000), event(-100000), event(-1000), event(-500000, '2026-10-14')])
  assert.equal(totals.get(day), 49000)
  assert.equal(calendarDayToneClass(totals.get(day), true), 'calendar-day-tone--positive-mid')
  assert.equal(totals.get('2026-10-14'), -500000)
})

it('uses totals from all events, including those beyond the visible chip limit', () => {
  const total = calendarDayTotals([event(-100), event(-100), event(-100), event(-100000)]).get(day)
  assert.equal(calendarDayToneClass(total, true), 'calendar-day-tone--negative-high')
})

it('handles color boundaries, offsetting events, and empty days', () => {
  assert.equal(calendarDayToneClass(-19999, true), 'calendar-day-tone--low')
  assert.equal(calendarDayToneClass(-20000, true), 'calendar-day-tone--negative-mid')
  assert.equal(calendarDayToneClass(-100000, true), 'calendar-day-tone--negative-high')
  assert.equal(calendarDayToneClass(100000, true), 'calendar-day-tone--positive-high')
  assert.equal(calendarDayToneClass(calendarDayTotals([event(100000), event(-100000)]).get(day), true), 'calendar-day-tone--low')
  assert.equal(calendarDayToneClass(0, false), 'calendar-day-tone--none')
})

it('keeps interest and payment for the same card/day while removing exact duplicates', () => {
  const interest = { ...event(-1000), key: `card-1-interest-${day}`, kind: 'payable', sourceId: 'card-1' }
  const payment = { ...event(-100000), key: `card-1-payment-${day}`, kind: 'payable', sourceId: 'card-1', netWorthDeltaCents: 0 }
  const rows = uniqueCalendarEvents([interest, payment, interest])
  assert.equal(rows.length, 2)
  assert.equal(calendarDayTotals(rows).get(day), -101000)
  assert.equal(calendarDayToneClass(calendarDayTotals(rows).get(day), true), 'calendar-day-tone--negative-high')
})
