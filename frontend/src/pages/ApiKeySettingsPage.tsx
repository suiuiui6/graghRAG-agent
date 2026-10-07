import { useState, useEffect } from 'react'
import { api } from '../lib/api'

interface ApiKeyRecord {
  key_id: string; name: string; key_prefix: string; created_at: string;
  last_used_at: string | null; revoked: boolean; scopes: string[]; rate_limit_per_minute: number;
}

const SCOPES = [
  'read:query', 'read:catalog', 'read:export', 'write:ingest',
  'write:feedback', 'write:dict', 'admin:system', 'admin:keys',
]

export default function ApiKeySettingsPage() {
  const [keys, setKeys] = useState<ApiKeyRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', scopes: ['read:query'] as string[], rate_limit_per_minute: 60 })
  const [newKey, setNewKey] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try { setKeys(await api.listApiKeys()) } catch (err: unknown) { setError(err instanceof Error ? err.message : '加载失败') }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const toggleScope = (scope: string) => {
    setForm(f => ({ ...f, scopes: f.scopes.includes(scope) ? f.scopes.filter(s => s !== scope) : [...f.scopes, scope] }))
  }

  const createKey = async () => {
    setSaving(true)
    setNewKey(null)
    try {
      const result = await api.createApiKey(form.name, form.scopes, form.rate_limit_per_minute)
      setNewKey(result.full_key)
      setShowForm(false)
      setForm({ name: '', scopes: ['read:query'], rate_limit_per_minute: 60 })
      load()
    } catch (err: unknown) { setError(err instanceof Error ? err.message : '创建失败') }
    setSaving(false)
  }

  const revokeKey = async (id: string) => {
    try { await api.revokeApiKey(id); load() } catch (err: unknown) { setError(err instanceof Error ? err.message : '撤销失败') }
  }

  const rotateKey = async (id: string) => {
    setNewKey(null)
    try {
      const result = await api.rotateApiKey(id)
      setNewKey(result.full_key)
      load()
    } catch (err: unknown) { setError(err instanceof Error ? err.message : '轮换失败') }
  }

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold">API Key 管理</h2>
          <p className="text-xs text-text-muted mt-1">为第三方服务创建独立的 API Key，支持权限范围和限额</p>
        </div>
        <button onClick={() => { setShowForm(!showForm); setNewKey(null) }}
          className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-all">
          {showForm ? '取消' : '+ 创建 Key'}
        </button>
      </div>

      {error && <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-100 text-xs text-red-500">{error}</div>}

      {newKey && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-amber-50 border border-amber-200 text-xs">
          <p className="font-semibold text-amber-800 mb-1">新 Key 已创建（仅显示一次，请立即复制）：</p>
          <code className="block font-mono text-amber-900 bg-amber-100 px-2 py-1 rounded mt-1 break-all select-all">{newKey}</code>
        </div>
      )}

      {showForm && (
        <div className="bg-surface border border-border rounded-xl p-5 mb-6 space-y-4">
          <div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wider">名称</label>
            <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full mt-1 px-3 py-2 rounded-lg border border-border bg-root text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
              placeholder="Engine-Vue集成" />
          </div>
          <div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wider">权限范围 (Scopes)</label>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {SCOPES.map(s => (
                <label key={s} className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs cursor-pointer transition-all
                  ${form.scopes.includes(s) ? 'border-accent bg-accent/5 text-accent' : 'border-border text-text-secondary hover:border-accent/30'}`}>
                  <input type="checkbox" checked={form.scopes.includes(s)} onChange={() => toggleScope(s)} className="sr-only" />
                  <span className="font-mono">{s}</span>
                </label>
              ))}
            </div>
          </div>
          <button onClick={createKey} disabled={saving || !form.name}
            className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-all">
            {saving ? '创建中…' : '创建 API Key'}
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-text-muted py-8 text-center">加载中…</div>
      ) : keys.length === 0 ? (
        <div className="text-sm text-text-muted py-12 text-center border border-dashed border-border rounded-xl">
          暂无 API Key
        </div>
      ) : (
        <div className="space-y-3">
          {keys.map(k => (
            <div key={k.key_id} className="bg-surface border border-border rounded-xl p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-1.5 h-1.5 rounded-full ${k.revoked ? 'bg-red' : 'bg-green'}`} />
                    <span className="font-medium text-sm">{k.name}</span>
                    <code className="text-[10px] text-text-muted">{k.key_prefix}...{k.key_id.slice(0, 6)}</code>
                  </div>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {k.scopes.map(s => (
                      <span key={s} className="px-2 py-0.5 rounded-md bg-root border border-border text-[10px] font-mono text-text-secondary">{s}</span>
                    ))}
                  </div>
                  <div className="text-[10px] text-text-muted mt-2">
                    创建于 {new Date(k.created_at).toLocaleString()}
                    {k.last_used_at && ` · 最近使用 ${new Date(k.last_used_at).toLocaleString()}`}
                    {k.revoked && <span className="text-red-500 ml-2 font-semibold">已撤销</span>}
                  </div>
                </div>
                <div className="flex gap-1.5 flex-shrink-0">
                  {!k.revoked && (
                    <>
                      <button onClick={() => rotateKey(k.key_id)}
                        className="px-3 py-1.5 rounded-lg border border-border text-xs text-text-secondary hover:bg-root transition-all">轮换</button>
                      <button onClick={() => revokeKey(k.key_id)}
                        className="px-3 py-1.5 rounded-lg border border-red-200 text-xs text-red-500 hover:bg-red-50 transition-all">撤销</button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
