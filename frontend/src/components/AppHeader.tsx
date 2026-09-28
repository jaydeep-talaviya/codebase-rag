import { Logo } from './Logo'
import { GitHubMark } from './GitHubMark'
import { ThemeToggle } from './ThemeToggle'
import { API_BASE_URL, apiDisplayHost } from '@/lib/env'

export function AppHeader({
  theme,
  onToggleTheme,
  backendOnline,
}: {
  theme: 'dark' | 'light'
  onToggleTheme: () => void
  backendOnline: boolean | null
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-canvas/85 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
        <Logo />

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[14px] font-semibold tracking-tight text-fg">
            Codebase RAG Assistant
          </h1>
          <p className="hidden truncate text-[11.5px] text-faint sm:block">
            Ask questions about your codebase with AI
          </p>
        </div>

        <div
          className="hidden items-center gap-2 rounded-lg border border-line bg-surface px-2.5 py-1.5 md:flex"
          title={
            backendOnline === null
              ? 'Checking backend…'
              : `${API_BASE_URL} — ${backendOnline ? 'reachable' : 'unreachable'}`
          }
        >
          <GitHubMark className="size-3.5 text-faint" />
          <span className="font-mono text-[11px] text-muted">
            {apiDisplayHost()}
          </span>
          <span
            className={`size-1.5 rounded-full ${
              backendOnline === null
                ? 'bg-faint'
                : backendOnline
                  ? 'bg-success'
                  : 'bg-danger animate-pulse'
            }`}
          />
        </div>

        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </div>
    </header>
  )
}
