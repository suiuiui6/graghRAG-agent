# GraphRAG 多模态知识图谱问答系统 — 项目整合方案

> 基于现有 MinerU 文档解析服务 + LangExtract 实体抽取服务的 RAG 问答系统整合指南

---

## 一、现有资产盘点

在动手整合之前，先明确你已有的东西：

| 组件 | 位置 | 功能 | 状态 |
|------|------|------|------|
| MinerU 文档解析 | `mineru-mvp-test/` | PDF → Markdown + 图片 + Layout JSON | 已可用 (独立 .venv) |
| LangExtract 实体抽取 | `langextract/` | 纯文本 → 结构化实体抽取 | 已可用 (独立 .venv) |
| BridgePipeline 管道 | `integration/` | MinerU 输出 → LangExtract 输入 → KG | 已实现 5 阶段 Pipeline |
| Backend 服务 | `backend/` | FastAPI + LangGraph Agent | 已有基本骨架 |
| Frontend | `frontend/` | Web UI | 待完善 |

**关键认知**：你不是从零开始，而是在已有 BridgePipeline (MinerU -> LangExtract -> KG) 的基础上补齐"检索"和"对话"两层。

---

## 二、推荐目录结构

保持现有结构，在关键位置做增补。建议的完整目录如下：

```
D:\graghRAG-agent\
│
├── mineru-mvp-test/              # [已有] MinerU 文档解析 (独立 .venv)
│   ├── .venv/
│   ├── run_mvp.py
│   └── output/                   # 解析结果缓存
│
├── langextract/                  # [已有] LangExtract 实体抽取 (独立 .venv)
│   ├── .venv/
│   ├── langextract/
│   ├── docs/
│   │   ├── LangExtract-Pipeline-Specification.md
│   │   ├── MinerU-API-Specification.md
│   │   ├── bridge-pipeline-specification-v1.0.md
│   │   └── MinerU_MVP测试配置指南.md_v1.0.md
│   └── output/
│
├── integration/                  # [已有] BridgePipeline + 索引构建 + Agent
│   ├── .env                      # 统一环境变量
│   ├── pipeline.py               # [已有] 5 阶段 Pipeline
│   ├── bridge.py                 # [已有] Format Bridge
│   ├── grounding.py              # [已有] 溯源解析
│   ├── kg_builder.py             # [已有] KG 构建
│   ├── schema.py                 # [已有] 数据模型
│   ├── config/
│   │   └── extraction_examples.yaml
│   │
│   ├── indexing/                 # [新增] 索引构建模块
│   │   ├── __init__.py
│   │   ├── build_indices.py      # 统一索引构建入口
│   │   ├── vector_store.py       # ChromaDB 向量索引
│   │   ├── graph_store.py        # NetworkX 图索引
│   │   └── text_index.py         # BM25 全文本索引
│   │
│   ├── agentic_rag/              # [新增] Agentic-RAG 运行时
│   │   ├── __init__.py
│   │   ├── agent.py              # LangGraph StateGraph 定义
│   │   ├── tools.py              # 5 个 LangChain Tool
│   │   ├── router.py             # 问题分类路由
│   │   ├── fusion.py             # 多路召回融合 + 重排序
│   │   └── supervisor.py         # Supervisor Agent (多 Agent 模式)
│   │
│   ├── output/kg/                # [已有] KG 输出
│   │   ├── nodes.json
│   │   ├── edges.json
│   │   └── integrated_*.jsonl
│   └── output/indices/           # [新增] 索引持久化
│       ├── chroma_db/
│       └── graph_cache.pkl
│
├── backend/                      # [已有] FastAPI 后端
│   ├── .venv/                    # 独立 venv
│   ├── server.py                 # FastAPI 入口
│   ├── models.py                 # 数据模型
│   ├── security.py               # 安全 + Rate Limiting
│   ├── worker.py                 # 异步任务处理
│   ├── oss_uploader.py           # OSS 上传
│   ├── routes/
│   │   ├── health.py             # GET /api/v1/health
│   │   ├── ingest.py             # POST /api/v1/ingest
│   │   ├── query.py              # POST /api/v1/query
│   │   ├── documents.py          # GET/DELETE /api/v1/documents
│   │   └── graph.py              # [新增] GET /api/v1/graph/{doc_id}
│   ├── config/
│   └── uploads/
│
├── frontend/                     # [已有] 前端
│   ├── src/
│   ├── public/
│   └── package.json
│
├── plans/                        # [已有] 规划文档
│   ├── backend-fix-plan.md
│   ├── frontend-fix-plan.md
│   └── workflow-fix-plan.md
│
├── docs/                         # [新增] 项目级规范文档 (见第五节)
│   ├── architecture-overview.md
│   ├── data-flow-specification.md
│   ├── api-contract.md
│   ├── deployment-guide.md
│   └── test-plan.md
│
├── docker-compose.yml            # [新增] 容器编排
└── .gitignore
```

**关键设计原则**:

1. **三独立 venv**：`mineru-mvp-test/.venv`(MinerU 专用) + `langextract/.venv`(LangExtract + BridgePipeline + Agent 共用) + `backend/.venv`(FastAPI 专用)。组件间依赖互不污染。
2. **integration/ 是核心枢纽**：所有离线处理 (索引构建) 和在线推理 (Agent) 的代码都放在 integration 下，与 langextract 共用同一个 .venv。
3. **backend/ 只做薄层 API**：不包含任何索引或 Agent 逻辑，只做 HTTP 路由、任务调度、安全校验。

---

## 三、实施顺序：6 个 Phase

### Phase 0：规范文档确立 (1-2 天) — 先于一切

在写任何新代码之前，先把规范文档定下来。这是最重要的一步，决定了后续所有人(和人 + AI)对系统边界和接口的理解是一致的。

具体要写的文档见第五节。

### Phase 1：索引构建层 (2-3 天)

这是从 KG 到可检索系统的关键一步。BridgePipeline 已经输出了 `nodes.json`(310 个节点) 和 `edges.json`(1529 条边)，现在要把它们变成三种可查询的索引：

| 序号 | 任务 | 输入 | 输出 | 工具 |
|------|------|------|------|------|
| 1.1 | 构建向量索引 | `nodes.json` 中每个 entity 的 label + entity_type | ChromaDB collection | `langchain-chroma` + DeepSeek Embedding |
| 1.2 | 构建图索引 | `nodes.json` + `edges.json` | NetworkX 图对象 | `networkx` |
| 1.3 | 构建全文索引 | `integrated_*.jsonl` 中的 section text | BM25 索引 | `rank-bm25` |
| 1.4 | 编写统一构建脚本 | 以上三种索引 | 一键 `python -m indexing.build_indices` | 自定义脚本 |

**验收标准**：
- `search_vector("Transformer BLEU score")` 返回相关 entity 列表
- `search_kg(entity_type="metric")` 返回子图
- `search_keyword("attention mechanism")` 返回原文片段

### Phase 2：核心 Agent 构建 (3-4 天)

在索引之上构建 LangGraph Agent，这是整个系统的"大脑"。

| 序号 | 任务 | 说明 |
|------|------|------|
| 2.1 | 实现 5 个 LangChain Tool | `search_kg` / `search_vector` / `search_keyword` / `get_entity_detail` / `get_page_context` |
| 2.2 | 实现问题分类路由 | 根据 query 特征路由到不同检索策略 (metric/graph/concept/metadata/hybrid) |
| 2.3 | 实现 LangGraph StateGraph | `classify → search → fusion → generate` 流程 |
| 2.4 | 实现多路召回融合 + 重排序 | Reciprocal Rank Fusion (RRF) 或 Cross-encoder rerank |
| 2.5 | 编写 Agent 入口脚本 | `python -m agentic_rag.agent --query "..."` |

**技术选型**：
- **Agent 框架**：`langgraph` (StateGraph 模式)
- **LLM**：DeepSeek (via `langchain-openai` OpenAI-compatible)
- **Embedding**：DeepSeek `text-embedding-3-small` 或本地 BGE-M3
- **向量存储**：ChromaDB (轻量，适合 MVP；生产可换 Milvus)

**验收标准**：
- "Transformer 的 BLEU 分数是多少？" → 返回具体数值 + 来源页面位置
- "Multi-Head Attention 是什么？" → 返回概念定义 + 关联实体

### Phase 3：API 化 (1-2 天)

将 Agent 包装成 RESTful API，让前端和其他服务可以调用。

| 序号 | 任务 | 说明 |
|------|------|------|
| 3.1 | 完善 `POST /api/v1/ingest` | 上传 PDF → 触发 BridgePipeline → 构建索引 → 返回 task_id |
| 3.2 | 完善 `POST /api/v1/query` | 接收自然语言问题 → 调用 Agent → 返回 {answer, sources, subgraph} |
| 3.3 | 新增 `GET /api/v1/graph/{doc_id}` | 返回 KG 子图数据供前端可视化 |
| 3.4 | 实现异步任务队列 | 使用 FastAPI BackgroundTasks 或 Celery 处理 ingest 长任务 |

**关键接口格式**：

```json
// POST /api/v1/query
// Request
{
  "query": "Transformer 的 BLEU 分数是多少？",
  "doc_id": "87bc1f56",
  "top_k": 5
}

// Response
{
  "answer": "Transformer 在 WMT 2014 EN-DE 上达到 28.4 BLEU...",
  "sources": [
    {
      "node_id": "n0042",
      "label": "BLEU Score",
      "page_idx": 7,
      "bbox_norm": [0.12, 0.45, 0.88, 0.52],
      "relevance": 0.95
    }
  ],
  "subgraph": { "nodes": [...], "edges": [...] },
  "confidence": 0.87
}
```

### Phase 4：前端可视化 (2-3 天)

| 序号 | 任务 |
|------|------|
| 4.1 | 文档上传页面 (拖拽 PDF + 进度条) |
| 4.2 | 问答对话界面 (Chat UI + 历史记录) |
| 4.3 | 答案溯源高亮 (点击 source → PDF 对应位置高亮) |
| 4.4 | 知识图谱子图可视化 (D3.js / vis.js 渲染 entity-relation 网络) |

### Phase 5：端到端测试与优化 (1-2 天)

| 序号 | 任务 |
|------|------|
| 5.1 | 使用 arXiv Transformer 论文跑通完整流程 |
| 5.2 | 覆盖 6 种 query 类型测试用例 |
| 5.3 | 验证 source citation 准确性 (page_idx + bbox → PDF 位置) |
| 5.4 | 性能基准：端到端延迟 < 5 秒 |
| 5.5 | 编写 `test_plan.md` 记录测试结果 |

---

## 四、数据流全景图

帮助理解完整流程：

```
┌─────────────────────────────────────────────────────────────────────┐
│                         离线索引层 (Offline)                         │
│                                                                      │
│  PDF ──► MinerU API ──► full.md + images + layout.json              │
│                              │                                       │
│                              ▼                                       │
│                         Format Bridge                                │
│                    (section 分段 + PositionMap)                       │
│                              │                                       │
│                              ▼                                       │
│                   LangExtract + DeepSeek                             │
│                    (结构化实体抽取 + 关系抽取)                          │
│                              │                                       │
│                    ┌─────────┼─────────┐                             │
│                    ▼         ▼         ▼                             │
│              nodes.json  edges.json   integrated_*.jsonl              │
│                    │         │         │                             │
│                    ▼         ▼         ▼                             │
│              Vector Index  Graph Index  Full-Text Index               │
│              (ChromaDB)    (NetworkX)   (BM25)                       │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                         在线查询层 (Online)                           │
│                                                                      │
│  User Query                                                          │
│      │                                                               │
│      ▼                                                               │
│  ┌─────────────────┐                                                │
│  │ Query Classifier │ → metric / graph / concept / metadata / hybrid │
│  └────────┬────────┘                                                │
│           │                                                          │
│     ┌─────┼─────┬──────────┐                                        │
│     ▼     ▼     ▼          ▼                                        │
│  ┌────┐┌────┐┌──────┐┌──────────┐                                  │
│  │ KG ││Vec ││BM25  ││Metadata  │  ← 并行检索                        │
│  │Tool││Tool││Tool  ││Tool      │                                    │
│  └──┬─┘└──┬─┘└──┬───┘└────┬─────┘                                  │
│     │     │     │          │                                         │
│     └─────┼─────┼──────────┘                                        │
│           ▼                                                          │
│  ┌──────────────────┐                                               │
│  │ Fusion + Rerank  │ ← RRF / Cross-encoder                          │
│  └────────┬─────────┘                                               │
│           ▼                                                          │
│  ┌──────────────────┐                                               │
│  │ LLM Generation   │ ← DeepSeek 生成答案 + 引用                      │
│  └────────┬─────────┘                                               │
│           ▼                                                          │
│  Final Answer + Sources + Subgraph                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 五、规范文档清单 (Phase 0 必需产出)

这些文档应该在写代码之前完成，确保所有人对系统边界和接口理解一致。

### 5.1 项目级规范文档 (放在 `docs/` 下)

| # | 文档 | 文件名 | 核心内容 |
|---|------|--------|----------|
| 1 | **架构全景图** | `architecture-overview.md` | 系统分层架构、组件关系图、技术选型决策记录、部署拓扑 |
| 2 | **数据流规范** | `data-flow-specification.md` | 从 PDF 到最终答案的完整数据流，每个阶段的数据格式定义 (输入/输出 schema)、错误处理策略 |
| 3 | **API 契约** | `api-contract.md` | 所有 REST 端点的 Request/Response JSON Schema、状态码、错误码枚举、认证方式 |
| 4 | **部署运维指南** | `deployment-guide.md` | 环境变量清单、venv 创建步骤、Docker Compose 配置、健康检查端点 |
| 5 | **测试计划** | `test-plan.md` | 6 种 query 类型的测试用例矩阵、验收标准、性能基线 |
| 6 | **环境隔离规范** | `environment-isolation.md` | 三个 .venv 的依赖清单、激活方式、CI/CD 中的环境管理策略 |

### 5.2 组件级规范文档 (已有，需维护)

这些文档已经存在，但应该在 Phase 0 重新审视并更新：

| # | 文档 | 位置 | 状态 |
|---|------|------|------|
| 7 | MinerU API 规范 | `langextract/docs/MinerU-API-Specification.md` | 已有，检查是否需要更新 |
| 8 | MinerU MVP 测试配置指南 | `langextract/docs/MinerU_MVP测试配置指南.md_v1.0.md` | 已有 |
| 9 | LangExtract Pipeline 规范 | `langextract/docs/LangExtract-Pipeline-Specification.md` | 已有 |
| 10 | BridgePipeline 规范 | `langextract/docs/bridge-pipeline-specification-v1.0.md` | 已有 |
| 11 | Agentic-RAG 架构方案 | `integration/Agentic-RAG-Architecture.md` | 已有，内容充分 |

### 5.3 每个规范文档应包含的要素

一个好的规范文档必须回答以下问题：

1. **What**：这个组件/接口做什么？
2. **Input/Output**：输入格式是什么？输出格式是什么？用 JSON Schema 或类型定义精确描述。
3. **Dependencies**：依赖哪些外部服务/环境变量？(例如 DeepSeek API Key、MinerU API URL)
4. **Error Handling**：每种可能的错误场景如何处理？返回什么？
5. **Performance**：预期的延迟、吞吐量、资源消耗。
6. **Examples**：至少 2 个完整的输入输出示例。

---

## 六、关键风险与缓解措施

| 风险 | 影响 | 缓解 |
|------|------|------|
| MinerU API 不稳定/限流 | ingest 流程中断 | 本地缓存解析结果；实现重试机制；支持跳过 MinerU 阶段 (`--cached` 模式) |
| DeepSeek API 调用失败 | 实体抽取或答案生成失败 | 指数退避重试；降级到本地小模型；记录失败 node 供后续补抽 |
| KG 节点过多导致检索慢 | 查询延迟超标 | 限制 k-hop 范围；按 entity_type 预过滤；使用向量 ANN 近似搜索 |
| 三个 .venv 依赖混乱 | 开发环境不可用 | 严格执行环境隔离规范；在 CLAUDE.md 中写明激活步骤；CI 中验证 |
| 前端与后端接口不匹配 | 联调失败 | 先定 API 契约再并行开发；使用 Swagger UI 作为联调基准 |

---

## 七、执行建议

1. **不要跳过 Phase 0**。规范文档看似"不产出代码"，但它决定了后续所有阶段的效率。宁可花 2 天花在文档上，也不要花 5 天在返工上。
2. **保持三个 .venv 的物理隔离**。已有的环境隔离策略 (`mineru-mvp-test/.venv` vs `langextract/.venv` vs `backend/.venv`) 是正确的，不要合并。
3. **先用单文档测试完整链路**。用 arXiv Transformer 论文从 PDF 到答案跑通一次，确认所有边界情况都处理好了，再考虑多文档扩展。
4. **Agent 先做简单再做复杂**。Phase 2 先实现单 Agent (一个 StateGraph 走完 classify→search→generate)，Phase 3 验证通过后再考虑多 Agent 协作 (Supervisor + Sub-agent)。
5. **已有资产充分复用**。`integration/pipeline.py` 的 5 阶段 Pipeline 和 `backend/server.py` 的路由骨架已经可用，新代码应该插入到这些已有框架中，而不是另起炉灶。
