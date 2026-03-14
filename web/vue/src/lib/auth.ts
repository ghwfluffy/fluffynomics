import { ref } from 'vue'
import { request } from '@/lib/api'
import { clearMaskedMode, syncMaskedModeForUser } from '@/lib/maskedMode'

export interface User {
  id: string
  username: string
  example_data: boolean
  is_admin: boolean
  avatar_icon_id: string | null
  paypal_account_id: string | null
  google_pay_account_id: string | null
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

export async function refreshSession(): Promise<User | null> {
  try {
    const user = await request.get<User>('/auth/me', { suppressError: true })
    currentUser.value = user
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
  const response = await request.post<LoginResponse>('/auth/login', {
    username,
    password,
    session_seconds: sessionSeconds,
  })
  currentUser.value = response.user
  sessionToken.value = response.session_token
  syncMaskedModeForUser(response.user.id)
  return response.user
}

export async function register(
  username: string,
  password: string,
  addExampleData = false,
  registrationCode?: string,
): Promise<User> {
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

export async function deleteOwnAccount(currentPassword: string): Promise<void> {
  await request.post('/auth/delete-account', { current_password: currentPassword })
  clearLocalSession()
}
