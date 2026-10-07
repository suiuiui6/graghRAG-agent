import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAppStore } from '../stores/useAppStore'
import { api } from '../lib/api'

export default function AuthCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const setUser = useAppStore(s => s.setUser)
  const [error, setError] = useState('')

  useEffect(() => {
    const accessToken = searchParams.get('access_token')
    const refreshToken = searchParams.get('refresh_token')

    if (accessToken) {
      localStorage.setItem('access_token', accessToken)
      if (refreshToken) localStorage.setItem('refresh_token', refreshToken)

      api.authMe()
        .then(user => { setUser(user); navigate('/', { replace: true }) })
        .catch(() => { setError('无法获取用户信息'); setTimeout(() => navigate('/login', { replace: true }), 2000) })
    } else {
      setError('SSO 登录失败：未收到认证令牌')
      setTimeout(() => navigate('/login', { replace: true }), 2000)
    }
  }, [searchParams, navigate, setUser])

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="text-center">
        {error ? (
          <div className="text-red-500 text-sm">{error}</div>
        ) : (
          <>
            <div className="w-10 h-10 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-text-muted">SSO 登录成功，正在跳转…</p>
          </>
        )}
      </div>
    </div>
  )
}
