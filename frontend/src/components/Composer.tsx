import { useEffect, useRef } from 'react'
import { ArrowUp, Square } from 'lucide-react'

export function Composer({
  value,
  onChange,
  onSend,
  onStop,
  isAsking,
  disabled,
}: {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  onStop: () => void
  isAsking: boolean
  disabled?: boolean
}) {
  const ref = useRef<HTMLTextAreaElement>(null)

  // Auto-grow up to a cap, then scroll.
  useEffect(() => {
    const node = ref.current
    if (!node) return
    node.style.height = '0px'
    node.style.height = `${Math.min(node.scrollHeight, 180)}px`
  }, [value])

  const canSend = value.trim().length > 0 && !isAsking && !disabled

  return (
    <div className="rounded-[14px] border border-line bg-surface shadow-lg shadow-black/5 transition-colors duration-200 focus-within:border-accent/50">
      <textarea
        ref={ref}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            if (canSend) onSend()
          }
        }}
        rows={1}
        disabled={disabled}
        placeholder="Ask anything about this repository…"
        aria-label="Ask a question about the repository"
        className="max-h-[180px] w-full resize-none bg-transparent px-4 pt-3.5 pb-2 text-[14px] leading-relaxed text-fg placeholder:text-faint focus:outline-none disabled:opacity-50"
      />

      <div className="flex items-center justify-between px-2.5 pb-2.5">
        <span className="pl-1.5 text-[11px] text-faint">
          <kbd className="rounded border border-line bg-surface-2 px-1 py-px font-mono text-[10px]">
            Enter
          </kbd>{' '}
          to send ·{' '}
          <kbd className="rounded border border-line bg-surface-2 px-1 py-px font-mono text-[10px]">
            Shift + Enter
          </kbd>{' '}
          for a new line
        </span>

        {isAsking ? (
          <button
            type="button"
            onClick={() => onStop()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface-2 px-2.5 py-1.5 text-[12px] text-muted transition-colors hover:border-line-strong hover:text-fg"
          >
            <Square className="size-3 fill-current" />
            Stop
          </button>
        ) : (
          <button
            type="button"
            onClick={() => onSend()}
            disabled={!canSend}
            aria-label="Send question"
            className="inline-flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent-strong text-white transition-all duration-200 hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:brightness-100"
          >
            <ArrowUp className="size-4" strokeWidth={2.5} />
          </button>
        )}
      </div>
    </div>
  )
}
