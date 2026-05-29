import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../lib/api'
import type { QueryResponse } from '../lib/api'
import { TYPE_COLORS } from '../lib/constants'

interface Message { id: string; role: 'user' | 'agent'; content: string; sources?: QueryResponse['sources'] }

export function QueryPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedSource, setSelectedSource] = useState<any>(null)
  const [kgStats, setKgStats] = useState<{ nodes: number; edges: number; docs: number } | null>(null)
  const chatRef = useRef<HTMLDivElement>(null)

  // Load KG stats on mount
  useEffect(() => {
    api.getGraphAll().then(data => {
      setKgStats({
        nodes: data.stats.total_nodes,
        edges: data.stats.total_edges,
        docs: data.documents.length
      })
      // Set welcome message with actual stats
      setMessages([{
        id: 'welcome',
        role: 'agent',
        content: `👋 **你好！** 我已加载 **${data.documents.length}个文档** 的知识图谱。\n\n📊 **图谱概况：** ${data.stats.total_nodes} 实体 · ${data.stats.total_edges} 关系 · ${Object.keys(data.stats.entity_types).length} 种类型\n\n你可以直接向我提问。`
      }])
    }).catch(() => {
      setMessages([{
        id: 'welcome',
        role: 'agent',
        content: `👋 **你好！** 知识图谱加载中...\n\n你可以直接向我提问。`
      }])
    })
  }, [])

  useEffect(() => { chatRef.current?.scrollTo(0, chatRef.current.scrollHeight) }, [messages])

  const send = async () => {
    if (!input.trim() || loading) return
    const q = input.trim()
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: q }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    try {
      const resp = await api.ask(q)
      const agentMsg: Message = { id: (Date.now() + 1).toString(), role: 'agent', content: resp.answer, sources: resp.sources || undefined }
      setMessages(prev => [...prev, agentMsg])
    } catch (e: any) {
      const errMsg: Message = { id: (Date.now() + 1).toString(), role: 'agent', content: `❌ 查询失败: ${e.message}` }
      setMessages(prev => [...prev, errMsg])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-52px)] max-md:flex-col">
      {/* Chat panel */}
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
              <div className={`p-3 px-4 rounded-2xl text-[13px] leading-relaxed
                ${m.role === 'user' ? 'bg-accent text-white rounded-br' : 'bg-elevated rounded-bl'}`}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
              </div>
              {m.sources && m.sources.length > 0 && (
                <div className="flex gap-1.5 mt-2 flex-wrap">
                  {m.sources.map((s: any) => (
                    <button key={s.node_id} onClick={() => setSelectedSource(s)}
                      className="py-1 px-2.5 rounded-full text-[11px] font-semibold border transition-all hover:opacity-80"
                      style={{ color: TYPE_COLORS[s.entity_type] || '#94a3b8', borderColor: (TYPE_COLORS[s.entity_type] || '#94a3b8') + '44', backgroundColor: (TYPE_COLORS[s.entity_type] || '#94a3b8') + '11' }}
                    >{s.node_id}</button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="p-4 border-t border-border flex gap-2.5">
          <textarea value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder="输入你的问题，Enter 发送..." rows={1} disabled={loading}
            className="flex-1 bg-elevated border border-border rounded-full py-2.5 px-4 text-text-primary text-[13px] resize-none font-sans focus:outline-none focus:border-accent min-h-[42px] max-h-[100px] disabled:opacity-50"
          />
          <button onClick={send} disabled={loading}
            className="w-[42px] h-[42px] rounded-full bg-accent text-white flex items-center justify-center text-lg flex-shrink-0 hover:bg-accent-light transition-all disabled:opacity-50"
          >→</button>
        </div>
      </div>
      {/* Detail panel */}
      <div className="flex-1 overflow-y-auto p-6">
        {selectedSource ? (
          <div>
            <h3 className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-4">答案溯源</h3>
            <div className="bg-surface border border-border rounded-card p-5">
              <div className="flex items-center gap-2 mb-3">
                <span className="py-1 px-2.5 rounded-md text-[11px] font-semibold"
                  style={{ color: TYPE_COLORS[selectedSource.entity_type] || '#94a3b8', backgroundColor: (TYPE_COLORS[selectedSource.entity_type] || '#94a3b8') + '18' }}>
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
              <a href="/graph" className="block text-center mt-4 py-2 border border-border rounded-full text-xs text-text-secondary hover:border-accent hover:text-accent">🔮 在知识图谱中查看</a>
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
