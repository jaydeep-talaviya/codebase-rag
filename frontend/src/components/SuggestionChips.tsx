import { ArrowRight, Sparkles } from 'lucide-react'

const SUGGESTIONS = [
  'How does authentication work?',
  'Where is the database connection configured?',
  'How are API requests handled?',
  'Where is Redis used?',
  'Explain the payment flow.',
]

export function SuggestionChips({
  onSelect,
  title = 'Try one of these',
}: {
  onSelect: (question: string) => void
  title?: string
}) {
  return (
    <div className="animate-fade-up mx-auto w-full max-w-2xl px-1 py-6">
      <div className="mb-4 flex items-center gap-2">
        <Sparkles className="size-3.5 text-accent" />
        <h2 className="text-[12px] font-semibold uppercase tracking-[0.12em] text-faint">
          {title}
        </h2>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => onSelect(question)}
            className="group flex items-center justify-between gap-3 rounded-xl border border-line bg-surface px-3.5 py-3 text-left transition-all duration-200 hover:-translate-y-px hover:border-accent/40 hover:bg-surface-2"
          >
            <span className="text-[13px] leading-snug text-muted transition-colors group-hover:text-fg">
              {question}
            </span>
            <ArrowRight className="size-3.5 shrink-0 text-faint opacity-0 transition-all duration-200 group-hover:translate-x-0.5 group-hover:text-accent group-hover:opacity-100" />
          </button>
        ))}
      </div>
    </div>
  )
}
