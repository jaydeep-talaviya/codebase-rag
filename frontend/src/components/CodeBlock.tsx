import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { highlightLines, resolveLanguage } from '@/lib/highlight'

interface CodeBlockProps {
  code: string
  /** Pygments name ("Python") or hljs id ("python"). */
  language?: string
  /** Line number shown in the gutter for the first row. */
  startLine?: number
  showLineNumbers?: boolean
  maxHeight?: number
  /** Inclusive 1-based range to tint, e.g. the lines a citation points at. */
  highlightRange?: { start: number; end: number }
}

export function CodeBlock({
  code,
  language,
  startLine = 1,
  showLineNumbers = true,
  maxHeight,
  highlightRange,
}: CodeBlockProps) {
  const resolved = resolveLanguage(language, language)
  const lines = useMemo(() => highlightLines(code, resolved), [code, resolved])
  const [copied, setCopied] = useState(false)
  const gutterWidth = `${String(startLine + lines.length - 1).length + 1}ch`

  // Index of the first row inside the highlight range, for scroll-into-view.
  const firstMarkedIndex = useMemo(() => {
    if (highlightRange === undefined) return -1
    const index = highlightRange.start - startLine
    return index >= 0 && index < lines.length ? index : -1
  }, [highlightRange, startLine, lines.length])

  // Open the file on the cited lines instead of at the top.
  const scrollerRef = useRef<HTMLDivElement>(null)
  const firstMarkedRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const scroller = scrollerRef.current
    const marked = firstMarkedRef.current
    if (!scroller || !marked || !maxHeight) return
    scroller.scrollTop = Math.max(
      0,
      marked.offsetTop - scroller.clientHeight / 2 + marked.offsetHeight / 2,
    )
  }, [code, highlightRange, maxHeight])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1_600)
    } catch {
      // Clipboard is unavailable (insecure context) — silently ignore.
    }
  }

  return (
    <div className="overflow-hidden rounded-[10px] border border-line bg-canvas-soft">
      <div className="flex items-center justify-between border-b border-line bg-surface-2/60 px-3 py-1.5">
        <span className="font-mono text-[11px] uppercase tracking-wider text-faint">
          {language ?? 'text'}
        </span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-faint transition-colors hover:bg-surface-3 hover:text-muted"
          aria-label="Copy code"
        >
          {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      <div
        ref={scrollerRef}
        className="relative overflow-auto"
        style={maxHeight ? { maxHeight: `${maxHeight}px` } : undefined}
      >
        <pre className="min-w-full py-2 font-mono text-[12.5px] leading-[1.65]">
          <code>
            {lines.map((html, index) => {
              const lineNo = startLine + index
              const marked =
                highlightRange !== undefined &&
                lineNo >= highlightRange.start &&
                lineNo <= highlightRange.end
              return (
                <div
                  key={index}
                  ref={marked && index === firstMarkedIndex ? firstMarkedRef : undefined}
                  className={
                    marked
                      ? 'flex border-l-2 border-accent bg-accent/10'
                      : 'flex border-l-2 border-transparent hover:bg-surface-2/50'
                  }
                >
                  {showLineNumbers && (
                    <span
                      aria-hidden="true"
                      className={
                        marked
                          ? 'sticky left-0 shrink-0 select-none bg-accent/20 pr-3 text-right font-semibold text-accent'
                          : 'sticky left-0 shrink-0 select-none bg-canvas-soft pr-3 text-right text-faint/70'
                      }
                      style={{ width: gutterWidth }}
                    >
                      {lineNo}
                    </span>
                  )}
                  <span
                    className="pr-4 whitespace-pre"
                    dangerouslySetInnerHTML={{ __html: html === '' ? ' ' : html }}
                  />
                </div>
              )
            })}
          </code>
        </pre>
      </div>
    </div>
  )
}
