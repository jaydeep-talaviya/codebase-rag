import { AlertTriangle, RotateCw, SearchX } from 'lucide-react'

/**
 * One component for every failure the user can hit, chosen from a small set of
 * visually distinct variants so the cause is obvious at a glance.
 */
export function ErrorPanel({
  message,
  variant = 'error',
  onRetry,
  retryLabel = 'Try again',
  compact = false,
}: {
  /** Backend-supplied reason. Ignored by the `empty` variant, which is fixed copy. */
  message?: string
  variant?: 'error' | 'empty'
  onRetry?: () => void
  retryLabel?: string
  compact?: boolean
}) {
  const isEmpty = variant === 'empty'
  const Icon = isEmpty ? SearchX : AlertTriangle
  const tone = isEmpty
    ? 'border-warn/25 bg-warn/[0.06] text-warn'
    : 'border-danger/25 bg-danger/[0.06] text-danger'

  return (
    <div
      role="alert"
      className={`animate-pop-in flex gap-3 rounded-[10px] border ${tone} ${
        compact ? 'px-3 py-2.5' : 'px-4 py-3.5'
      }`}
    >
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className={`font-medium ${isEmpty ? 'text-warn' : 'text-danger'}`}>
          {isEmpty ? "We couldn't find enough relevant code" : 'Request failed'}
        </p>
        <p className="mt-0.5 text-[13px] leading-relaxed text-muted">
          {isEmpty
            ? "We couldn't find enough relevant code to answer this question. Try rephrasing it, or ask about a different area of the repository."
            : (message ?? 'An unexpected error occurred.')}
        </p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[12px] text-fg transition-colors duration-200 hover:border-line-strong hover:bg-surface-2"
          >
            <RotateCw className="size-3.5" />
            {retryLabel}
          </button>
        )}
      </div>
    </div>
  )
}
