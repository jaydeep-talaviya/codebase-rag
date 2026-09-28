import { CheckCircle2, CircleDashed, Loader2, XCircle } from 'lucide-react'
import type { RepositoryStatus } from '@/types/api'

const STYLES: Record<RepositoryStatus, { label: string; className: string; Icon: typeof CheckCircle2 }> = {
  pending: {
    label: 'Pending',
    className: 'border-line bg-surface-2 text-muted',
    Icon: CircleDashed,
  },
  processing: {
    label: 'Processing',
    className: 'border-cyan/30 bg-cyan/10 text-cyan',
    Icon: Loader2,
  },
  completed: {
    label: 'Completed',
    className: 'border-success/30 bg-success/10 text-success',
    Icon: CheckCircle2,
  },
  failed: {
    label: 'Failed',
    className: 'border-danger/30 bg-danger/10 text-danger',
    Icon: XCircle,
  },
}

export function StatusBadge({
  status,
  className = '',
}: {
  status: RepositoryStatus
  className?: string
}) {
  const { label, className: tone, Icon } = STYLES[status] ?? STYLES.pending
  const spinning = status === 'processing'

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium tracking-wide ${tone} ${className}`}
    >
      <Icon className={`size-3.5 ${spinning ? 'animate-spin' : ''}`} />
      {label}
    </span>
  )
}
