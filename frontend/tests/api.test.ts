import { beforeEach, expect, it, vi } from 'vitest'
import { api, buildQueryRequest, normalizeQueryResponse } from '../src/lib/api'
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json' } })
beforeEach(() => localStorage.clear())
it('preserves scoped query options and normalizes legacy metadata without dropping evidence', async () => {
  const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response({ answer: '答案', sources: null, metadata: { retrieval_mode: 'hybrid', retrieval_latency_ms: 20, runtime: { generation_latency_ms: 30 } } })))
  vi.stubGlobal('fetch', fetcher)
  const result = await api.ask('问题', 'old', { documentId: 'doc', sessionId: 'session', projectId: 'project', orgId: 'org', includeSources: false, queryOptions: { language: 'ja', max_context_tokens: 100, max_total_candidates: 5, enable_cross_encoder: false, enable_multi_query: true, enable_global_mode: false, per_source_caps: { kg: 2 } } })
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toMatchObject({ document_id: 'doc', session_id: 'session', project_id: 'project', org_id: 'org', options: { language: 'ja', include_sources: false, max_total_candidates: 5 } })
  expect(result).toMatchObject({ query: '', answer: '答案', sources: [], metadata: { query_mode: 'hybrid', retrieval_ms: 20, generation_ms: 30 } })
  expect(buildQueryRequest('default').options).toMatchObject({ language: 'ch', include_sources: true })
  expect(normalizeQueryResponse({ sources: [] }).answer).toBe('')
  expect(normalizeQueryResponse({ query: 'q', answer: 'a', sources: [], metadata: { query_mode: 'kg', retrieval_ms: 0, generation_ms: 0 } }).metadata).toMatchObject({ query_mode: 'kg', retrieval_ms: 0, generation_ms: 0 })
  await api.ask('default')
})
it('rotates expired bearer tokens and retries the original request', async () => {
  localStorage.setItem('access_token', 'old'); localStorage.setItem('refresh_token', 'refresh')
  const f = vi.fn().mockResolvedValueOnce(response({}, 401)).mockResolvedValueOnce(response({ access_token: 'new', refresh_token: 'next' })).mockResolvedValueOnce(response({ user_id: 'u' }))
  vi.stubGlobal('fetch', f)
  expect(await api.authMe()).toEqual({ user_id: 'u' })
  expect(localStorage.getItem('access_token')).toBe('new')
  expect(JSON.parse(f.mock.calls[1][1].body)).toEqual({ refresh_token: 'refresh' })
  expect(f.mock.calls[2][1].headers.Authorization).toBe('Bearer new')
})
it.each(['none', 'refresh-fails', 'network', 'retry-detail', 'retry-nested', 'retry-status', 'retry-invalid'])('clears both tokens when refresh cannot restore a session: %s', async mode => {
  localStorage.setItem('access_token', 'old')
  if (mode !== 'none') localStorage.setItem('refresh_token', 'refresh')
  const f = vi.fn().mockResolvedValueOnce(response({}, 401))
  if (mode === 'network') f.mockRejectedValueOnce(new Error('offline'))
  else if (mode === 'refresh-fails') f.mockResolvedValueOnce(response({}, 403))
  else if (mode.startsWith('retry')) {
    f.mockResolvedValueOnce(response({ access_token: 'new', refresh_token: 'next' }))
    f.mockResolvedValueOnce(mode === 'retry-invalid' ? new Response('invalid', { status: 401, statusText: 'Denied' }) : response(mode === 'retry-detail' ? { detail: 'denied' } : mode === 'retry-nested' ? { error: { message: 'nested' } } : {}, 401))
  }
  vi.stubGlobal('fetch', f)
  await expect(api.authMe()).rejects.toThrow('Session expired')
  expect(localStorage.getItem('access_token')).toBeNull(); expect(localStorage.getItem('refresh_token')).toBeNull()
})
it.each([{ detail: 'detail' }, { error: { message: 'nested' } }, {}, null])('surfaces API error envelopes %j', async data => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(data, 500)))
  await expect(api.health()).rejects.toThrow(data?.detail || data?.error?.message || 'HTTP 500')
})
it('handles invalid JSON errors and multipart upload success/failure', async () => {
  const f = vi.fn().mockResolvedValueOnce(new Response('bad', { status: 502, statusText: 'Gateway' })).mockResolvedValueOnce(response({ task_id: 't' })).mockResolvedValueOnce(response({ detail: 'invalid file' }, 400)).mockResolvedValueOnce(response({}, 500)).mockResolvedValueOnce(new Response('bad', { status: 502, statusText: 'Gateway' }))
  vi.stubGlobal('fetch', f)
  await expect(api.health()).rejects.toThrow('Gateway')
  const fd = new FormData(); expect(await api.ingest(fd)).toEqual({ task_id: 't' }); expect(f.mock.calls[1][1].body).toBe(fd)
  await expect(api.ingest(fd)).rejects.toThrow('invalid file'); await expect(api.ingest(fd)).rejects.toThrow('Upload failed: HTTP 500'); await expect(api.ingest(fd)).rejects.toThrow('Gateway')
})
it('all REST adapters retain methods, identifiers and optional parameters', async () => {
  const f = vi.fn().mockImplementation(() => Promise.resolve(response({}))); vi.stubGlobal('fetch', f)
  const cases: [() => unknown, string, string?][] = [
    [() => api.getStatus('t'), '/status/t'], [() => api.listDocuments(), '/documents'], [() => api.deleteDocument('d'), '/documents/d', 'DELETE'], [() => api.getGraphAll(), '/graph/all'], [() => api.getGraph('d'), '/graph/d'],
    [() => api.catalog(), '/catalog'], [() => api.catalogSummary(), '/catalog/summary'], [() => api.catalogLowQuality(), '/catalog/low-quality?threshold=0.5'], [() => api.catalogLowQuality(.2), '/catalog/low-quality?threshold=0.2'], [() => api.lineageEntity('e'), '/lineage/entity/e'], [() => api.lineageAnswer('q'), '/lineage/answer/q'],
    [() => api.qualityReport(), '/system/quality'], [() => api.storageReport(), '/system/storage'], [() => api.cleanupPreview(), '/system/cleanup/preview'], [() => api.listBackups(), '/system/backups'], [() => api.triggerBackup(), '/system/backup', 'POST'],
    [() => api.authLoginPage(), '/auth/login'], [() => api.authLogin('u', 'p'), '/auth/login', 'POST'], [() => api.authLogin('u', 'p', 'sso'), '/auth/login', 'POST'], [() => api.authRefresh('r'), '/auth/refresh', 'POST'], [() => api.authLogout(), '/auth/logout', 'POST'],
    [() => api.listWebhooks(), '/webhooks'], [() => api.createWebhook({ url: 'x', events: [] }), '/webhooks', 'POST'], [() => api.deleteWebhook('w'), '/webhooks/w', 'DELETE'], [() => api.testWebhook('w'), '/webhooks/w/test', 'POST'],
    [() => api.listApiKeys(), '/api-keys'], [() => api.createApiKey('n', []), '/api-keys', 'POST'], [() => api.createApiKey('n', [], 5), '/api-keys', 'POST'], [() => api.revokeApiKey('k'), '/api-keys/k/revoke', 'POST'], [() => api.rotateApiKey('k'), '/api-keys/k/rotate', 'POST'],
    [() => api.queryAudit({}), '/audit'], [() => api.queryAudit({ event: 'a b' }), '/audit?event=a+b'], [() => api.exportAudit(), '/audit/export'], [() => api.exportAudit('e', 'u'), '/audit/export?event=e&user_id=u'], [() => api.botConfig(), '/bot/config'],
    [() => api.listOrgs(), '/orgs'], [() => api.createOrg('n', 's'), '/orgs', 'POST'], [() => api.getOrg('o'), '/orgs/o'], [() => api.updateOrg('o', { name: 'n' }), '/orgs/o', 'PUT'], [() => api.listProjects('o'), '/orgs/o/projects'], [() => api.createProject('o', 'n'), '/orgs/o/projects', 'POST'], [() => api.createProject('o', 'n', 'd'), '/orgs/o/projects', 'POST'], [() => api.archiveProject('o', 'p'), '/orgs/o/projects/p/archive', 'POST'], [() => api.listMembers('o'), '/orgs/o/members'], [() => api.inviteMember('o', 'u', 'r'), '/orgs/o/members', 'POST'], [() => api.updateMemberRole('o', 'u', 'r'), '/orgs/o/members/u/role', 'PUT'], [() => api.removeMember('o', 'u'), '/orgs/o/members/u', 'DELETE'],
  ]
  for (const [run, path, method] of cases) { await run(); const call = f.mock.calls.at(-1)!; expect(call[0]).toBe('/api/v1' + path); expect(call[1]?.method || 'GET').toBe(method || 'GET') }
})
it.each([{}, { total_kg_nodes: 2, total_kg_edges: 3, queries_today: 4 }])('aggregates live health and document counts %j', async stats => {
  vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(response(url.endsWith('health') ? { stats } : { total: 7 }))))
  expect(await api.getStats()).toEqual({ total_docs: 7, total_kg_nodes: stats.total_kg_nodes ?? 0, total_kg_edges: stats.total_kg_edges ?? 0, queries_today: stats.queries_today ?? 0 })
})
