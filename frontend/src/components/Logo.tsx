import { Braces } from 'lucide-react'

/** App mark: a code glyph on an accent tile. */
export function Logo({ className = 'size-9' }: { className?: string }) {
  return (
    <span
      className={`${className} glow-accent relative inline-flex shrink-0 items-center justify-center rounded-[11px] bg-gradient-to-br from-accent via-accent-strong to-cyan text-white`}
    >
      <Braces className="size-[58%]" strokeWidth={2.4} />
    </span>
  )
}
