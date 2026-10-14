import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import type { LineageTrace, LineageNode } from '../lib/types'

interface LineageGraphProps {
  entityId: string
  onClose: () => void
}

const NODE_COLORS: Record<string, string> = {
  document: '#4ade80',
  section: '#a3e635',
  extraction: '#facc15',
  entity: '#60a5fa',
  chunk: '#c084fc',
  retrieval: '#fbbf24',
  generation: '#fb923c',
  answer: '#f87171',
  feedback: '#ef4444',
  domain_expand: '#22d3ee',
  conv_turn: '#a78bfa',
  kg_version: '#94a3b8',
}

const NODE_LABELS: Record<string, string> = {
  document: '文档',
  section: '章节',
  extraction: '抽取',
  entity: '实体',
  chunk: '区块',
  retrieval: '检索',
  generation: '生成',
  answer: '答案',
  feedback: '反馈',
  domain_expand: '词典展开',
  conv_turn: '会话轮次',
  kg_version: 'KG版本',
}

export function LineageGraph({ entityId, onClose }: LineageGraphProps) {
  const [trace, setTrace] = useState<LineageTrace | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.lineageEntity(entityId)
      .then(data => { setTrace(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [entityId])

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <span className="text-text-muted">⏳ 加载血缘链路...</span>
    </div>
  )
  if (error) return (
    <div className="flex items-center justify-center h-full">
      <span className="text-red">⚠ {error}</span>
    </div>
  )
  if (!trace || trace.trace.length === 0) return (
    <div className="flex items-center justify-center h-full">
      <span className="text-text-muted">暂无血缘数据</span>
    </div>
  )

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border flex-shrink-0">
        <div>
          <h3 className="text-sm font-bold">血缘追踪</h3>
          <p className="text-[10px] text-text-muted">{trace.entity_id} · {trace.trace.length} 节点</p>
        </div>
        <button onClick={onClose} className="text-text-muted hover:text-text-primary text-lg">✕</button>
      </div>

      {/* Timeline View */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-[11px] top-0 bottom-0 w-0.5 bg-border" />

          <div className="space-y-4">
            {trace.trace.map((node, idx) => (
              <LineageNodeCard key={node.node_id || idx} node={node} isLast={idx === trace.trace.length - 1} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function LineageNodeCard({ node, isLast }: { node: LineageNode; isLast: boolean }) {
  const color = NODE_COLORS[node.node_type] || '#94a3b8'
  const typeLabel = NODE_LABELS[node.node_type] || node.node_type

  return (
    <div className="relative pl-8">
      {/* Dot on the timeline */}
      <div
        className={`absolute left-[3px] top-2 w-[17px] h-[17px] rounded-full border-2 border-surface z-10 ${isLast ? 'ring-2 ring-accent/30' : ''}`}
        style={{ backgroundColor: color }}
      />

      <div className="bg-elevated border border-border rounded-lg p-3">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
            style={{ backgroundColor: `${color}20`, color }}>
            {typeLabel}
          </span>
          {node.timestamp && (
            <span className="text-[10px] text-text-muted">
              {new Date(node.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
        <p className="text-xs text-text-primary leading-relaxed">{node.label}</p>

        {/* Domain terms */}
        {node.domain_terms && node.domain_terms.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {node.domain_terms.map(t => (
              <span key={t} className="text-[10px] bg-accent/10 text-accent px-1.5 py-0.5 rounded-full">{t}</span>
            ))}
          </div>
        )}

        {/* Key metadata */}
        {node.metadata && Object.keys(node.metadata).length > 0 && (
          <div className="mt-2 pt-2 border-t border-border/50">
            {Object.entries(node.metadata).slice(0, 3).map(([k, v]) => (
              <div key={k} className="flex justify-between text-[10px]">
                <span className="text-text-muted">{k}</span>
                <span className="text-text-primary max-w-[60%] truncate">{String(v)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
