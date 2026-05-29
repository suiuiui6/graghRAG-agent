export const TYPE_COLORS: Record<string, string> = {
  paper_metadata: '#3b82f6', section_header: '#22c55e', model_component: '#a855f7',
  metric: '#eab308', dataset: '#f97316', method: '#ec4899',
  definition: '#8b5cf6', equation: '#14b8a6', reference: '#94a3b8', claim: '#ef4444',
}

export const TYPE_ICONS: Record<string, string> = {
  paper_metadata: '\u{1F4CB}', section_header: '\u{1F4D1}', model_component: '\u{1F9E9}',
  metric: '\u{1F4CA}', dataset: '\u{1F4BE}', method: '\u{1F527}',
  definition: '\u{1F4D6}', equation: '∑', reference: '\u{1F4CE}', claim: '\u{1F4A1}',
}

export const ENTITY_TYPES = [
  { type: 'reference', count: 76 }, { type: 'claim', count: 48 },
  { type: 'model_component', count: 40 }, { type: 'metric', count: 35 },
  { type: 'paper_metadata', count: 31 }, { type: 'method', count: 23 },
  { type: 'section_header', count: 18 }, { type: 'equation', count: 16 },
  { type: 'definition', count: 13 }, { type: 'dataset', count: 10 },
]

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
  { path: '/health', icon: '\u{1F4CA}', label: '系统状态' },
]
