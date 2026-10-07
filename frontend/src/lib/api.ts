import type { GraphData, SystemStats } from './types'
import type { CatalogResponse, CatalogSummary, LowQualityItem, LineageTrace, QualityReport, CleanupPreview, StorageReport, BackupItem } from './types'

const BASE = '/api/v1'

function getToken(): string | null {
  return localStorage.getItem('access_token')
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(options?.headers as Record<string, string> || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 401 && token) {
    const refreshToken = localStorage.getItem('refresh_token')
    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${BASE}/auth/refresh`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
        if (refreshRes.ok) {
          const data = await refreshRes.json()
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          headers['Authorization'] = `Bearer ${data.access_token}`
          const retryRes = await fetch(`${BASE}${path}`, { ...options, headers })
          if (!retryRes.ok) {
            const err = await retryRes.json().catch(() => ({ detail: retryRes.statusText }))
            throw new Error(err?.detail || err?.error?.message || `HTTP ${retryRes.status}`)
          }
          return retryRes.json()
        }
      } catch { }
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    window.location.href = '/login'
    throw new Error('Session expired')
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err?.detail || err?.error?.message || `HTTP ${res.status}`)
  }
  return res.json()
}

export interface IngestResponse {
  task_id: string; status: string; filename: string;
  file_size_bytes: number; created_at: string;
  estimated_duration_seconds: number; links: { status: string };
}

export interface StatusResponse {
  task_id: string; status: 'pending' | 'running' | 'done' | 'failed';
  stage: string | null;
  progress: { stage_name: string; current_step: number; total_steps: number; details: Record<string, string> } | null;
  result: { document_id?: string; kg_nodes?: number; kg_edges?: number; grounded_entities?: number; entity_types?: number; pages_parsed?: number } | null;
  error: { code: string; message: string } | null;
  created_at: string; updated_at: string; duration_seconds: number | null;
}

export interface RagQueryBudget {
  max_total_candidates?: number
  max_context_tokens?: number
  per_source_caps?: Record<string, number>
  enable_cross_encoder?: boolean
  enable_multi_query?: boolean
  enable_global_mode?: boolean
  rerank_budget_ms?: number
  rerank_max_candidates?: number
  rerank_high_recall_max_candidates?: number
  rerank_max_chars?: number
}

export interface QueryMetadata {
  document_id?: string
  model?: string
  tool_calls?: number
  duration_ms?: number
  retrieval_ms?: number
  retrieval_latency_ms?: number
  generation_ms?: number
  timestamp?: string
  mode?: string
  query_mode?: string
  retrieval_mode?: string
  degraded_mode?: string | null
  rewritten_query?: string | null
  rewrite_reason?: string | null
  session_id?: string | null
  has_citations?: boolean
  has_table?: boolean
  final_context_chunk_ids?: string[]
  final_context_node_ids?: string[]
  pre_rerank_chunk_ids?: string[]
  pre_rerank_node_ids?: string[]
  retrieval_chunk_ids?: string[]
  retrieval_node_ids?: string[]
  path_hit_node_ids?: Record<string, string[]>
  active_recall_paths?: number
  token_usage?: Record<string, number>
  budget?: RagQueryBudget
  runtime?: Record<string, unknown>
  [key: string]: unknown
}

export interface QueryOptions {
  language?: 'en' | 'ch' | 'ja'
  include_sources?: boolean
  max_total_candidates?: number
  max_context_tokens?: number
  enable_cross_encoder?: boolean
  enable_multi_query?: boolean
  enable_global_mode?: boolean
  per_source_caps?: Record<string, number>
}

export interface QueryRequestOptions {
  sessionId?: string
  documentId?: string
  projectId?: string
  orgId?: string
  includeSources?: boolean
  queryOptions?: QueryOptions
}

export interface QueryResponse {
  query: string; answer: string;
  sources: Array<{ node_id: string; entity_type: string; label: string; properties: Record<string, unknown>; page_idx: number | null; bbox_norm: number[] | null; grounding_status: string; relevance_score: number; source?: string }> | null;
  metadata: QueryMetadata;
}

export interface DocumentItem {
  document_id: string; filename: string; status: string;
  kg_nodes: number | null; kg_edges: number | null; pages: number | null;
  indexed_at: string | null; file_size_mb: number | null;
}

export interface HealthResponse {
  status: string; version: string; uptime_seconds: number;
  components: Record<string, string>; stats: Record<string, number>;
}

export function buildQueryRequest(query: string, options: {
  documentId?: string
  sessionId?: string
  projectId?: string
  orgId?: string
  options?: QueryOptions
} = {}) {
  return {
    query,
    document_id: options.documentId,
    session_id: options.sessionId,
    project_id: options.projectId,
    org_id: options.orgId,
    options: {
      language: options.options?.language ?? 'ch',
      include_sources: options.options?.include_sources ?? true,
      max_total_candidates: options.options?.max_total_candidates,
      max_context_tokens: options.options?.max_context_tokens,
      enable_cross_encoder: options.options?.enable_cross_encoder,
      enable_multi_query: options.options?.enable_multi_query,
      enable_global_mode: options.options?.enable_global_mode,
      per_source_caps: options.options?.per_source_caps,
    },
  }
}

export function normalizeQueryResponse(payload: Partial<QueryResponse> & { metadata?: Record<string, unknown> }): QueryResponse {
  const rawMetadata = (payload.metadata ?? {}) as QueryMetadata
  const metadata: QueryMetadata = {
    ...rawMetadata,
    query_mode: rawMetadata.query_mode ?? rawMetadata.retrieval_mode,
    retrieval_ms: rawMetadata.retrieval_ms ?? rawMetadata.retrieval_latency_ms,
    generation_ms: rawMetadata.generation_ms ?? (rawMetadata.runtime?.generation_latency_ms as number | undefined),
  }

  return {
    query: payload.query ?? '',
    answer: payload.answer ?? '',
    sources: Array.isArray(payload.sources) ? payload.sources : [],
    metadata,
  }
}

export const api = {
  ingest: (formData: FormData): Promise<IngestResponse> =>
    fetch(`${BASE}/ingest`, { method: 'POST', body: formData }).then(async r => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }))
        throw new Error(err?.detail || `Upload failed: HTTP ${r.status}`)
      }
      return r.json()
    }),

  getStatus: (taskId: string): Promise<StatusResponse> =>
    request(`/status/${taskId}`),

  ask: async (query: string, documentId?: string, requestOptions: QueryRequestOptions = {}): Promise<QueryResponse> => {
    const payload = buildQueryRequest(query, {
      documentId: requestOptions.documentId ?? documentId,
      sessionId: requestOptions.sessionId,
      projectId: requestOptions.projectId,
      orgId: requestOptions.orgId,
      options: {
        language: requestOptions.queryOptions?.language ?? 'ch',
        include_sources: requestOptions.includeSources ?? true,
        max_total_candidates: requestOptions.queryOptions?.max_total_candidates,
        max_context_tokens: requestOptions.queryOptions?.max_context_tokens,
        enable_cross_encoder: requestOptions.queryOptions?.enable_cross_encoder,
        enable_multi_query: requestOptions.queryOptions?.enable_multi_query,
        enable_global_mode: requestOptions.queryOptions?.enable_global_mode,
        per_source_caps: requestOptions.queryOptions?.per_source_caps,
      },
    })
    const response = await request<QueryResponse>('/rag/query', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    return normalizeQueryResponse(response)
  },

  listDocuments: (): Promise<{ documents: DocumentItem[]; total: number }> =>
    request('/documents'),

  deleteDocument: (docId: string): Promise<{ document_id: string; status: string; deleted_at: string }> =>
    request(`/documents/${docId}`, { method: 'DELETE' }),

  getGraphAll: (): Promise<GraphData> => request('/graph/all'),
  getGraph: (docId: string): Promise<GraphData> => request(`/graph/${docId}`),

  health: (): Promise<HealthResponse> => request('/health'),

  getStats: async (): Promise<SystemStats> => {
    const [healthData, docsData] = await Promise.all([
      api.health(),
      api.listDocuments(),
    ])
    return {
      total_docs: docsData.total,
      total_kg_nodes: healthData.stats.total_kg_nodes ?? 0,
      total_kg_edges: healthData.stats.total_kg_edges ?? 0,
      queries_today: healthData.stats.queries_today ?? 0,
    }
  },

  catalog: (): Promise<CatalogResponse> => request('/catalog'),
  catalogSummary: (): Promise<CatalogSummary> => request('/catalog/summary'),
  catalogLowQuality: (threshold = 0.5): Promise<{ items: LowQualityItem[]; threshold: number }> =>
    request(`/catalog/low-quality?threshold=${threshold}`),

  lineageEntity: (entityId: string): Promise<LineageTrace> =>
    request(`/lineage/entity/${entityId}`),
  lineageAnswer: (queryId: string): Promise<LineageTrace> =>
    request(`/lineage/answer/${queryId}`),

  qualityReport: (): Promise<QualityReport> => request('/system/quality'),

  storageReport: (): Promise<StorageReport> => request('/system/storage'),
  cleanupPreview: (): Promise<{ previews: CleanupPreview[] }> => request('/system/cleanup/preview'),
  listBackups: (): Promise<{ backups: BackupItem[] }> => request('/system/backups'),
  triggerBackup: (): Promise<{ backup_id: string; status: string }> =>
    request('/system/backup', { method: 'POST' }),

  authLoginPage: (): Promise<{ login_url: string }> => request('/auth/login'),
  authLogin: (username: string, password: string, provider = 'local'): Promise<{ access_token: string; refresh_token: string; token_type: string; expires_in: number }> =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password, provider }) }),
  authMe: (): Promise<{ user_id: string; username: string; email: string; display_name: string; roles: string[]; department: string | null; last_login: string | null }> =>
    request('/auth/me'),
  authRefresh: (refreshToken: string): Promise<{ access_token: string; refresh_token: string; expires_in: number; token_type: string }> =>
    request('/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: refreshToken }) }),
  authLogout: (): Promise<void> => { localStorage.removeItem('access_token'); localStorage.removeItem('refresh_token'); return request('/auth/logout', { method: 'POST' }) },

  listWebhooks: (): Promise<any[]> => request('/webhooks'),
  createWebhook: (data: { url: string; events: string[]; secret?: string }): Promise<any> =>
    request('/webhooks', { method: 'POST', body: JSON.stringify(data) }),
  deleteWebhook: (id: string): Promise<void> => request(`/webhooks/${id}`, { method: 'DELETE' }),
  testWebhook: (id: string): Promise<any> => request(`/webhooks/${id}/test`, { method: 'POST' }),

  listApiKeys: (): Promise<any[]> => request('/api-keys'),
  createApiKey: (name: string, scopes: string[], rate_limit_per_minute = 60): Promise<{ key_id: string; name: string; full_key: string; scopes: string[] }> =>
    request('/api-keys', { method: 'POST', body: JSON.stringify({ name, scopes, rate_limit_per_minute }) }),
  revokeApiKey: (id: string): Promise<void> => request(`/api-keys/${id}/revoke`, { method: 'POST' }),
  rotateApiKey: (id: string): Promise<{ full_key: string }> => request(`/api-keys/${id}/rotate`, { method: 'POST' }),

  queryAudit: (params: Record<string, string>): Promise<{ audit_logs: any[]; total: number }> => {
    const qs = new URLSearchParams(params).toString()
    return request(`/audit${qs ? '?' + qs : ''}`)
  },
  exportAudit: (event?: string, userId?: string): Promise<string> => {
    const params: Record<string, string> = {}
    if (event) params.event = event
    if (userId) params.user_id = userId
    const qs = new URLSearchParams(params).toString()
    return request(`/audit/export${qs ? '?' + qs : ''}`)
  },

  botConfig: (): Promise<any> => request('/bot/config'),

  listOrgs: (): Promise<{ orgs: any[] }> => request('/orgs'),
  createOrg: (name: string, slug: string): Promise<{ org: any }> =>
    request('/orgs', { method: 'POST', body: JSON.stringify({ name, slug }) }),
  getOrg: (orgId: string): Promise<{ org: any }> => request(`/orgs/${orgId}`),
  updateOrg: (orgId: string, body: Record<string, unknown>): Promise<{ org: any }> =>
    request(`/orgs/${orgId}`, { method: 'PUT', body: JSON.stringify(body) }),
  listProjects: (orgId: string): Promise<{ projects: any[] }> => request(`/orgs/${orgId}/projects`),
  createProject: (orgId: string, name: string, description = ''): Promise<{ project: any }> =>
    request(`/orgs/${orgId}/projects`, { method: 'POST', body: JSON.stringify({ name, description }) }),
  archiveProject: (orgId: string, projectId: string): Promise<any> =>
    request(`/orgs/${orgId}/projects/${projectId}/archive`, { method: 'POST' }),
  listMembers: (orgId: string): Promise<{ members: any[] }> => request(`/orgs/${orgId}/members`),
  inviteMember: (orgId: string, userId: string, role: string): Promise<{ member: any }> =>
    request(`/orgs/${orgId}/members`, { method: 'POST', body: JSON.stringify({ user_id: userId, role }) }),
  updateMemberRole: (orgId: string, userId: string, role: string): Promise<{ member: any }> =>
    request(`/orgs/${orgId}/members/${userId}/role`, { method: 'PUT', body: JSON.stringify({ role }) }),
  removeMember: (orgId: string, userId: string): Promise<any> =>
    request(`/orgs/${orgId}/members/${userId}`, { method: 'DELETE' }),
}
