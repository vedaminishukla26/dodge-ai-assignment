import { useState, useRef, useEffect, useCallback } from 'react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  cypher_query?: string
  node_ids?: string[]
}

interface ChatSidebarProps {
  onHighlightNodes: (nodeIds: string[]) => void
}

const SAMPLE_QUERIES = [
  { icon: '📦', text: 'How many sales orders are there in the system?' },
  { icon: '👥', text: 'Which customers have the highest total billing amount?' },
  { icon: '🏭', text: 'Show me all products and which plants they are produced at' },
  { icon: '🔄', text: 'Trace the full O2C flow for sales order 1' },
  { icon: '📊', text: 'What is the total net amount across all billing documents?' },
  { icon: '🚚', text: 'List all deliveries and their goods movement status' },
]

export default function ChatSidebar({ onHighlightNodes }: ChatSidebarProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const sendMessage = async (query: string) => {
    if (!query.trim() || isLoading) return

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query.trim(),
    }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    // Create a placeholder assistant message for streaming
    const assistantId = `assistant-${Date.now()}`
    const assistantMessage: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
    }
    setMessages(prev => [...prev, assistantMessage])

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim(),
          session_id: sessionId,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) throw new Error('No response body')

      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE events from buffer
        const lines = buffer.split('\n')
        buffer = ''

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i]

          if (line.startsWith('event: ')) {
            const eventType = line.slice(7).trim()
            const dataLine = lines[i + 1]

            if (dataLine && dataLine.startsWith('data: ')) {
              try {
                const data = JSON.parse(dataLine.slice(6))

                switch (eventType) {
                  case 'session':
                    setSessionId(data.session_id)
                    break

                  case 'token':
                    setMessages(prev =>
                      prev.map(m =>
                        m.id === assistantId
                          ? { ...m, content: m.content + data.token }
                          : m
                      )
                    )
                    break

                  case 'cypher':
                    setMessages(prev =>
                      prev.map(m =>
                        m.id === assistantId
                          ? { ...m, cypher_query: data.cypher_query }
                          : m
                      )
                    )
                    break

                  case 'node_ids':
                    setMessages(prev =>
                      prev.map(m =>
                        m.id === assistantId
                          ? { ...m, node_ids: data.node_ids }
                          : m
                      )
                    )
                    onHighlightNodes(data.node_ids || [])
                    break

                  case 'guardrail':
                    setMessages(prev =>
                      prev.map(m =>
                        m.id === assistantId
                          ? { ...m, content: data.message }
                          : m
                      )
                    )
                    break

                  case 'error':
                    setMessages(prev =>
                      prev.map(m =>
                        m.id === assistantId
                          ? { ...m, content: `⚠️ ${data.message}` }
                          : m
                      )
                    )
                    break
                }
              } catch {
                // incomplete JSON, keep in buffer
                buffer = lines.slice(i).join('\n')
                break
              }
              i++ // skip the data line
            }
          } else if (line !== '') {
            // Incomplete line, put back in buffer
            buffer = lines.slice(i).join('\n')
            break
          }
        }
      }
    } catch (e) {
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? { ...m, content: `⚠️ Connection error: ${e instanceof Error ? e.message : 'Unknown error'}` }
            : m
        )
      )
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <div className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <span className="logo-icon">⚡</span>
        <span className="logo">Dodge AI</span>
        <span className="subtitle">O2C Analytics</span>
      </div>

      {/* Messages */}
      {messages.length === 0 ? (
        <div className="welcome-container">
          <div className="welcome-logo">🔮</div>
          <div className="welcome-title">Ask anything about O2C</div>
          <div className="welcome-subtitle">
            Query your SAP Order-to-Cash data using natural language.
            I'll translate to Cypher and visualize the results.
          </div>
          <div className="sample-queries">
            {SAMPLE_QUERIES.map((q, i) => (
              <div
                key={i}
                className="sample-query-card"
                onClick={() => sendMessage(q.text)}
              >
                <span className="card-icon">{q.icon}</span>
                {q.text}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="messages-container">
          {messages.map(msg => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div>{msg.content}</div>
              {msg.cypher_query && (
                <>
                  <div className="cypher-label">Cypher Query</div>
                  <div className="cypher-block">{msg.cypher_query}</div>
                </>
              )}
            </div>
          ))}
          {isLoading && messages[messages.length - 1]?.content === '' && (
            <div className="typing-indicator">
              <div className="typing-dot" />
              <div className="typing-dot" />
              <div className="typing-dot" />
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Input */}
      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <input
            ref={inputRef}
            className="chat-input"
            type="text"
            placeholder="Ask about sales orders, deliveries, billing..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <button
            className="send-button"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isLoading}
          >
            ➤
          </button>
        </div>
      </div>
    </div>
  )
}
