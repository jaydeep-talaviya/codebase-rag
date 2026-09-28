import { Bot, User } from 'lucide-react'
import { Markdown } from '@/lib/markdown'
import { SourcesList } from './SourcesList'
import { ThinkingIndicator } from './ThinkingIndicator'
import { ErrorPanel } from './ErrorPanel'
import type { Message } from '@/hooks/useChat'

export function MessageRow({
  message,
  isAsking,
  stageIndex,
  onRetry,
  repositoryId,
}: {
  message: Message
  isAsking: boolean
  stageIndex: number
  onRetry: () => void
  repositoryId?: number
}) {
  if (message.role === 'user') return <UserBubble message={message} />
  return (
    <AssistantBubble
      message={message}
      isAsking={isAsking}
      stageIndex={stageIndex}
      onRetry={onRetry}
      repositoryId={repositoryId}
    />
  )
}

function UserBubble({ message }: { message: Message }) {
  return (
    <div className="animate-fade-up flex justify-end gap-2.5">
      <div className="max-w-[85%] rounded-[14px] rounded-br-[4px] border border-accent/25 bg-accent/10 px-3.5 py-2.5">
        <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-fg">
          {message.text}
        </p>
      </div>
      <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-lg border border-line bg-surface-2 text-faint">
        <User className="size-3.5" />
      </span>
    </div>
  )
}

function AssistantBubble({
  message,
  isAsking,
  stageIndex,
  onRetry,
  repositoryId,
}: {
  message: Message
  isAsking: boolean
  stageIndex: number
  onRetry: () => void
  repositoryId?: number
}) {
  const pending = isAsking && message.text === '' && !message.error

  return (
    <div className="animate-fade-up flex gap-2.5">
      <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-cyan text-white">
        <Bot className="size-3.5" />
      </span>

      <div className="min-w-0 flex-1 space-y-3 pt-1">
        {pending && <ThinkingIndicator stageIndex={stageIndex} />}

        {message.error ? (
          <ErrorPanel
            message={message.error}
            onRetry={onRetry}
            compact
          />
        ) : message.noResults ? (
          <ErrorPanel
            variant="empty"
            onRetry={onRetry}
            retryLabel="Ask a different question"
            compact
          />
        ) : (
          message.text && (
            <>
              <Markdown>{message.text}</Markdown>
              <SourcesList sources={message.sources ?? []} repositoryId={repositoryId} />
            </>
          )
        )}
      </div>
    </div>
  )
}
