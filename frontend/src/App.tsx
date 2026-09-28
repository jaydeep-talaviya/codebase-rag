import { useCallback, useEffect, useState } from 'react'
import { AppHeader } from '@/components/AppHeader'
import { Landing } from '@/components/Landing'
import { RepoTopBar } from '@/components/RepoTopBar'
import { ChatPanel } from '@/components/ChatPanel'
import { useTheme } from '@/hooks/useTheme'
import { useRepository } from '@/hooks/useRepository'
import { useChat } from '@/hooks/useChat'
import { api } from '@/lib/api'

export default function App() {
  const { theme, toggle } = useTheme()
  const repository = useRepository()
  const [draft, setDraft] = useState('')
  const [lastUrl, setLastUrl] = useState<string | null>(null)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)

  const chat = useChat(repository.state === 'ready' ? repository.repository?.id ?? null : null)

  // Re-open the last repository, and probe the backend for the status dot.
  useEffect(() => {
    void repository.restore()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void api.health(controller.signal).then(setBackendOnline)
    return () => controller.abort()
  }, [])

  const handleConnect = useCallback(
    (url: string) => {
      setLastUrl(url)
      void repository.connect(url)
    },
    [repository],
  )

  const handleSend = useCallback(
    (question?: string) => {
      // Guarded rather than trusted: a suggestion chip passes a string, the
      // composer passes nothing, and anything else falls back to the draft.
      const text = (typeof question === 'string' ? question : draft).trim()
      if (!text) return
      setDraft('')
      void chat.ask(text)
    },
    [chat, draft],
  )

  const ready = repository.state === 'ready' && repository.repository

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-canvas">
      <AppHeader
        theme={theme}
        onToggleTheme={toggle}
        backendOnline={backendOnline}
      />

      <main className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {ready ? (
          <>
            <RepoTopBar
              repository={repository.repository!}
              onReconnect={repository.reset}
            />
            <ChatPanel
              messages={chat.messages}
              isAsking={chat.isAsking}
              stageIndex={chat.stageIndex}
              draft={draft}
              onDraftChange={setDraft}
              onSend={handleSend}
              onStop={chat.stop}
              onRetry={chat.retry}
              repositoryName={repository.repository!.name}
              repositoryId={repository.repository!.id}
            />
          </>
        ) : (
          <Landing
            state={repository.state}
            stage={repository.stage}
            error={repository.error}
            onConnect={handleConnect}
            activeRepositoryId={repository.repository?.id}
            onOpenRepository={(id) => void repository.openRepository(id)}
            onRetry={() => {
              if (lastUrl) handleConnect(lastUrl)
              else repository.reset()
            }}
          />
        )}
      </main>
    </div>
  )
}
