import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { TYPE_COLORS, TYPE_ICONS } from '../lib/constants'
import { StructuredView } from '../components/StructuredView'

declare const vis: any

interface GraphData { nodes: any[]; edges: any[]; stats: { total_nodes: number; total_edges: number; grounded_nodes: number; entity_types: Record<string, number> } }

type ViewMode = 'network' | 'structured'

export function GraphPage() {
  const { docId } = useParams<{ docId?: string }>()
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<any>(null)
  const [data, setData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>('network')
  const [highlightNodeId, setHighlightNodeId] = useState<string | null>(null)

  // Fetch data — auto-poll every 10s
  useEffect(() => {
    const fetchGraph = () => {
      const p = docId ? api.getGraph(docId) : api.getGraphAll()
      p.then(d => { setData(d); setLoading(false); setError('') })
       .catch(e => { if (!data) setError(e.message); setLoading(false) })
    }
    fetchGraph()
    const t = setInterval(fetchGraph, 10000)
    return () => clearInterval(t)
  }, [docId])

  // CDN timeout detection for vis.js
  useEffect(() => {
    if (!data) return
    if (typeof vis !== 'undefined') return
    const timer = setTimeout(() => {
      setError('vis.js CDN 加载超时，请检查网络连接后刷新页面')
      setLoading(false)
    }, 10000)
    return () => clearTimeout(timer)
  }, [data])

  // Init vis.js — uses CDN global `vis` like visualizer.html
  useEffect(() => {
    if (!data || !containerRef.current || typeof vis === 'undefined') return

    // Destroy previous if exists
    if (networkRef.current) {
      networkRef.current.destroy()
      networkRef.current = null
    }

    const c = containerRef.current
    const nodesDS = new vis.DataSet(data.nodes.map((n: any) => ({
      id: n.id,
      label: (n.label?.length > 25 ? n.label.slice(0, 23) + '…' : n.label) || '',
      color: {
        background: n.color || '#64748b',
        border: n.borderColor || '#ffffff',
        highlight: { background: n.color || '#64748b', border: '#ffffff' },
      },
      shape: 'dot',
      size: n.size || 10,
      borderWidth: n.borderWidth || 2,
      title: `<b>[${n.entity_type}]</b> ${n.label}${n.page_idx != null ? '<br/>📍 Page ' + n.page_idx : ''}`,
    })))

    const edgesDS = new vis.DataSet(data.edges.map((e: any) => ({
      id: e.id, from: e.from, to: e.to,
      color: { color: e.color || 'rgba(148,163,184,0.15)', highlight: '#38bdf8' },
      width: e.width || 0.5,
    })))

    networkRef.current = new vis.Network(c, { nodes: nodesDS, edges: edgesDS }, {
      physics: {
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -40,
          centralGravity: 0.008,
          springLength: 100,
          springConstant: 0.04,
          avoidOverlap: 0.5
        },
        stabilization: {
          enabled: true,
          iterations: 150,
          updateInterval: 25
        },
        maxVelocity: 50,
        minVelocity: 0.75,
        timestep: 0.5
      },
      interaction: {
        hover: true,
        zoomView: true,
        dragView: true,
        navigationButtons: false,
        keyboard: false
      },
      nodes: {
        font: { size: 9, color: '#e2e8f0', strokeWidth: 2, strokeColor: '#0b1120' }
      },
      edges: {
        smooth: {
          enabled: true,
          type: 'continuous'
        }
      }
    })

    return () => {
      if (networkRef.current) { networkRef.current.destroy(); networkRef.current = null }
    }
  }, [data])

  // Highlight node when switching from structured view
  useEffect(() => {
    if (viewMode === 'network' && highlightNodeId && networkRef.current && typeof vis !== 'undefined') {
      // Focus on the node
      networkRef.current.focus(highlightNodeId, {
        scale: 1.5,
        animation: { duration: 500, easingFunction: 'easeInOutQuad' }
      })
      // Select the node
      networkRef.current.selectNodes([highlightNodeId])
      // Clear highlight after animation
      setTimeout(() => setHighlightNodeId(null), 1000)
    }
  }, [viewMode, highlightNodeId])

  const handleViewInNetwork = (nodeId: string) => {
    setHighlightNodeId(nodeId)
    setViewMode('network')
  }

  const entityTypes = data?.stats?.entity_types
    ? Object.entries(data.stats.entity_types).sort(([, a], [, b]) => b - a)
    : []

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-52px)] text-text-muted gap-3">
        <div className="w-10 h-10 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        <span className="text-sm">加载知识图谱数据...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-52px)] gap-4">
        <div className="text-4xl">⚠️</div>
        <p className="text-red font-semibold">图谱加载失败</p>
        <p className="text-text-muted text-sm">{error}</p>
        <button onClick={() => window.location.reload()} className="py-2 px-6 bg-accent text-white rounded-full text-sm">重新加载</button>
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-52px)] relative bg-root">
      {/* View Switcher */}
      <div className="absolute top-4 left-4 z-10 bg-surface/95 backdrop-blur border border-border rounded-full p-1 shadow-lg flex gap-1">
        <button
          onClick={() => setViewMode('network')}
          className={`px-4 py-2 rounded-full text-xs font-semibold transition-all ${
            viewMode === 'network'
              ? 'bg-accent text-white'
              : 'text-text-muted hover:text-text-primary'
          }`}
        >
          🔮 网络图谱
        </button>
        <button
          onClick={() => setViewMode('structured')}
          className={`px-4 py-2 rounded-full text-xs font-semibold transition-all ${
            viewMode === 'structured'
              ? 'bg-accent text-white'
              : 'text-text-muted hover:text-text-primary'
          }`}
        >
          📋 结构化视图
        </button>
      </div>

      {/* Network View */}
      {viewMode === 'network' && (
        <>
          {/* Legend */}
          <div className="absolute top-4 right-4 z-10 bg-surface/95 backdrop-blur border border-border rounded-card p-3.5 max-h-[calc(100%-100px)] overflow-y-auto text-[11px] shadow-lg min-w-[180px]">
            <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-2">Entity Types</div>
            {entityTypes.map(([type, count]) => (
              <div key={type} className="flex items-center gap-2 py-0.5">
                <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: TYPE_COLORS[type] || '#64748b' }} />
                {TYPE_ICONS[type] || '?'} {type}
                <span className="ml-auto text-text-muted">{count}</span>
              </div>
            ))}
            <div className="mt-3 pt-2 border-t border-border text-text-muted leading-relaxed">
              {(data?.stats?.total_nodes ?? 0)} nodes<br/>
              {(data?.stats?.total_edges ?? 0)} edges<br/>
              {(data?.stats?.grounded_nodes ?? 0)} grounded
            </div>
          </div>
          <div ref={containerRef} className="w-full h-full" />
        </>
      )}

      {/* Structured View */}
      {viewMode === 'structured' && data && (
        <StructuredView data={data} onViewInNetwork={handleViewInNetwork} />
      )}
    </div>
  )
}
