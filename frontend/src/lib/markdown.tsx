import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { CodeBlock } from '@/components/CodeBlock'

/**
 * Renders an AI answer as GitHub-flavoured Markdown, delegating all fenced
 * code to the shared CodeBlock so answer snippets and source snippets look
 * identical.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          pre: ({ children }) => <>{children}</>,
          code: ({ className, children, ...rest }) => {
            const language = /language-([\w+#-]+)/.exec(className ?? '')?.[1]
            const text = String(children).replace(/\n$/, '')

            if (!language) {
              return (
                <code className="font-mono" {...rest}>
                  {children}
                </code>
              )
            }

            return <CodeBlock code={text} language={language} showLineNumbers={false} />
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
