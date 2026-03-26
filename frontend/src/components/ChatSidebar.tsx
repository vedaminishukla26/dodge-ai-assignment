import { useState, useRef, useEffect, useCallback } from 'react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  cypher_query?: string
  node_ids?: string[]
}

interface ChatSession {
  id: string
  title: string
  created_at: string
  updated_at: string
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
  const [showTrace, setShowTrace] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [traceLogs, setTraceLogs] = useState<string[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const fetchSessions = useCallback(async () => {
    try {
      const response = await fetch('/api/chat/sessions')
      if (response.ok) {
        const data = await response.json()
        setSessions(data)
      }
    } catch (e) {
      console.error('Failed to fetch sessions:', e)
    }
  }, [])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

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

    // Clear old trace logs for new message
    setTraceLogs(prev => [...prev, `--- New Query: ${query} ---`])

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

        const chunk = decoder.decode(value, { stream: true })
        buffer += chunk

        // Log raw SSE data to trace
        setTraceLogs(prev => [...prev, chunk])

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

  const handleNewChat = () => {
    setMessages([])
    setSessionId(null)
    setTraceLogs([])
    setInput('')
    setShowHistory(false)
    fetchSessions()
  }

  const loadSession = async (session: ChatSession) => {
    setIsLoading(true)
    setSessionId(session.id)
    setShowHistory(false)
    setMessages([])

    try {
      const response = await fetch(`/api/chat/history/${session.id}`)
      if (response.ok) {
        const data = await response.json()
        setMessages(data)
      } else {
        throw new Error('Failed to load history')
      }
    } catch (e) {
      console.error(e)
      setMessages([{
        id: 'err',
        role: 'assistant',
        content: `⚠️ Failed to load session: ${e instanceof Error ? e.message : 'Unknown error'}`
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    // Optional: add a toast or temporary state for "Copied!"
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
        <div className="header-top">
          <div className="brand">
            <span className="logo-icon">⚡</span>
            <span className="logo">Dodge AI</span>
          </div>
          <button className="new-chat-btn" onClick={handleNewChat} title="New Session">
            <span>+</span> New
          </button>
        </div>
        <div className="header-actions">
          <button
            className={`history-toggle ${showHistory ? 'active' : ''}`}
            onClick={() => setShowHistory(!showHistory)}
            title="Recent Conversations"
          >
            History
          </button>
          <button
            className={`trace-toggle ${showTrace ? 'active' : ''}`}
            onClick={() => setShowTrace(!showTrace)}
            title="View Raw Trace Logs"
          >
            Trace
          </button>
        </div>
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
          {messages.map((msg: Message) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="message-content">{msg.content}</div>
              {msg.cypher_query && (
                <div className="cypher-wrapper">
                  <div className="cypher-header">
                    <span className="cypher-label">Cypher Query</span>
                    <button
                      className="copy-btn"
                      onClick={() => copyToClipboard(msg.cypher_query!)}
                      title="Copy to clipboard"
                    >
                      📋 Copy
                    </button>
                  </div>
                  <div className="cypher-block">{msg.cypher_query}</div>
                </div>
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

      {/* Trace Logs Panel */}
      {showTrace && (
        <div className="trace-panel">
          <div className="trace-header">
            <span>Debug Trace</span>
            <button onClick={() => setTraceLogs([])}>Clear</button>
          </div>
          <div className="trace-content">
            {traceLogs.map((log, i) => (
              <div key={i} className="trace-log-line">{log}</div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>
      )}

      {/* History Panel */}
      {showHistory && (
        <div className="history-panel">
          <div className="history-header">
            <span>Recent Chats</span>
            <button onClick={() => setShowHistory(false)}>Close</button>
          </div>
          <div className="history-list">
            {sessions.length === 0 ? (
              <div className="no-history">No sessions found</div>
            ) : (
              sessions.map((s: ChatSession) => (
                <div
                  key={s.id}
                  className={`history-item ${sessionId === s.id ? 'active' : ''}`}
                  onClick={() => loadSession(s)}
                >
                  <div className="history-title">{s.title || 'Untitled Chat'}</div>
                  <div className="history-date">
                    {new Date(s.updated_at).toLocaleDateString()}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
