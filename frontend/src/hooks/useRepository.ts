import { useCallback, useEffect, useRef, useState } from 'react'
import { api, isValidGithubUrl, normaliseGithubUrl } from '@/lib/api'
import { ApiError } from '@/lib/http'
import type { Repository } from '@/types/api'

export type ConnectState = 'idle' | 'working' | 'ready' | 'error'

/** Ordered ingestion stages, mirroring the backend's actual pipeline. */
const INDEXING_STAGES = ['parsing', 'chunking', 'embedding'] as const
type IndexingStage = (typeof INDEXING_STAGES)[number]
export type ActiveStage = 'cloning' | IndexingStage

const ACTIVE_REPO_KEY = 'cra:active-repository-id'

/**
 * Owns the repository lifecycle: register -> clone -> parse/chunk/embed -> ready.
 *
 * The backend performs indexing inside one synchronous request, so the
 * parse/chunk/embed labels advance on a timer to keep the wait legible. The
 * labels themselves are real pipeline stages, not invented ones.
 */
export function useRepository() {
  const [state, setState] = useState<ConnectState>('idle')
  const [repository, setRepository] = useState<Repository | null>(null)
  const [stage, setStage] = useState<ActiveStage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const connect = useCallback(async (rawUrl: string) => {
    const url = normaliseGithubUrl(rawUrl)

    if (!isValidGithubUrl(url)) {
      setState('error')
      setError('That does not look like a GitHub repository URL.')
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const { signal } = controller

    setState('working')
    setError(null)
    setStage('cloning')

    try {
      const repo = await api.createRepository(url, signal)
      if (signal.aborted) return
      setRepository(repo)
      window.localStorage.setItem(ACTIVE_REPO_KEY, String(repo.id))

      // Clone — a no-op when the repository is already on disk, and refused by
      // the backend only if a run is genuinely in flight (it can tell a live
      // run from an abandoned one, which the client cannot).
      if (repo.status !== 'completed') {
        try {
          await api.cloneRepository(repo.id, signal)
        } catch (cloneError) {
          // "already been processed" means the clone exists; carry on to indexing.
          const alreadyCloned =
            cloneError instanceof ApiError &&
            cloneError.status === 400 &&
            /already been processed|already being processed/i.test(cloneError.message)
          if (!alreadyCloned) throw cloneError
        }
      }
      if (signal.aborted) return

      // Index — advance through the real sub-stages while the call runs.
      let stageIndex = 0
      setStage(INDEXING_STAGES[0])
      const ticker = window.setInterval(() => {
        stageIndex = Math.min(stageIndex + 1, INDEXING_STAGES.length - 1)
        setStage(INDEXING_STAGES[stageIndex])
      }, 3_500)

      try {
        await api.indexRepository(repo.id, signal)
      } finally {
        window.clearInterval(ticker)
      }
      if (signal.aborted) return

      setStage(null)
      setState('ready')
      setRepository((current) => (current ? { ...current, status: 'completed' } : current))
    } catch (caught) {
      if (signal.aborted) return
      setStage(null)
      setState('error')
      setError(describeIngestError(caught))
    }
  }, [])

  /** Re-open a repository that was connected in a previous session. */
  const restore = useCallback(async () => {
    const storedId = Number(window.localStorage.getItem(ACTIVE_REPO_KEY))
    if (!Number.isFinite(storedId) || storedId <= 0) return

    setState('working')
    setStage('cloning')
    try {
      const repo = await api.getRepository(storedId)
      if (!repo) {
        window.localStorage.removeItem(ACTIVE_REPO_KEY)
        setState('idle')
        return
      }
      // Only a fully indexed repository has anything to search. The backend now
      // keeps the status honest (`processing` until chunks are stored, `failed`
      // if indexing errored), so trust it instead of opening an empty workspace
      // that would answer every question with "no relevant code found".
      if (repo.status !== 'completed') {
        window.localStorage.removeItem(ACTIVE_REPO_KEY)
        setState('idle')
        setError(
          repo.status === 'processing'
            ? 'That repository was still being indexed when you left. Reconnect it to finish indexing.'
            : 'That repository did not finish indexing. Reconnect it to try again.',
        )
        return
      }
      setRepository(repo)
      setStage(null)
      setState('ready')
    } catch {
      window.localStorage.removeItem(ACTIVE_REPO_KEY)
      setState('idle')
    }
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    window.localStorage.removeItem(ACTIVE_REPO_KEY)
    setRepository(null)
    setStage(null)
    setError(null)
    setState('idle')
  }, [])

  return { state, repository, stage, error, connect, reset, restore }
}

function describeIngestError(caught: unknown): string {
  if (caught instanceof ApiError) {
    if (caught.kind === 'network') return caught.message
    if (caught.kind === 'timeout') return 'Indexing took longer than expected. Try again.'
    if (/not found/i.test(caught.message)) return 'Repository not found. Reconnect it and try again.'
    if (caught.status === 500) return 'Analysis failed while processing the repository.'
    return caught.message
  }
  if (caught instanceof Error) return caught.message
  return 'Something went wrong while connecting the repository.'
}
