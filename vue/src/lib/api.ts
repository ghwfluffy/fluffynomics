import axios from 'axios'
import type { AxiosRequestConfig, AxiosResponse } from 'axios'
import { ref } from 'vue'

export const errorMessage = ref('')
export const snackbar = ref(false)

const instance = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
})

async function handleRequest<T>(promise: Promise<AxiosResponse<T>>): Promise<T | undefined> {
  try {
    const response = await promise
    return response.data
  } catch (err: any) {
    errorMessage.value = err.response?.data?.detail || 'Unexpected error'
    snackbar.value = true
    throw err
  }
}

export const request = {
  get:    <T = any>(url: string, config?: AxiosRequestConfig) => handleRequest<T>(instance.get(url, config)),
  post:   <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => handleRequest<T>(instance.post(url, data, config)),
  put:    <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => handleRequest<T>(instance.put(url, data, config)),
  patch:  <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => handleRequest<T>(instance.patch(url, data, config)),
  delete: <T = any>(url: string, config?: AxiosRequestConfig) => handleRequest<T>(instance.delete(url, config)),
}
