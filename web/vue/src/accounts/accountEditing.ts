export interface AccountBalances {
  balance_cents?: number
  usd_balance_cents?: number
}

interface DisplayedAccountBalances extends AccountBalances {
  stored_balance_cents?: number | null
  stored_usd_balance_cents?: number | null
}

/** Editors use persisted amounts; tiles and forecasts may include pending moves. */
export function storedAccountBalances(account: DisplayedAccountBalances): AccountBalances {
  return {
    balance_cents: account.stored_balance_cents === undefined
      ? account.balance_cents
      : account.stored_balance_cents ?? undefined,
    usd_balance_cents: account.stored_usd_balance_cents === undefined
      ? account.usd_balance_cents
      : account.stored_usd_balance_cents ?? undefined,
  }
}

/** Metadata saves must not overwrite a balance that settled while the editor was open. */
export function accountEditPayload<T extends AccountBalances>(draft: T, original: AccountBalances): T {
  const payload = { ...draft }
  if ((draft.balance_cents ?? 0) === (original.balance_cents ?? 0)) delete payload.balance_cents
  if ((draft.usd_balance_cents ?? 0) === (original.usd_balance_cents ?? 0)) delete payload.usd_balance_cents
  return payload
}
