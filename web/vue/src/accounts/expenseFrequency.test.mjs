import assert from 'node:assert/strict'
import { after, describe, it } from 'node:test'

import { formatExpenseFrequency } from './expenseFrequency.ts'

const originalTimezone = process.env.TZ
const weekdayCases = [
  [0, 'Mon'],
  [1, 'Tue'],
  [2, 'Wed'],
  [3, 'Thu'],
  [4, 'Fri'],
  [5, 'Sat'],
  [6, 'Sun'],
]

after(() => {
  if (originalTimezone === undefined) {
    delete process.env.TZ
    return
  }
  process.env.TZ = originalTimezone
})

for (const timezone of ['America/Los_Angeles', 'Pacific/Kiritimati']) {
  describe(`expense frequency labels in ${timezone}`, () => {
    it('runs with the representative timezone active', () => {
      process.env.TZ = timezone

      assert.equal(Intl.DateTimeFormat().resolvedOptions().timeZone, timezone)
    })

    for (const [weekday, label] of weekdayCases) {
      it(`uses Monday-first weekday index ${weekday} for weekly schedules`, () => {
        process.env.TZ = timezone

        assert.equal(
          formatExpenseFrequency(JSON.stringify({ kind: 'weekly_weekday', weekday })),
          `Weekly (${label})`,
        )
      })

      it(`uses Monday-first weekday index ${weekday} for biweekly schedules`, () => {
        process.env.TZ = timezone

        assert.equal(
          formatExpenseFrequency(
            JSON.stringify({ kind: 'biweekly_weekday', weekday, start_date: '2026-08-21' }),
          ),
          `Every 2 weeks (${label})`,
        )
      })

      it(`uses Monday-first weekday index ${weekday} for every-N-weeks schedules`, () => {
        process.env.TZ = timezone
        const frequency = JSON.stringify({
          kind: 'every_n_weeks_weekday',
          interval_weeks: 3,
          weekday,
          start_date: '2026-08-21',
        })

        assert.equal(formatExpenseFrequency(frequency), `Every 3 weeks (${label})`)
        assert.deepEqual(JSON.parse(frequency), {
          kind: 'every_n_weeks_weekday',
          interval_weeks: 3,
          weekday,
          start_date: '2026-08-21',
        })
      })
    }
  })
}
