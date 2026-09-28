import { RETRIEVAL_STAGES } from '@/hooks/useChat'

export function ThinkingIndicator({ stageIndex }: { stageIndex: number }) {
  const stage = RETRIEVAL_STAGES[stageIndex] ?? RETRIEVAL_STAGES[0]

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1" aria-hidden="true">
        {[0, 1, 2].map((dot) => (
          <span
            key={dot}
            className="size-1.5 animate-pulse rounded-full bg-accent"
            style={{ animationDelay: `${dot * 160}ms` }}
          />
        ))}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] text-muted">{stage}</p>
        <div className="mt-1.5 h-px w-full overflow-hidden rounded-full bg-line">
          <div className="skeleton h-full w-1/3" />
        </div>
      </div>
    </div>
  )
}
