import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useAppStore } from '../stores/useAppStore'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const setUser = useAppStore(s => s.setUser)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) navigate('/', { replace: true })
  }, [navigate])

  const handleLocalLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const result = await api.authLogin(username, password, 'local')
      localStorage.setItem('access_token', result.access_token)
      localStorage.setItem('refresh_token', result.refresh_token)
      const me = await api.authMe()
      setUser(me)
      const redirect = searchParams.get('redirect') || '/'
      navigate(redirect, { replace: true })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSSOLogin = async () => {
    setLoading(true)
    setError('')
    try {
      const { login_url } = await api.authLoginPage()
      window.location.href = login_url
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '无法获取 SSO 登录地址')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-accent to-indigo-500 rounded-2xl flex items-center justify-center text-2xl text-white mx-auto mb-4">⚡</div>
          <h2 className="text-xl font-bold">GraphRAG 知识引擎</h2>
          <p className="text-sm text-text-muted mt-1">企业知识图谱问答系统</p>
        </div>

        <form onSubmit={handleLocalLogin} className="bg-surface border border-border rounded-xl p-6 space-y-4">
          <div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wider">用户名</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="w-full mt-1.5 px-3 py-2 rounded-lg border border-border bg-root text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
              placeholder="admin 或 OA 账号"
              required
            />
          </div>
          <div>
            <label className="text-xs font-medium text-text-secondary uppercase tracking-wider">密码</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full mt-1.5 px-3 py-2 rounded-lg border border-border bg-root text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
              placeholder="开发模式可留空"
            />
          </div>
          {error && (
            <div className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</div>
          )}
          <div className="space-y-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-accent text-white text-sm font-semibold hover:bg-accent/90 disabled:opacity-50 transition-all"
            >
              {loading ? '登录中…' : '本地登录'}
            </button>
            <button
              type="button"
              onClick={handleSSOLogin}
              disabled={loading}
              className="w-full py-2.5 rounded-lg border border-border text-text-secondary text-sm font-medium hover:bg-surface/50 disabled:opacity-50 transition-all"
            >
              SSO 统一认证
            </button>
          </div>
          <p className="text-[10px] text-text-muted text-center">
            开发环境接受任意用户名登录 · admin 账号拥有全部权限
          </p>
        </form>
      </div>
    </div>
  )
}
