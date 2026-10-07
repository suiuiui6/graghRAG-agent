import { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAppStore } from '../../stores/useAppStore'
import { api } from '../../lib/api'
import { NAV_ITEMS } from '../../lib/constants'
import ChatWidget from '../ChatWidget'
import type { ReactNode } from 'react'

export function AppShell({ children }: { children: ReactNode }) {
  const loc = useLocation()
  const docCount = useAppStore(s => s.documents.length)
  const stats = useAppStore(s => s.stats)
  const setStats = useAppStore(s => s.setStats)
  const setStatsError = useAppStore(s => s.setStatsError)

  useEffect(() => {
    api.getStats().then(setStats).catch(e => setStatsError(e.message))
    const t = setInterval(() => {
      api.getStats().then(setStats).catch(() => {})
    }, 30000)
    return () => clearInterval(t)
  }, [setStats, setStatsError])

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-[240px] min-w-[240px] bg-surface border-r border-border flex flex-col z-10 max-md:hidden">
        <div className="p-5 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-[38px] h-[38px] bg-gradient-to-br from-accent to-indigo-500 rounded-[10px] flex items-center justify-center text-lg text-white">⚡</div>
            <div>
              <h1 className="text-[15px] font-bold tracking-tight">RAG 知识图谱</h1>
              <p className="text-[10px] text-text-muted uppercase tracking-wider mt-0.5">QA System</p>
            </div>
          </div>
        </div>
        <nav className="p-3 flex-1">
          {NAV_ITEMS.map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-medium mb-0.5 transition-all
                ${loc.pathname.startsWith(item.path) ? 'bg-accent/10 text-accent' : 'text-text-secondary hover:bg-white/3 hover:text-text-primary'}`}
            >
              <span className="text-base w-[22px] text-center">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="p-3.5 mx-3 mb-3 border-t border-border text-[11px] text-text-muted">
          <div className="flex justify-between py-0.5"><span>已索引文档</span><span className="text-text-secondary font-semibold">{docCount}</span></div>
          <div className="flex justify-between py-0.5"><span>图谱节点</span><span className="text-text-secondary font-semibold">{stats ? stats.total_kg_nodes.toLocaleString() : '—'}</span></div>
          <div className="flex justify-between py-0.5"><span>图谱关系</span><span className="text-text-secondary font-semibold">{stats ? stats.total_kg_edges.toLocaleString() : '—'}</span></div>
          <div className="flex justify-between py-0.5"><span>今日查询</span><span className="text-text-secondary font-semibold">{stats ? stats.queries_today.toLocaleString() : '—'}</span></div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-[52px] px-6 border-b border-border flex items-center justify-between bg-root flex-shrink-0">
          <div className="text-xs text-text-muted">
            系统 / <span className="text-text-primary font-medium">{NAV_ITEMS.find(i => loc.pathname.startsWith(i.path))?.label || '首页'}</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex gap-3 text-[11px] text-text-muted">
              <span><span className="w-1.5 h-1.5 rounded-full bg-green inline-block mr-1" />MinerU</span>
              <span><span className="w-1.5 h-1.5 rounded-full bg-green inline-block mr-1" />DeepSeek</span>
              <span><span className="w-1.5 h-1.5 rounded-full bg-green inline-block mr-1" />KG Store</span>
            </div>
            {useAppStore(s => s.user) && (
              <button
                onClick={() => {
                  localStorage.removeItem('access_token')
                  localStorage.removeItem('refresh_token')
                  window.location.href = '/login'
                }}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border text-xs text-text-secondary hover:bg-surface transition-all"
              >
                <span className="w-5 h-5 rounded-full bg-accent/10 text-accent flex items-center justify-center text-[10px] font-semibold">
                  {useAppStore(s => s.user)?.display_name?.[0] || 'U'}
                </span>
                <span>{useAppStore(s => s.user)?.display_name || '用户'}</span>
              </button>
            )}
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>

      {/* AI Chat Widget */}      <ChatWidget />

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 bg-surface border-t border-border flex justify-around py-2 z-20">
        {NAV_ITEMS.map(item => (
          <Link key={item.path} to={item.path}
            className={`flex flex-col items-center gap-0.5 text-[10px] p-2 rounded-lg
              ${loc.pathname.startsWith(item.path) ? 'text-accent' : 'text-text-muted'}`}
          >
            <span className="text-lg">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  )
}
