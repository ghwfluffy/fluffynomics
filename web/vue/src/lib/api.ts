import axios from 'axios'
import type { AxiosRequestConfig, AxiosResponse } from 'axios'
import { ref } from 'vue'

export const errorMessage = ref('')
export const snackbar = ref(false)

type RequestConfig = AxiosRequestConfig & {
  suppressError?: boolean
}

const instance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
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
    return handleRequest<T>(instance.post(url, data, axiosConfig), suppressError)
  },
  put: <T = unknown>(url: string, data?: unknown, config?: RequestConfig) => {
    const { suppressError, ...axiosConfig } = config || {}
    return handleRequest<T>(instance.put(url, data, axiosConfig), suppressError)
  },
  patch: <T = unknown>(url: string, data?: unknown, config?: RequestConfig) => {
    const { suppressError, ...axiosConfig } = config || {}
    return handleRequest<T>(instance.patch(url, data, axiosConfig), suppressError)
  },
  delete: <T = unknown>(url: string, config?: RequestConfig) => {
    const { suppressError, ...axiosConfig } = config || {}
    return handleRequest<T>(instance.delete(url, axiosConfig), suppressError)
  },
}
