import assert from 'node:assert/strict'
import { after, it } from 'node:test'
import { expenseOccurrencesInRange } from './expenseCalendar.ts'
import { calendarDayTotals } from './calendarDayTotals.ts'

const previousTimezone = process.env.TZ
process.env.TZ = 'America/Chicago'
after(() => {
  if (previousTimezone === undefined) delete process.env.TZ
  else process.env.TZ = previousTimezone
})
const date = (iso) => new Date(`${iso}T00:00:00`)
const iso = (value) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
const weekly = {
  enabled: true,
  next_expensed_date: '2026-10-19',
  general_frequency: JSON.stringify({ kind: 'weekly_weekday', weekday: 0 }),
}
const occurrences = (expense = weekly, start = '2026-09-27', end = '2026-11-07') =>
  expenseOccurrencesInRange(expense, date(start), date(end)).map(iso)

it('shows groceries next week, the following week, and the trailing month cell', () => {
  assert.deepEqual(occurrences(), ['2026-10-19', '2026-10-26', '2026-11-02'])
  const totals = calendarDayTotals(occurrences().map((dateIso) => ({ dateIso, signedAmountCents: -15000 })))
  assert.equal(totals.get('2026-10-26'), -15000)
})

it('continues in later months even when the next expense precedes the grid', () => {
  assert.deepEqual(occurrences(weekly, '2026-11-01', '2026-12-12'), [
    '2026-11-02', '2026-11-09', '2026-11-16', '2026-11-23', '2026-11-30', '2026-12-07',
  ])
})

it('preserves the API early-expense skip without skipping a second occurrence', () => {
  assert.deepEqual(occurrences({ ...weekly, last_expensed_date: '2026-10-16', next_expensed_date: '2026-10-26' }), [
    '2026-10-26', '2026-11-02',
  ])
})

it('honors an overridden next date once and then resumes the regular schedule', () => {
  assert.deepEqual(occurrences({ ...weekly, next_date_is_static: true, next_expensed_date: '2026-10-21' }), [
    '2026-10-21', '2026-10-26', '2026-11-02',
  ])
})

it('keeps unrecurring dates single, and excludes disabled or missing dates', () => {
  assert.deepEqual(occurrences({ ...weekly, general_frequency: undefined }), ['2026-10-19'])
  assert.deepEqual(occurrences({ ...weekly, general_frequency: 'invalid' }), ['2026-10-19'])
  assert.deepEqual(occurrences({ ...weekly, enabled: false }), [])
  assert.deepEqual(occurrences({ ...weekly, next_expensed_date: undefined }), [])
  assert.deepEqual(occurrences({ ...weekly, next_expensed_date: '2026-12-01' }), [])
})

it('preserves interval cadence when navigating months across daylight saving time', () => {
  const expense = { ...weekly, general_frequency: JSON.stringify({ kind: 'biweekly_weekday', weekday: 0, start_date: '2026-10-19' }) }
  assert.deepEqual(occurrences(expense, '2026-11-01', '2026-12-12'), ['2026-11-02', '2026-11-16', '2026-11-30'])
})

it('includes daily occurrences on both grid boundaries', () => {
  assert.deepEqual(occurrences({ ...weekly, general_frequency: 'daily' }, '2026-10-25', '2026-10-27'), [
    '2026-10-25', '2026-10-26', '2026-10-27',
  ])
})

for (const kind of ['biweekly_weekday', 'every_n_weeks_weekday']) {
  it(`continues ${kind} after the spring daylight-saving transition`, () => {
    const expense = {
      ...weekly,
      next_expensed_date: '2027-03-01',
      general_frequency: JSON.stringify({ kind, interval_weeks: 2, weekday: 0, start_date: '2027-03-01' }),
    }
    assert.deepEqual(occurrences(expense, '2027-03-01', '2027-04-12'), [
      '2027-03-01', '2027-03-15', '2027-03-29', '2027-04-12',
    ])
  })
}

it('handles month-end clamping and twice-monthly schedules', () => {
  const expense = { ...weekly, next_expensed_date: '2027-01-31', general_frequency: JSON.stringify({ kind: 'monthly_day', day: 31 }) }
  assert.deepEqual(occurrences(expense, '2027-02-01', '2027-03-31'), ['2027-02-28', '2027-03-31'])
  assert.deepEqual(occurrences({ ...weekly, next_expensed_date: '2026-10-15', general_frequency: JSON.stringify({ kind: 'twice_monthly', day_1: 1, day_2: 15 }) }), ['2026-10-15', '2026-11-01'])
})

it('uses backend legacy recurrence mappings after a custom next date', () => {
  assert.deepEqual(occurrences({ ...weekly, next_expensed_date: '2026-10-21', general_frequency: 'weekly' }), ['2026-10-21', '2026-10-26', '2026-11-02'])
  assert.deepEqual(occurrences({ ...weekly, general_frequency: 'monthly' }), ['2026-10-19', '2026-11-01'])
})
