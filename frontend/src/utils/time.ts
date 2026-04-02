import dayjs from 'dayjs'

/**
 * Parse a server-returned timestamp string as UTC and return a dayjs object
 * that will display in the browser's local timezone (Beijing UTC+8).
 *
 * The backend stores datetimes in UTC but SQLite strips timezone info on
 * read-back, so Pydantic serializes them without a 'Z' suffix. Without 'Z',
 * browsers treat the string as local time instead of UTC, causing an 8-hour
 * display error. Appending 'Z' fixes this.
 */
export function parseServerTime(ts: string | null | undefined): dayjs.Dayjs | null {
  if (!ts) return null
  // If already has timezone info (Z or +offset), parse as-is
  const normalized = /[Z+]/.test(ts) ? ts : ts + 'Z'
  return dayjs(normalized)
}
