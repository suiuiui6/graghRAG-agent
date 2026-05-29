# 多模态 RAG 知识图谱问答系统 — 产品需求文档 PRD v1.0

> **版本**: v1.0 | **日期**: 2026-05-24 | **状态**: MVP 后端已验证
>
> **关联规范**: `backend-api-architecture-v1.0.md` (后端) | `frontend-system-design-v1.0.md` (前端)

---

## 目录

1. [产品概述](#1-产品概述)
2. [产品流程](#2-产品流程)
3. [页面/模块清单与设计](#3-页面模块清单与设计)
4. [核心交互逻辑](#4-核心交互逻辑)
5. [UI 设计规范](#5-ui-设计规范)

---

## 1. 产品概述

### 1.1 产品定义

**多模态 RAG 知识图谱问答系统** 是一套面向非结构化文档的知识管理平台。
用户上传 PDF/Word/PPT/Excel 等任意格式文档后，系统自动完成文档解析、
实体关系抽取、知识图谱构建，并提供基于知识图谱的自然语言问答能力。

**产品形态**: Web 应用 (响应式), PWA-ready

### 1.2 产品一句话

> 上传文档 → 自动建图谱 → 直接问答案，全程无需编码。

### 1.3 核心目标

| 目标 | 衡量指标 | 当前 MVP 状态 |
|---|---|---|
| 零门槛文档知识化 | 用户上传到可用 < 3 min | ✅ 已验证: 109s (15 页论文) |
| 可溯源的结构化问答 | 每条答案关联 source node + PDF 页码 | ✅ 已验证: page_idx + bbox 溯源 |
| 多格式文档支持 | 11 种输入格式 (PDF/DOCX/PPTX/XLSX/EPUB/HTML/图片) | ✅ MinerU API 已支持 |
| 可视化知识探索 | 力导向图交互 + entity type 筛选 | ✅ visualizer.html 已验证 |

### 1.4 核心场景

| 场景 | 用户 | 典型操作 | 价值 |
|---|---|---|---|
| **论文研读** | 研究员/学生 | 上传论文 PDF → 自动提取关键指标、模型、方法 → 问答对比多篇论文 | 10 倍速文献调研 |
| **合同审查** | 法务/律师 | 上传合同 PDF → 提取关键条款、金额、日期 → 自然语言查询 "违约金条款是什么" | 降低遗漏风险 |
| **财报分析** | 分析师/投资人 | 上传财报 PDF → 提取收入、利润、增长率 → 可视化趋势问答 | 秒级数据定位 |
| **技术文档** | 工程师 | 上传 API 文档 PDF → 构建技术知识图谱 → 自然语言查询 "认证接口怎么调" | 即时文档检索 |
| **医疗病历** | 医生/研究者 | 上传病历 PDF → 提取诊断、用药、指标 → 问答 "该患者血压控制情况" | 结构化病历数据 |

### 1.5 业务痛点

| 痛点 | 现状 | 本产品方案 |
|---|---|---|
| **文档信息碎片化** | PDF/Word 中的结构化数据无法被直接检索，只能靠人工翻阅 | MinerU 自动解析 + LangExtract 实体抽取 → 全量结构化 |
| **跨文档对比困难** | 多篇论文/合同需要逐篇阅读对比，耗时巨大 | 统一 KG 索引 → 跨文档实体关联 → 一键问答 |
| **引用溯源缺失** | LLM 直接问答存在幻觉，无法精确定位信息来源 | BridgePipeline 接地追踪 → 每条答案关联 PDF 页码+bbox |
| **数据格式壁垒** | 不同格式文档 (PDF/DOCX/PPTX) 需不同工具处理，流程断裂 | 11 种格式统一上传入口 → 自动路由解析引擎 |
| **知识沉淀困难** | 每次查阅文档后知识无法积累和复用 | KG 持久化存储 → 历史文档可被后续查询复用 |

### 1.6 目标用户群体

| 用户群 | 规模 | 痛点强度 | 特征 |
|---|---|---|---|
| **学术研究者** | 大 | 高 | 大量论文 PDF，需要快速提取关键信息 |
| **法务/合规人员** | 中 | 高 | 海量合同文档，需要条款检索和对比 |
| **金融分析师** | 中 | 中 | 财报/研报 PDF，需要数值提取和趋势 |
| **技术文档工程师** | 中 | 中 | API 文档/技术手册，需要结构化查询 |
| **医疗从业者** | 小 | 高 | 病历/检验报告，需要结构化数据抽取 |

### 1.7 产品边界

**V1.0 包含**:
- 单文档上传 → 自动建 KG → 单文档问答
- 11 种文件格式支持
- KG 可视化浏览 (力导向图)
- 答案溯源 (page_idx + bbox)

**V1.0 不包含**:
- 多文档联合问答 (V2.0)
- 用户登录/权限管理 (V2.0)
- 团队协作/文档共享 (V3.0)
- 文档 OCR 校正手动标注
- PDF 页面级原文件预览 (内嵌 PDF viewer)
- Embedding 向量语义检索 (当前仅 KG 图检索)

---

## 2. 产品流程

### 2.1 端到端用户旅程

```
           ┌──────────────┐
           │   入口页面    │  /upload
           │ 拖拽/选择文件 │
           └──────┬───────┘
                  │
                  ▼
           ┌──────────────┐
           │  配置参数     │  语言 / OCR / 公式 / 表格 / 引擎
           │  (可选折叠)   │
           └──────┬───────┘
                  │
                  ▼ 点击 "开始解析"
           ┌──────────────┐
           │  实时进度     │  5 阶段 Pipeline 动画
           │  等待完成     │  MinerU → Bridge → Extract → Grounding → KG
           │  (≈90s)      │  每阶段更新状态
           └──────┬───────┘
                  │
                  ▼ 完成
           ┌──────────────┐
           │  结果摘要     │  310 nodes / 1529 edges / 10 types
           │               │  [去问答]  [去可视化]
           └──────┬───────┘
                  │
          ┌───────┴────────┐
          ▼                ▼
   ┌──────────┐    ┌──────────────┐
   │ 问答页面  │    │  可视化大屏   │
   │ /query   │    │  /graph      │
   │          │    │              │
   │ 输入问题  │    │ 力导向图交互  │
   │ 获取答案  │    │ 节点筛选/详情 │
   │ 查看溯源  │    │ 页面溯源定位  │
   └──────────┘    └──────────────┘
```

### 2.2 上传与索引 Pipeline 详细流程

```
Step 1: 文件选择
  ├─ 用户拖拽 PDF 到 UploadZone
  ├─ 或点击 UploadZone 触发系统文件选择器
  └─ 前端校验:
      ├─ 格式: .pdf/.docx/.pptx/.xlsx/.png/.jpg/.epub/.html 白名单
      ├─ 大小: ≤ 200 MB
      ├─ 通过 → 显示 FilePreview (文件名 + 大小 + 格式图标)
      └─ 不通过 → Toast 错误提示 + 红色边框

Step 2: 配置参数 (可选)
  ├─ 语言: 下拉选择 [中文/English/日本語]
  ├─ OCR: 开关 (扫描件需开启)
  ├─ 公式识别: 开关 (学术论文开启)
  ├─ 表格识别: 开关 (财报/合同打开)
  ├─ 解析引擎: pipeline (快速) / vlm (高精度)
  └─ 系统根据文件扩展名自动设置推荐参数

Step 3: 提交索引任务
  ├─ 用户点击 "开始解析" 按钮
  ├─ 前端 POST /api/v1/ingest (multipart/form-data)
  ├─ 后端返回 task_id
  └─ 前端启动轮询: GET /api/v1/status/{task_id} (每 2s)

Step 4: 实时进度展示
  ├─ 5 阶段进度条:
  │   ┌────────────────────────────────────────────┐
  │   │ ❶ MinerU    ████████████  done (12s)       │
  │   │ ❷ Bridge    ████████████  done (2s)        │
  │   │ ❸ Extract   ████████████  running (45s)    │
  │   │ ❹ Grounding ░░░░░░░░░░░░  pending          │
  │   │ ❺ KG Build  ░░░░░░░░░░░░  pending          │
  │   └────────────────────────────────────────────┘
  ├─ 每个阶段完成 → 绿色 ✓ + 耗时
  ├─ 当前阶段 → 蓝色脉冲动画
  └─ 失败阶段 → 红色 ✗ + 错误信息 + 重试按钮

Step 5: 结果展示
  ├─ 全部完成后:
  │   ┌─────────┬─────────┬─────────┬─────────┐
  │   │ 310     │ 1529    │ 214     │ 10      │
  │   │ Nodes   │ Edges   │Grounded │Types    │
  │   └─────────┴─────────┴─────────┴─────────┘
  ├─ [去问答] 按钮 → /query/{docId}
  └─ [去可视化] 按钮 → /graph/{docId}
```

### 2.3 问答交互详细流程

```
Step 1: 进入问答页
  ├─ 路由 /query/:docId (或 /query 显示文档选择器)
  ├─ 加载文档 KG 元信息 (nodes count / types / edges)
  └─ 展示 5 条建议问题 (从 section_header + metric 类型自动生成)

Step 2: 用户输入问题
  ├─ 在底部输入框输入自然语言问题
  ├─ 支持 Ctrl+Enter 快捷发送
  └─ 前端显示 "typing" 状态

Step 3: Agent 推理
  ├─ POST /api/v1/query {"query":"...","document_id":"..."}
  ├─ 后端 Agent 执行:
  │   ├─ LLM 分析问题 → 决定调用哪些 tools
  │   ├─ search_kg_by_type(entity_type="metric", keyword="BLEU")
  │   ├─ get_entity_neighbors(label_keyword="Transformer", k_hops=1)
  │   └─ LLM 综合工具结果 → 生成最终答案
  └─ 返回: { answer, sources[], metadata }

Step 4: 答案展示
  ├─ 答案气泡 (Markdown 渲染):
  │   ┌─────────────────────────────────┐
  │   │ Based on the KG, the Transformer│
  │   │ achieved:                       │
  │   │                                 │
  │   │ | BLEU | Dataset |              │
  │   │ |:----:|:--------|              │
  │   │ | 28.4 | WMT EN-DE |            │
  │   │ | 41.8 | WMT EN-FR |            │
  │   │                                 │
  │   │ 📎 n0019  📎 n0020             │
  │   └─────────────────────────────────┘
  └─ 底部 Source Chips: 每条引用的 KG 节点

Step 5: 溯源交互
  ├─ 点击 source chip → 右侧面板展开
  │   ┌──────────────────────────────┐
  │   │ 📊 metric                    │
  │   │ 28.4 BLEU                   │
  │   │ ────────────────────────────│
  │   │ Properties:                  │
  │   │  name: BLEU                  │
  │   │  value: 28.4                │
  │   │  task: translation           │
  │   │ ────────────────────────────│
  │   │ 📍 Page 0                    │
  │   │ 📐 [150, 400, 280, 415]     │
  │   │                             │
  │   │ Related:                     │
  │   │  ├─ n0018 Transformer       │
  │   │  └─ n0020 41.8 BLEU        │
  │   └──────────────────────────────┘
  └─ [在图中查看] 按钮 → 跳转到 Graph 页面并高亮该节点
```

### 2.4 图谱可视交互详细流程

```
Step 1: 进入可视化页
  ├─ 路由 /graph/:docId
  ├─ 加载完整 KG 数据 (nodes.json + edges.json)
  └─ 渲染力导向图 (310 节点 + 1138 边)

Step 2: 默认视图
  ├─ 全部节点可见, 10 色按 entity_type 着色
  ├─ 右侧 Legend 面板显示每种类型的颜色 + 数量
  ├─ 左上角 Toolbar: 重置 / 物理开关 / Grounded Only / 缩放
  └─ 右下角 MiniMap (可选, 小尺寸缩略图)

Step 3: 图筛选交互
  ├─ 点击 Legend 中的某个 entity_type → 该类节点高亮, 其余半透明
  ├─ 再次点击 → 该类节点隐藏
  ├─ Grounded Only 开关 → 只显示 grounded 节点 (214)
  └─ 顶部搜索框 → 输入节点 label → 搜索结果列表 → 点击 → 居中+高亮

Step 4: 节点详情交互
  ├─ 点击节点 → 节点放大 + 1-hop 邻居高亮
  ├─ 右侧 Panel 切换为该节点完整信息
  ├─ 邻居列表可点击 → 递归探索 (breadcrumb 记录路径)
  └─ 双击空白 → 取消选中 + 重置视图

Step 5: 导出
  ├─ 导出当前视图为 PNG
  ├─ 导出当前子图数据为 JSON
  └─ 导出全量 KG 为 GraphML (供 Neo4j/Gephi 导入)
```

---

## 3. 页面/模块清单与设计

### 3.1 页面清单

| # | 页面名称 | 路由 | 级别 | 说明 |
|---|---|---|---|---|
| P1 | 文档上传 | `/upload` | 一级 | 产品入口，文件上传 + Pipeline 进度 |
| P2 | 文档列表 | `/documents` | 一级 | 已索引文档管理 |
| P3 | KG 问答 | `/query/:docId` | 二级 | 核心功能：自然语言问答 |
| P4 | KG 可视化 | `/graph/:docId` | 二级 | 力导向图交互探索 |
| P5 | 系统状态 | `/health` | 一级 | 组件健康 + 任务队列 |

### 3.2 关键模块设计

---

#### P1: 文档上传页 `/upload`

**页面定位**: 产品入口，首次用户体验的第一触点

**模块清单**:

| 模块 | 功能 | 优先级 |
|---|---|---|
| UploadZone | 拖拽/点击上传，格式白名单校验，文件预览 | P0 |
| ConfigPanel | 折叠式参数面板 (语言/OCR/公式/表格/引擎) | P1 |
| PipelineProgress | 5 阶段 Pipeline 实时进度动画 | P0 |
| ResultCard | 完成后的统计摘要 + CTA 按钮 | P0 |
| ErrorCard | 失败后的错误详情 + 重试按钮 | P1 |
| FormatHint | 底部格式支持说明 (图标 + 扩展名列表) | P2 |

**UploadZone 交互规则**:
- 拖入文件时: 边框变蓝 + 背景加深 + "释放以上传" 提示
- 拖入不支持格式: 边框变红 + "不支持 .docm 格式" 
- 拖入超大文件 (>200MB): 边框变红 + "最大 200MB"
- 验证通过: 显示文件图标 + 名称 + 大小 + ✓ 标记
- 支持一次性选择一个文件 (批量上传 V2)

**PipelineProgress 动画规则**:
- 当前阶段: 蓝色脉冲圆点 + 进度文字 "running"
- 已完成阶段: 绿色实心圆点 + "done (12s)"
- 待执行阶段: 灰色空心圆点 + "pending"
- 失败阶段: 红色圆点 + 错误信息
- 每阶段完成有轻微弹跳动画 (200ms ease-out)

---

#### P2: 文档列表页 `/documents`

**页面定位**: 已索引文档的管理中心

**模块清单**:

| 模块 | 功能 | 优先级 |
|---|---|---|
| FilterBar | 状态筛选 (All/Indexed/Indexing/Failed) + 文件名搜索 | P1 |
| DocumentTable | 表格展示 (文件名/状态/KG 统计/页数/时间/操作) | P0 |
| EmptyState | 无文档时的引导 (插画 + CTA 按钮) | P0 |
| DeleteConfirm | 删除确认弹窗 (Modal) | P1 |

**表格列定义**:

| 列名 | 宽度 | 内容 | 排序 |
|---|---|---|---|
| 文件名 | 30% | 格式图标 + 文件名 (截断+tooltip) | ✅ |
| 状态 | 12% | Badge: green=indexed, yellow=indexing, red=failed | ✅ |
| KG 统计 | 15% | "310 N / 1529 E" | ❌ |
| 页数 | 8% | "15 pages" | ✅ |
| 索引时间 | 18% | 相对时间 (3分钟前) + tooltip 精确时间 | ✅ |
| 操作 | 17% | [问答] [可视化] [删除] 三个按钮 | ❌ |

---

#### P3: KG 问答页 `/query/:docId`

**页面定位**: 核心功能，自然语言 KG 问答

**模块清单**:

| 模块 | 功能 | 优先级 |
|---|---|---|
| DocumentSelector | 顶部下拉选择已索引文档 | P0 |
| SuggestedQueries | 首次加载时的快捷问题列表 | P1 |
| ChatHistory | 对话气泡列表 (用户问题 + AI 答案) | P0 |
| QueryInput | 底部固定输入框 (TextArea 自动增高 + 发送按钮) | P0 |
| AnswerBubble | 单条答案气泡 (Markdown 渲染 + Source Chips) | P0 |
| AnswerDetail | 右侧面板: 选中答案的完整内容 | P1 |
| SourceCard | 单个 source node 的摘要卡片 | P0 |
| SourcePreview | 右侧面板: 选中 source 的完整详情 | P0 |

**消息数据结构**:
```typescript
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;           // Markdown
  timestamp: Date;
  sources?: SourceNode[];    // AI 回答专属
  metadata?: {
    tool_calls: number;
    duration_ms: number;
    model: string;
  };
}
```

**输入框交互**:
- 单行 → 高度 48px
- 多行 (超过 2 行) → 自动增高到 max 120px，显示滚动条
- Enter 发送 (Shift+Enter 换行)
- 发送中 → 按钮变为 loading spinner，输入框 disabled
- 发送完成 → 自动 focus 回输入框

---

#### P4: KG 可视化大屏 `/graph/:docId`

**页面定位**: 知识图谱可视化浏览

**模块清单**:

| 模块 | 功能 | 优先级 |
|---|---|---|
| GraphCanvas | vis.js 力导向图 (全屏) | P0 |
| FloatingPanel | 右侧可折叠面板 (搜索+详情+邻居) | P0 |
| Toolbar | 左上角浮动工具栏 | P0 |
| LegendFilter | entity type 图例 + 点击筛选 | P0 |
| NodeTooltip | 悬停节点的快速信息浮层 | P1 |
| MiniMap | 右下角小地图 (V2) | P2 |

**图节点视觉规范**:
- 大小: grounded=12px, ungrounded=8px
- 边框: grounded 白色 2px, ungrounded 红色 1px
- 选中: 放大 1.5x + 边框增粗
- 邻居高亮: 选中节点的 1-hop 邻居颜色加深，其余节点透明度 0.2
- 标签: 超过 30 字符截断为 "xxx..."

---

#### P5: 系统状态页 `/health`

**页面定位**: 运维监控面板

**模块清单**:

| 模块 | 功能 | 优先级 |
|---|---|---|
| StatusCards | 4 个组件状态卡片 (API/MinerU/DeepSeek/KG) | P0 |
| SystemStats | 文档总数 / 总节点 / 总查询 / 平均延迟 | P1 |
| RecentTasks | 最近 10 个索引任务列表 | P1 |

---

## 4. 核心交互逻辑

### 4.1 关键节点定义

| 节点 | 触发条件 | 涉及组件 | 数据流 |
|---|---|---|---|
| N1: 文件校验 | 用户拖入/选择文件 | UploadZone | 前端白名单 + 大小校验 |
| N2: 提交索引 | 点击 "开始解析" | UploadPage → API | POST /ingest → task_id |
| N3: 进度轮询 | 获得 task_id 后 | PipelineProgress | GET /status/{id} (每2s) |
| N4: 索引完成 | status=done | ResultCard | 解析 result 数据 |
| N5: 问答提交 | 输入问题 + Enter | QueryPage → API | POST /query |
| N6: 答案渲染 | API 响应返回 | ChatHistory | Markdown 解析 + source 注入 |
| N7: 溯源查看 | 点击 source chip | SourcePreview | 从 sources[] 提取详情 |
| N8: 图谱加载 | 进入 /graph 页面 | GraphCanvas | 加载 nodes.json/edges.json |
| N9: 节点选中 | 点击图中节点 | FloatingPanel | 1-hop 邻居查询 |
| N10: 类型筛选 | 点击 Legend item | GraphCanvas | entity_type 过滤 |

### 4.2 N3-N4: Pipeline 轮询逻辑

```
伪代码:
function pollStatus(taskId) {
  timer = setInterval(async () => {
    res = await GET /api/v1/status/{taskId}
    data = res.data

    updatePipelineUI(data.progress)

    if (data.status === 'done') {
      clearInterval(timer)
      showResultCard(data.result)
    }
    if (data.status === 'failed') {
      clearInterval(timer)
      showErrorCard(data.error)
    }
  }, 2000)

  // 安全阀: 10 分钟后强制停止
  setTimeout(() => clearInterval(timer), 600000)
}
```

### 4.3 N5-N6: 问答请求与渲染

```
用户输入 "Transformer BLEU score?"
        │
        ▼
POST /api/v1/query {"query":"...","document_id":"doc_123"}
        │
        ▼ 等待... (显示 typing 动画)
        │
        ▼ 响应返回
        │
        ▼
渲染 AnswerBubble:
├── 1. 解析 Markdown:
│      └── ### → h3, |---| → table, **bold**, `code`
├── 2. 识别 node_id 引用:
│      └── regex /n\d{4}/ → 替换为可点击 chip
├── 3. 渲染 SourceChips:
│      └── 每个 source 显示: [entity_type icon] + label + score
└── 4. 滚动到最新消息 (smooth scroll)
```

### 4.4 N7: 溯源面板

```
用户点击 source chip "n0019 (28.4 BLEU)"
        │
        ▼
右侧 SourcePreview 展开:
├── 从 sources[] 数组中找到 node_id === "n0019" 的项
├── 渲染内容:
│   ├── Header: entity_type badge + node_id
│   ├── Label: "28.4 BLEU"
│   ├── Properties Table:
│   │   ├── name → BLEU
│   │   ├── value → 28.4
│   │   └── task → translation
│   ├── Grounding:
│   │   ├── 📍 Page 0
│   │   └── 📐 Bbox [150, 400, 280, 415]
│   ├── Neighbor List (fetch from subgraph):
│   │   ├── n0018 Transformer (model_component)
│   │   └── n0020 41.8 BLEU (metric)
│   └── Actions:
│       └── [在图中查看] → 跳转 /graph/doc_123?highlight=n0019
└── 面板从右滑入 (300ms ease-out)
```

### 4.5 N9: 图谱节点选中

```
用户点击图中节点 n0074 (multi-head self-attention mechanism)
        │
        ▼
视觉反馈:
├── 选中节点: 放大 1.5x + 白色发光边框
├── 1-hop 邻居: 颜色加深
├── 其余节点: opacity 降至 0.2
└── Canvas 自动平移到选中节点居中 (500ms animation)

FloatingPanel 更新:
├── SearchBar 显示当前 node_id
├── NodeDetail section 更新:
│   ├── Type: 🧩 model_component
│   ├── Label: multi-head self-attention mechanism
│   ├── Properties: {"component_type": "mechanism"}
│   ├── Grounding: Page 2, [120, 200, 380, 220]
│   └── Neighbors (top 10):
│       ├── n0075 feed-forward network → adjacent_to
│       └── n0076 residual connection → co_occurs_with
└── "View in Query Page" 按钮

双击空白:
├── 取消选中
├── opacity 恢复 1.0
├── 视图重置
└── Panel 恢复默认
```

### 4.6 状态切换矩阵

| 触发 | Loading | Success | Empty | Error |
|---|---|---|---|---|
| 上传文件 | UploadZone 渐变 shimmer | FilePreview + ✓ | — | 红色边框 + Toast |
| 轮询进度 | PipelineProgress 蓝色脉冲 | 绿色 ✓ + 耗时 | — | 红色 ✗ + 重试 |
| 文档列表 | 骨架表格 (4行闪烁) | 数据表格 | 插画 + CTA | Toast + 重试 |
| 问答请求 | Typing dots 动画 | AnswerBubble | "KG 中未找到" | Toast "API 错误" |
| 图谱加载 | Canvas 中央 spinner | 力导向图 | "无 KG 数据" | Toast + 重试 |

---

## 5. UI 设计规范

### 5.1 整体设计语言

| 属性 | 定义 |
|---|---|
| **风格流派** | Dark-first Clean Dashboard — 数据密集型产品的专业感 |
| **设计参考** | Linear App (暗色模式) + Vercel Analytics (数据卡片) + ChatGPT (对话交互) |
| **核心原则** | 1) 内容优先, 装饰最小化 2) 状态可见, 过渡流畅 3) 操作可达, 路径最短 |

### 5.2 配色方案

```
                    暗色主题 (默认)
    ┌─────────────────────────────────────────────┐
    │                                             │
    │  Background                                  │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
    │  │ #0f172a  │ │ #1e293b  │ │ #334155  │    │
    │  │  Root    │ │ Surface  │ │ Elevated │    │
    │  └──────────┘ └──────────┘ └──────────┘    │
    │                                             │
    │  Text                                       │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
    │  │ #f1f5f9  │ │ #94a3b8  │ │ #64748b  │    │
    │  │ Primary  │ │Secondary │ │  Muted   │    │
    │  └──────────┘ └──────────┘ └──────────┘    │
    │                                             │
    │  Accent                                     │
    │  ┌──────────┐ ┌──────────┐                 │
    │  │ #38bdf8  │ │ #7dd3fc  │  Sky blue       │
    │  │ Default  │ │  Hover   │                 │
    │  └──────────┘ └──────────┘                 │
    │                                             │
    │  Semantic                                   │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
    │  │ #4ade80  │ │ #facc15  │ │ #f87171  │    │
    │  │ Success  │ │ Warning  │ │  Error   │    │
    │  └──────────┘ └──────────┘ └──────────┘    │
    │                                             │
    └─────────────────────────────────────────────┘
```

**Entity Type 10 色映射** (全局统一):

| Entity Type | 颜色 | 色值 |
|---|---|---|
| paper_metadata | Sky | `#38bdf8` |
| section_header | Green | `#4ade80` |
| model_component | Purple | `#c084fc` |
| metric | Yellow | `#facc15` |
| dataset | Orange | `#fb923c` |
| method | Pink | `#f472b6` |
| definition | Violet | `#a78bfa` |
| equation | Teal | `#2dd4bf` |
| reference | Gray | `#94a3b8` |
| claim | Red | `#f87171` |

### 5.3 字体规范

| 用途 | 字体 | Weight | Size | Line Height |
|---|---|---|---|---|
| 页面标题 (H1) | Inter | 700 | 24px | 32px |
| 区块标题 (H2) | Inter | 600 | 18px | 28px |
| 卡片标题 (H3) | Inter | 600 | 14px | 20px |
| 正文 | Inter | 400 | 14px | 22px |
| 辅助文字 | Inter | 400 | 12px | 18px |
| 代码/数据 | JetBrains Mono | 400 | 13px | 20px |
| 数值 (StatCard) | Inter | 700 | 28px | 36px |

### 5.4 组件样式规范

#### 按钮

```
┌──────────────────────────────────────────────────────┐
│  Primary:    [████████████]  bg=accent, text=white    │
│  Secondary:  [▓▓▓▓▓▓▓▓▓▓▓▓]  bg=transparent, border  │
│  Danger:     [████████████]  bg=#7f1d1d, text=red    │
│  Ghost:      [              ]  bg=transparent, hover  │
│                                                      │
│  Size:  sm=32px | md=40px | lg=48px                  │
│  Radius: 6px                                         │
│  Hover: brightness 1.1, 150ms transition              │
│  Disabled: opacity 0.4, cursor not-allowed            │
└──────────────────────────────────────────────────────┘
```

#### 卡片

```
┌─────────────────────────────────┐
│  padding: 16px                  │
│  bg: var(--bg-surface)          │
│  border: 1px solid var(--border)│
│  radius: 8px                    │
│  shadow: none (flat design)     │
│  ─────────────────────────────  │
│  Hover (interactive cards only):│
│    border-color: var(--accent)  │
│    bg: rgba(56,189,248,0.04)    │
│    transition: 200ms ease        │
└─────────────────────────────────┘
```

#### Badge

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│ indexed  │  │ running  │  │  failed  │
│ bg:green │  │bg:yellow │  │ bg:red   │
│ 15% opac │  │ 15% opac │  │ 15% opac │
└──────────┘  └──────────┘  └──────────┘

Size: padding 2px 8px, font 11px, radius 4px
Dot indicator: 6px circle before text
```

#### Input

```
┌──────────────────────────────────────────────┐
│  bg: var(--bg-surface)                       │
│  border: 1px solid var(--border)             │
│  radius: 8px                                 │
│  padding: 10px 14px                          │
│  font: Inter 14px                            │
│  placeholder: var(--text-muted)              │
│  ─────────────────────────────────────────── │
│  Focus:                                      │
│    border-color: var(--accent)               │
│    box-shadow: 0 0 0 3px rgba(56,189,248,.15)│
│    transition: 200ms ease                     │
│  Error:                                      │
│    border-color: var(--danger)               │
│    box-shadow: 0 0 0 3px rgba(248,113,113,.15)│
└──────────────────────────────────────────────┘
```

#### Toast (sonner)

```
┌─────────────────────────────────┐
│  🔴  [ERROR] message            │  Position: bottom-right
│  ─────────────────────────────  │  Duration: 4s (error), 2s (success)
│  文件格式不支持                  │  Animation: slide-up + fade
└─────────────────────────────────┘
```

### 5.5 响应式适配规则

| 断点 | 宽度 | Sidebar | 表格 | 问答布局 | 图谱面板 |
|---|---|---|---|---|---|
| **Desktop** | ≥1280px | 240px, 常驻 | 6 列 | 左40% 右60% | 右侧 340px 浮动 |
| **Laptop** | 1024-1279px | 200px, 常驻 | 5 列 (隐藏 bbox) | 左35% 右65% | 右侧 280px |
| **Tablet** | 768-1023px | 折叠, 汉堡菜单 | 4 列 (隐藏时间/bbox) | 上下 Stack | 面板 overlay |
| **Mobile** | <768px | 底部 Tab 导航 | 卡片列表 | 全屏对话式 | 底部 sheet 面板 |

**移动端特殊规则**:
- Sidebar → 底部固定导航栏 (4 个 Tab: Upload/Documents/Query/Graph)
- UploadZone 全宽, 最小高度 200px
- ChatHistory 全屏, QueryInput fixed bottom
- GraphCanvas 全屏, FloatingPanel 改为底部 sheet (拖拽展开)

### 5.6 动画与过渡

| 元素 | 动画 | 时长 | Easing |
|---|---|---|---|
| 页面切换 | fade-in + slide-up(8px) | 200ms | ease-out |
| Sidebar 展开/折叠 | slide-right + width 过渡 | 250ms | ease-in-out |
| Pipeline stage 完成 | 脉冲 + 绿色填充 | 300ms | ease-out |
| 对话气泡出现 | slide-up(12px) + fade-in | 200ms | ease-out |
| SourcePanel 展开 | slide-left | 300ms | ease-out |
| 节点选中 | scale(1.5) + 邻居透明度渐变 | 500ms | ease-in-out |
| Toast 出现 | slide-up(16px) + fade-in | 300ms | ease-out |
| Modal 出现 | scale(0.95→1) + fade-in | 200ms | ease-out |

### 5.7 间距与栅格

基于 4px 基础栅格 (Tailwind spacing):

```
 4px  — 最小间距 (icon-text gap)
 8px  — 紧凑间距 (badge padding, chip gap)
12px  — 组件内间距 (card padding-x)
16px  — 标准间距 (card padding-y, section gap)
20px  — 段落间距
24px  — 区域间距 (between sections)
32px  — 页面级间距 (page padding-x)
48px  — 大间距 (hero sections)
```

---

## 附录 A: 术语表

| 术语 | 全称 | 说明 |
|---|---|---|
| KG | Knowledge Graph | 知识图谱，由实体(节点)和关系(边)组成 |
| BridgePipeline | — | MinerU → LangExtract 组件对接管道 |
| Grounded / 接地 | — | 实体可在原始 PDF 中定位到具体位置 |
| Entity Type | 实体类别 | 10 种分类: metadata/header/component/metric/dataset/method/definition/equation/reference/claim |
| Node ID | — | KG 节点唯一标识，格式 `n0001` |
| Pipeline | — | MinerU 文档解析引擎 (vs VLM 视觉语言模型) |

## 附录 B: 文档修订记录

| 版本 | 日期 | 修订内容 |
|---|---|---|
| v1.0 | 2026-05-24 | 初始 PRD: 产品概述、核心流程、5 页面设计、10 个关键交互节点、完整 UI 设计规范、响应式适配 |
