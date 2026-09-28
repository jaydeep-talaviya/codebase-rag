import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, ChevronRight, FileCode2, Loader2 } from 'lucide-react'
import { CodeBlock } from './CodeBlock'
import { inferLanguageFromPath } from '@/lib/language'
import { api } from '@/lib/api'
import type { RepositoryFile, SourceRef } from '@/types/api'

type FileState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; file: RepositoryFile }
  | { status: 'error'; message: string }

export function SourceCard({
  source,
  repositoryId,
}: {
  source: SourceRef
  repositoryId?: number
}) {
  const [open, setOpen] = useState(false)
  const [state, setState] = useState<FileState>({ status: 'idle' })
  const requestRef = useRef(0)

  const fileName = source.filePath.split('/').pop() ?? source.filePath
  const directory = source.filePath.slice(0, source.filePath.length - fileName.length)
  const language = source.language ?? inferLanguageFromPath(source.filePath)
  const rangeLabel =
    source.startLine === source.endLine
      ? `L${source.startLine}`
      : `${source.startLine}–${source.endLine}`

  // Load on first expand and keep it cached, so reopening is instant.
  const load = useCallback(() => {
    if (repositoryId === undefined || state.status === 'ready' || state.status === 'loading') {
      return
    }
    const ticket = ++requestRef.current
    setState({ status: 'loading' })
    api
      .fetchRepositoryFile(repositoryId, source.filePath)
      .then((file) => {
        if (requestRef.current === ticket) setState({ status: 'ready', file })
      })
      .catch((error: unknown) => {
        if (requestRef.current !== ticket) return
        setState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Could not load this file.',
        })
      })
  }, [repositoryId, source.filePath, state.status])

  useEffect(() => () => void requestRef.current++, [])

  const toggle = () => {
    const next = !open
    setOpen(next)
    if (next) load()
  }

  return (
    <div className="overflow-hidden rounded-[10px] border border-line bg-surface-2/40 transition-colors duration-200 hover:border-line-strong">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full items-center gap-2.5 px-3 py-2 text-left"
      >
        <ChevronRight
          className={`size-3.5 shrink-0 text-faint transition-transform duration-200 ${
            open ? 'rotate-90' : ''
          }`}
        />
        <FileCode2 className="size-4 shrink-0 text-accent" />
        <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-fg">
          {directory && <span className="text-faint">{directory}</span>}
          {fileName}
        </span>
        <span className="shrink-0 rounded-md border border-line bg-surface-3 px-1.5 py-0.5 font-mono text-[10.5px] text-muted">
          {rangeLabel}
        </span>
      </button>

      <div
        className="grid transition-all duration-300 ease-out"
        style={{ gridTemplateRows: open ? '1fr' : '0fr' }}
      >
        <div className="overflow-hidden">
          <div className="space-y-2.5 border-t border-line px-3 py-3">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[11.5px]">
              <dt className="text-faint">File</dt>
              <dd className="truncate font-mono text-muted">{source.filePath}</dd>
              <dt className="text-faint">Language</dt>
              <dd className="text-muted">{language ?? 'unknown'}</dd>
              <dt className="text-faint">Cited lines</dt>
              <dd className="font-mono text-muted">
                {source.startLine}–{source.endLine}
              </dd>
            </dl>

            {source.content ? (
              <CodeBlock
                code={source.content}
                language={language}
                startLine={source.startLine}
                maxHeight={340}
              />
            ) : state.status === 'loading' ? (
              <p className="flex items-center gap-2 px-1 py-6 text-[11.5px] text-faint">
                <Loader2 className="size-3.5 animate-spin" />
                Loading file…
              </p>
            ) : state.status === 'error' ? (
              <p className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-[11.5px] leading-relaxed text-muted">
                <AlertTriangle className="mt-px size-3.5 shrink-0 text-danger" />
                <span>{state.message}</span>
              </p>
            ) : state.status === 'ready' ? (
              <>
                <CodeBlock
                  code={state.file.content}
                  language={state.file.language || language}
                  startLine={1}
                  maxHeight={340}
                  highlightRange={{ start: source.startLine, end: source.endLine }}
                />
                <p className="text-[11px] text-faint">
                  Highlighted lines {source.startLine}–{source.endLine} are the cited
                  passage.
                </p>
              </>
            ) : (
              <p className="px-1 py-2 text-[11.5px] text-faint">Loading file…</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
