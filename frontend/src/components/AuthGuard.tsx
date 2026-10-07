import { useEffect, type ReactNode } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { api } from '../lib/api'
import { useAppStore } from '../stores/useAppStore'

export function AuthGuard({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const user = useAppStore(s => s.user)
  const setUser = useAppStore(s => s.setUser)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      navigate(`/login?redirect=${encodeURIComponent(location.pathname)}`, { replace: true })
      return
    }
    if (!user) {
      api.authMe()
        .then(setUser)
        .catch(() => {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          navigate(`/login?redirect=${encodeURIComponent(location.pathname)}`, { replace: true })
        })
    }
  }, [navigate, location.pathname, user, setUser])

  if (!localStorage.getItem('access_token')) {
    return null
  }

  return <>{children}</>
}
