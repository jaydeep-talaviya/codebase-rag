import { GitPullRequest, Layers, Search, Sparkles, Workflow } from 'lucide-react'
import { ConnectForm } from './ConnectForm'
import { IngestProgress } from './IngestProgress'
import { ErrorPanel } from './ErrorPanel'
import type { ActiveStage, ConnectState } from '@/hooks/useRepository'

const CAPABILITIES = [
  {
    Icon: Search,
    title: 'Semantic search',
    body: 'Queries are embedded and matched against your code with pgvector, not keyword grep.',
  },
  {
    Icon: Layers,
    title: 'Reranked context',
    body: 'A cross-encoder re-scores every candidate chunk so the model sees the most relevant code.',
  },
  {
    Icon: Workflow,
    title: 'Grounded answers',
    body: 'The model answers only from retrieved snippets and cites the exact files and lines.',
  },
]

export function Landing({
  state,
  stage,
  error,
  onConnect,
  onRetry,
}: {
  state: ConnectState
  stage: ActiveStage | null
  error: string | null
  onConnect: (url: string) => void
  onRetry: () => void
}) {
  const working = state === 'working'

  return (
    <div className="relative">
      <div className="backdrop-grid pointer-events-none absolute inset-x-0 top-0 h-[420px]" aria-hidden="true" />

      <div className="relative mx-auto w-full max-w-5xl px-4 py-16 sm:px-6 sm:py-24">
        <div className="flex flex-col items-center text-center">
          <span className="animate-pop-in mb-6 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-[11.5px] text-muted">
            <GitPullRequest className="size-3 text-accent" />
            Retrieval-augmented generation over your own code
          </span>

          <h1 className="text-gradient max-w-3xl text-4xl font-bold leading-[1.1] tracking-tight sm:text-5xl">
            Ask questions about your codebase
          </h1>

          <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-muted">
            Connect a GitHub repository and ask questions about its code. The AI
            searches your codebase, finds relevant files, and answers with source
            references.
          </p>

          <div className="mt-9 w-full">
            {working ? (
              <div className="flex justify-center">
                <IngestProgress stage={stage} />
              </div>
            ) : (
              <div className="flex justify-center">
                <ConnectForm onSubmit={onConnect} isWorking={working} />
              </div>
            )}
          </div>

          {error && !working && (
            <div className="mt-5 w-full max-w-xl text-left">
              <ErrorPanel message={error} onRetry={onRetry} />
            </div>
          )}

          <div className="mt-16 grid w-full gap-3 sm:grid-cols-3">
            {CAPABILITIES.map(({ Icon, title, body }) => (
              <div
                key={title}
                className="rounded-[14px] border border-line bg-surface/60 p-4 text-left transition-colors duration-200 hover:border-line-strong"
              >
                <span className="mb-2.5 inline-flex size-8 items-center justify-center rounded-lg bg-accent/10 text-accent">
                  <Icon className="size-4" />
                </span>
                <h3 className="text-[13px] font-semibold text-fg">{title}</h3>
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{body}</p>
              </div>
            ))}
          </div>

          <p className="mt-10 flex items-center gap-1.5 text-[11.5px] text-faint">
            <Sparkles className="size-3" />
            Clone · parse · chunk · embed · search · rerank · cite
          </p>
        </div>
      </div>
    </div>
  )
}
