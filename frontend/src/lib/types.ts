// Shared entity types used across components

export interface GraphNode {
  id: string
  label: string
  entity_type: string
  color?: string
  borderColor?: string
  size?: number
  borderWidth?: number
  page_idx?: number | null
  bbox_norm?: number[] | null
  grounding_status?: string
  properties?: Record<string, unknown>
  neighbors?: NeighborNode[]
}

export interface NeighborNode {
  node_id: string
  label: string
  entity_type: string
  relation: string
}

export interface GraphEdge {
  id: string
  from: string
  to: string
  color?: string
  width?: number
  relation?: string
}

export interface GraphStats {
  total_nodes: number
  total_edges: number
  grounded_nodes: number
  entity_types: Record<string, number>
}

export interface GraphDocument {
  document_id: string
  filename: string
  kg_nodes: number
  kg_edges: number
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: GraphStats
  documents: GraphDocument[]
}

/** Matches QueryResponse.sources array item */
export interface SourceItem {
  node_id: string
  entity_type: string
  label: string
  properties: Record<string, unknown>
  page_idx: number | null
  bbox_norm: number[] | null
  grounding_status: string
  relevance_score: number
  /** Retrieval source: "vector" | "kg" | "bm25" | "table" | "multi_query" */
  source?: string
}

export interface SourceItemWithResolvedSource extends SourceItem {
  resolved_source?: string
}

/** Derived from /api/v1/health stats + document count */
export interface SystemStats {
  total_docs: number
  total_kg_nodes: number
  total_kg_edges: number
  queries_today: number
}

// ── Phase 2 Types ─────────────────────────────────────────────────────

export interface CatalogSummary {
  total_documents: number
  total_entities: number
  total_edges: number
  total_chunks: number
  total_conversations: number
  total_feedback: number
  domain_terms: number
  by_entity_type: Record<string, number>
  by_project: Record<string, { documents: number; entities: number }>
}

export interface DomainDictStats {
  total_terms: number
  by_category: Record<string, number>
  terms: string[]
}

export interface ConversationStats {
  total_sessions: number
  active_sessions: number
  avg_turns_per_session: number
  max_turns_session: number
}

export interface FeedbackStats {
  total: number
  positive: number
  negative: number
  positive_ratio: number
}

export interface QualityMetrics {
  grounded_rate: number
  entities_without_edges: number
  orphan_entities: number
  low_quality_docs: Array<{ doc_id: string; issue: string; value: number }>
}

export interface CatalogResponse {
  summary: CatalogSummary
  domain_dict: DomainDictStats | null
  conversations: ConversationStats | null
  feedback: FeedbackStats | null
  retrieval: Record<string, unknown> | null
  quality_metrics: QualityMetrics | null
  last_updated: string
}

export interface LowQualityItem {
  doc_id: string
  issue: string
  value: number
  entities_total: number
  entities_grounded: number
}

export interface LineageNode {
  node_id: string
  node_type: string
  label: string
  metadata: Record<string, unknown>
  parent_ids: string[]
  child_ids: string[]
  session_id?: string
  kg_version?: number
  domain_terms?: string[]
  feedback_id?: string
  timestamp?: string
}

export interface LineageTrace {
  entity_id: string
  trace: LineageNode[]
  direction: string
}

export interface QualityReport {
  extraction_quality: {
    grounding_rate: number
    confidence_avg: number
    extraction_error_rate: number
    total_entities: number
    grounded_entities: number
  }
  retrieval_quality: Record<string, unknown>
  feedback_quality: {
    total: number
    positive: number
    negative: number
    positive_ratio: number
    negative_clusters: string[]
  }
  data_freshness: {
    days_since_last_ingest: number
    stale_entities: number
    conversation_active_today: number
  }
  overall_score: number
  alerts: Array<{ severity: string; metric: string; value: number; threshold: number }>
  generated_at: string
}

export interface CleanupPreview {
  category: string
  policy: Record<string, unknown>
  items_to_remove: number
  items_sample: string[]
}

export interface StorageReport {
  directories: Record<string, { size_bytes: number; size_mb: number; files: number }>
  total_size_bytes: number
  last_checked: string
}

export interface BackupItem {
  backup_id: string
  size_mb: number
  created_at: string
}
