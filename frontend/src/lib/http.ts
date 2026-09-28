import { API_BASE_URL, REQUEST_TIMEOUT_MS } from './env'

/**
 * A normalised error. Every failure the UI can show — network, timeout, HTTP
 * 4xx/5xx, malformed payload — arrives as one of these, so components can
 * render a message without ever inspecting a raw Response.
 */
export class ApiError extends Error {
  readonly status: number
  readonly kind: ApiErrorKind

  constructor(
    message: string,
    options: { status?: number; kind?: ApiErrorKind } = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status ?? 0
    this.kind = options.kind ?? 'unknown'
  }
}

export type ApiErrorKind =
  | 'network'
  | 'timeout'
  | 'not_found'
  | 'validation'
  | 'conflict'
  | 'server'
  | 'unknown'

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** Serialised as JSON. */
  body?: unknown
  /** Serialised as query parameters. */
  query?: Record<string, string | number | boolean | null | undefined>
  timeoutMs?: number
  signal?: AbortSignal
  /**
   * When true the response body is discarded. Used for endpoints that stream
   * back a large payload we do not need.
   */
  discardBody?: boolean
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  // Resolved against the page origin so a relative VITE_API_BASE_URL (used when
  // the app sits behind a same-origin proxy) works too.
  const url = new URL(`${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`, window.location.origin)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null) continue
      url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

/**
 * FastAPI puts the human-readable reason in `detail`, which is either a
 * string or a list of validation objects. Flatten both into one sentence.
 */
function extractDetail(payload: unknown): string | undefined {
  if (typeof payload !== 'object' || payload === null) return undefined
  const detail = (payload as { detail?: unknown }).detail
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (typeof item === 'object' && item !== null) {
          const { loc, msg } = item as { loc?: unknown[]; msg?: unknown }
          const field = Array.isArray(loc) ? loc[loc.length - 1] : undefined
          return typeof msg === 'string' ? `${String(field ?? 'field')}: ${msg}` : null
        }
        return null
      })
      .filter((part): part is string => Boolean(part))
    if (parts.length) return parts.join('; ')
  }
  return undefined
}

function kindForStatus(status: number): ApiErrorKind {
  if (status === 404) return 'not_found'
  if (status === 409) return 'conflict'
  if (status === 400 || status === 422) return 'validation'
  if (status >= 500) return 'server'
  return 'unknown'
}

function combineSignals(timeoutMs: number, external?: AbortSignal) {
  const controller = new AbortController()
  let timedOut = false

  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  const onExternalAbort = () => controller.abort()
  external?.addEventListener('abort', onExternalAbort)

  return {
    signal: controller.signal,
    didTimeOut: () => timedOut,
    cleanup: () => {
      clearTimeout(timer)
      external?.removeEventListener('abort', onExternalAbort)
    },
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, discardBody = false } = options
  const timeoutMs = options.timeoutMs ?? REQUEST_TIMEOUT_MS
  const { signal, didTimeOut, cleanup } = combineSignals(timeoutMs, options.signal)

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      signal,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (error) {
    if (didTimeOut()) {
      throw new ApiError('The backend took too long to respond.', { kind: 'timeout' })
    }
    if (options.signal?.aborted) {
      throw new ApiError('Request cancelled.', { kind: 'unknown' })
    }
    throw new ApiError(describeTransportFailure(API_BASE_URL), { kind: 'network' })
  } finally {
    cleanup()
  }

  if (discardBody) {
    // Drain so the connection can be reused, then hand back an empty result.
    await response.arrayBuffer().catch(() => undefined)
  }

  if (!response.ok) {
    let detail: string | undefined
    try {
      const payload = await response.json()
      detail = extractDetail(payload)
    } catch {
      detail = undefined
    }
    throw new ApiError(detail ?? defaultMessageFor(response.status), {
      status: response.status,
      kind: kindForStatus(response.status),
    })
  }

  if (discardBody) return undefined as T

  if (response.status === 204) return undefined as T

  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError('The backend returned a malformed response.', {
      status: response.status,
      kind: 'server',
    })
  }
}

function defaultMessageFor(status: number): string {
  if (status === 404) return 'That endpoint was not found on the backend.'
  if (status >= 500) return 'The backend ran into an internal error.'
  return 'The request was rejected by the backend.'
}

/**
 * A rejected `fetch` is deliberately vague in the browser — it hides the
 * reason on purpose. The cause is almost always one of four things, so name
 * them instead of guessing "is it running?" and sending the user hunting.
 */
function describeTransportFailure(baseUrl: string): string {
  if (typeof window === 'undefined') return 'Could not reach the backend.'

  const usingHttps = window.location.protocol === 'https:'
  if (usingHttps && baseUrl.startsWith('http://')) {
    return `The browser blocked an insecure request: this page is ${window.location.protocol}// but the backend is http://. Serve the app over http in development, or put the API behind https.`
  }

  const origin = window.location.origin
  return [
    `The browser could not reach ${baseUrl} (page origin: ${origin}).`,
    'One of these is usually the cause: the backend is not running;',
    `CORS is rejecting ${origin} — add it to CORS_ORIGINS in the backend .env;`,
    'or the URL is wrong for this machine (127.0.0.1 points at the browser\'s host).',
  ].join(' ')
}

/**
 * Some routes exist in more than one shape (the current backend and the
 * documented RESTful contract differ on method and path). We try them in
 * order and only fall through on 404/405 — a real 400 or 500 is a genuine
 * failure and is surfaced immediately.
 */
export async function requestAny<T>(
  attempts: Array<{ path: string; options?: RequestOptions }>,
): Promise<T> {
  let lastError: ApiError | undefined

  for (const attempt of attempts) {
    try {
      return await request<T>(attempt.path, attempt.options)
    } catch (error) {
      if (!(error instanceof ApiError)) throw error
      lastError = error
      const routeMissing = error.status === 404 || error.status === 405
      if (!routeMissing) throw error
    }
  }

  throw lastError ?? new ApiError('No matching backend route was found.')
}
