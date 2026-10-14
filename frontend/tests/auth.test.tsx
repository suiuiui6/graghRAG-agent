import { beforeEach, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { api } from '../src/lib/api'
import { useAppStore } from '../src/stores/useAppStore'
import { AuthGuard } from '../src/components/AuthGuard'
import LoginPage from '../src/pages/LoginPage'
import AuthCallbackPage from '../src/pages/AuthCallbackPage'
import { mount, user } from './helpers'
beforeEach(() => useAppStore.setState({ user: null }))
it('redirects an anonymous protected path with an encoded return target', async () => {
  mount(<AuthGuard><p>保护内容</p></AuthGuard>, '/settings/org', '/settings/org')
  expect(await screen.findByTestId('location')).toHaveTextContent('/login?redirect=%2Fsettings%2Forg'); expect(screen.queryByText('保护内容')).toBeNull()
})
it.each([true, false])('hydrates or clears invalid authenticated sessions: %s', async valid => {
  localStorage.setItem('access_token', 'test'); localStorage.setItem('refresh_token', 'test')
  vi.spyOn(api, 'authMe')[valid ? 'mockResolvedValue' : 'mockRejectedValue'](valid ? user : new Error('denied'))
  mount(<AuthGuard><p>保护内容</p></AuthGuard>, '/secure', '/secure')
  await waitFor(() => valid ? expect(useAppStore.getState().user).toEqual(user) : expect(screen.getByTestId('location')).toHaveTextContent('/login?redirect=%2Fsecure'))
  if (!valid) expect(localStorage.getItem('refresh_token')).toBeNull()
})
it('does not re-fetch an already hydrated user', () => {
  localStorage.setItem('access_token', 'test'); useAppStore.getState().setUser(user); const f=vi.spyOn(api,'authMe')
  mount(<AuthGuard><p>保护内容</p></AuthGuard>); expect(screen.getByText('保护内容')).toBeInTheDocument(); expect(f).not.toHaveBeenCalled()
})
it.each(['/documents', '/'])('local login stores tokens and redirects to %s', async dest => {
  vi.spyOn(api, 'authLogin').mockResolvedValue({ access_token:'test-a',refresh_token:'test-r' } as never); vi.spyOn(api,'authMe').mockResolvedValue(user)
  mount(<LoginPage />, dest === '/' ? '/login' : '/login?redirect=/documents', '/login')
  fireEvent.change(screen.getByPlaceholderText('admin 或 OA 账号'), { target: { value: 'alice' } }); fireEvent.change(screen.getByPlaceholderText('开发模式可留空'), { target: { value: 'test' } }); fireEvent.click(screen.getByText('本地登录'))
  await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(dest)); expect(localStorage.getItem('access_token')).toBe('test-a'); expect(api.authLogin).toHaveBeenCalledWith('alice','test','local')
})
it.each([new Error('denied'), 'bad'])('local and SSO failures reset loading and display safe messages %s', async error => {
  vi.spyOn(api,'authLogin').mockRejectedValue(error); vi.spyOn(api,'authLoginPage').mockRejectedValue(error)
  mount(<LoginPage />); fireEvent.change(screen.getByPlaceholderText('admin 或 OA 账号'), { target: { value:'u' } }); fireEvent.click(screen.getByText('本地登录'))
  expect(await screen.findByText(error instanceof Error ? 'denied' : '登录失败')).toBeInTheDocument()
  fireEvent.click(screen.getByText('SSO 统一认证')); expect(await screen.findByText(error instanceof Error ? 'denied' : '无法获取 SSO 登录地址')).toBeInTheDocument(); expect(screen.getByText('本地登录')).toBeEnabled()
})
it('existing token redirects away from login', async () => { localStorage.setItem('access_token','test'); mount(<LoginPage />, '/login','/login'); await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/')) })
it.each([true,false])('OAuth callback retains optional refresh token %s', async refresh => {
  vi.spyOn(api,'authMe').mockResolvedValue(user); mount(<AuthCallbackPage />, '/auth/callback?access_token=test'+(refresh?'&refresh_token=refresh':''), '/auth/callback')
  await waitFor(() => expect(useAppStore.getState().user).toEqual(user)); expect(localStorage.getItem('refresh_token')).toBe(refresh?'refresh':null)
})
it.each(['missing','denied'])('OAuth callback redirects on %s', async mode => {
  vi.useFakeTimers(); vi.spyOn(api,'authMe').mockRejectedValue(new Error('denied'))
  mount(<AuthCallbackPage />, '/auth/callback'+(mode==='denied'?'?access_token=test':''), '/auth/callback')
  await act(async () => {}); expect(screen.getByText(mode==='missing'?'SSO 登录失败：未收到认证令牌':'无法获取用户信息')).toBeInTheDocument()
  await act(async () => { await vi.advanceTimersByTimeAsync(2000) }); expect(screen.getByTestId('location')).toHaveTextContent('/login')
})
