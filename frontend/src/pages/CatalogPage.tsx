import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import type { CatalogResponse, LowQualityItem } from '../lib/types'

export function CatalogPage() {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null)
  const [lowQuality, setLowQuality] = useState<LowQualityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api.catalog(),
      api.catalogLowQuality(0.5),
    ])
      .then(([catData, lqData]) => {
        setCatalog(catData)
        setLowQuality(lqData.items)
        setLoading(false)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  if (loading) return <div className="text-center py-20 text-text-muted">⏳ 加载数据资产目录...</div>
  if (error) return <div className="p-8 text-center text-red">⚠ 加载失败: {error}</div>
  if (!catalog) return null

  const s = catalog.summary
  const qm = catalog.quality_metrics
  const fb = catalog.feedback
  const conv = catalog.conversations
  const dd = catalog.domain_dict

  const cards = [
    { label: '文档数', value: s.total_documents, icon: '📄' },
    { label: '实体数', value: s.total_entities, icon: '🔗' },
    { label: '边数', value: s.total_edges, icon: '🕸️' },
    { label: '区块数', value: s.total_chunks, icon: '🧩' },
  ]
  const cards2 = [
    { label: '会话数', value: s.total_conversations, icon: '💬' },
    { label: '反馈数', value: s.total_feedback, icon: '📝' },
    { label: '领域术语', value: s.domain_terms, icon: '📖' },
    { label: '接地率', value: qm ? `${(qm.grounded_rate * 100).toFixed(1)}%` : '--', icon: '📌' },
  ]

  return (
    <div className="p-8 max-w-[1100px] max-md:p-4">
      <h2 className="text-[22px] font-extrabold mb-1">数据资产目录</h2>
      <p className="text-text-muted text-sm mb-6">
        更新于 {new Date(catalog.last_updated).toLocaleString()}
      </p>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-3 mb-6 max-md:grid-cols-2">
        {[...cards, ...cards2].map(c => (
          <div key={c.label} className="bg-surface border border-border rounded-card p-4">
            <div className="text-2xl mb-1">{c.icon}</div>
            <div className="text-xl font-extrabold text-text-primary">{c.value}</div>
            <div className="text-[11px] text-text-muted">{c.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6 max-md:grid-cols-1">
        {/* Entity Type Distribution */}
        <div className="bg-surface border border-border rounded-card p-5">
          <h3 className="text-sm font-bold mb-3">实体类型分布</h3>
          {Object.keys(s.by_entity_type).length === 0 ? (
            <div className="text-text-muted text-xs py-4 text-center">暂无数据</div>
          ) : (
            <div className="space-y-2">
              {Object.entries(s.by_entity_type).sort((a, b) => b[1] - a[1]).map(([type, count]) => (
                <div key={type} className="flex items-center gap-2">
                  <div className="flex-1 text-xs text-text-primary">{type}</div>
                  <div className="text-xs font-semibold text-text-primary">{count}</div>
                  <div className="w-24 h-2 bg-elevated rounded-full overflow-hidden">
                    <div
                      className="h-full bg-accent rounded-full"
                      style={{ width: `${(count / s.total_entities * 100).toFixed(1)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quality Metrics */}
        <div className="bg-surface border border-border rounded-card p-5">
          <h3 className="text-sm font-bold mb-3">质量指标</h3>
          {qm ? (
            <div className="space-y-3">
              <MetricRow label="实体接地率" value={`${(qm.grounded_rate * 100).toFixed(1)}%`}
                ok={qm.grounded_rate >= 0.5} />
              <MetricRow label="孤立实体" value={String(qm.orphan_entities)} ok={qm.orphan_entities < 10} />
              <MetricRow label="低质量文档" value={String(qm.low_quality_docs.length)}
                ok={qm.low_quality_docs.length === 0} />
            </div>
          ) : (
            <div className="text-text-muted text-xs py-4 text-center">暂无质量数据</div>
          )}
        </div>

        {/* Domain Dictionary */}
        {dd && (
          <div className="bg-surface border border-border rounded-card p-5">
            <h3 className="text-sm font-bold mb-3">领域词典</h3>
            <div className="space-y-2">
              {Object.entries(dd.by_category).map(([cat, count]) => (
                <div key={cat} className="flex justify-between text-xs">
                  <span className="text-text-muted">{cat === 'safety' ? '安全' : cat === 'equipment' ? '设备' : cat === 'ppe' ? '防护' : cat === 'regulation' ? '法规' : cat}</span>
                  <span className="font-semibold">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Feedback Stats */}
        {fb && (
          <div className="bg-surface border border-border rounded-card p-5">
            <h3 className="text-sm font-bold mb-3">用户反馈</h3>
            <div className="space-y-2">
              <MetricRow label="好评率" value={`${(fb.positive_ratio * 100).toFixed(1)}%`}
                ok={fb.positive_ratio >= 0.7} />
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">好评 / 差评</span>
                <span className="font-semibold text-green">{fb.positive}</span>
                <span className="text-text-muted">/</span>
                <span className="font-semibold text-red">{fb.negative}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Low Quality Warnings */}
      {lowQuality.length > 0 && (
        <div className="mt-6 bg-red/5 border border-red/20 rounded-card p-5">
          <h3 className="text-sm font-bold text-red mb-3">⚠ 数据质量预警</h3>
          <div className="space-y-2">
            {lowQuality.map(item => (
              <div key={item.doc_id} className="flex justify-between items-center text-xs bg-surface rounded-lg p-3">
                <span className="text-text-primary font-medium">{item.doc_id}</span>
                <span className="text-text-muted">{item.issue} ({item.value.toFixed(2)})</span>
                <span className="text-text-muted">
                  实体: {item.entities_grounded}/{item.entities_total}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function MetricRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-text-muted">{label}</span>
      <span className={`font-semibold ${ok ? 'text-green' : 'text-red'}`}>{value}</span>
    </div>
  )
}
