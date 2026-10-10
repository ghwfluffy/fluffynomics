import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { accountEditPayload, storedAccountBalances } from './accountEditing.ts'

describe('account editing with pending transfers', () => {
  it('uses stored card debt rather than a queued-payment tile preview', () => {
    const balances = storedAccountBalances({ balance_cents: 7000, stored_balance_cents: 10000 })
    assert.equal(balances.balance_cents, 10000)
    const payload = accountEditPayload({ ...balances, minimum_payment_cents: 3500 }, balances)
    assert.equal(payload.minimum_payment_cents, 3500)
    assert.equal('balance_cents' in payload, false)
  })

  it('does not send untouched funding or USD balances back to the server', () => {
    const balances = storedAccountBalances({
      balance_cents: 97000, stored_balance_cents: 100000,
      usd_balance_cents: 19000, stored_usd_balance_cents: 20000,
    })
    const payload = accountEditPayload({ ...balances, name: 'Renamed account' }, balances)
    assert.deepEqual(payload, { name: 'Renamed account' })
    assert.equal(balances.balance_cents, 100000)
  })

  it('includes an explicitly changed balance, including zero', () => {
    assert.deepEqual(accountEditPayload({ balance_cents: 0 }, { balance_cents: 10000 }), { balance_cents: 0 })
    assert.deepEqual(accountEditPayload({ usd_balance_cents: 5000 }, { usd_balance_cents: 20000 }), { usd_balance_cents: 5000 })
  })

  it('does not invent a balance for an account with a null stored amount', () => {
    const balances = storedAccountBalances({ balance_cents: 7000, stored_balance_cents: null })
    assert.equal(balances.balance_cents, undefined)
    assert.deepEqual(accountEditPayload({ balance_cents: 0, name: 'Metadata only' }, balances), { name: 'Metadata only' })
  })

  it('leaves metadata saves independent of a settlement while editing', () => {
    const original = { balance_cents: 10000 }
    const draft = { ...original, minimum_payment_cents: 2500 }
    // If a transfer settles in the meantime, no old amount is submitted to undo it.
    assert.deepEqual(accountEditPayload(draft, original), { minimum_payment_cents: 2500 })
  })
})
