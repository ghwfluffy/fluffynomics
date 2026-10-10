import assert from 'node:assert/strict'
import { it } from 'node:test'
import { createRefreshGate, loadForecastRanges } from './forecastRefresh.ts'

it('uses one long forecast for a future anchor and shorter widgets without overflowing cents', async () => {
  const calls = []
  const points = [
    { snapshot_date: '2026-10-10', value_cents: 100 },
    { snapshot_date: '2026-11-14', value_cents: 200 },
    { snapshot_date: '2026-12-14', value_cents: 300 },
    { snapshot_date: '2036-11-14', value_cents: 5_000_000_000 },
  ]
  const result = await loadForecastRanges(async (date) => { calls.push(date); return points },
    '2026-11-14', '2026-12-14', '2036-11-14', '2026-10-10')
  assert.deepEqual(calls, ['2036-11-14'])
  assert.deepEqual(result.trend, points.slice(0, 2))
  assert.deepEqual(result.next30, points.slice(0, 3))
  assert.equal(result.projection.at(-1).value_cents, 5_000_000_000)
})

it('has no future trend for a historical anchor', async () => {
  let through
  const result = await loadForecastRanges(async (date) => { through = date; return [] },
    '2015-10-10', '2015-11-09', '2025-10-10', '2026-10-10')
  assert.equal(through, '2025-10-10')
  assert.deepEqual(result.trend, [])
})

it('discards an older response when dates change while requests are in flight', async () => {
  const gate = createRefreshGate()
  let resolveOld
  const oldResponse = new Promise((resolve) => { resolveOld = resolve })
  let shown
  const oldToken = gate.begin()
  const oldRun = oldResponse.then((value) => { if (gate.isCurrent(oldToken)) shown = value })
  const newToken = gate.begin()
  if (gate.isCurrent(newToken)) shown = 'new date'
  resolveOld('old date')
  await oldRun
  assert.equal(shown, 'new date')
})
