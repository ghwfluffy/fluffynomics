import axios from 'axios'
import { createSessionRecovery } from './sessionRecovery'
import type { AxiosRequestConfig, AxiosResponse } from 'axios'
import { ref } from 'vue'
import { apiBasePath, authMode } from '@/lib/paths'

export const errorMessage = ref('')
export const snackbar = ref(false)

type RequestConfig = AxiosRequestConfig & {
  suppressError?: boolean
}

const instance = axios.create({
  baseURL: apiBasePath,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

const recoverSession = createSessionRecovery(() => `${apiBasePath}/auth/oauth/login?next=%2Fapp`, authMode === 'oauth')
instance.interceptors.response.use(undefined, async (error) => {
  const config = error.config
  if (error.response?.status !== 401 || !config || config.sessionRecoveryAttempted ||
      (config.url?.startsWith('/auth/') && config.url !== '/auth/me')) throw error
  config.sessionRecoveryAttempted = true
  let first = true
  const result = await recoverSession(async () => {
    if (first) { first = false; return error.response }
    return instance.request(config)
  })
  if (result === error.response) throw error
  return result
})

async function handleRequest<T>(
  promise: Promise<AxiosResponse<T>>,
  suppressError = false,
): Promise<T> {
  try {
    const response = await promise
    return response.data
  } catch (err: any) {
    if (!suppressError) {
      errorMessage.value = err.response?.data?.detail || 'Unexpected error'
      snackbar.value = true
    }
    throw err
  }
}

export const request = {
  get: <T = unknown>(url: string, config?: RequestConfig) => {
    const { suppressError, ...axiosConfig } = config || {}
    return handleRequest<T>(instance.get(url, axiosConfig), suppressError)
  },
  post: <T = unknown>(url: string, data?: unknown, config?: RequestConfig) => {
    const { suppressError, ...axiosConfig } = config || {}
    if (typeof FormData !== 'undefined' && data instanceof FormData) {
      axiosConfig.headers = { ...(axiosConfig.headers || {}), 'Content-Type': undefined }
    }
    return handleRequest<T>(instance.post(url, data, axiosConfig), suppressError)
  },
  put: <T = unknown>(url: string, data?: unknown, config?: RequestConfig) => {
    const { suppressError, ...axiosConfig } = config || {}
    if (typeof FormData !== 'undefined' && data instanceof FormData) {
      axiosConfig.headers = { ...(axiosConfig.headers || {}), 'Content-Type': undefined }
    }
    return handleRequest<T>(instance.put(url, data, axiosConfig), suppressError)
  },
  patch: <T = unknown>(url: string, data?: unknown, config?: RequestConfig) => {
    const { suppressError, ...axiosConfig } = config || {}
    if (typeof FormData !== 'undefined' && data instanceof FormData) {
      axiosConfig.headers = { ...(axiosConfig.headers || {}), 'Content-Type': undefined }
    }
    return handleRequest<T>(instance.patch(url, data, axiosConfig), suppressError)
  },
  delete: <T = unknown>(url: string, config?: RequestConfig) => {
    const { suppressError, ...axiosConfig } = config || {}
    return handleRequest<T>(instance.delete(url, axiosConfig), suppressError)
  },
}
