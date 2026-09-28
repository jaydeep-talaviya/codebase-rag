/**
 * ============================================================================
 *  API SERVICE LAYER — the only place in the app that knows about HTTP.
 * ============================================================================
 *
 * Components receive plain, camelCase, already-validated objects. If the
 * backend contract changes, this file is the only thing that needs to change.
 *
 * Route notes
 * -----------
 * The deployed FastAPI backend currently exposes:
 *   POST /repositories/?url=...            (url is a *query* parameter)
 *   GET  /repositories/
 *   GET  /repositories/{id}/ingest         (clone)
 *   GET  /repositories/{id}/files          (parse -> chunk -> embed -> store)
 *   GET  /repositories/search?query=&repository_id=
 *
 * while the documented RESTful contract is:
 *   POST /repositories                     (JSON body {url})
 *   POST /repositories/{id}/ingest
 *   POST /repositories/{id}/ask            (JSON body {question})
 *   GET  /repositories/{id}
 *
 * Rather than pick one and break against the other, each operation tries the
 * current shape first and falls back to the documented shape on 404/405.
 * Requests carry the payload in *both* the body and the query string so a
 * body-reading backend and a query-reading backend are both satisfied.
 */

import type { AskAnswer, Repository, RepositoryFile, RepositoryStatus, SourceRef } from '@/types/api'
import { ApiError, request, requestAny } from './http'
import { INGEST_TIMEOUT_MS, REQUEST_TIMEOUT_MS } from './env'

/* -------------------------------------------------------------------------- */
/*                              URL validation                                */
/* -------------------------------------------------------------------------- */

// Mirrors `is_valid_github_url` in app/services/repository.py so the user gets
// instant feedback instead of a round trip that would 400 anyway.
const GITHUB_URL_PATTERN = /^https?:\/\/github\.com\/[\w-]+\/[\w.-]+\/?$/i

export function isValidGithubUrl(value: string): boolean {
  return GITHUB_URL_PATTERN.test(value.trim())
}

export function normaliseGithubUrl(value: string): string {
  return value.trim().replace(/\/+$/, '')
}

export function repoNameFromUrl(url: string): string {
  return normaliseGithubUrl(url).split('/').pop() || url
}

/* -------------------------------------------------------------------------- */
/*                              Normalisation                                 */
/* -------------------------------------------------------------------------- */

const VALID_STATUSES: readonly RepositoryStatus[] = [
  'pending',
  'processing',
  'completed',
  'failed',
]

function toRepository(raw: unknown): Repository | null {
  if (typeof raw !== 'object' || raw === null) return null
  const record = raw as Record<string, unknown>

  const id = Number(record.id)
  if (!Number.isFinite(id)) return null

  const url = typeof record.url === 'string' ? record.url : ''
  const rawStatus = typeof record.status === 'string' ? record.status.toLowerCase() : ''
  const status = VALID_STATUSES.includes(rawStatus as RepositoryStatus)
    ? (rawStatus as RepositoryStatus)
    : 'pending'

  return {
    id,
    url,
    name: typeof record.name === 'string' && record.name ? record.name : repoNameFromUrl(url),
    status,
  }
}

function toSourceRef(raw: unknown): SourceRef | null {
  if (typeof raw !== 'object' || raw === null) return null
  const record = raw as Record<string, unknown>

  const filePath =
    (typeof record.file_path === 'string' && record.file_path) ||
    (typeof record.filePath === 'string' && record.filePath) ||
    (typeof record.path === 'string' && record.path)
  if (!filePath) return null

  const startLine = Number(record.start_line ?? record.startLine ?? 0)
  const endLine = Number(record.end_line ?? record.endLine ?? startLine)
  const language = record.language
  const content = record.content ?? record.snippet

  return {
    filePath,
    startLine: Number.isFinite(startLine) ? startLine : 0,
    endLine: Number.isFinite(endLine) ? endLine : 0,
    language: typeof language === 'string' && language ? language : undefined,
    content: typeof content === 'string' ? content : undefined,
  }
}

function toAnswer(raw: unknown): AskAnswer {
  if (typeof raw !== 'object' || raw === null) {
    throw new ApiError('The backend returned an unexpected answer payload.', { kind: 'server' })
  }
  const record = raw as Record<string, unknown>
  const answer = typeof record.answer === 'string' ? record.answer : ''
  const rawSources = Array.isArray(record.sources) ? record.sources : []

  const sources = rawSources
    .map(toSourceRef)
    .filter((source): source is SourceRef => source !== null)
    .filter(dedupeByFileRange)

  return { answer, sources }
}

/** The same file+range can legitimately appear twice after retrieval. */
function dedupeByFileRange(source: SourceRef, index: number, all: SourceRef[]): boolean {
  return !all.slice(0, index).some(
    (other) =>
      other.filePath === source.filePath &&
      other.startLine === source.startLine &&
      other.endLine === source.endLine,
  )
}

/* -------------------------------------------------------------------------- */
/*                                 Operations                                 */
/* -------------------------------------------------------------------------- */

export const api = {
  /** Liveness probe. Used by the connection banner, never blocks the UI. */
  async health(signal?: AbortSignal): Promise<boolean> {
    try {
      await request<unknown>('/health', { signal, timeoutMs: 4_000 })
      return true
    } catch {
      return false
    }
  },

  /** Register a repository. Returns the existing row if the URL is known. */
  createRepository(url: string, signal?: AbortSignal): Promise<Repository> {
    const clean = normaliseGithubUrl(url)
    return requestAny<Repository>([
      { path: '/repositories/', options: { method: 'POST', body: { url: clean }, query: { url: clean }, signal } },
      { path: '/repositories', options: { method: 'POST', body: { url: clean }, signal } },
    ]).then((raw) => {
      const repo = toRepository(raw)
      if (!repo) throw new ApiError('Could not create the repository.', { kind: 'server' })
      return repo
    })
  },

  listRepositories(signal?: AbortSignal): Promise<Repository[]> {
    return request<unknown>('/repositories/', { signal }).then((raw) => {
      if (!Array.isArray(raw)) return []
      return raw.map(toRepository).filter((repo): repo is Repository => repo !== null)
    })
  },

  /**
   * Fetch a single repository, preferring the dedicated route and falling
   * back to locating it in the collection.
   */
  async getRepository(id: number, signal?: AbortSignal): Promise<Repository | null> {
    try {
      const raw = await request<unknown>(`/repositories/${id}`, { signal })
      return toRepository(raw)
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 404) throw error
      const all = await api.listRepositories(signal)
      return all.find((repo) => repo.id === id) ?? null
    }
  },

  /**
   * Clone the repository. The backend marks the row `processing` here and
   * `completed` once the clone lands — indexing is a separate step.
   */
  cloneRepository(id: number, signal?: AbortSignal): Promise<Repository> {
    return requestAny<Repository>([
      { path: `/repositories/${id}/ingest`, options: { method: 'POST', timeoutMs: INGEST_TIMEOUT_MS, signal } },
      { path: `/repositories/${id}/ingest`, options: { method: 'GET', timeoutMs: INGEST_TIMEOUT_MS, signal } },
    ]).then((raw) => toRepository(raw) ?? { id, name: '', url: '', status: 'processing' })
  },

  /**
   * Run the real RAG ingestion: walk files, chunk, embed, store in pgvector.
   * This is one long synchronous backend call, so its body is discarded.
   */
  indexRepository(id: number, signal?: AbortSignal): Promise<void> {
    return requestAny<void>([
      { path: `/repositories/${id}/index`, options: { method: 'POST', timeoutMs: INGEST_TIMEOUT_MS, signal, discardBody: true } },
      { path: `/repositories/${id}/files`, options: { method: 'GET', timeoutMs: INGEST_TIMEOUT_MS, signal, discardBody: true } },
    ])
  },

  /**
   * Fetch a real file from an indexed repository so citations can show code
   * instead of bare coordinates. `filePath` is passed through verbatim — the
   * backend accepts both the stored `data/repositories/{id}/...` form and a
   * repo-relative one.
   */
  fetchRepositoryFile(
    repositoryId: number,
    filePath: string,
    signal?: AbortSignal,
  ): Promise<RepositoryFile> {
    return request<Record<string, unknown>>(
      `/repositories/${repositoryId}/files/${filePath.split('/').map(encodeURIComponent).join('/')}`,
      { method: 'GET', signal, timeoutMs: REQUEST_TIMEOUT_MS },
    ).then(normalizeRepositoryFile)
  },

  /** Ask a question about an indexed repository. */
  askRepository(
    repositoryId: number,
    question: string,
    signal?: AbortSignal,
  ): Promise<AskAnswer> {
    return requestAny<AskAnswer>([
      {
        path: `/repositories/${repositoryId}/ask`,
        options: { method: 'POST', body: { question }, timeoutMs: REQUEST_TIMEOUT_MS, signal },
      },
      {
        path: '/repositories/search',
        options: {
          method: 'GET',
          query: { query: question, repository_id: repositoryId },
          timeoutMs: REQUEST_TIMEOUT_MS,
          signal,
        },
      },
    ]).then(toAnswer)
  },
}

function normalizeRepositoryFile(raw: Record<string, unknown>): RepositoryFile {
  return {
    filePath: String(raw.file_path ?? ''),
    language: String(raw.language ?? 'unknown'),
    content: String(raw.content ?? ''),
    lineCount: Number(raw.line_count ?? 0),
  }
}
