import { ExternalLink, RefreshCw } from 'lucide-react'
import { GitHubMark } from './GitHubMark'
import { StatusBadge } from './StatusBadge'
import type { Repository } from '@/types/api'

export function RepoTopBar({
  repository,
  onReconnect,
}: {
  repository: Repository
  onReconnect: () => void
}) {
  return (
    <div className="border-b border-line bg-canvas-soft/80 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
        <GitHubMark className="size-4 shrink-0 text-fg" />

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2.5">
            <h1 className="truncate text-[14px] font-semibold tracking-tight text-fg">
              {repository.name}
            </h1>
            <StatusBadge status={repository.status} />
          </div>
          <a
            href={repository.url}
            target="_blank"
            rel="noreferrer noopener"
            className="mt-0.5 inline-flex max-w-full items-center gap-1 font-mono text-[11.5px] text-faint transition-colors hover:text-accent"
          >
            <span className="truncate">{repository.url}</span>
            <ExternalLink className="size-3 shrink-0" />
          </a>
        </div>

        <button
          type="button"
          onClick={onReconnect}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[12px] text-muted transition-colors duration-200 hover:border-line-strong hover:text-fg"
        >
          <RefreshCw className="size-3.5" />
          Switch repository
        </button>
      </div>
    </div>
  )
}
