import { useState, useEffect } from 'react'
import { api } from '../lib/api'

interface Webhook {
  webhook_id: string; url: string; events: string[]; secret: string; enabled: boolean; created_at: string; updated_at: string
}

const EVENT_TYPES = [
  'doc.ingested', 'doc.deleted', 'kg.version_created', 'kg.version_switched',
  'feedback.received', 'feedback.resolved', 'backup.completed', 'backup.failed',
  'cleanup.executed', 'quality.alert',
]

export default function WebhookSettingsPage() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ url: '', events: [] as string[], secret: '' })
  const [saving, setSaving] = useState(false)
  const [testingId, setTestingId] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try { setWebhooks(await api.listWebhooks()) } catch (err: unknown) { setError(err instanceof Error ? err.message : '加载失败') }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const toggleEvent = (eventType: string) => {
    setForm(f => ({
      ...f,
      events: f.events.includes(eventType)
        ? f.events.filter(e => e !== eventType)
        : [...f.events, eventType],
    }))
  }

  const createWebhook = async () => {
    setSaving(true)
    try {
      await api.createWebhook({ url: form.url, events: form.events, secret: form.secret })
      setShowForm(false)
      setForm({ url: '', events: [], secret: '' })
      load()
    } catch (err: unknown) { setError(err instanceof Error ? err.message : '创建失败') }
    setSaving(false)
  }

  const deleteWebhook = async (id: string) => {
    try { await api.deleteWebhook(id); load() } catch (err: unknown) { setError(err instanceof Error ? err.message : '删除失败') }
  }

  const testWebhook = async (id: string) => {
    setTestingId(id)
    try { await api.testWebhook(id) } catch (err: unknown) { setError(err instanceof Error ? err.message : '测试失败') }
    setTestingId(null)
  }

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold">Webhook 管理</h2>
          <p className="text-xs text-text-muted mt-1">订阅系统事件，投递到外部 URL</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-all">
          {showForm ? '取消' : '+ 添加 Webhook'}
        </button>
      </div>

      {error && <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-100 text-xs text-red-500">{error}</div>}

      {showForm && (
        <div className="bg-surface border border-border rounded-xl p-5 mb-6 space-y-4">
          <div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wider">回调 URL</label>
            <input type="url" value={form.url} onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
              className="w-full mt-1 px-3 py-2 rounded-lg border border-border bg-root text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
              placeholder="https://my-system.com/hooks/graphrag" />
          </div>
          <div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wider">共享密钥 (HMAC-SHA256)</label>
            <input type="text" value={form.secret} onChange={e => setForm(f => ({ ...f, secret: e.target.value }))}
              className="w-full mt-1 px-3 py-2 rounded-lg border border-border bg-root text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
              placeholder="wh_shared_secret" />
          </div>
          <div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wider">订阅事件</label>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {EVENT_TYPES.map(et => (
                <label key={et} className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs cursor-pointer transition-all
                  ${form.events.includes(et) ? 'border-accent bg-accent/5 text-accent' : 'border-border text-text-secondary hover:border-accent/30'}`}>
                  <input type="checkbox" checked={form.events.includes(et)} onChange={() => toggleEvent(et)} className="sr-only" />
                  <span className="font-mono">{et}</span>
                </label>
              ))}
            </div>
          </div>
          <button onClick={createWebhook} disabled={saving || !form.url || form.events.length === 0}
            className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-all">
            {saving ? '创建中…' : '创建 Webhook'}
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-text-muted py-8 text-center">加载中…</div>
      ) : webhooks.length === 0 ? (
        <div className="text-sm text-text-muted py-12 text-center border border-dashed border-border rounded-xl">
          暂无 Webhook，点击上方按钮添加
        </div>
      ) : (
        <div className="space-y-3">
          {webhooks.map(wh => (
            <div key={wh.webhook_id} className="bg-surface border border-border rounded-xl p-4 flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`w-1.5 h-1.5 rounded-full ${wh.enabled ? 'bg-green' : 'bg-text-muted'}`} />
                  <span className="font-medium text-sm truncate">{wh.url}</span>
                </div>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {wh.events.map(e => (
                    <span key={e} className="px-2 py-0.5 rounded-md bg-root border border-border text-[10px] font-mono text-text-secondary">{e}</span>
                  ))}
                </div>
                <div className="text-[10px] text-text-muted mt-2">创建于 {new Date(wh.created_at).toLocaleString()}</div>
              </div>
              <div className="flex gap-1.5 flex-shrink-0">
                <button onClick={() => testWebhook(wh.webhook_id)} disabled={testingId === wh.webhook_id}
                  className="px-3 py-1.5 rounded-lg border border-border text-xs text-text-secondary hover:bg-root disabled:opacity-50 transition-all">
                  {testingId === wh.webhook_id ? '测试中' : '测试'}
                </button>
                <button onClick={() => deleteWebhook(wh.webhook_id)}
                  className="px-3 py-1.5 rounded-lg border border-red-200 text-xs text-red-500 hover:bg-red-50 transition-all">
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
