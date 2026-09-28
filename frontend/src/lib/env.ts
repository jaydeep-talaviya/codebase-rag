/**
 * Runtime configuration.
 *
 * The API base URL comes from VITE_API_BASE_URL and is resolved here exactly
 * once. No other module is allowed to read import.meta.env directly.
 */

const DEFAULT_BASE_URL = 'http://localhost:8000'

function resolveBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL
  if (typeof raw !== 'string' || raw.trim() === '') return DEFAULT_BASE_URL
  return raw.trim().replace(/\/+$/, '')
}

export const API_BASE_URL = resolveBaseUrl()

/**
 * Host shown in the header badge. Returns '' for a relative base URL (e.g. when
 * the app is served behind a same-origin proxy), which is rendered as-is.
 */
export function apiDisplayHost(): string {
  try {
    return new URL(API_BASE_URL, window.location.origin).host
  } catch {
    return API_BASE_URL
  }
}


/** How long a single backend call may take before we surface a timeout. */
export const REQUEST_TIMEOUT_MS = 30_000

/**
 * Ingestion (clone + embed an entire repository) is a single long request on
 * the backend, so it gets a much larger budget than a chat question.
 */
export const INGEST_TIMEOUT_MS = 15 * 60_000
