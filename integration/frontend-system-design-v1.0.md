# 多模态 RAG 问答系统 — 前端系统设计 v1.0

> **版本**: v1.0 | **日期**: 2026-05-24 | **角色**: 前端产品设计
>
> 基于后端 API 规范 (`backend-api-architecture-v1.0.md`)，
> 设计可运行的 Web 原型系统。

---

## 目录

1. [系统整体架构](#1-系统整体架构)
2. [UI 布局风格](#2-ui-布局风格)
3. [响应式适配方案](#3-响应式适配方案)
4. [完整页面清单](#4-完整页面清单)
5. [详细交互逻辑](#5-详细交互逻辑)
6. [技术选型与组件树](#6-技术选型与组件树)
7. [数据流与状态管理](#7-数据流与状态管理)
8. [实施路线图](#8-实施路线图)

---

## 1. 系统整体架构

### 1.1 前端架构分层

```
┌──────────────────────────────────────────────────────────────────┐
│                       PRESENTATION LAYER                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐    │
│  │ Upload   │ │ Document │ │ KG Query │ │ KG Visualization │    │
│  │ Page     │ │ List     │ │ Page     │ │ Canvas           │    │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘    │
│       │             │            │                │              │
├───────┴─────────────┴────────────┴────────────────┴──────────────┤
│                       APPLICATION LAYER                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    Zustand Store                          │    │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────┐   │    │
│  │  │useUpload │ │useDocsStore│ │useQuery  │ │useKGStore │   │    │
│  │  └──────────┘ └───────────┘ └──────────┘ └───────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    React Router                           │    │
│  │   /upload  |  /documents  |  /query/:docId  |  /graph    │    │
│  └──────────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────────┤
│                         DATA LAYER                               │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    API Client (axios/fetch)               │    │
│  │  POST /api/v1/ingest   GET /api/v1/status/{id}            │    │
│  │  POST /api/v1/query    GET /api/v1/documents              │    │
│  │  GET  /api/v1/health   DELETE /api/v1/documents/{id}      │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 路由结构

```
/                        →  重定向到 /upload
/upload                  →  文档上传页 (主入口)
/documents               →  已索引文档列表
/query/:documentId       →  KG 问答页 (指定文档)
/query                   →  KG 问答页 (全局)
/graph/:documentId       →  KG 可视化大屏
```

---

## 2. UI 布局风格

### 2.1 设计语言

| 维度 | 选择 | 说明 |
|---|---|---|
| **风格** | Dark-first, clean dashboard | 深色主题，数据密集型产品定位 |
| **主色调** | `#0f172a` (Slate 900) 背景 | 专业感，低视觉疲劳 |
| **强调色** | `#38bdf8` (Sky 400) | 交互元素、选中态 |
| **成功色** | `#4ade80` (Green 400) | 完成状态、已接地标识 |
| **警告色** | `#facc15` (Yellow 400) | 进行中、未接地 |
| **错误色** | `#f87171` (Red 400) | 失败、删除 |
| **字体** | `Inter` (body) + `JetBrains Mono` (code/data) | 现代数据产品标准 |
| **圆角** | `8px` (card), `12px` (modal), `6px` (button) | 柔和但不幼稚 |
| **间距** | 4px 基础栅格 (Tailwind spacing) | 视觉节奏统一 |
| **图表** | Entity Type 10 色映射 (继承自 visualizer.html) | 跨页面颜色一致性 |

### 2.2 全局布局骨架

```
┌──────────────────────────────────────────────────────────────┐
│  SIDEBAR (240px)              │         MAIN CONTENT         │
│                               │                              │
│  ┌────────────────┐           │  ┌────────────────────────┐  │
│  │  ⚡ RAG System  │  Logo     │  │  Page Header           │  │
│  ├────────────────┤           │  │  Breadcrumb + Actions   │  │
│  │  📤 Upload     │  Nav1     │  ├────────────────────────┤  │
│  │  📄 Documents  │  Nav2     │  │                        │  │
│  │  💬 Query      │  Nav3     │  │  Page Content          │  │
│  │  🔮 Graph      │  Nav4     │  │  (router-outlet)       │  │
│  ├────────────────┤           │  │                        │  │
│  │  📊 Stats      │  Footer   │  │                        │  │
│  │  1 doc · 310 N │           │  │                        │  │
│  └────────────────┘           │  └────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 主题变量定义

```css
:root {
  /* Backgrounds */
  --bg-root:     #0f172a;
  --bg-surface:  #1e293b;
  --bg-elevated: #334155;
  --bg-hover:    rgba(56,189,248,0.08);

  /* Text */
  --text-primary:   #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted:     #64748b;

  /* Accent */
  --accent:       #38bdf8;
  --accent-hover: #7dd3fc;
  --accent-muted: rgba(56,189,248,0.15);

  /* Semantic */
  --success: #4ade80;
  --warning: #facc15;
  --danger:  #f87171;
  --info:    #818cf8;

  /* Borders */
  --border:        #334155;
  --border-hover:  #475569;

  /* Spacing */
  --radius-sm: 6px;
  --radius:    8px;
  --radius-lg: 12px;

  /* Shadows */
  --shadow: 0 4px 12px rgba(0,0,0,0.3);

  /* Entity Type Colors (consistent with visualizer.html) */
  --color-paper_metadata:  #38bdf8;
  --color-section_header:  #4ade80;
  --color-model_component: #c084fc;
  --color-metric:          #facc15;
  --color-dataset:         #fb923c;
  --color-method:          #f472b6;
  --color-definition:      #a78bfa;
  --color-equation:        #2dd4bf;
  --color-reference:       #94a3b8;
  --color-claim:           #f87171;
}
```

---

## 3. 响应式适配方案

### 3.1 断点定义

| 断点 | 宽度 | 布局策略 |
|---|---|---|
| **Desktop** | ≥ 1280px | Sidebar (240px) + Content (fluid) |
| **Laptop** | 1024-1279px | Sidebar (200px) + Content (fluid) |
| **Tablet** | 768-1023px | Sidebar 折叠为汉堡菜单 (overlay) |
| **Mobile** | < 768px | 单列布局，底部 Tab 导航 |

### 3.2 各页面适配规则

| 页面 | Desktop | Tablet | Mobile |
|---|---|---|---|
| Upload | 居中卡片 (max-w-2xl) + 拖拽区 | 同 Desktop | 全宽拖拽区 + 底部按钮 |
| Documents | 表格 (6 列) | 表格 (4 列, 隐藏 bbox/时间) | 卡片列表 |
| Query | 左输入 (40%) + 右结果 (60%) | 上下 Stack | 全屏对话式 |
| Graph | 全屏 Canvas + 右侧面板 | 全屏 Canvas (面板 overlay) | 全屏 Canvas (底部面板) |

### 3.3 移动端底部导航

```
┌────────────┬────────────┬────────────┬────────────┐
│   📤       │   📄       │   💬       │   🔮       │
│  Upload    │ Documents  │   Query    │   Graph    │
└────────────┴────────────┴────────────┴────────────┘
```

---

## 4. 完整页面清单

### 4.1 页面一览

| # | 页面 | 路由 | 核心功能 |
|---|---|---|---|
| P1 | **文档上传页** | `/upload` | 拖拽上传、格式校验、Pipeline 动画 |
| P2 | **文档列表页** | `/documents` | 已索引文档表格、状态筛选、删除 |
| P3 | **KG 问答页** | `/query/:docId` | 对话式 QA、答案溯源、source 高亮 |
| P4 | **KG 可视化大屏** | `/graph/:docId` | 力导向图、节点筛选、PDF 溯源 |
| P5 | **系统状态页** | `/health` | API 连通性、KG 统计、任务队列 |

### 4.2 页面详情

---

#### P1: 文档上传页 `/upload`

**布局**: 居中单列卡片 (max-w-2xl)

**组件树**:
```
UploadPage
├── UploadZone (拖拽区域)
│   ├── FileDropArea (拖拽/点击上传)
│   ├── FormatHint (格式支持提示: PDF/DOCX/PPTX/...)
│   └── FilePreview (上传后: 文件名 + 大小 + 图标)
├── ConfigPanel (参数配置, 折叠)
│   ├── LanguageSelect (ch/en/ja)
│   ├── OcrToggle (扫描件开关)
│   ├── FormulaToggle (公式识别)
│   ├── TableToggle (表格识别)
│   └── ModelSelect (pipeline/vlm)
├── PipelineProgress (5 阶段进度条)
│   ├── StageIndicator × 5 (MinerU→Bridge→Extraction→Grounding→KG)
│   └── ElapsedTimer
└── ResultCard (完成后的摘要)
    ├── StatGrid (Nodes / Edges / Entities / Types)
    └── ActionButtons (去问答 / 去可视化)
```

**交互**:
1. 用户拖拽文件到 UploadZone → 显示 FilePreview
2. 点击 "Start Indexing" 按钮
3. PipelineProgress 实时更新 (轮询 `GET /status/{taskId}` 每 2s)
4. 完成后 ResultCard 弹出 + 跳转按钮

---

#### P2: 文档列表页 `/documents`

**布局**: 全宽表格

**组件树**:
```
DocumentsPage
├── PageHeader (标题 + 总数)
├── FilterBar
│   ├── StatusFilter (All / Indexed / Indexing / Failed)
│   └── SearchInput (文件名搜索)
├── DocumentTable
│   ├── Column: Filename (带格式图标)
│   ├── Column: Status (Badge: 绿色=done, 黄色=running, 红色=failed)
│   ├── Column: KG Stats (N Nodes / M Edges)
│   ├── Column: Pages
│   ├── Column: Indexed At (相对时间)
│   └── Column: Actions (Query / Graph / Delete)
└── EmptyState (暂无文档时: 插画 + CTA 按钮去上传)
```

---

#### P3: KG 问答页 `/query/:docId`

**布局**: 左右分栏 (Desktop) / 上下 Stack (Mobile)

**组件树**:
```
QueryPage
├── LeftPanel (40%)
│   ├── DocumentSelector (下拉选择已索引文档)
│   ├── ChatHistory (对话气泡列表)
│   │   ├── UserBubble (用户问题)
│   │   └── AnswerBubble (AI 答案 + SourceChips)
│   ├── QueryInput (底部固定)
│   │   ├── TextArea (自动增高)
│   │   ├── OptionChips (temperature / language)
│   │   └── SendButton
│   └── SuggestedQueries (快捷问题, 首次加载)
└── RightPanel (60%)
    ├── AnswerDetail (选中对话的完整答案)
    │   ├── MarkdownRenderer (表格/列表/公式)
    │   └── SourceCard[] (每个引用的 KG node)
    └── SourcePreview (点击 source → 高亮对应 node)
        ├── NodeId + EntityType Badge
        ├── Properties Table
        ├── PageIdx + Bbox 标注
        └── RelatedEntities (邻居节点预览)
```

**交互**:
1. 选择文档 → 加载 suggested queries
2. 输入问题 → Enter 发送 → AnswerBubble 出现 (流式?)
3. 答案中 node ID 可点击 → 右侧 SourcePreview 定位
4. SourceCard 可点击 → 跳转到 Graph 页面高亮该节点

---

#### P4: KG 可视化大屏 `/graph/:docId`

**布局**: 全屏 Canvas + 右侧浮动面板

**组件树**:
```
GraphPage
├── GraphCanvas (vis.js, 全屏)
│   ├── ForceDirectedNodes (310+ nodes, 10 色)
│   ├── Edges (1138+ lines, opacity by relation type)
│   └── HoverTooltip (node 详情浮层)
├── FloatingPanel (右侧, 宽 340px, 可折叠)
│   ├── SearchBar (节点搜索)
│   ├── LegendFilter (entity type 图例, 点击筛选)
│   ├── NodeDetail (选中节点)
│   │   ├── Label + Type Badge
│   │   ├── Properties JSON
│   │   ├── PageReference (page_idx + bbox)
│   │   └── NeighborList (1-hop 邻居)
│   └── ExportButton (导出当前子图为 PNG/SVG)
├── Toolbar (左上角浮动)
│   ├── ResetView
│   ├── TogglePhysics
│   ├── GroundedOnly Filter
│   └── ZoomControls (+/-)
└── MiniMap (右下角, 可选)
```

**交互**:
1. 加载 → 全部节点以力导向布局呈现
2. 左侧搜索 → 高亮 + 居中目标节点
3. 点击节点 → 右侧 Panel 展示详情 + 邻居节点高亮
4. 图例点击 → 隐藏/显示对应 entity type
5. GroundedOnly → 只显示接地节点 (214 → 子图)
6. 双击空白 → 重置视图

---

#### P5: 系统状态页 `/health`

**布局**: Dashboard 卡片网格

**组件树**:
```
HealthPage
├── StatusOverview (4 个状态卡片)
│   ├── APIServerCard (green dot + uptime)
│   ├── MineruAPICard (green/yellow/red)
│   ├── DeepSeekAPICard
│   └── KGStoreCard (nodes count)
├── SystemStats
│   ├── TotalDocuments
│   ├── TotalQueries
│   └── AvgQueryLatency
└── TaskQueuePanel
    └── RecentTasks (最近 10 个 ingest 任务)
```

---

## 5. 详细交互逻辑

### 5.1 Upload → Indexing Pipeline Flow

```
 User Action              Frontend                      Backend
 ────────────            ──────────                    ──────────
                                                       POST /ingest
  Drop file    ──►  Validate format + size
                    │ (unsupported → error toast)
                    │ (valid → show FilePreview)
                    ▼
  Click "Start" ──►  POST /api/v1/ingest  ──────────►  save file
                    (multipart/form-data)              return task_id
                    │
                    ▼
                 Start polling loop:
                 setInterval(2000ms):
                   GET /api/v1/status/{id}  ──────────►  return progress
                   │                                     │
                   ├─ status=pending → Stage 0 active    │
                   ├─ status=running → Stage N active    │
                   │   ├─ stage=mineru → "Parsing..."    │
                   │   ├─ stage=bridge → "Sectioning..." │
                   │   ├─ stage=extraction → "LLM..."    │
                   │   ├─ stage=grounding → "Mapping..." │
                   │   └─ stage=kg_build → "Building..." │
                   │                                     │
                   ├─ status=done → stop polling         │
                   │   └─ show ResultCard                │
                   │                                     │
                   └─ status=failed → stop polling       │
                       └─ show ErrorCard + retry btn     │
```

### 5.2 Query → Answer Flow

```
 User types question
        │
        ▼
 POST /api/v1/query  ──►  Backend
 {                         ├─ Load KG
   "query": "...",         ├─ Agent: search_kg_by_type()
   "document_id": "..."    ├─ Agent: get_entity_neighbors()
 }                         └─ Agent: generate answer
        │                         │
        │◄────────────────────────┘
        ▼
 Receive: { answer, sources[], metadata }
        │
        ▼
 Render AnswerBubble:
 ├─ Parse Markdown (tables, bold, lists)
 ├─ Highlight node_id references → clickable
 └─ Render SourceChips at bottom
        │
        ▼
 (User clicks source chip)
        │
        ▼
 RightPanel updates:
 ├─ Show SourceCard with full node detail
 ├─ page_idx + bbox → "Page 7, Position [150,400]"
 └─ Fetch related neighbors → show list
```

### 5.3 Graph → Node Inspection Flow

```
 Graph loaded (310 nodes, 1138 edges)
        │
        ▼
 User clicks a node (e.g., n0019 "28.4 BLEU")
        │
        ▼
 Node selected:
 ├─ Node enlarges + highlights
 ├─ 1-hop neighbors highlight (dimmer)
 ├─ Tooltip shows: type icon + label + properties summary
 └─ RightPanel loads full node detail
        │
        ▼
 RightPanel shows:
 ├─ Entity Type Badge (metric, yellow)
 ├─ Node ID + Label
 ├─ Properties Table
 │   ├─ name: BLEU
 │   ├─ value: 28.4
 │   └─ task: translation
 ├─ Grounding Info
 │   ├─ page_idx: 0
 │   └─ bbox_norm: [150, 400, 280, 415]
 ├─ Neighbors (click + traverse)
 └─ "Go to Query" button (跳转问答页并预填问题)
```

### 5.4 Error & Empty State Handling

| 场景 | UI 表现 |
|---|---|
| 文件格式不支持 | UploadZone 红色边框 + Toast "不支持 .docm 格式" |
| 文件超大 | UploadZone 拒绝 + Toast "最大 200MB" |
| MinerU API 故障 | Stage 1 变红 + 错误信息 + 重试按钮 |
| DeepSeek API 故障 | Stage 3 变红 + 错误信息 + 重试按钮 |
| 文档不存在 | 404 页面 + "返回文档列表" 链接 |
| 文档列表为空 | 插画 + "上传第一篇文档" CTA |
| 问答无结果 | "KG 中未找到相关信息" + 建议换个问法 |
| 网络断开 | 全局 Toast "网络连接已断开" + 自动重连 |

### 5.5 键盘快捷键

| 快捷键 | 作用域 | 功能 |
|---|---|---|
| `Ctrl+Enter` | Query 输入框 | 发送问题 |
| `Ctrl+K` | 全局 | 命令面板 (跳转页面/搜索文档) |
| `Esc` | Graph 页面 | 取消选中节点 |
| `Space` | Graph 页面 | 切换物理模拟 |
| `R` | Graph 页面 | 重置视图 |
| `1-5` | Graph 页面 | 按页码跳转 |

---

## 6. 技术选型与组件树

### 6.1 技术栈

| 层 | 技术 | 版本 | 选择理由 |
|---|---|---|---|
| Framework | **React 18** + TypeScript | ^18.3 | 生态成熟，状态管理完善 |
| Build | **Vite** | ^6 | HMR 快速，支持 CSS Modules |
| Routing | **React Router** | ^7 | 嵌套路由 + 动态参数 |
| State | **Zustand** | ^5 | 轻量 (1KB)，无 boilerplate |
| Styling | **Tailwind CSS** | ^4 | Utility-first，暗色主题内置 |
| HTTP | **axios** | ^1.7 | 拦截器 + 进度回调 |
| Graph | **vis-network** | ^9.1 | 力导向图，与 visualizer.html 一致 |
| Markdown | **react-markdown** + **remark-gfm** | ^9 | 表格/列表/粗体渲染 |
| Toast | **sonner** | ^2 | 简洁 toast 通知 |
| Icons | **lucide-react** | ^0.4 | 图标一致性 |
| Forms | **react-hook-form** + **zod** | ^7 + ^3 | 类型安全的表单校验 |

### 6.2 全局组件树

```
App
├── AppShell
│   ├── Sidebar (desktop) / BottomTab (mobile)
│   │   ├── SidebarLogo
│   │   ├── SidebarNav (links to /upload /documents /query /graph)
│   │   └── SidebarStats (global KG stats)
│   ├── MainContent
│   │   ├── TopBar (breadcrumb + global actions)
│   │   └── RouterOutlet
│   │       ├── UploadPage
│   │       │   ├── UploadZone
│   │       │   ├── ConfigPanel
│   │       │   ├── PipelineProgress
│   │       │   └── ResultCard
│   │       ├── DocumentsPage
│   │       │   ├── FilterBar
│   │       │   ├── DocumentTable
│   │       │   └── EmptyState
│   │       ├── QueryPage
│   │       │   ├── DocumentSelector
│   │       │   ├── ChatHistory
│   │       │   ├── QueryInput
│   │       │   ├── AnswerDetail
│   │       │   └── SourcePreview
│   │       ├── GraphPage
│   │       │   ├── GraphCanvas
│   │       │   ├── FloatingPanel
│   │       │   └── Toolbar
│   │       └── HealthPage
│   │           ├── StatusOverview
│   │           ├── SystemStats
│   │           └── TaskQueuePanel
│   └── ToastContainer (sonner)
```

### 6.3 目录结构

```
integration/webapp/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── src/
│   ├── main.tsx                     ← React 入口
│   ├── App.tsx                      ← Router + AppShell
│   ├── styles/
│   │   └── globals.css              ← Tailwind + 暗色主题变量
│   ├── lib/
│   │   ├── api.ts                   ← axios 实例 + 拦截器
│   │   └── constants.ts             ← ENTITY_COLORS, SUPPORTED_FORMATS
│   ├── stores/
│   │   ├── useUploadStore.ts        ← 上传 + Pipeline 状态
│   │   ├── useDocsStore.ts          ← 文档列表
│   │   ├── useQueryStore.ts         ← 问答对话
│   │   └── useKGStore.ts            ← 图数据 + 选中节点
│   ├── pages/
│   │   ├── UploadPage.tsx
│   │   ├── DocumentsPage.tsx
│   │   ├── QueryPage.tsx
│   │   ├── GraphPage.tsx
│   │   └── HealthPage.tsx
│   ├── components/
│   │   ├── ui/                      ← 通用 UI 组件
│   │   │   ├── Badge.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   ├── StatCard.tsx
│   │   │   └── PipelineProgress.tsx
│   │   ├── layout/
│   │   │   ├── AppShell.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── TopBar.tsx
│   │   ├── upload/
│   │   │   ├── UploadZone.tsx
│   │   │   ├── ConfigPanel.tsx
│   │   │   └── ResultCard.tsx
│   │   ├── query/
│   │   │   ├── ChatHistory.tsx
│   │   │   ├── QueryInput.tsx
│   │   │   ├── AnswerBubble.tsx
│   │   │   ├── AnswerDetail.tsx
│   │   │   └── SourceCard.tsx
│   │   └── graph/
│   │       ├── GraphCanvas.tsx
│   │       ├── FloatingPanel.tsx
│   │       └── LegendFilter.tsx
│   └── hooks/
│       ├── usePolling.ts            ← 轮询 status 端点
│       └── useKeyboard.ts           ← 快捷键绑定
└── public/
    └── favicon.svg
```

---

## 7. 数据流与状态管理

### 7.1 Zustand Store 设计

```typescript
// stores/useUploadStore.ts
interface UploadState {
  file: File | null;
  taskId: string | null;
  status: 'idle' | 'uploading' | 'indexing' | 'done' | 'failed';
  stage: PipelineStage | null;
  progress: StageProgress | null;
  result: TaskResult | null;
  error: string | null;

  // Actions
  setFile: (file: File) => void;
  startUpload: () => Promise<void>;
  pollStatus: () => void;
  reset: () => void;
}

// stores/useQueryStore.ts
interface QueryState {
  documentId: string | null;
  messages: Message[];        // { role, content, sources?, timestamp }
  isLoading: boolean;

  // Actions
  sendQuery: (query: string) => Promise<void>;
  setDocument: (docId: string) => void;
  clearHistory: () => void;
}

// stores/useKGStore.ts
interface KGState {
  nodes: KGNode[];
  edges: KGEdge[];
  selectedNodeId: string | null;
  filteredTypes: Set<string>;
  groundedOnly: boolean;

  // Actions
  loadGraph: (docId: string) => Promise<void>;
  selectNode: (nodeId: string | null) => void;
  toggleType: (entityType: string) => void;
  toggleGroundedOnly: () => void;
}
```

### 7.2 API Client 封装

```typescript
// lib/api.ts
const API_BASE = 'http://localhost:8000/api/v1';

const api = axios.create({ baseURL: API_BASE, timeout: 30000 });

// Response interceptor: 统一错误处理
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const code = err.response?.data?.error?.code || 'NETWORK_ERROR';
    const msg = err.response?.data?.error?.message || err.message;
    toast.error(`[${code}] ${msg}`);
    return Promise.reject(err);
  }
);

export const ingestAPI = {
  upload: (formData: FormData, onProgress?: (pct: number) => void) =>
    api.post('/ingest', formData, { onUploadProgress: ... }),
};

export const statusAPI = {
  get: (taskId: string) => api.get(`/status/${taskId}`),
};

export const queryAPI = {
  ask: (body: QueryRequest) => api.post('/query', body),
};

export const docsAPI = {
  list: () => api.get('/documents'),
  delete: (docId: string) => api.delete(`/documents/${docId}`),
};

export const healthAPI = {
  check: () => api.get('/health'),
};
```

---

## 8. 实施路线图

### Phase 1: 项目脚手架 (0.5 天)

```
□ Vite + React + TypeScript 项目初始化
□ Tailwind CSS 配置 + 暗色主题变量
□ 路由配置 (5 routes)
□ AppShell 布局 (Sidebar + TopBar + RouterOutlet)
□ API Client 封装 + axios 拦截器
□ Zustand stores 骨架
```

### Phase 2: 上传 + 文档列表 (1.5 天)

```
□ UploadZone (拖拽/点击/格式校验)
□ ConfigPanel (语言/OCR/公式/表格/模型选择)
□ PipelineProgress (5 阶段动画进度条)
□ ResultCard (统计摘要 + 跳转按钮)
□ DocumentsPage (表格 + 筛选 + 空状态)
□ useUploadStore + 轮询逻辑
```

### Phase 3: KG 可视化 (1.5 天)

```
□ GraphCanvas (vis.js 集成 + 10 色图例)
□ FloatingPanel (搜索 + 节点详情 + 邻居列表)
□ Toolbar (重置/物理/GroundedOnly/缩放)
□ LegendFilter (点击筛选 entity type)
□ Node 选中 + 高亮 + Tooltip
□ useKGStore (数据加载 + 交互状态)
```

### Phase 4: 问答页 (1.5 天)

```
□ ChatHistory (对话气泡列表 + 自动滚动)
□ QueryInput (TextArea + 发送 + 选项)
□ AnswerBubble (Markdown 渲染 + node 高亮)
□ AnswerDetail (完整答案 + SourceCards)
□ SourcePreview (右侧面板: node 详情 + 邻居)
□ SuggestedQueries (快捷问题)
□ useQueryStore (对话管理)
```

### Phase 5: 联调 + 打磨 (1 天)

```
□ 端到端测试: 上传 → 索引 → 问答 → 可视化
□ 错误状态覆盖 (格式不支持 / API 故障 / 网络断开)
□ 响应式适配测试 (Desktop / Tablet / Mobile)
□ 键盘快捷键实现
□ Loading / Empty / Error 三态全覆盖
□ 构建优化 (code splitting, lazy loading routes)
```

**总计**: 5.5 天

---

## 附录 A: 页面状态矩阵

| 页面 | Loading | Empty | Error | Success |
|---|---|---|---|---|
| Upload | — | 初始态: 拖拽区 + 格式说明 | 格式不支持 / 太大 | 文件预览 → Pipeline → 结果卡片 |
| Documents | 骨架表格 (4 行闪烁) | 插画 + CTA 链接 | API 错误 + 重试按钮 | 数据表格 + 分页 |
| Query | 输入框 + 骨架对话 | 欢迎语 + 5 条建议问题 | 文档未索引 / API 故障 | 对话历史 + 答案详情 |
| Graph | Canvas Loading | "No KG data" + 去上传 | 加载失败 + 重试 | 力导向图 + 交互面板 |
| Health | 骨架卡片 | — | 红色状态 + 错误信息 | 绿色状态卡片 + 统计数据 |

## 附录 B: 设计参考

- 配色系统: Linear App dark mode
- 图表风格: Vercel Analytics Dashboard
- 对话交互: ChatGPT / Claude.ai
- 力导向图: vis.js examples (network/physics.html)
- 文件上传: Dropbox upload zone

---

## 已知陷阱（来自历史排障报告回流，2026-05-29）

### 上传组件约束

- 上传前端必须读取后端 `/api/config` 返回的体积上限，**不要**前端硬编码 100MB
- 上传成功后必须用后端返回的 `filename` 字段渲染列表，**禁止**使用本地 `File.name`（OSS 改名后会不一致）
- 上传失败的错误提示要区分：413（体积超限）/ 401（凭证失效）/ 5xx（服务端故障）

### 文档列表渲染约束

- 列表 key 用后端返回的 `file_id`，不要用数组 index（会因为列表更新错乱）
- 渲染字段必须是 `filename`，与后端 schema 对齐
- 列表为空时显示空态组件，**禁止**显示骨架屏（骨架屏只在 loading 状态使用）
