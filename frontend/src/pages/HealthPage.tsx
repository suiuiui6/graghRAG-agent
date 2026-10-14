import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import type { HealthResponse } from '../lib/api'

export function HealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.health()
      .then(data => { setHealth(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  if (loading) return <div className="text-center py-20 text-text-muted">⏳ 加载中...</div>
  if (error) return <div className="p-8 text-center text-red">⚠ 无法连接后端: {error}</div>
  if (!health) return null

  const components = [
    { name: 'API 网关', key: 'api_server', icon: '🌐', detail: `端口 8000 · v${health.version}` },
    { name: 'MinerU 服务', key: 'mineru_api', icon: '📄', detail: '云端 API' },
    { name: 'DeepSeek API', key: 'deepseek_api', icon: '🤖', detail: 'deepseek-chat' },
    { name: 'KG 图谱存储', key: 'kg_store', icon: '🔗', detail: `${health.stats.total_kg_nodes} nodes · 已服务 ${health.stats.total_queries_served} 次查询` },
  ]

  return (
    <div className="p-8 max-w-[900px] max-md:p-4">
      <h2 className="text-[22px] font-extrabold mb-1">系统状态</h2>
      <p className="text-text-muted text-sm mb-6">
        {health.status === 'healthy' ? '✅ 所有组件运行正常' : '⚠ 部分组件异常'} · 已运行 {Math.floor(health.uptime_seconds / 60)} 分
      </p>

      <div className="grid grid-cols-4 gap-3 max-md:grid-cols-2">
        {components.map(c => (
          <div key={c.key} className="bg-surface border border-border rounded-card p-5">
            <div className="flex items-center gap-2 mb-1">
              <span>{c.icon}</span>
              <span className={`w-2 h-2 rounded-full ${health.components[c.key] === 'ok' ? 'bg-green' : 'bg-red'}`} />
            </div>
            <div className="text-[13px] font-bold">{c.name}</div>
            <div className="text-[11px] text-text-muted mt-1">{c.detail}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
