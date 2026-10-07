import { buildQueryRequest, normalizeQueryResponse, type QueryOptions } from './api'

const options: QueryOptions = {
  include_sources: true,
  enable_cross_encoder: false,
  max_total_candidates: 6,
}

const requestPayload = buildQueryRequest('W4S1 是什么？', {
  documentId: 'doc-1',
  sessionId: 'sess-1',
  projectId: 'proj-1',
  orgId: 'org-1',
  options,
})

if (requestPayload.query !== 'W4S1 是什么？') {
  throw new Error('query should be preserved')
}

if (requestPayload.document_id !== 'doc-1') {
  throw new Error('document_id should be forwarded')
}

if (requestPayload.session_id !== 'sess-1') {
  throw new Error('session_id should be included for rag conversations')
}

if (requestPayload.project_id !== 'proj-1' || requestPayload.org_id !== 'org-1') {
  throw new Error('enterprise metadata should be included in the request body')
}

if (requestPayload.options.include_sources !== true || requestPayload.options.max_total_candidates !== 6) {
  throw new Error('query options should be merged into the request payload')
}

const normalized = normalizeQueryResponse({
  query: '它的弃电量是多少？',
  answer: '来自上下文的回答',
  sources: [],
  metadata: {
    document_id: 'doc-1',
    duration_ms: 812,
    rewritten_query: 'W4S1 的弃电量是多少？',
    rewrite_reason: 'coreference_resolution',
    degraded_mode: 'candidate_trimmed',
    final_context_chunk_ids: ['chunk-a', 'chunk-b'],
    pre_rerank_chunk_ids: ['chunk-a', 'chunk-b', 'chunk-c'],
    retrieval_mode: 'hybrid',
    retrieval_latency_ms: 224,
    runtime: {
      generation_latency_ms: 501,
    },
  },
})

if (normalized.metadata.rewritten_query !== 'W4S1 的弃电量是多少？') {
  throw new Error('rewritten_query should be preserved')
}

if (normalized.metadata.degraded_mode !== 'candidate_trimmed') {
  throw new Error('degraded_mode should be preserved')
}

if (normalized.metadata.final_context_chunk_ids?.length !== 2) {
  throw new Error('final_context_chunk_ids should be preserved')
}

if ((normalized.metadata.runtime?.generation_latency_ms as number | undefined) !== 501) {
  throw new Error('runtime metadata should survive normalization')
}
