import { Check, GitBranch, Loader2, Scissors, Search, Sparkles } from 'lucide-react'
import type { ActiveStage } from '@/hooks/useRepository'

const STAGES: Array<{
  key: ActiveStage
  label: string
  hint: string
  Icon: typeof GitBranch
}> = [
  { key: 'cloning', label: 'Cloning', hint: 'Fetching the repository', Icon: GitBranch },
  { key: 'parsing', label: 'Parsing', hint: 'Filtering and reading source files', Icon: Search },
  { key: 'chunking', label: 'Chunking', hint: 'Splitting code with line offsets', Icon: Scissors },
  { key: 'embedding', label: 'Embedding', hint: 'Storing vectors in pgvector', Icon: Sparkles },
]

export function IngestProgress({ stage }: { stage: ActiveStage | null }) {
  const currentIndex = STAGES.findIndex((entry) => entry.key === stage)

  return (
    <div className="animate-fade-up w-full max-w-lg rounded-[14px] border border-line bg-surface p-5">
      <div className="mb-4 flex items-center gap-2.5">
        <Loader2 className="size-4 animate-spin text-accent" />
        <h2 className="text-[13.5px] font-semibold text-fg">Indexing your codebase</h2>
      </div>

      <ol className="space-y-3">
        {STAGES.map((entry, index) => {
          const done = currentIndex > index
          const active = currentIndex === index
          const { Icon } = entry

          return (
            <li key={entry.key} className="flex items-start gap-3">
              <span
                className={`mt-px inline-flex size-5 shrink-0 items-center justify-center rounded-full border transition-colors duration-300 ${
                  done
                    ? 'border-success/40 bg-success/15 text-success'
                    : active
                      ? 'animate-pulse-ring border-accent/50 bg-accent/15 text-accent'
                      : 'border-line bg-surface-2 text-faint'
                }`}
              >
                {done ? (
                  <Check className="size-3" strokeWidth={3} />
                ) : (
                  <Icon className="size-3" />
                )}
              </span>

              <div className="min-w-0 flex-1">
                <p
                  className={`text-[13px] font-medium transition-colors duration-300 ${
                    active ? 'text-fg' : done ? 'text-muted' : 'text-faint'
                  }`}
                >
                  {entry.label}
                </p>
                <p className="text-[11.5px] text-faint">{entry.hint}</p>
              </div>

              {active && (
                <span className="mt-1 flex items-end gap-0.5" aria-hidden="true">
                  {[0, 1, 2].map((bar) => (
                    <span
                      key={bar}
                      className="w-0.5 animate-pulse rounded-full bg-accent"
                      style={{ height: `${6 + bar * 3}px`, animationDelay: `${bar * 150}ms` }}
                    />
                  ))}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
