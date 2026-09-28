import { useState, type FormEvent } from 'react'
import { Loader2, Search, X } from 'lucide-react'
import { isValidGithubUrl, normaliseGithubUrl } from '@/lib/api'
import { GitHubMark } from './GitHubMark'

const PLACEHOLDER = 'https://github.com/user/repository'

export function ConnectForm({
  onSubmit,
  isWorking,
}: {
  onSubmit: (url: string) => void
  isWorking: boolean
}) {
  const [value, setValue] = useState('')
  const [touched, setTouched] = useState(false)

  const trimmed = value.trim()
  const invalid = touched && trimmed.length > 0 && !isValidGithubUrl(normaliseGithubUrl(trimmed))

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    setTouched(true)
    const url = normaliseGithubUrl(trimmed)
    if (!isValidGithubUrl(url) || isWorking) return
    onSubmit(url)
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xl">
      <label
        htmlFor="repo-url"
        className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.12em] text-faint"
      >
        GitHub Repository URL
      </label>

      <div
        className={`flex flex-col gap-2 rounded-[14px] border bg-surface p-2 transition-colors duration-200 sm:flex-row sm:items-center ${
          invalid ? 'border-danger/50' : 'border-line focus-within:border-accent/50'
        }`}
      >
        <div className="flex min-w-0 flex-1 items-center gap-2.5 px-1.5">
          <GitHubMark className="size-4 shrink-0 text-faint" />
          <input
            id="repo-url"
            type="text"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            value={value}
            disabled={isWorking}
            placeholder={PLACEHOLDER}
            onChange={(event) => {
              setValue(event.target.value)
              if (invalid) setTouched(false)
            }}
            onBlur={() => setTouched(true)}
            aria-invalid={invalid}
            aria-describedby="repo-url-hint"
            className="min-w-0 flex-1 bg-transparent py-1.5 font-mono text-[13px] text-fg placeholder:text-faint focus:outline-none disabled:opacity-50"
          />
          {value && !isWorking && (
            <button
              type="button"
              onClick={() => setValue('')}
              aria-label="Clear URL"
              className="shrink-0 rounded-md p-1 text-faint transition-colors hover:bg-surface-2 hover:text-muted"
            >
              <X className="size-3.5" />
            </button>
          )}
        </div>

        <button
          type="submit"
          disabled={isWorking}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-[10px] bg-gradient-to-br from-accent to-accent-strong px-4 py-2.5 text-[13px] font-medium text-white transition-all duration-200 hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isWorking ? (
            <>
              <Loader2 className="size-3.5 animate-spin" />
              Analyzing
            </>
          ) : (
            <>
              <Search className="size-3.5" />
              Analyze Repository
            </>
          )}
        </button>
      </div>

      <p
        id="repo-url-hint"
        className={`mt-2 px-1 text-[11.5px] transition-colors ${
          invalid ? 'text-danger' : 'text-faint'
        }`}
      >
        {invalid
          ? 'Enter a full GitHub repository URL, e.g. https://github.com/user/repository'
          : 'The repository is cloned, parsed, chunked and embedded before you can ask questions.'}
      </p>
    </form>
  )
}
