# GraphRAG 问答系统整合方案

## 0. 输入盘点：你手上有什么

| 组件 | 能力 | 输入 | 输出 | 运行环境 |
|---|---|---|---|---|
| **MinerU** | 文档解析 (PDF/DOCX/PPTX/XLSX等11种格式) | 文档文件 | Markdown + 图片 + layout.json | mineru-mvp-test/.venv (独立隔离) |
| **LangExtract** | 结构化实体抽取 | 纯文本 (JSONL/CSV) | nodes.json + edges.json + 标注 | langextract/.venv (独立隔离) |

两个组件各自独立可用，但中间存在一个鸿沟：MinerU 输出的是 Markdown 文本，LangExtract 需要的是结构化分段的文本列表，而且 LangExtract 抽出来的实体没有与原始 PDF 页面位置的对应关系。

---

## 1. 目录结构：推荐的工程组织

```
D:\graghRAG-agent\
├── mineru-service/                  # MinerU 文档解析 (已有, 原名 mineru-mvp-test)
│   ├── .venv/                       # 独立 uv 虚拟环境
│   ├── .env / .env.example
│   ├── run_mineru.py                # MinerU API 调用入口
│   └── output/                      # MinerU 解析缓存
│
├── langextract/                     # LangExtract 实体抽取 (已有)
│   ├── .venv/                       # 独立 uv 虚拟环境
│   ├── .env
│   └── langextract/                 # 核心源码 (不变)
│
├── integration/                     # 组件对接层 (已有)
│   ├── CLAUDE.md                    # BridgePipeline 说明
│   ├── pipeline.py                  # 主编排器: MinerU→Bridge→LangExtract→KG
│   ├── bridge.py                    # 格式桥接: Markdown分段 + 位置映射(PositionMap)
│   ├── grounding.py                 # 溯源解析: 实体→原始PDF页面+bbox
│   ├── kg_builder.py               # KG构建: nodes.json + edges.json 合并去重
│   ├── schema.py                    # 数据类定义 (位置映射/实体/KG节点/边的类型)
│   ├── config/
│   │   └── extraction_examples.yaml # LangExtract few-shot 示例
│   └── output/
│       └── kg/
│           ├── nodes.json           # 最终KG节点
│           └── edges.json           # 最终KG边
│
├── backend/                         # 在线服务层 (已有)
│   ├── .venv/                       # 独立 uv 虚拟环境
│   ├── server.py                    # FastAPI 主入口 (:8000)
│   ├── routes/
│   │   ├── health.py                # GET /health
│   │   ├── ingest.py                # POST /ingest (文档上传 → 触发索引)
│   │   ├── query.py                 # POST /query (KG问答)
│   │   ├── documents.py             # GET /documents, DELETE /documents/:id
│   │   └── graph.py                 # GET /graph/:docId (图数据返回)
│   ├── models.py                    # 数据库/内存模型
│   ├── worker.py                    # 后台异步任务 (Pipeline编排)
│   ├── indexer/                     # 三层索引构建 (待补)
│   │   ├── vector_index.py          # ChromaDB 向量索引
│   │   ├── graph_index.py           # NetworkX 图索引 (已部分在 query.py 中)
│   │   └── text_index.py            # BM25 全文索引
│   ├── agent/                       # Agent 运行时 (待拆分)
│   │   ├── tools.py                 # LangChain Tool 集
│   │   ├── graph_agent.py           # LangGraph StateGraph
│   │   └── supervisor.py            # Supervisor 路由
│   └── uploads/                     # 上传文件存储
│
├── frontend/                        # Web UI (已有)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Upload.tsx           # 上传页
│   │   │   ├── Documents.tsx        # 文档列表
│   │   │   ├── Query.tsx            # 问答页
│   │   │   └── Graph.tsx            # KG可视化大屏
│   │   ├── components/              # 可复用组件
│   │   ├── stores/                  # Zustand 状态管理
│   │   └── api/                     # API 客户端封装
│   └── package.json
│
├── docs/                            # 规范文档集中目录 (顶层)
│   ├── architecture/
│   │   ├── system-architecture-v1.0.md        # 系统架构总览
│   │   └── component-isolation-spec-v1.0.md    # 组件隔离与环境规范
│   ├── pipeline/
│   │   ├── bridge-pipeline-specification-v1.0.md  # MinerU→LangExtract对接规范
│   │   └── grounding-algorithm-v1.0.md              # 溯源算法设计
│   ├── api/
│   │   └── backend-api-architecture-v1.0.md    # REST API 规范
│   ├── agent/
│   │   └── agentic-rag-architecture-v1.0.md    # Agent运行时架构
│   ├── frontend/
│   │   └── frontend-system-design-v1.0.md      # 前端系统设计
│   └── product/
│       └── multimodal-rag-prd-v1.0.md          # 产品需求文档
│
├── tests/                           # 集成测试 (待建)
│   ├── test_pipeline.py             # 端到端Pipeline测试
│   ├── test_query_accuracy.py       # 问答准确性评测
│   └── test_grounding.py            # 溯源准确性验证
│
├── .claude/                         # Claude Code 配置
├── .gitignore
└── README.md
```

### 为什么这样组织？

1. **三层分离**：`mineru-service` / `langextract` 是"原子能力层"，`integration` 是"对接编排层"，`backend` + `frontend` 是"产品交付层"。每一层只依赖下一层，不反向依赖。

2. **独立虚拟环境**：三个 Python 组件各用各的 `.venv`，避免依赖地狱。`integration` 与 `langextract` 共用虚拟环境（因为 integration 需要 import langextract），`mineru-service` 通过 HTTP 调用完全解耦。

3. **规范文档集中管理**：所有 `.md` 规范文档放在顶层 `docs/` 目录下，按架构/管道/API/Agent/前端/产品分类，任何人都能快速找到对应的设计决策依据。

---

## 2. 实施顺序：先做什么，后做什么

### 阶段 0: 能力边界摸底与MVP跑通 (1-2天) -- 已完成

**输入**：两个独立的原子能力组件 (MinerU, LangExtract)
**输出**：一个最小的端到端链路验证过的集成原型

```
MinerU (PDF解析) ──Markdown──► Bridge (格式转换) ──JSONL──► LangExtract (实体抽取)
                                                                    │
                                                                    ▼
                                                        nodes.json + edges.json
```

**交付物清单**：
- [x] `mineru-mvp-test/run_mvp.py` -- 能调通 MinerU API, 产出 Markdown + layout.json
- [x] `langextract/mvp_deepseek_test.py` -- 能调通 LangExtract, 抽取 310 nodes + 1529 edges
- [x] `integration/pipeline.py` -- 一条命令跑通全链路: `python pipeline.py --pdf sample.pdf`
- [x] `integration/bridge.py` -- MinerU Markdown → LangExtract JSONL 格式转换, 附带位置映射
- [x] `integration/grounding.py` -- 实体字符偏移 → 原始 PDF page_idx + bbox 的溯源解析
- [x] `integration/kg_builder.py` -- JSONL 抽取结果 → nodes.json + edges.json 的合并去重
- [x] `integration/config/extraction_examples.yaml` -- 4个 few-shot 示例

**关键验证点**：
- 15页学术论文 PDF → 全链路 109 秒完成
- nodes.json 中 100% 节点携带 `page_idx` 和 `bbox_norm` (可溯源)
- 实体类型覆盖: metric / model_component / method / dataset / hyperparameter / architecture / reference / author

---

### 阶段 1: 架构设计与规范文档沉淀 (1天) -- 在进行中

**目的**：在 MVP 验证可行之后，把所有"隐式知识"写成规范文档，作为后续开发合同。

**必写文档清单** (按优先级排序):

| # | 文档名称 | 核心内容 | 读者 |
|---|---|---|---|
| 1 | `bridge-pipeline-specification-v1.0.md` | MinerU输出 → Bridge转换 → LangExtract输入 的完整数据流; 位置映射(PositionMap)数据结构; grounding算法; KG schema (node/edge的字段定义) | 后端工程师 |
| 2 | `system-architecture-v1.0.md` | 离线索引层 + 在线查询层 的分层架构; 组件拓扑; 数据流向; 部署拓扑 | 全体工程师 |
| 3 | `component-isolation-spec-v1.0.md` | 三个 Python 组件的虚拟环境边界; 环境变量命名空间; API Key 配置规范; 组件间通信协议 | DevOps / 后端 |
| 4 | `backend-api-architecture-v1.0.md` | FastAPI 路由树; 请求/响应 schema; 异步任务状态机; 错误码规范; 文件上传安全 | 前后端工程师 |
| 5 | `agentic-rag-architecture-v1.0.md` | Agent 运行时设计: 5个工具定义; LangGraph StateGraph; 问题分类路由; 多路召回融合; E2E查询示例 | Agent工程师 |
| 6 | `frontend-system-design-v1.0.md` | 页面路由/组件树; Zustand 状态管理; 数据流; 响应式布局; D3力导向图集成 | 前端工程师 |
| 7 | `multimodal-rag-prd-v1.0.md` | 产品一句话; 核心场景 (5个); 业务痛点; 用户旅程; 页面交互逻辑; V1.0 边界 | PM / 全体 |

**规范文档的质量标准**：
- 每份文档必须有"版本号 + 日期 + 关联规范索引"
- 关键技术决策必须写明"为什么选A不选B" (例如: 为什么用 NetworkX 而不是 Neo4j 做 MVP)
- 数据 schema 必须用表格列出字段名/类型/必填/示例值
- 代码片段必须是可执行的伪代码，不能是纯描述

---

### 阶段 2: 在线查询引擎 (Agentic RAG Runtime) (2-3天) -- 已启动

**输入**：阶段0产出的 `nodes.json` + `edges.json`
**输出**：一个能回答问题的 LangGraph Agent

```
User Query
    │
    ▼
Supervisor Agent (LangGraph StateGraph)
    │
    ├──► classify_query (问题类型分类)
    │
    ├──► KG Search Tool (图遍历: 1-hop / k-hop neighbor)
    ├──► Vector Search Tool (语义检索: 实体向量相似度)       ← 待补
    ├──► Keyword Search Tool (BM25 全文检索: section文本)     ← 待补
    ├──► Entity Detail Tool (单实体详情: 属性+关联+页面位置)
    └──► Page Context Tool (原文回溯: 获取PDF页面上下文)
    │
    ▼
Fusion + Rerank (多路召回合并去重排序)
    │
    ▼
LLM Generation (DeepSeek 生成最终答案 + source citation)
```

**核心工作**：
1. 实现 5 个 LangChain Tool (其中3个已完成: kg_search / entity_detail / page_context)
2. 补充 Vector Search Tool (使用 ChromaDB 或 FAISS, 向量化所有 node['label'])
3. 补充 Keyword Search Tool (使用 rank-bm25, 索引 JSONL 的所有 section 文本)
4. 实现 LangGraph StateGraph (classify → search(s) → fusion → generate → [done | retry])
5. 实现问题分类路由: metric / graph / concept / metadata / hybrid
6. 实现答案溯源: 每条答案必须携带 `[node_id, page_idx, bbox_norm, source_text]`

**关键设计决策**：
- MVP 阶段图存储用 NetworkX (内存图), 不上 Neo4j -- 310 nodes 完全够用
- 向量存储用 ChromaDB (本地持久化), 不上 Milvus -- 单机部署即可
- LLM 用 DeepSeek Chat API (OpenAI Compatible), 通过 `langchain-openai` 适配

---

### 阶段 3: 后端 API 化 (1-2天) -- 已启动

**输入**：阶段2的 Agent + 阶段1的 API 规范
**输出**：FastAPI 服务, 提供全功能 REST API

**API 端点设计** (已实现大部分):

```
POST   /api/v1/ingest                   # 上传文档 + 触发离线索引
  Body: multipart/form-data {file, language, ocr, formula, table}
  Response: {task_id, status: "queued"}

GET    /api/v1/status/{task_id}          # 查询索引任务进度
  Response: {status, stage, progress_pct, nodes_count, edges_count}

POST   /api/v1/query                    # 知识图谱问答
  Body: {doc_id, question, top_k}
  Response: {answer, sources: [{node_id, label, page_idx, bbox, snippet}], confidence}

GET    /api/v1/documents                # 已索引文档列表
GET    /api/v1/documents/{doc_id}       # 文档详情
DELETE /api/v1/documents/{doc_id}       # 删除文档及其KG

GET    /api/v1/graph/{doc_id}           # 返回完整KG数据 (供前端可视化)
GET    /api/v1/health                   # 健康检查
```

**关键后端设计**：
- **异步任务队列**: 使用 `asyncio.create_task` (MVP), 未来升级到 Celery + Redis
- **任务状态机**: queued → uploading → parsing → extracting → indexing → completed | failed
- **文件安全**: 上传文件通过 UUID 重命名 + 文件类型白名单 + 大小限制 200MB
- **CORS**: 开发阶段允许所有来源, 生产环境收紧到前端域名

---

### 阶段 4: 前端 UI (2-3天) -- 已启动

**输入**：阶段3的 API + 阶段1的前端设计文档
**输出**：React + TypeScript + Tailwind CSS Web应用

**核心页面**：
1. **UploadPage** (`/upload`): 拖拽上传区 + 参数配置面板 + 实时进度条 (5阶段动画)
2. **DocumentsPage** (`/documents`): 文档卡片列表, 显示 node/edge 统计, 支持删除
3. **QueryPage** (`/query/:docId`): 聊天式问答界面, 每条答案带 source citation 展开
4. **GraphPage** (`/graph/:docId`): D3.js 力导向图, 支持 entity_type 筛选, 节点点击弹详情

**前端技术栈**：
- React 18 + TypeScript
- Tailwind CSS (样式)
- Zustand (状态管理)
- React Router v6 (路由)
- D3.js (知识图谱可视化)
- Vite (构建)

---

### 阶段 5: 集成测试与评测 (1天) -- 待做

**输入**：阶段3的后端 + 阶段4的前端
**输出**：测试报告 + bug修复

**测试用例覆盖 6 种查询类型**：

| 查询类型 | 示例问题 | 预期Agent路径 | 验证点 |
|---|---|---|---|
| metric_search | "BLEU分数是多少？" | KG tool → entity lookup | 数值精确匹配 |
| graph_traversal | "Encoder和Decoder的关系？" | KG tool → k-hop expand | 子图包含两者 |
| semantic_search | "什么是Multi-Head Attention？" | Vector tool → top-k | 语义相关实体 |
| keyword_search | "论文引用了哪些工作？" | BM25 tool → section | 原文定位准确 |
| metadata_search | "作者是谁？发表在哪？" | entity_detail tool | 元数据完整 |
| hybrid_all | "总结这篇论文的方法" | 多路并行 → fusion | 答案覆盖全 |

**量化评测指标**：
- 答案正确率 (人工评判): 目标 > 80%
- 溯源准确率 (page_idx + bbox 是否正确定位到原文): 目标 > 90%
- 端到端延迟 (从 query 到 answer): 目标 < 5秒
- 索引吞吐 (15页论文的完整 Pipeline): 目标 < 120秒

**边界条件测试**：
- 空文档 / 极短文档 (1页)
- 超大文档 (100+ 页)
- 非英文文档 (中文论文)
- 扫描件 PDF (需要 OCR)
- 并发查询压测 (5个并发)

---

### 阶段 6: 部署与投产 (1天) -- 待做

**输入**：阶段5验证通过的系统
**输出**：可部署的服务包

**部署方式** (按推荐度排序):
1. **Docker Compose** (推荐): 三个容器 (backend + frontend + chromadb), 一条命令启动
2. **单机直接运行**: 适合开发调试, Python + Node 直接启动
3. **云部署**: backend → 云服务器, frontend → Vercel/Netlify, ChromaDB → 云数据库

**Docker Compose 拓扑**:
```
services:
  backend:    FastAPI :8000, 挂载 ./uploads, ./output
  frontend:   Nginx :3000, 反代到 backend
  chromadb:   ChromaDB :8001, 持久化到 volume
```

---

## 3. 规范文档体系总览

### 3.1 文档分层

```
Layer 1: 产品层 (给所有人看)
  └── multimodal-rag-prd-v1.0.md
      "为什么做这个产品, 解决了什么问题, 用户怎么用"
      关键词: 场景 → 角色 → 旅程 → 页面交互 → 边界

Layer 2: 架构层 (给工程师看)
  ├── system-architecture-v1.0.md
  │   "整个系统长什么样, 数据怎么流, 组件怎么通信"
  │   关键词: 分层架构 → 数据流 → 部署拓扑
  └── component-isolation-spec-v1.0.md
      "各组件怎么隔离, 虚拟环境/API Key/端口怎么管"
      关键词: .venv 边界 → 环境变量 → 通信协议

Layer 3: 接口层 (给前后端工程师看)
  ├── backend-api-architecture-v1.0.md
  │   "后端提供什么 API, 请求/响应长什么样, 怎么处理错误"
  │   关键词: 路由树 → Schema → 状态机 → 错误码
  └── frontend-system-design-v1.0.md
      "前端页面怎么设计, 组件树, 状态管理, 交互逻辑"
      关键词: 路由 → 组件 → Store → API Client

Layer 4: 算法层 (给核心开发者看)
  ├── bridge-pipeline-specification-v1.0.md
  │   "MinerU → Bridge → LangExtract 完整数据流, 每个字段的来源和含义"
  │   关键词: PositionMap → grounding → KG Schema
  ├── agentic-rag-architecture-v1.0.md
  │   "Agent 怎么设计: 工具定义, 图结构, 路由逻辑, 融合策略"
  │   关键词: Tool → StateGraph → Supervisor → Rerank
  └── grounding-algorithm-v1.0.md
      "溯源算法的设计: 字符偏移→ bbox → page_idx 的数学推导"
      关键词: origin\_char\_idx → PositionMap → bbox\_norm
```

### 3.2 每份文档的必备要素 (模板)

```markdown
# 文档标题

> **版本**: vX.Y | **日期**: YYYY-MM-DD | **状态**: Draft/Review/Approved
>
> **关联规范**: [相关文档列表]
> **作者**: [谁写的]

## 1. 概述 (1-2句话说明本文档的目的和范围)

## 2. 核心概念 (定义本文档使用的专有名词)

## 3. 设计详情 (本文档的核心内容: 架构图/数据流/算法/接口)
  - 每个设计决策后面跟一个 "Why" 解释

## 4. 数据契约 (Schema / 接口签名 / 类型定义, 用表格呈现)

## 5. 实现约束 (必须遵守的规则, 用 checklist)

## 6. 示例/用例 (最小可运行示例或典型使用场景)

## 7. 修订历史
  | 版本 | 日期 | 变更内容 |
```

---

## 4. 关键设计原则 (贯穿所有阶段)

### 原则 1: 组件隔离, 接口明确
- 每个 Python 组件独立 `.venv`, 互不污染
- 组件间只通过明确的接口通信: HTTP API (MinerU) / Python import (LangExtract) / 文件系统 JSON (KG 输出)
- 原则: 任何一个组件替换实现, 不影响其他组件

### 原则 2: 离线与在线分离
- **离线索引层** (Pipeline): 耗时操作, 允许分钟级延迟, 面向吞吐优化
  - MinerU 解析 (60-90s)
  - LangExtract 抽取 (3-5s)
  - 向量/图/全文索引构建 (1-2s)
- **在线查询层** (Agent): 实时响应, 毫秒级延迟, 面向延迟优化
  - 问题分类 (100ms)
  - 多路检索 (200ms each, 可并行)
  - 答案生成 (500-2000ms)

### 原则 3: 一切可溯源
- 每个 KG node 必须携带 `page_idx` + `bbox_norm` + `grounding_status`
- 每个答案必须携带 `sources` 数组, 每条 source 可定位到 PDF 中的具体位置
- 这是 RAG 系统对抗幻觉的"定海神针"

### 原则 4: MVP 先跑通, 再完善
- 先做一个15页论文的完整链路, 验证 109 秒能跑通
- 验证通过后再写规范文档 (避免"纸上谈兵")
- 规范文档写完之后再工程化 (FastAPI + React)

### 原则 5: 规范文档即"开发合同"
- 前后端通过 API 规范文档对齐接口预期
- 集成交付通过 Pipeline 规范文档对齐数据格式
- 产品决策通过 PRD 锁定 V1.0 边界, 避免范围蔓延

---

## 5. 当前进度总结 (截至 2026-05-25)

| 阶段 | 状态 | 完成度 | 剩余关键工作 |
|---|---|---|---|
| 阶段0: MVP 验证 | 已完成 | 100% | -- |
| 阶段1: 规范文档 | 基本完成 | 85% | grounding-algorithm 独立文档待写; 文档移到顶层 docs/ 目录 |
| 阶段2: Agent 引擎 | 已启动 | 60% | Vector Search Tool 待补; Keyword Search Tool 待补; Fusion Rerank 待优化 |
| 阶段3: 后端 API | 已启动 | 70% | 用户上传/文件管理接口完善; 异步任务状态机完善 |
| 阶段4: 前端 UI | 已启动 | 50% | KG 可视化大屏待完善; 移动端适配 |
| 阶段5: 集成测试 | 未开始 | 0% | 6类查询的完整评测; 边界条件测试 |
| 阶段6: 部署 | 未开始 | 0% | Docker Compose 配置; 部署文档 |

---

## 6. 给下一个接手者的接力清单

1. **第一个要读的规范文档**: `multimodal-rag-prd-v1.0.md` -- 理解产品全貌
2. **第一个要跑的命令**: `cd integration && python pipeline.py --cached ../mineru-mvp-test/output/87bc1f56` -- 验证核心链路
3. **第一个要补的功能**: Vector Search Tool -- 让 Agent 能做语义检索, 而不只是图遍历
4. **第一个要写的测试**: `test_query_accuracy.py` -- 基于 Transformer 论文跑一遍 6 类查询, 记录基线指标
5. **第一个要解决的技术债**: 把分散在各子目录的 `.md` 文档集中到顶层 `docs/` 目录, 建立文档索引
