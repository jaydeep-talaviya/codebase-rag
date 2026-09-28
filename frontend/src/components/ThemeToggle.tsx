import { Moon, Sun } from 'lucide-react'

export function ThemeToggle({
  theme,
  onToggle,
}: {
  theme: 'dark' | 'light'
  onToggle: () => void
}) {
  const next = theme === 'dark' ? 'light' : 'dark'

  return (
    <button
      type="button"
      onClick={onToggle}
      title={`Switch to ${next} mode`}
      aria-label={`Switch to ${next} mode`}
      className="inline-flex size-9 items-center justify-center rounded-lg border border-line bg-surface text-muted transition-colors duration-200 hover:border-line-strong hover:text-fg"
    >
      {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  )
}
