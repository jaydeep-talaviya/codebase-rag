/**
 * The contract between the UI and the backend.
 *
 * The backend speaks snake_case; the UI speaks camelCase. All translation
 * happens in `src/lib/api.ts` so that no component ever touches a raw payload.
 */

export type RepositoryStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface Repository {
  id: number
  name: string
  url: string
  status: RepositoryStatus
}

/** A single citation returned alongside an answer. */
export interface SourceRef {
  filePath: string
  startLine: number
  endLine: number
  /** Pygments display name, e.g. "Python". Optional — the API may omit it. */
  language?: string
  /**
   * Raw snippet. Older/newer backends may inline this; when it is absent the UI
   * fetches the whole file via `GET /repositories/{id}/files/{path}` instead.
   */
  content?: string
}

/** A whole file fetched from an indexed repository clone. */
export interface RepositoryFile {
  filePath: string
  language: string
  content: string
  lineCount: number
}

export interface AskAnswer {
  answer: string
  sources: SourceRef[]
}
