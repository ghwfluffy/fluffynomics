import { ref } from 'vue'
import { request } from '@/lib/api'

export interface User {
  id: string
  username: string
  example_data: boolean
  avatar_icon_id: string | null
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
    return user
  } catch {
    currentUser.value = null
    sessionToken.value = null
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
  return response.user
}

export async function register(
  username: string,
  password: string,
  addExampleData = false,
): Promise<User> {
  return request.post<User>('/auth/register', {
    username,
    password,
    add_example_data: addExampleData,
  })
}

export async function logout(): Promise<void> {
  await request.post('/auth/logout')
  currentUser.value = null
  sessionToken.value = null
}

export async function updateProfile(payload: {
  avatar_icon_id?: string | null
  current_password?: string
  new_password?: string
}): Promise<User> {
  const user = await request.put<User>('/auth/profile', payload)
  currentUser.value = user
  return user
}
