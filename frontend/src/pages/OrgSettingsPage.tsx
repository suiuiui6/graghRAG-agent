import { useState, useEffect } from 'react'
import { api } from '../lib/api'

interface Org {
  org_id: string; name: string; slug: string; created_at: string;
  plan: string; is_active: boolean;
}

interface Project {
  project_id: string; org_id: string; name: string; description: string;
  project_code: string | null; is_archived: boolean; created_at: string;
}

interface Member {
  membership_id: string; org_id: string; user_id: string;
  username: string; role: string; joined_at: string;
}

export default function OrgSettingsPage() {
  const [orgs, setOrgs] = useState<Org[]>([])
  const [selectedOrg, setSelectedOrg] = useState<Org | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'projects' | 'members'>('projects')
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', slug: '', description: '' })

  useEffect(() => { loadOrgs() }, [])

  const loadOrgs = async () => {
    setLoading(true)
    try {
      const data = await api.listOrgs()
      setOrgs(data.orgs)
      if (data.orgs.length > 0 && !selectedOrg) {
        selectOrg(data.orgs[0])
      }
    } catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed') }
    setLoading(false)
  }

  const selectOrg = async (org: Org) => {
    setSelectedOrg(org)
    try {
      const [projData, memData] = await Promise.all([
        api.listProjects(org.org_id),
        api.listMembers(org.org_id),
      ])
      setProjects(projData.projects || [])
      setMembers(memData.members || [])
    } catch { /* ignore */ }
  }

  const createOrg = async () => {
    if (!form.name || !form.slug) return
    try {
      await api.createOrg(form.name, form.slug)
      setShowCreate(false)
      setForm({ name: '', slug: '', description: '' })
      loadOrgs()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed') }
  }

  const createProject = async () => {
    if (!selectedOrg || !form.name) return
    try {
      await api.createProject(selectedOrg.org_id, form.name, form.description)
      setShowCreate(false)
      setForm({ name: '', slug: '', description: '' })
      selectOrg(selectedOrg)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed') }
  }

  const inviteMember = async () => {
    if (!selectedOrg) return
    const userId = prompt('输入用户 ID:')
    if (!userId) return
    const role = prompt('角色 (org_admin / org_editor / org_viewer):', 'org_viewer')
    if (!role) return
    try {
      await api.inviteMember(selectedOrg.org_id, userId, role)
      selectOrg(selectedOrg)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed') }
  }

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold">组织与项目管理</h2>
          <p className="text-xs text-text-muted mt-1">多租户隔离：组织 → 项目 → 文档</p>
        </div>
        <button onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-all">
          {showCreate ? '取消' : '+ 新建'}
        </button>
      </div>

      {error && <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-100 text-xs text-red-500">{error}</div>}

      {showCreate && (
        <div className="bg-surface border border-border rounded-xl p-5 mb-6 space-y-3">
          <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            placeholder={selectedOrg ? '项目名称' : '组织名称'}
            className="w-full px-3 py-2 rounded-lg border border-border bg-root text-sm" />
          {!selectedOrg && (
            <input type="text" value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value }))}
              placeholder="URL 标识 (如 jilin-huajian)"
              className="w-full px-3 py-2 rounded-lg border border-border bg-root text-sm" />
          )}
          {selectedOrg && (
            <input type="text" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              placeholder="项目描述"
              className="w-full px-3 py-2 rounded-lg border border-border bg-root text-sm" />
          )}
          <button onClick={selectedOrg ? createProject : createOrg}
            className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium">
            创建 {selectedOrg ? '项目' : '组织'}
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-text-muted py-8 text-center">加载中…</div>
      ) : orgs.length === 0 ? (
        <div className="text-sm text-text-muted py-12 text-center border border-dashed border-border rounded-xl">
          暂无组织，点击上方按钮创建
        </div>
      ) : (
        <div className="flex gap-4">
          {/* Org sidebar */}
          <div className="w-56 flex-shrink-0 space-y-1">
            {orgs.map(org => (
              <button key={org.org_id} onClick={() => selectOrg(org)}
                className={`w-full text-left px-3.5 py-2.5 rounded-lg text-sm transition-all
                  ${selectedOrg?.org_id === org.org_id ? 'bg-accent/10 text-accent font-medium' : 'text-text-secondary hover:bg-surface'}`}>
                <div className="truncate">{org.name}</div>
                <div className="text-[10px] text-text-muted">{org.slug} · {org.plan}</div>
              </button>
            ))}
          </div>

          {/* Detail panel */}
          {selectedOrg && (
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-4">
                <h3 className="font-semibold">{selectedOrg.name}</h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/10 text-accent">{selectedOrg.plan}</span>
              </div>

              <div className="flex gap-2 mb-4">
                {(['projects', 'members'] as const).map(t => (
                  <button key={t} onClick={() => setTab(t)}
                    className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all
                      ${tab === t ? 'bg-accent text-white' : 'border border-border text-text-secondary hover:bg-surface'}`}>
                    {t === 'projects' ? `项目 (${projects.length})` : `成员 (${members.length})`}
                  </button>
                ))}
              </div>

              {tab === 'projects' && (
                <div className="space-y-2">
                  {projects.length === 0 ? (
                    <div className="text-xs text-text-muted py-6 text-center border border-dashed border-border rounded-lg">
                      暂无项目
                    </div>
                  ) : projects.map(p => (
                    <div key={p.project_id} className="bg-surface border border-border rounded-lg p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{p.name}</span>
                        {p.is_archived && <span className="text-[10px] px-1.5 py-0.5 rounded bg-text-muted/10 text-text-muted">已归档</span>}
                      </div>
                      {p.description && <div className="text-xs text-text-muted mt-1">{p.description}</div>}
                      {p.project_code && <code className="text-[10px] text-accent mt-1 block">{p.project_code}</code>}
                    </div>
                  ))}
                </div>
              )}

              {tab === 'members' && (
                <div className="space-y-2">
                  <button onClick={inviteMember}
                    className="text-xs px-3 py-1.5 rounded-lg border border-border text-text-secondary hover:bg-surface transition-all mb-2">
                    + 邀请成员
                  </button>
                  {members.length === 0 ? (
                    <div className="text-xs text-text-muted py-6 text-center border border-dashed border-border rounded-lg">
                      暂无成员
                    </div>
                  ) : members.map(m => (
                    <div key={m.membership_id} className="bg-surface border border-border rounded-lg p-3 flex items-center justify-between">
                      <div>
                        <span className="text-sm font-medium">{m.username || m.user_id}</span>
                        <span className="text-[10px] text-text-muted ml-2">{m.user_id}</span>
                      </div>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                        m.role === 'org_admin' ? 'bg-accent/10 text-accent' :
                        m.role === 'org_editor' ? 'bg-blue-50 text-blue-600' : 'bg-text-muted/10 text-text-muted'
                      }`}>{m.role}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
