import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { ApiError } from '@/lib/http'
import type { SourceRef } from '@/types/api'

export type Role = 'user' | 'assistant'

export interface Message {
  id: string
  role: Role
  text: string
  sources?: SourceRef[]
  /** Present on assistant messages that failed. */
  error?: string
  /** The backend answered, but retrieval surfaced nothing citable. */
  noResults?: boolean
  /** The question this message answered, kept so retry can re-send it. */
  question?: string
}

export const RETRIEVAL_STAGES = [
  'Searching your codebase…',
  'Finding relevant code…',
  'Generating answer…',
] as const

let counter = 0
const nextId = () => `m${(counter += 1)}`

/** Owns the conversation transcript and the in-flight ask lifecycle. */
export function useChat(repositoryId: number | null) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isAsking, setIsAsking] = useState(false)
  const [stageIndex, setStageIndex] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    setMessages([])
    setError(null)
  }, [repositoryId])

  useEffect(() => () => abortRef.current?.abort(), [])

  const ask = useCallback(
    async (question: string) => {
      const trimmed = question.trim()
      if (!trimmed || !repositoryId || isAsking) return

      const userMessage: Message = { id: nextId(), role: 'user', text: trimmed }
      const placeholderId = nextId()
      const placeholder: Message = { id: placeholderId, role: 'assistant', text: '', question: trimmed }

      setMessages((current) => [...current, userMessage, placeholder])
      setIsAsking(true)
      setError(null)
      setStageIndex(0)

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      const { signal } = controller

      // The backend runs retrieve -> rerank -> generate as one call, so the
      // stage labels advance on a timer to keep the wait legible.
      const ticker = window.setInterval(() => {
        setStageIndex((index) => Math.min(index + 1, RETRIEVAL_STAGES.length - 1))
      }, 2_200)

      try {
        const result = await api.askRepository(repositoryId, trimmed, signal)
        if (signal.aborted) return
        setMessages((current) =>
          current.map((message) =>
            message.id === placeholderId
              ? {
                  ...message,
                  text: result.answer,
                  sources: result.sources,
                  noResults: result.sources.length === 0,
                }
              : message,
          ),
        )
      } catch (caught) {
        if (signal.aborted) return
        const message = describeAskError(caught)
        setMessages((current) =>
          current.map((item) =>
            item.id === placeholderId
              ? { ...item, text: '', sources: [], error: message }
              : item,
          ),
        )
        setError(message)
      } finally {
        window.clearInterval(ticker)
        if (!controller.signal.aborted) setIsAsking(false)
      }
    },
    [repositoryId, isAsking],
  )

  /** Re-ask the last question, dropping its failed turn. */
  const retry = useCallback(() => {
    const lastUser = [...messages].reverse().find((message) => message.role === 'user')
    if (!lastUser) return
    setMessages((current) => current.filter((message) => message.role === 'user'))
    setError(null)
    // Defer so the filtered state commits before the new turn is appended.
    window.setTimeout(() => {
      void ask(lastUser.text)
    }, 0)
  }, [messages, ask])

  const stop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsAsking(false)
    setStageIndex(0)
  }, [])

  return { messages, isAsking, stageIndex, error, ask, retry, stop }
}

function describeAskError(caught: unknown): string {
  if (caught instanceof ApiError) {
    if (caught.kind === 'network') return caught.message
    if (caught.kind === 'timeout') return 'The assistant took too long to answer. Try again.'
    if (caught.status === 404) {
      return 'Repository not ready. It may not be indexed yet — try reconnecting.'
    }
    if (/llm|model|openrouter|completion|rate.?limit|insufficient/i.test(caught.message)) {
      return 'The language model returned an error. Check the backend LLM configuration and retry.'
    }
    if (caught.status >= 500) return 'The backend failed while answering this question.'
    return caught.message
  }
  if (caught instanceof Error) return caught.message
  return 'Something went wrong while answering this question.'
}
