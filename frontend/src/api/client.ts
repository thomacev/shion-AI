import axios, { type InternalAxiosRequestConfig } from 'axios'

export const SESSION_EXPIRED = 'shion:session-expired'
const baseURL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
const client = axios.create({ baseURL, withCredentials: true, timeout: 30_000 })
const authClient = axios.create({ baseURL, withCredentials: true, timeout: 15_000 })
let refreshPromise: Promise<unknown> | null = null

// All callers await the same refresh, including rejection. No stranded queue.
client.interceptors.response.use(response => response, async (error: unknown) => {
  if (!axios.isAxiosError(error)) throw error
  const request = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
  if (error.response?.status !== 401 || !request || request._retry ||
      /^\/auth\/(login|register|refresh)$/.test(request.url ?? '')) throw error
  request._retry = true
  if (!refreshPromise) {
    refreshPromise = authClient.post('/auth/refresh', {}).catch((refreshError: unknown) => {
      if (axios.isAxiosError(refreshError) && [401, 403].includes(refreshError.response?.status ?? 0)) {
        window.dispatchEvent(new Event(SESSION_EXPIRED))
      }
      throw refreshError
    }).finally(() => { refreshPromise = null })
  }
  await refreshPromise
  return client(request)
})

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ECONNABORTED') return 'This is taking longer than expected. Check the result before trying again.'
    if (!error.response) return 'We couldn’t reach the server. Check your connection and try again.'
    const detail = error.response.data?.detail ?? error.response.data?.message
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(' ')
    if (error.response.status === 429) return 'Too many requests. Please wait a little before trying again.'
    return `The request couldn’t be completed (${error.response.status}). Please try again.`
  }
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

export default client
