import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Clock, History, Loader2, Search } from 'lucide-react'
import { api } from '@/lib/api'
import type { Repository } from '@/types/api'

/**
 * Every repository uploaded so far, newest first. Clicking one reopens it as-is —
 * no re-cloning, no re-indexing — because the backend already holds the chunks.
 */
export function RepositoryHistory({
  activeId,
  onOpen,
  disabled,
}: {
  activeId?: number
  onOpen: (id: number) => void
  disabled?: boolean
}) {
  const [repositories, setRepositories] = useState<Repository[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()

    api
      .listRepositories(controller.signal)
      .then((list) => {
        if (!cancelled) setRepositories(list)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [])

  if (repositories === null) {
    return failed ? null : (
      <p className="flex items-center justify-center gap-2 py-6 text-[12px] text-faint">
        <Loader2 className="size-3.5 animate-spin" />
        Loading your repositories…
      </p>
    )
  }

  if (repositories.length === 0) return null

  return (
    <section className="w-full text-left" aria-labelledby="history-heading">
      <h2
        id="history-heading"
        className="mb-3 flex items-center justify-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint"
      >
        <History className="size-3.5" />
        Your repositories
      </h2>

      <ul className="grid gap-2 sm:grid-cols-2">
        {repositories.map((repository) => (
          <li key={repository.id}>
            <HistoryCard
              repository={repository}
              active={repository.id === activeId}
              disabled={disabled}
              onOpen={onOpen}
            />
          </li>
        ))}
      </ul>
    </section>
  )
}

function HistoryCard({
  repository,
  active,
  disabled,
  onOpen,
}: {
  repository: Repository
  active: boolean
  disabled?: boolean
  onOpen: (id: number) => void
}) {
  const { present, detail } = describe(repository)
  const Icon = present ? CheckCircle2 : present === false ? AlertTriangle : Clock
  const selectable = !disabled && repository.status === 'completed' && (repository.chunkCount ?? 0) > 0

  return (
    <button
      type="button"
      onClick={() => selectable && onOpen(repository.id)}
      disabled={!selectable}
      aria-disabled={!selectable}
      className={[
        'group flex w-full items-start gap-3 rounded-[12px] border bg-surface/60 p-3 text-left transition-colors duration-200',
        active
          ? 'border-accent/50 bg-accent/5'
          : selectable
            ? 'border-line hover:border-line-strong hover:bg-surface'
            : 'border-line opacity-60',
        selectable ? 'cursor-pointer' : 'cursor-not-allowed',
      ].join(' ')}
    >
      <span
        className={[
          'mt-px inline-flex size-7 shrink-0 items-center justify-center rounded-lg',
          present === true
            ? 'bg-success/10 text-success'
            : present === false
              ? 'bg-danger/10 text-danger'
              : 'bg-surface-3 text-faint',
        ].join(' ')}
      >
        <Icon className="size-3.5" />
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="truncate text-[13px] font-medium text-fg">{repository.name}</span>
          {active && (
            <span className="shrink-0 rounded border border-accent/40 px-1 py-px text-[9.5px] uppercase tracking-wide text-accent">
              active
            </span>
          )}
        </span>
        <span className="mt-0.5 block truncate font-mono text-[11px] text-faint">
          {repository.url.replace(/^https?:\/\/(www\.)?github\.com\//, '')}
        </span>
        <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted">
          <span className="font-mono">{repository.chunkCount ?? 0} chunks</span>
          <span className="text-faint/60">·</span>
          <span className="text-faint">{detail}</span>
          <ExpiryNote expiresAt={repository.expiresAt} />
        </span>
      </span>

      {selectable && (
        <Search className="mt-1 size-3.5 shrink-0 text-faint opacity-0 transition-opacity group-hover:opacity-100" />
      )}
    </button>
  )
}

/** `present` answers "is this worth opening?", which status alone does not. */
function describe(repository: Repository): { present: boolean | null; detail: string } {
  const chunks = repository.chunkCount
  const when = formatWhen(repository.createdAt)

  if (repository.status === 'completed' && (chunks ?? 0) > 0) {
    return { present: true, detail: when ?? 'indexed' }
  }
  if (repository.status === 'failed') {
    return { present: false, detail: 'indexing failed' }
  }
  if (repository.status === 'processing') {
    return { present: null, detail: 'indexing…' }
  }
  if (repository.status === 'completed') {
    return { present: false, detail: 'nothing indexed' }
  }
  return { present: null, detail: 'not indexed' }
}

/**
 * How long this repository has left before the sweeper reclaims it.
 *
 * Renders nothing when the backend sends no deadline, which is the case for an
 * older backend or when cleanup is switched off — better to say nothing than to
 * invent a promise the backend will not keep.
 *
 * The wording is "expires in", not "removed in": "removed in 7h" reads as past
 * tense in English, which is the opposite of the intent.
 */
function ExpiryNote({ expiresAt }: { expiresAt?: string }) {
  const label = formatExpiry(expiresAt)
  if (!label) return null

  const overdue = isOverdue(expiresAt)

  return (
    <>
      <span className="text-faint/60">·</span>
      <span
        className={overdue ? 'text-warn' : 'text-faint'}
        title={expiresAt ? `Eligible for cleanup after ${new Date(expiresAt).toLocaleString()}` : undefined}
      >
        {label}
      </span>
    </>
  )
}

function isOverdue(iso: string | undefined): boolean {
  if (!iso) return false
  const at = new Date(iso).getTime()
  return !Number.isNaN(at) && at - Date.now() <= 0
}

function formatExpiry(iso: string | undefined): string | null {
  if (!iso) return null
  const at = new Date(iso).getTime()
  if (Number.isNaN(at)) return null

  const ms = at - Date.now()

  // Past the threshold but not yet deleted: the sweeper runs on an interval, so
  // claiming "now" would be a lie. This is the state a user should notice and
  // act on, hence the warning colour.
  if (ms <= 0) return 'expiring soon'

  // Round up so a repository with 40 minutes left never reads "0m".
  const minutes = Math.ceil(ms / 60_000)
  if (minutes < 60) return `expires in ${minutes}m`

  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `expires in ${hours}h`
  return `expires in ${Math.floor(hours / 24)}d`
}

function formatWhen(iso: string | undefined): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null

  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000)
  if (days <= 0) return 'added today'
  if (days === 1) return 'added yesterday'
  if (days < 30) return `added ${days} days ago`
  return `added ${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`
}
