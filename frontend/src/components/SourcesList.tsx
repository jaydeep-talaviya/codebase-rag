import { Quote } from 'lucide-react'
import { SourceCard } from './SourceCard'
import type { SourceRef } from '@/types/api'

export function SourcesList({
  sources,
  repositoryId,
}: {
  sources: SourceRef[]
  repositoryId?: number
}) {
  if (sources.length === 0) return null

  return (
    <div className="mt-4 border-t border-line pt-3.5">
      <div className="mb-2.5 flex items-center gap-2">
        <Quote className="size-3.5 text-faint" />
        <h4 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
          Sources
        </h4>
        <span className="rounded-full border border-line bg-surface-2 px-1.5 py-px font-mono text-[10px] text-faint">
          {sources.length}
        </span>
      </div>
      <div className="space-y-1.5">
        {sources.map((source, index) => (
          <SourceCard
            key={`${source.filePath}:${source.startLine}:${index}`}
            source={source}
            repositoryId={repositoryId}
          />
        ))}
      </div>
    </div>
  )
}
