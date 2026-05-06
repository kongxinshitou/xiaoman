import axios from 'axios'
import { logApiCall } from '../utils/logger'
import type { Department } from '../types/user'

/**
 * Admin endpoints live under /admin (not /api/v1) and require an admin JWT.
 * We use a dedicated axios instance because the shared client is bound to /api/v1.
 */
const adminClient = axios.create({
  baseURL: '/admin',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

adminClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('xiaoman_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  ;(config as unknown as Record<string, unknown>)._startMs = Date.now()
  return config
})

adminClient.interceptors.response.use(
  (response) => {
    const start = (response.config as unknown as Record<string, unknown>)._startMs as number | undefined
    const duration = start ? Date.now() - start : -1
    logApiCall(
      response.config.method?.toUpperCase() || 'GET',
      `/admin${response.config.url || ''}`,
      response.status,
      duration,
    )
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('xiaoman_token')
      localStorage.removeItem('xiaoman_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export const departmentsApi = {
  list: async () => {
    const res = await adminClient.get<Department[]>('/depts')
    return res.data
  },
  create: async (code: string, name: string) => {
    const res = await adminClient.post<Department>('/depts', { code, name })
    return res.data
  },
  update: async (code: string, data: Partial<Pick<Department, 'name' | 'enabled'>>) => {
    const res = await adminClient.patch<Department>(`/depts/${code}`, data)
    return res.data
  },
  remove: async (code: string) => {
    await adminClient.delete(`/depts/${code}`)
  },
}
