import { beforeEach, expect, it, vi } from 'vitest'
import { fireEvent } from '@testing-library/react'
import { deferred } from './helpers'

type WidgetApi = { open(): void; close(): void; toggle(): void; ask(question: string): void }
const widget = () => (window as unknown as { GraphRAGChat: WidgetApi }).GraphRAGChat
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve() }
const response = (data: unknown, status = 200) => ({ ok: status < 400, status, json: async () => data })
async function boot(dataset: Record<string, string> = {}) {
  const script = document.createElement('script')
  script.src = 'https://service.example/static/chat-widget.js'
  Object.assign(script.dataset, dataset)
  vi.spyOn(document, 'currentScript', 'get').mockReturnValue(script)
  vi.resetModules()
  // Import the actual shipped IIFE so V8 coverage includes its production source.
  // @ts-expect-error Standalone public script has no TypeScript module declaration.
  await import('../public/chat-widget.js')
  if (!document.getElementById('graphrag-chat-widget-root')) document.dispatchEvent(new Event('DOMContentLoaded'))
  return document.getElementById('graphrag-chat-widget-root')!.shadowRoot!
}
beforeEach(() => { document.body.replaceChildren() })

it('renders untrusted title, answer and source label/type as inert text', async () => {
  const payload = '<img src=x onerror="window.pwn=1">'
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ answer: payload, sources: [{ label: payload, entity_type: payload, relevance_score: .85 }], metadata: { query_id: 'q' } })))
  const root = await boot({ title: payload })
  widget().ask('question')
  await flush()
  expect(root.querySelector('.chat-header span')?.textContent).toBe(payload)
  expect(root.querySelector('.message.assistant')?.textContent).toContain(payload)
  expect(root.querySelector('.source-label')?.textContent).toContain(payload)
  expect(root.querySelector('.source-type')?.textContent).toContain(payload)
  expect(root.querySelector('img')).toBeNull()
  expect(root.querySelector('[onerror]')).toBeNull()
})

it('supports panel controls, keyboard send, resize, loading guard and formatted evidence', async () => {
  vi.useFakeTimers()
  const pending = deferred<ReturnType<typeof response>>()
  const fetcher = vi.fn().mockReturnValueOnce(pending.promise).mockResolvedValue(response({ answer: '', sources: [] }))
  vi.stubGlobal('fetch', fetcher)
  const root = await boot({ theme: 'dark', endpoint: 'https://api.example', orgId: 'org', projectId: 'project' })
  expect(root.querySelector('style')!.textContent).toContain('#1e293b')
  const panel = root.querySelector('.chat-panel')!
  const input = root.querySelector('textarea')!
  fireEvent.click(root.querySelector('.chat-toggle')!)
  await vi.advanceTimersByTimeAsync(300)
  expect(panel).not.toHaveClass('hidden')
  expect(root.activeElement).toBe(input)
  fireEvent.click(root.querySelector('.chat-close')!)
  expect(panel).toHaveClass('hidden')
  widget().toggle()
  widget().close()
  widget().open()
  fireEvent.click(root.querySelector('.chat-send-btn')!)
  expect(fetcher).not.toHaveBeenCalled()
  input.value = 'hello'
  Object.defineProperty(input, 'scrollHeight', { value: 180 })
  fireEvent.input(input)
  expect(input.style.height).toBe('100px')
  fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })
  expect(fetcher).not.toHaveBeenCalled()
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(root.querySelector('.chat-send-btn')).toBeDisabled()
  expect(root.querySelectorAll('.loading-dot')).toHaveLength(3)
  widget().ask('ignored while loading')
  expect(fetcher).toHaveBeenCalledTimes(1)
  pending.resolve(response({ answer: '# 一级\n## 二级\n### 三级\n**粗体** *斜体* `代码`\n```js\nconst x = 1\n```\n- 条目\n1. 顺序\n\n证据[citation:1] & <script>alert(1)</script>', sources: [{ label: '来源', relevance_score: 0 }, { label: '二', entity_type: 'metric' }], metadata: { query_id: 'q1' } }))
  await flush()
  expect(root.querySelector('.message.loading')).toBeNull()
  expect(root.querySelector('.chat-send-btn')).toBeEnabled()
  for (const selector of ['h2', 'h3', 'h4', 'strong', 'em', 'code', 'pre', 'li', 'sup']) expect(root.querySelector(selector)).not.toBeNull()
  expect(root.querySelector('script')).toBeNull()
  expect(root.querySelector('.source-type')?.textContent).toContain('unknown (0%)')
  const toggle = root.querySelector('.sources-toggle')!
  fireEvent.click(toggle)
  expect(root.querySelector('.sources-list')).toHaveClass('open')
  expect(toggle.textContent).toContain('收起')
  fireEvent.click(toggle)
  expect(root.querySelector('.sources-list')).not.toHaveClass('open')
  expect(toggle.textContent).toContain('查看')
  const buttons = root.querySelectorAll('.fb-btn')
  fireEvent.click(buttons[0]); await flush()
  expect(buttons[0]).toHaveClass('active')
  fireEvent.click(buttons[0]); await flush()
  expect(fetcher).toHaveBeenCalledTimes(2)
  fireEvent.click(buttons[1]); await flush()
  fireEvent.click(buttons[1]); await flush()
  expect(buttons[0]).not.toHaveClass('active')
  expect(buttons[1]).toHaveClass('active')
  expect(JSON.parse(fetcher.mock.calls[2][1].body)).toEqual({ query_id: 'q1', rating: 'negative' })
  widget().ask('second'); await flush()
  const first = JSON.parse(fetcher.mock.calls[0][1].body)
  const second = JSON.parse(fetcher.mock.calls[3][1].body)
  expect(second.session_id).toBe(first.session_id)
  expect(fetcher.mock.calls[0][0]).toBe('https://api.example/api/v1/rag/query')
  expect(fetcher.mock.calls[0][1].headers).toEqual({ 'Content-Type': 'application/json', 'X-Org-Id': 'org', 'X-Project-Id': 'project' })
})

it.each(['network', 'detail', 'http', 'invalid-json', 'empty-error'])('recovers after %s request failure', async kind => {
  const fetcher = vi.fn()
  if (kind === 'network') fetcher.mockRejectedValueOnce(new Error('offline'))
  else if (kind === 'empty-error') fetcher.mockRejectedValueOnce({})
  else if (kind === 'invalid-json') fetcher.mockResolvedValueOnce({ ok: false, status: 502, json: async () => { throw new Error('not json') } })
  else fetcher.mockResolvedValueOnce(response(kind === 'detail' ? { detail: '拒绝访问' } : {}, 403))
  fetcher.mockResolvedValue(response({ answer: '恢复成功', sources: null }))
  vi.stubGlobal('fetch', fetcher)
  const root = await boot()
  widget().ask('<b>question</b>'); await flush()
  expect(root.querySelector('.message.user')?.textContent).toBe('<b>question</b>')
  expect(root.querySelector('.message.user b')).toBeNull()
  const expected = kind === 'network' ? 'offline' : kind === 'detail' ? '拒绝访问' : kind === 'empty-error' ? '请求失败' : kind === 'invalid-json' ? 'HTTP 502' : 'HTTP 403'
  expect(root.querySelector('.message.error')?.textContent).toContain(expected)
  expect(root.querySelector('.chat-send-btn')).toBeEnabled()
  widget().ask('retry'); await flush()
  expect(root.querySelector('.message.assistant')?.textContent).toContain('恢复成功')
  expect(fetcher).toHaveBeenCalledTimes(2)
})

it('does not post feedback without a query identifier and supports default bootstrap', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ answer: null, sources: [{ label: 'no id' }] })))
  vi.spyOn(document, 'currentScript', 'get').mockReturnValue(null)
  vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading')
  vi.resetModules()
  // @ts-expect-error Public IIFE intentionally has no module types.
  await import('../public/chat-widget.js')
  expect(document.getElementById('graphrag-chat-widget-root')).toBeNull()
  document.dispatchEvent(new Event('DOMContentLoaded'))
  const root = document.getElementById('graphrag-chat-widget-root')!.shadowRoot!
  expect(root.querySelector('.chat-header span')?.textContent).toBe('AI 助手')
  widget().ask('q'); await flush()
  fireEvent.click(root.querySelector('.fb-btn')!); await flush()
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(vi.mocked(fetch).mock.calls[0][0]).toBe('/api/v1/rag/query')
})
