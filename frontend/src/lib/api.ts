const BASE = '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
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

export interface QueryResponse {
  query: string; answer: string;
  sources: Array<{ node_id: string; entity_type: string; label: string; properties: Record<string, unknown>; page_idx: number | null; bbox_norm: number[] | null; grounding_status: string; relevance_score: number }> | null;
  metadata: { document_id: string; model: string; tool_calls: number; duration_ms: number; timestamp: string };
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

export interface DemoEntity {
  id: string
  type: string
  label: string
  grounding_status: string
}

export interface DemoRelation {
  source: string
  target: string
  type: string
}

export interface DemoSource {
  document_id: string
  span: string
  start: number
  end?: number
  page: number | null
  entity_ids: string[]
}

export type DemoMode = 'offline' | 'provider' | 'not-run'

export interface DemoResponse {
  mode: DemoMode
  document_id: string
  document: { id: string; title: string; text: string }
  entities: DemoEntity[]
  relations: DemoRelation[]
  questions: string[]
  answer: string
  sources: DemoSource[]
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

  ask: (query: string, documentId?: string): Promise<QueryResponse> =>
    request('/query', {
      method: 'POST',
      body: JSON.stringify({ query, document_id: documentId, options: { include_sources: true } }),
    }),

  listDocuments: (): Promise<{ documents: DocumentItem[]; total: number }> =>
    request('/documents'),

  deleteDocument: (docId: string): Promise<{ document_id: string; status: string; deleted_at: string }> =>
    request(`/documents/${docId}`, { method: 'DELETE' }),

  getGraphAll: (): Promise<any> => request('/graph/all'),
  getGraph: (docId: string): Promise<any> => request(`/graph/${docId}`),

  health: (): Promise<HealthResponse> => request('/health'),

  getDemoSample: (): Promise<DemoResponse> => request('/demo/sample'),
}
