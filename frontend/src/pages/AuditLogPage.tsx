import { useState } from 'react'
import { api } from '../lib/api'

interface AuditRecord {
  event: string; user_id: string; timestamp: string; ip: string; details: Record<string, unknown>
}

export default function AuditLogPage() {
  const [records, setRecords] = useState<AuditRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [event, setEvent] = useState('')
  const [userId, setUserId] = useState('')
  const [exporting, setExporting] = useState(false)

  const query = async () => {
    setLoading(true)
    setRecords([])
    setError('')
    try {
      const params: Record<string, string> = {}
      if (event) params.event = event
      if (userId) params.user_id = userId
      const data = await api.queryAudit(params)
      setRecords(data.audit_logs)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '查询失败')
    }
    setLoading(false)
  }

  const exportCsv = async () => {
    setExporting(true)
    try {
      const csv = await api.exportAudit(event || undefined, userId || undefined)
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit-export-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '导出失败')
    }
    setExporting(false)
  }

  const EVENT_CATEGORIES: Record<string, string> = {
    'user.login': '认证', 'user.logout': '认证', 'user.login_failed': '认证',
    'doc.ingested': '文档', 'doc.deleted': '文档', 'doc.reingested': '文档',
    'entity.created': '数据操作', 'entity.updated': '数据操作', 'entity.deleted': '数据操作',
    'kg.version_created': 'KG', 'kg.version_switched': 'KG',
    'feedback.received': '反馈', 'feedback.resolved': '反馈',
    'backup.triggered': '系统', 'restore.executed': '系统', 'cleanup.executed': '系统',
    'api_key.created': '权限', 'api_key.revoked': '权限',
    'data.exported': '导出',
  }

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold">审计日志</h2>
          <p className="text-xs text-text-muted mt-1">记录所有敏感操作，保留 365 天</p>
        </div>
        <button onClick={exportCsv} disabled={exporting}
          className="px-4 py-2 rounded-lg border border-border text-text-secondary text-sm font-medium hover:bg-surface transition-all">
          {exporting ? '导出中…' : '导出 CSV'}
        </button>
      </div>

      {error && <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-100 text-xs text-red-500">{error}</div>}

      <div className="flex gap-3 mb-6">
        <input
          type="text"
          value={event}
          onChange={e => setEvent(e.target.value)}
          placeholder="事件类型 (如 user.login)"
          className="flex-1 px-3 py-2 rounded-lg border border-border bg-root text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
        />
        <input
          type="text"
          value={userId}
          onChange={e => setUserId(e.target.value)}
          placeholder="用户 ID"
          className="w-48 px-3 py-2 rounded-lg border border-border bg-root text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
        />
        <button onClick={query} disabled={loading}
          className="px-6 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-all">
          {loading ? '查询中…' : '查询'}
        </button>
      </div>

      {records.length === 0 && !loading ? (
        <div className="text-sm text-text-muted py-12 text-center border border-dashed border-border rounded-xl">
          {error ? '查询出错' : '输入查询条件后点击查询'}
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-root">
                  <th className="text-left px-4 py-2.5 font-medium text-text-secondary">时间</th>
                  <th className="text-left px-4 py-2.5 font-medium text-text-secondary">事件</th>
                  <th className="text-left px-4 py-2.5 font-medium text-text-secondary">用户</th>
                  <th className="text-left px-4 py-2.5 font-medium text-text-secondary">类别</th>
                  <th className="text-left px-4 py-2.5 font-medium text-text-secondary">详情</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r, i) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-root/50">
                    <td className="px-4 py-2.5 text-text-muted whitespace-nowrap font-mono">
                      {new Date(r.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 font-mono">{r.event}</td>
                    <td className="px-4 py-2.5 text-text-secondary">{r.user_id || '—'}</td>
                    <td className="px-4 py-2.5">
                      <span className="px-2 py-0.5 rounded-md bg-root border border-border text-[10px] text-text-secondary">
                        {EVENT_CATEGORIES[r.event] || '其他'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-text-muted max-w-[300px] truncate">
                      {r.ip ? `IP: ${r.ip}` : ''}{r.details ? ` ${JSON.stringify(r.details).slice(0, 80)}` : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
