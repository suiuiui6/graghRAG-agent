import type React from 'react'
import {
  Building2, Users, GitBranch, Gauge, Milestone, Package,
  AlertTriangle, ScrollText, Building, Clock,
} from 'lucide-react'

export const TYPE_COLORS: Record<string, string> = {
  project_metadata: '#3b82f6',
  person_role: '#8b5cf6',
  process_step: '#22c55e',
  metric: '#eab308',
  milestone: '#f97316',
  deliverable: '#06b6d4',
  risk_item: '#ef4444',
  regulation_ref: '#ec4899',
  department: '#14b8a6',
  timeline_event: '#94a3b8',
}

export const TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  project_metadata: Building2,
  person_role: Users,
  process_step: GitBranch,
  metric: Gauge,
  milestone: Milestone,
  deliverable: Package,
  risk_item: AlertTriangle,
  regulation_ref: ScrollText,
  department: Building,
  timeline_event: Clock,
}

export const ENTITY_TYPES = [
  { type: 'person_role', count: 76 },
  { type: 'risk_item', count: 48 },
  { type: 'process_step', count: 40 },
  { type: 'metric', count: 35 },
  { type: 'project_metadata', count: 31 },
  { type: 'milestone', count: 23 },
  { type: 'deliverable', count: 18 },
  { type: 'timeline_event', count: 16 },
  { type: 'department', count: 13 },
  { type: 'regulation_ref', count: 10 },
]

export const SOURCE_TYPE_LABELS: Record<string, string> = {
  vector: '向量检索',
  kg: '知识图谱',
  bm25: 'BM25',
  table: '表格',
  multi_query: '多查询',
}

export const SOURCE_TYPE_COLORS: Record<string, string> = {
  vector: '#3b82f6',
  kg: '#22c55e',
  bm25: '#eab308',
  table: '#f97316',
  multi_query: '#8b5cf6',
}

export const QUERY_LOW_EVIDENCE_SCORE = 0.35

export const SUPPORTED_FORMATS = ['PDF', 'DOCX', 'PPTX', 'XLSX', 'PNG', 'JPG', 'EPUB', 'HTML']

export const PIPELINE_STAGES = [
  { id: 1, name: 'MinerU 文档解析', desc: 'PDF → Markdown + JSON' },
  { id: 2, name: 'Format Bridge', desc: 'Section 分段 + PositionMap' },
  { id: 3, name: 'LangExtract 实体抽取', desc: 'DeepSeek-chat 结构化提取' },
  { id: 4, name: 'Grounding 溯源解析', desc: 'char_interval → bbox + page' },
  { id: 5, name: 'KG 知识图谱构建', desc: 'nodes.json + edges.json' },
]

export const NAV_ITEMS = [
  { path: '/upload', icon: '\u{1F4E4}', label: '上传文档' },
  { path: '/documents', icon: '\u{1F4DA}', label: '文档管理' },
  { path: '/query', icon: '\u{1F4AC}', label: '知识问答' },
  { path: '/graph', icon: '\u{1F52E}', label: '图谱可视化' },
  { path: '/catalog', icon: '\u{1F4C8}', label: '数据目录' },
  { path: '/quality', icon: '✅', label: '质量看板' },
  { path: '/webhooks', icon: '\u{1F517}', label: 'Webhook' },
  { path: '/api-keys', icon: '\u{1F511}', label: 'API Key' },
  { path: '/audit', icon: '\u{1F4CB}', label: '审计日志' },
  { path: '/settings/org', icon: '\u{1F3E2}', label: '组织管理' },
  { path: '/health', icon: '\u{1F4CA}', label: '系统状态' },
]

