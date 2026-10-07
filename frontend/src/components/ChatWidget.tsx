import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { MessageCircle, X, Send, ThumbsUp, ThumbsDown, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'

interface Source {
  node_id: string
  entity_type: string
  label: string
  relevance_score: number
  grounding_status: string
}

interface Message {
  role: 'user' | 'assistant' | 'error'
  content: string
  sources?: Source[]
  feedbackSent?: 'positive' | 'negative'
}

const BASE = '/api/v1'

async function ragQuery(query: string): Promise<{ answer: string; sources: Source[] }> {
  const token = localStorage.getItem('access_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}/rag/query`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

async function sendFeedback(queryId: string, rating: 'positive' | 'negative') {
  const token = localStorage.getItem('access_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  await fetch(`${BASE}/feedback`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query_id: queryId, rating }),
  })
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="bg-gray-100 dark:bg-gray-800 rounded-md p-3 my-1 overflow-x-auto text-xs leading-relaxed"><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="bg-gray-200 dark:bg-gray-700 px-1 rounded text-xs">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h4 class="font-semibold text-sm mt-2 mb-1">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 class="font-semibold text-base mt-2 mb-1">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 class="font-bold text-base mt-2 mb-1">$1</h2>')
    .replace(/^[*-] (.+)$/gm, '<li class="ml-4">$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li class="ml-4">$1</li>')
    .replace(/\[citation:(\d+)\]/g, '<sup class="text-blue-500 cursor-pointer font-semibold text-xs">[$1]</sup>')
    .replace(/\n\n/g, '</p><p class="mb-1">')
    .replace(/\n/g, '<br>')
}

export default function ChatWidget() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set())
  const messagesEnd = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 200)
  }, [open])

  async function handleSend() {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setLoading(true)

    const userMsg: Message = { role: 'user', content: q }
    setMessages(prev => [...prev, userMsg])

    try {
      const data = await ragQuery(q)
      const assistantMsg: Message = { role: 'assistant', content: data.answer, sources: data.sources || [] }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'error', content: err.message || '请求失败' }])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  async function handleFeedback(idx: number, rating: 'positive' | 'negative') {
    const msg = messages[idx]
    if (!msg || msg.feedbackSent) return
    setMessages(prev => prev.map((m, i) => i === idx ? { ...m, feedbackSent: rating } : m))
    await sendFeedback('', rating)
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-[9999] w-14 h-14 rounded-full bg-blue-500 text-white
          shadow-lg hover:shadow-xl hover:scale-105 active:scale-95
          flex items-center justify-center transition-all duration-200"
        title="AI 助手"
      >
        <MessageCircle size={26} />
      </button>
    )
  }

  return (
    <div className="fixed bottom-6 right-6 z-[9999] w-[420px] h-[560px] max-w-[calc(100vw-24px)]
      bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700
      flex flex-col overflow-hidden transition-all duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-blue-500 text-white shrink-0">
        <span className="font-semibold text-sm">AI 助手</span>
        <button onClick={() => setOpen(false)} className="opacity-80 hover:opacity-100">
          <X size={18} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 text-sm">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 py-12 text-sm">
            👋 你好！我是 AI 助手，可以回答文档相关问题。
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`animate-[fadeIn_0.2s_ease-out] ${msg.role === 'user'
            ? 'flex justify-end'
            : msg.role === 'error'
              ? 'flex justify-center'
              : 'flex justify-start'}`}>
            <div className={`max-w-[85%] px-3 py-2 rounded-xl text-sm leading-relaxed whitespace-pre-wrap
              ${msg.role === 'user'
                ? 'bg-blue-500 text-white rounded-br-sm'
                : msg.role === 'error'
                  ? 'bg-red-50 text-red-600 text-xs'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-100 rounded-bl-sm'}`}
            >
              {msg.role === 'assistant' ? (
                <div dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
              ) : (
                msg.content
              )}

              {/* Sources + Feedback */}
              {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                  {/* Feedback */}
                  <div className="flex gap-2 mb-1">
                    <button
                      onClick={() => handleFeedback(i, 'positive')}
                      className={`p-0.5 rounded transition-colors ${msg.feedbackSent === 'positive'
                        ? 'text-blue-500'
                        : 'text-gray-400 hover:text-blue-500'}`}
                      disabled={!!msg.feedbackSent}
                    >
                      <ThumbsUp size={14} />
                    </button>
                    <button
                      onClick={() => handleFeedback(i, 'negative')}
                      className={`p-0.5 rounded transition-colors ${msg.feedbackSent === 'negative'
                        ? 'text-red-500'
                        : 'text-gray-400 hover:text-red-500'}`}
                      disabled={!!msg.feedbackSent}
                    >
                      <ThumbsDown size={14} />
                    </button>
                  </div>

                  {/* Sources toggle */}
                  <button
                    onClick={() => setExpandedSources(prev => {
                      const next = new Set(prev)
                      next.has(i) ? next.delete(i) : next.add(i)
                      return next
                    })}
                    className="text-xs text-blue-500 hover:text-blue-600 flex items-center gap-1"
                  >
                    {expandedSources.has(i) ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    {expandedSources.has(i) ? '收起' : '查看'} {msg.sources.length} 条引用
                  </button>

                  {expandedSources.has(i) && (
                    <div className="mt-2 p-2 bg-gray-50 dark:bg-gray-800 rounded-md text-xs text-gray-500 space-y-1">
                      {msg.sources.map((s, j) => (
                        <div key={j} className="border-b border-gray-100 dark:border-gray-700 last:border-0 pb-1 last:pb-0">
                          <span className="font-medium text-gray-700 dark:text-gray-300">[{j + 1}] {s.label}</span>
                          <span className="ml-1 opacity-70">• {s.entity_type} ({Math.round(s.relevance_score * 100)}%)</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start animate-pulse">
            <div className="bg-gray-100 dark:bg-gray-700 rounded-xl rounded-bl-sm px-4 py-3">
              <Loader2 size={18} className="animate-spin text-gray-400" />
            </div>
          </div>
        )}

        <div ref={messagesEnd} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-gray-200 dark:border-gray-700 flex gap-2 shrink-0">
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的问题..."
          rows={1}
          className="flex-1 resize-none rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2
            text-sm bg-gray-50 dark:bg-gray-900 dark:text-gray-100
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
            min-h-[38px] max-h-[100px]"
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="px-4 rounded-lg bg-blue-500 text-white font-semibold text-sm
            hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed
            shrink-0 transition-colors flex items-center gap-1"
        >
          <Send size={15} />
          发送
        </button>
      </div>
    </div>
  )
}
