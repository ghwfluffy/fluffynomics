import { ref } from 'vue'
import { request } from '@/lib/api'
import { clearMaskedMode, syncMaskedModeForUser } from '@/lib/maskedMode'
import { apiUrl, authMode } from '@/lib/paths'

export interface User {
  id: string
  username: string
  example_data: boolean
  is_admin: boolean
  avatar_icon_id: string | null
  central_avatar_url: string | null
  paypal_account_id: string | null
  google_pay_account_id: string | null
  widget_token: string | null
  widget_last_accessed_at: string | null
  widget_last_net_worth_cents: number | null
  last_login_at: string | null
  password_changed_at: string | null
  created_at: string
  updated_at: string
}

interface LoginResponse {
  user: User
  session_token: string
}

export const currentUser = ref<User | null>(null)
export const sessionToken = ref<string | null>(null)
const oauthAutoRetryKey = 'fluffynomics.oauth_state_auto_retry'

function clearOAuthStateAutoRetry(): void {
  try {
    window.sessionStorage.removeItem(oauthAutoRetryKey)
  } catch {
    // Ignore unavailable session storage.
  }
}

export function beginOAuthLogin(nextPath: unknown = '/app'): void {
  const safeNextPath = typeof nextPath === 'string' ? nextPath : '/app'
  window.location.assign(apiUrl(`/auth/oauth/login?next=${encodeURIComponent(safeNextPath)}`))
}

export async function refreshSession(): Promise<User | null> {
  try {
    const user = await request.get<User>('/auth/me', { suppressError: true })
    currentUser.value = user
    clearOAuthStateAutoRetry()
    syncMaskedModeForUser(user.id)
    return user
  } catch {
    currentUser.value = null
    sessionToken.value = null
    clearMaskedMode()
    return null
  }
}

export async function login(username: string, password: string, sessionSeconds?: number): Promise<User> {
  if (authMode === 'oauth') {
    beginOAuthLogin()
    throw new Error('Redirecting to auth provider')
  }
  const response = await request.post<LoginResponse>('/auth/login', {
    username,
    password,
    session_seconds: sessionSeconds,
  })
  currentUser.value = response.user
  sessionToken.value = response.session_token
  clearOAuthStateAutoRetry()
  syncMaskedModeForUser(response.user.id)
  return response.user
}

export async function register(
  username: string,
  password: string,
  addExampleData = false,
  registrationCode?: string,
): Promise<User> {
  if (authMode === 'oauth') {
    beginOAuthLogin()
    throw new Error('Redirecting to auth provider')
  }
  return request.post<User>('/auth/register', {
    username,
    password,
    add_example_data: addExampleData,
    registration_code: registrationCode || null,
  })
}

export async function logout(): Promise<void> {
  await request.post('/auth/logout')
  currentUser.value = null
  sessionToken.value = null
  clearMaskedMode()
}

export function clearLocalSession(): void {
  currentUser.value = null
  sessionToken.value = null
  clearMaskedMode()
}

export async function updateProfile(payload: {
  avatar_icon_id?: string | null
  paypal_account_id?: string | null
  google_pay_account_id?: string | null
  current_password?: string
  new_password?: string
}): Promise<User> {
  const user = await request.put<User>('/auth/profile', payload)
  currentUser.value = user
  syncMaskedModeForUser(user.id)
  return user
}

export async function regenerateWidgetUrl(): Promise<User> {
  const user = await request.post<User>('/auth/widget-url/regenerate')
  currentUser.value = user
  syncMaskedModeForUser(user.id)
  return user
}

export async function deleteOwnAccount(currentPassword: string): Promise<void> {
  await request.post('/auth/delete-account', { current_password: currentPassword })
  clearLocalSession()
}
