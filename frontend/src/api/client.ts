import axios from 'axios'
import { logApiCall } from '../utils/logger'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - add auth token + start timer
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('xiaoman_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    // Store request start time in config metadata
    ;(config as Record<string, unknown>)._startMs = Date.now()
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor - handle auth errors + log timing
client.interceptors.response.use(
  (response) => {
    const start = (response.config as Record<string, unknown>)._startMs as number | undefined
    const duration = start ? Date.now() - start : -1
    const url = response.config.url || ''
    logApiCall(response.config.method?.toUpperCase() || 'GET', url, response.status, duration)
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('xiaoman_token')
      localStorage.removeItem('xiaoman_user')
      window.location.href = '/login'
    }
    const start = (error.config as Record<string, unknown>)?._startMs as number | undefined
    const duration = start ? Date.now() - start : -1
    const url = error.config?.url || ''
    const status = error.response?.status || 0
    logApiCall(error.config?.method?.toUpperCase() || 'GET', url, status, duration)
    return Promise.reject(error)
  },
)

export default client
