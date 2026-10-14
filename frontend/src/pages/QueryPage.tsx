import { useState, useRef, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { QueryMetadata, QueryResponse } from '../lib/api'
import type { SourceItem } from '../lib/types'
type QuerySource = NonNullable<QueryResponse['sources']>[number]
import { TYPE_COLORS, SOURCE_TYPE_LABELS, SOURCE_TYPE_COLORS } from '../lib/constants'

interface Message {
  id: string
  role: 'user' | 'agent'
  content: string
  sources?: QueryResponse['sources']
  metadata?: QueryMetadata
}

function createSessionId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }

  return `query-session-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function formatDuration(durationMs?: number): string | null {
  if (typeof durationMs !== 'number' || Number.isNaN(durationMs)) {
    return null
  }
  if (durationMs < 1000) {
    return `${durationMs}ms`
  }
  return `${(durationMs / 1000).toFixed(durationMs >= 10000 ? 0 : 1)}s`
}

function getResolvedSource(source: QuerySource): string | undefined {
  if (source?.source) {
    return source.source
  }

  const propertiesSource = source?.properties?.source
  return typeof propertiesSource === 'string' ? propertiesSource : undefined
}

function buildDiagnosticBadges(metadata?: QueryMetadata): string[] {
  if (!metadata) return []

  const badges: string[] = []
  const duration = formatDuration(metadata.duration_ms)
  if (duration) badges.push(`响应 ${duration}`)
  if (metadata.query_mode) badges.push(`${metadata.query_mode} 模式`)
  if (metadata.degraded_mode) badges.push(`降级: ${metadata.degraded_mode}`)
  if (metadata.rewrite_reason) badges.push(`改写: ${metadata.rewrite_reason}`)

  const contextCount = metadata.final_context_chunk_ids?.length
  if (typeof contextCount === 'number' && contextCount > 0) {
    badges.push(`证据 ${contextCount} 条`)
  }

  return badges
}

export function QueryPage() {
  const { docId } = useParams<{ docId?: string }>()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedSource, setSelectedSource] = useState<SourceItem | null>(null)
  const [kgStats, setKgStats] = useState<{ nodes: number; edges: number; docs: number } | null>(null)
  const chatRef = useRef<HTMLDivElement>(null)
  const sessionIdRef = useRef<string>(createSessionId())

  useEffect(() => {
    api.getGraphAll().then(data => {
      setKgStats({
        nodes: data.stats.total_nodes,
        edges: data.stats.total_edges,
        docs: data.documents.length,
      })
      setMessages([{
        id: 'welcome',
        role: 'agent',
        content: `👋 **你好！** 我已加载 **${data.documents.length}个文档** 的知识图谱。\n\n📊 **图谱概况：** ${data.stats.total_nodes} 实体 · ${data.stats.total_edges} 关系 · ${Object.keys(data.stats.entity_types).length} 种类型\n\n你可以直接向我提问。`,
      }])
    }).catch(() => {
      setMessages([{
        id: 'welcome',
        role: 'agent',
        content: '👋 **你好！** 知识图谱加载中...\n\n你可以直接向我提问。',
      }])
    })
  }, [])

  useEffect(() => {
    chatRef.current?.scrollTo(0, chatRef.current.scrollHeight)
  }, [messages])

  const send = async () => {
    if (!input.trim() || loading) return
    const q = input.trim()
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: q }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    try {
      const resp = await api.ask(q, docId, {
        sessionId: sessionIdRef.current,
        queryOptions: { language: 'ch' },
      })
      const agentMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: resp.answer,
        sources: resp.sources || undefined,
        metadata: resp.metadata,
      }
      setMessages(prev => [...prev, agentMsg])
    } catch (e: unknown) {
      const errMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: `❌ 查询失败: ${e instanceof Error ? e.message : '未知错误'}`,
      }
      setMessages(prev => [...prev, errMsg])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-52px)] max-md:flex-col">
      <div className="w-[45%] min-w-[400px] max-md:w-full max-md:min-w-0 max-md:h-[50%] flex flex-col border-r border-border">
        <div className="px-5 py-3.5 border-b border-border flex items-center gap-2">
          <span className="py-1 px-2.5 bg-accent/10 text-accent rounded-full text-[11px] font-semibold">
            📚 {kgStats ? `${kgStats.docs}个文档` : '加载中...'}
          </span>
          <span className="text-[11px] text-text-muted">
            {kgStats ? `${kgStats.nodes} 节点 · ${kgStats.edges} 边` : ''}
          </span>
          {loading && <span className="ml-auto text-[11px] text-text-muted">⏳ 查询中...</span>}
        </div>
        <div ref={chatRef} className="flex-1 overflow-y-auto p-5 flex flex-col gap-4">
          {messages.map(m => (
            <div key={m.id} className={`max-w-[88%] ${m.role === 'user' ? 'self-end' : 'self-start'}`}>
              <div className={`p-3 px-4 rounded-2xl text-[13px] leading-relaxed ${m.role === 'user' ? 'bg-accent text-white rounded-br' : 'bg-elevated rounded-bl'}`}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                {m.role === 'agent' && m.metadata && (
                  <div className="mt-3 pt-3 border-t border-border/60 text-[11px] text-text-muted space-y-2">
                    <div className="flex flex-wrap gap-1.5">
                      {buildDiagnosticBadges(m.metadata).map((badge) => (
                        <span key={badge} className="px-2 py-1 rounded-full bg-slate-900/40 border border-border/60 text-text-secondary">
                          {badge}
                        </span>
                      ))}
                    </div>
                    {m.metadata.rewritten_query && (
                      <div>改写后问题：<span className="text-text-primary">{m.metadata.rewritten_query}</span></div>
                    )}
                    {(!m.sources || m.sources.length === 0) && (
                      <div>本次回答未返回可展示来源，建议结合图谱或后端诊断指标复核。</div>
                    )}
                    {m.metadata.degraded_mode && (
                      <div>本次回答触发了降级路径，可能优先保证时延与稳定性。</div>
                    )}
                    {typeof m.metadata.final_context_chunk_ids?.length === 'number' && m.metadata.final_context_chunk_ids.length <= 1 && (
                      <div>本次最终上下文证据较少，适合继续追问或切换到图谱查看详情。</div>
                    )}
                  </div>
                )}
              </div>
              {m.sources && m.sources.length > 0 && (
                <div className="flex gap-1.5 mt-2 flex-wrap items-center">
                  {m.sources.map((s, index) => {
                    const resolvedSource = getResolvedSource(s)
                    return (
                      <button
                        key={`${s.node_id || 'source'}-${index}`}
                        onClick={() => setSelectedSource(s as SourceItem)}
                        className="py-1 px-2.5 rounded-full text-[11px] font-semibold border transition-all hover:opacity-80 flex items-center gap-1"
                        style={{ color: TYPE_COLORS[s.entity_type] || '#94a3b8', borderColor: (TYPE_COLORS[s.entity_type] || '#94a3b8') + '44', backgroundColor: (TYPE_COLORS[s.entity_type] || '#94a3b8') + '11' }}
                      >
                        {resolvedSource && (
                          <span
                            className="py-0.5 px-1.5 rounded text-[10px] font-bold leading-none"
                            style={{ color: SOURCE_TYPE_COLORS[resolvedSource] || '#94a3b8', backgroundColor: (SOURCE_TYPE_COLORS[resolvedSource] || '#94a3b8') + '18' }}
                          >
                            {SOURCE_TYPE_LABELS[resolvedSource] || resolvedSource}
                          </span>
                        )}
                        {s.node_id || `source-${index + 1}`}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="p-4 border-t border-border flex gap-2.5">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder="输入你的问题，Enter 发送..."
            rows={1}
            disabled={loading}
            className="flex-1 bg-elevated border border-border rounded-full py-2.5 px-4 text-text-primary text-[13px] resize-none font-sans focus:outline-none focus:border-accent min-h-[42px] max-h-[100px] disabled:opacity-50"
          />
          <button
            onClick={send}
            disabled={loading}
            className="w-[42px] h-[42px] rounded-full bg-accent text-white flex items-center justify-center text-lg flex-shrink-0 hover:bg-accent-light transition-all disabled:opacity-50"
          >→</button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        {selectedSource ? (
          <div>
            <h3 className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-4">答案溯源</h3>
            <div className="bg-surface border border-border rounded-card p-5">
              <div className="flex items-center gap-2 mb-3">
                <span className="py-1 px-2.5 rounded-md text-[11px] font-semibold" style={{ color: TYPE_COLORS[selectedSource.entity_type] || '#94a3b8', backgroundColor: (TYPE_COLORS[selectedSource.entity_type] || '#94a3b8') + '18' }}>
                  {selectedSource.entity_type}
                </span>
                <span className="text-[11px] text-text-muted">{selectedSource.node_id}</span>
                <span className={`ml-auto py-1 px-2 rounded-full text-[10px] font-semibold ${selectedSource.grounding_status === 'grounded' ? 'bg-green/10 text-green' : 'bg-red/10 text-red'}`}>
                  {selectedSource.grounding_status}
                </span>
              </div>
              <div className="text-base font-bold mb-4">{selectedSource.label}</div>
              {selectedSource.properties && Object.entries(selectedSource.properties).map(([k, v]) => (
                <div key={k} className="flex justify-between py-2 text-xs border-b border-border/50">
                  <span className="text-text-muted">{k}</span><span className="text-text-primary font-medium">{String(v)}</span>
                </div>
              ))}
              <div className="flex justify-between py-2 text-xs">
                <span className="text-text-muted">PDF 页码</span><span className="text-accent">📍 Page {selectedSource.page_idx}</span>
              </div>
              {selectedSource.bbox_norm && (
                <div className="flex justify-between py-2 text-xs">
                  <span className="text-text-muted">包围框</span><span className="text-green">[{selectedSource.bbox_norm.join(', ')}]</span>
                </div>
              )}
              <Link to="/graph" className="block text-center mt-4 py-2 border border-border rounded-full text-xs text-text-secondary hover:border-accent hover:text-accent">🔮 在知识图谱中查看</Link>
            </div>
          </div>
        ) : (
          <div className="text-center pt-20">
            <div className="text-5xl mb-3">💬</div>
            <h3 className="text-base font-semibold mb-1">答案溯源面板</h3>
            <p className="text-text-muted text-sm">点击左侧答案中的引用节点查看详情</p>
          </div>
        )}
      </div>
    </div>
  )
}

