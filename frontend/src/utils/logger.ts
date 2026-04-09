/**
 * Frontend logging utility.
 *
 * Captures user actions, API timings, and JS errors.
 * Batches entries in localStorage (≤100) and periodically uploads to the backend.
 */

const STORAGE_KEY = 'xiaoman_frontend_logs'
const MAX_LOCAL = 100
const UPLOAD_INTERVAL_MS = 30_000  // upload every 30 seconds
const UPLOAD_URL = '/api/v1/logs'

export type LogLevel = 'debug' | 'info' | 'warn' | 'error'

export interface LogEntry {
  level: LogLevel
  message: string
  timestamp: string
  data?: unknown
}

// ── Internal buffer ────────────────────────────────────────────────────────────

function loadBuffer(): LogEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveBuffer(entries: LogEntry[]): void {
  try {
    // Keep only the latest MAX_LOCAL entries
    const trimmed = entries.slice(-MAX_LOCAL)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed))
  } catch {
    // localStorage might be full — clear and retry
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch { /* ignore */ }
  }
}

function addToBuffer(entry: LogEntry): void {
  const buf = loadBuffer()
  buf.push(entry)
  saveBuffer(buf)
}

// ── Public API ─────────────────────────────────────────────────────────────────

function log(level: LogLevel, message: string, data?: unknown): void {
  const entry: LogEntry = {
    level,
    message,
    timestamp: new Date().toISOString(),
    data,
  }
  addToBuffer(entry)

  // Mirror to console
  const args = data !== undefined ? [message, data] : [message]
  switch (level) {
    case 'debug': console.debug(...args); break
    case 'info':  console.info(...args);  break
    case 'warn':  console.warn(...args);  break
    case 'error': console.error(...args); break
  }
}

export const logger = {
  debug: (msg: string, data?: unknown) => log('debug', msg, data),
  info:  (msg: string, data?: unknown) => log('info',  msg, data),
  warn:  (msg: string, data?: unknown) => log('warn',  msg, data),
  error: (msg: string, data?: unknown) => log('error', msg, data),
}

// ── Upload ─────────────────────────────────────────────────────────────────────

async function uploadLogs(): Promise<void> {
  const buf = loadBuffer()
  if (buf.length === 0) return

  const token = localStorage.getItem('xiaoman_token')
  if (!token) return  // not authenticated, skip

  try {
    const resp = await fetch(UPLOAD_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ logs: buf }),
    })
    if (resp.ok) {
      // Clear successfully uploaded logs
      saveBuffer([])
    }
  } catch {
    // Network error — will retry next interval
  }
}

// ── Global error capture ───────────────────────────────────────────────────────

function initGlobalErrorHandlers(): void {
  window.addEventListener('error', (e) => {
    logger.error(`Uncaught error: ${e.message}`, {
      filename: e.filename,
      lineno: e.lineno,
      colno: e.colno,
      stack: e.error?.stack,
    })
  })

  window.addEventListener('unhandledrejection', (e) => {
    logger.error(`Unhandled promise rejection: ${String(e.reason)}`, {
      stack: e.reason?.stack,
    })
  })
}

// ── Init ───────────────────────────────────────────────────────────────────────

let _initialized = false

export function initLogger(): void {
  if (_initialized) return
  _initialized = true

  initGlobalErrorHandlers()

  // Periodic upload
  setInterval(uploadLogs, UPLOAD_INTERVAL_MS)

  // Upload on page unload (best effort)
  window.addEventListener('beforeunload', () => {
    uploadLogs()
  })

  logger.info('Frontend logger initialized')
}

// ── API timing helper ──────────────────────────────────────────────────────────

export function logApiCall(method: string, url: string, status: number, durationMs: number): void {
  const level: LogLevel = status >= 500 ? 'error' : status >= 400 ? 'warn' : 'info'
  logger[level](`API ${method} ${url} → ${status} (${durationMs}ms)`)
}
