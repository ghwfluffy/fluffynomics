import { computed, ref } from 'vue'
import { errorMessage, snackbar } from '@/lib/api'

const STORAGE_KEY = 'mp_masked_mode_user_id'

const maskedModeUserId = ref<string | null>(null)

const readStoredMaskedModeUserId = () => {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

const writeStoredMaskedModeUserId = (userId: string | null) => {
  try {
    if (!userId) {
      window.localStorage.removeItem(STORAGE_KEY)
      return
    }
    window.localStorage.setItem(STORAGE_KEY, userId)
  } catch {
    // Ignore localStorage failures and keep the in-memory state.
  }
}

const hashString = (input: string) => {
  let hash = 2166136261
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

const hashUnit = (input: string) => hashString(input) / 0xffffffff

const maskSeed = (namespace: string) => `${maskedModeUserId.value || 'guest'}:${namespace}`

const formatCurrency = (valueCents: number, maximumFractionDigits = 2) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits,
  }).format(valueCents / 100)

export const maskedModeEnabled = computed(() => Boolean(maskedModeUserId.value))

export const syncMaskedModeForUser = (userId?: string | null) => {
  const storedUserId = readStoredMaskedModeUserId()
  maskedModeUserId.value = userId && storedUserId === userId ? userId : null
}

export const enableMaskedMode = (userId?: string | null) => {
  if (!userId) {
    return
  }
  maskedModeUserId.value = userId
  writeStoredMaskedModeUserId(userId)
}

export const clearMaskedMode = () => {
  maskedModeUserId.value = null
  writeStoredMaskedModeUserId(null)
}

export const guardMaskedMode = (action: string) => {
  if (!maskedModeEnabled.value) {
    return false
  }
  errorMessage.value = `Masked mode is locked for this session. Logout and sign back in to ${action}.`
  snackbar.value = true
  return true
}

export const maskCurrencyCents = (value?: number, namespace = 'currency') => {
  const safeValue = Number.isFinite(value) ? Math.round(value as number) : 0
  if (!maskedModeEnabled.value || safeValue === 0) {
    return safeValue
  }

  const sign = safeValue < 0 ? -1 : 1
  const absoluteValue = Math.abs(safeValue)

  if (absoluteValue < 100) {
    const centsGamma = 0.75 + hashUnit(maskSeed(`${namespace}:sub-dollar:${sign}`)) * 0.6
    const centsProgress = absoluteValue / 99
    return sign * Math.max(1, Math.round(99 * Math.pow(centsProgress, centsGamma)))
  }

  const dollars = Math.floor(absoluteValue / 100)
  const digitCount = Math.max(1, String(dollars).length)
  const low = 10 ** (digitCount - 1) * 100
  const high = 10 ** digitCount * 100 - 1
  const clampedValue = Math.min(high, Math.max(low, absoluteValue))
  const progress = (clampedValue - low) / Math.max(1, high - low)
  const gamma = 0.78 + hashUnit(maskSeed(`${namespace}:digits:${digitCount}:${sign}`)) * 0.5
  const maskedValue = low + Math.round((high - low) * Math.pow(progress, gamma))
  return sign * maskedValue
}

export const formatMaskedCurrencyCents = (value?: number) => formatCurrency(maskCurrencyCents(value), 2)

export const formatMaskedSignedCurrencyCents = (value: number) => {
  const maskedValue = maskCurrencyCents(value, 'signed-currency')
  const formatted = formatCurrency(Math.abs(maskedValue), 2)
  if (maskedValue > 0) {
    return `+${formatted}`
  }
  if (maskedValue < 0) {
    return `-${formatted}`
  }
  return formatted
}

export const formatMaskedIntegerCurrencyCents = (value: number, namespace = 'integer-currency') =>
  formatCurrency(maskCurrencyCents(value, namespace), 0)

export const maskAccountNumber = (value: string, namespace: string) => {
  if (!maskedModeEnabled.value || !value) {
    return value
  }
  return Array.from(value)
    .map((char, index) => {
      if (/\d/.test(char)) {
        return String(hashString(maskSeed(`${namespace}:digit:${index}`)) % 10)
      }
      if (/[A-Z]/.test(char)) {
        return String.fromCharCode(65 + (hashString(maskSeed(`${namespace}:upper:${index}`)) % 26))
      }
      if (/[a-z]/.test(char)) {
        return String.fromCharCode(97 + (hashString(maskSeed(`${namespace}:lower:${index}`)) % 26))
      }
      return char
    })
    .join('')
}
