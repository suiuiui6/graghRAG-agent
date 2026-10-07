# RAG 系统工程蓝图 v1.1

> 基于 graghRAG-agent 现有资产（BridgePipeline / KG-RAG MVP），构建可落地的完整 RAG 工程方案。
> 本文档是开发实施的唯一真相源，所有模块实现必须对齐本文档定义的接口与交互协议。
>
> **v1.1 适配场景**：企业项目报告（千级文档），核心查询：制度查询 / 流程归属 / 数据指标。
> **v1.0 → v1.1 变更摘要**：实体类型体系重构（学术→企业）、文档处理扩展（PDF+DOCX+XLSX）、
> KG 路权重提升（企业实体关系查询不可替代）、多 Query 路加入核心召回（企业表述多样性高）。
> **评审修订 (2026-06-08)**：修复 RRF 候选池计数、Table Recall 宽表补充、跨路数值冲突检测、
> chunks-Documents 数据流闭环、Phase 排序修正、Embedding 迁移路径、企业 KG 边关系体系、
> 配置中心规范、旧 KG 数据废弃策略、DOCX/XLSX 路由逻辑、project_id 识别、前端适配清单。

---

## 目录

1. [系统架构总览](#1-系统架构总览)
2. [核心必须模块](#2-核心必须模块)
   - 2.1 [文档处理模块](#21-文档处理模块)
   - 2.2 [Embedding 模块](#22-embedding-模块)
   - 2.3 [向量数据库](#23-向量数据库)
   - 2.4 [检索模块](#24-检索模块)（含 Query 预处理 / Query 向量化 / 多路召回 / Rerank 精排 / 冗余过滤）
   - 2.5 [Prompt 模块](#25-prompt-模块)
   - 2.6 [LLM 生成模块](#26-llm-生成模块)
3. [可选增强模块](#3-可选增强模块)
4. [模块间交互流程与数据流](#4-模块间交互流程与数据流)
5. [技术选型决策](#5-技术选型决策)
6. [实施路线图](#6-实施路线图)
7. [与现有资产的对接关系](#7-与现有资产的对接关系)

---

## 1. 系统架构总览

```
                        RAG 完整工程架构
┌──────────────────────────────────────────────────────────────────────────┐
│                         OFFLINE（离线索引构建）                            │
│                                                                          │
│  PDF/DOCX                                                                │
│     │                                                                    │
│     ▼                                                                    │
│  ┌─────────────────┐     ┌──────────────────┐                           │
│  │ ① 文档处理模块   │────►│ ② Embedding 模块  │                           │
│  │ (清洗/分块/元数据)│     │ (文本→向量)       │                           │
│  └─────────────────┘     └────────┬─────────┘                           │
│                                   │                                      │
│                    ┌──────────────┼──────────────┐                       │
│                    ▼              ▼              ▼                        │
│             ┌──────────┐  ┌───────────┐  ┌───────────┐                 │
│             │③ 向量数据库│  │ KG 图索引  │  │ 全文索引   │                 │
│             │ (ChromaDB)│  │(NetworkX) │  │ (BM25)    │                 │
│             └──────────┘  └───────────┘  └───────────┘                 │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                          ONLINE（在线问答）                               │
│                                                                          │
│  User Query（制度查询 / 流程归属 / 数据指标）                        │
│     │                                                                    │
│     ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                       ④ 检索模块（5 步流水线）                      │   │
│  │                                                                  │   │
│  │  4.1 Query 预处理     4.2 Query 向量化     4.3 多路召回           │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │   │
│  │  │意图识别/改写  │───►│query→vector  │───►│向量+表格+KG  │       │   │
│  │  │数值条件提取   │    │(同Embedding  │    │+BM25 五路并行│       │   │
│  │  │实体类型推断   │    │ 模型)        │    │召回          │       │   │
│  │  └──────────────┘    │ 模型)        │    └──────┬───────┘       │   │
│  │                      └──────────────┘           │               │   │
│  │                                                 ▼               │   │
│  │  4.5 冗余过滤              4.4 Rerank 精排                      │   │
│  │  ┌──────────────┐        ┌──────────────────┐                  │   │
│  │  │去重/合并/截断 │◄───────│RRF 粗排(100→20)  │                  │   │
│  │  │溯源标记注入   │        │Cross-encoder(20→5) │                │   │
│  │  └──────────────┘        └──────────────────┘                  │   │
│  └────────────────────────────┬─────────────────────────────────────┘   │
│                               │                                         │
│                               ▼ RetrievalResult (10 chunks + metadata) │
│  ┌─────────────────┐                                                     │
│  │ ⑤ Prompt 模块    │── 系统指令 + 检索结果上下文拼接                      │
│  │ (上下文拼接)     │── Token 预算控制                                    │
│  └────────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│  ┌─────────────────┐                                                     │
│  │ ⑥ LLM 生成模块   │── 答案生成 + 引用溯源                                │
│  │ (答案生成/溯源)  │── 格式校验                                          │
│  └─────────────────┘                                                     │
│                                                                          │
│  [可选增强]                                                              │
│  ┌──────────┐  ┌──────────┐                                             │
│  │效果评估   │  │自修正     │                                             │
│  └──────────┘  └──────────┘                                             │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.1 与现有 MVP 的关系

```
现有 MVP (已实现)              本蓝图补齐
─────────────────────        ─────────────────
BridgePipeline → KG          文档处理模块（产出 chunk）
NetworkX 图索引              向量数据库（ChromaDB）
KG-only 检索（4 tools）      多路检索（向量 + KG + BM25）
create_agent 单 Agent        Prompt 模块（独立可控）
DeepSeek 生成                LLM 生成模块（带溯源校验）
```

---

## 2. 核心必须模块

---

### 2.1 文档处理模块

**必要性：必须** — RAG 系统的数据源入口，无此模块后续所有环节无法运作。

**企业文档（项目报告）特征**：
- 格式多样：PDF 扫描件 + DOCX 正文 + XLSX 数据附表 混合存在
- 结构异构：封面→项目概述→预算→进度→风险→验收，不同项目差异大
- 关键元数据往往不在正文而在表格/附件中（如预算执行率、里程碑日期）

#### 功能定义

接收原始文档（PDF / DOCX / XLSX / Markdown），完成格式解析、文本清洗、分块、元数据提取，输出标准化的文档片段列表。

#### 核心职责

| 职责 | 说明 |
|------|------|
| 多格式解析 | PDF → MinerU API；DOCX → python-docx 直接提取；XLSX → openpyxl 结构化提取 |
| 表格提取 | DOCX/XLSX 中的表格 → 保留行列结构 → 转为结构化 JSON（不摊平为纯文本） |
| 文本清洗 | 去除页眉页脚、水印、模板固定文字、多余空白 |
| 智能分块 | 按章节标题边界切割，表格类内容独立成 chunk |
| 元数据提取 | 每个 chunk 标记：来源文档、章节归属、项目编号、实体类型标签 |
| 重复过滤 | 跨文档重复段落去重（企业项目报告常有多份文件引用同一段制度原文） |

#### 关键实现点

**多格式解析路由**：

```python
def parse_document(file_path: str) -> list[Section]:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _parse_pdf_via_mineru(file_path)   # 复用 MinerU API
    elif ext == ".docx":
        return _parse_docx(file_path)             # python-docx
    elif ext == ".xlsx":
        return _parse_xlsx_structured(file_path)  # openpyxl, 保留表格结构
    elif ext == ".md":
        return _parse_markdown(file_path)         # 直接按标题分段
```

**DOCX 解析要点**：
- `python-docx` 提取段落 + 表格，按标题样式（Heading 1-4）建立层级
- 表格内容以 JSON 结构存储：`{"type": "table", "headers": [...], "rows": [[...], ...]}`
- 不摊平为纯文本——表格结构对"数据指标"类查询至关重要

**DOCX/XLSX 与 MinerU 的路由决策**：

```
PDF  → MinerU API（现有，不可替代，PDF 布局解析质量最高）
DOCX → python-docx 本地解析（推荐，保留标题层级+表格结构）
       备选: 也可交给 MinerU API 解析（MinerU 支持 DOCX，但表格结构信息不如本地解析可控）
XLSX → openpyxl 本地解析（推荐，结构化提取 Sheet/表头/数据行）
       备选: 转为 PDF 再走 MinerU 路径（仅当 openpyxl 无法处理复杂格式时使用）
```

**关键决策原则**：
- **DOCX/XLSX 优先本地解析**：python-docx 和 openpyxl 对 Office 格式的结构化提取优于将文档转为 PDF 再走 MinerU 的图像/布局识别路径。
- **PDF 仍走 MinerU**：PDF 是最终呈现格式，本地无等效解析能力。
- **backend/worker.py 需更新路由逻辑**：当前 worker 将所有文件通过 OSS 上传后交给 MinerU API。需在 worker 中增加格式判断——DOCX/XLSX 直接本地解析产出 Section + chunks，PDF 走原有 MinerU → BridgePipeline 流程。

**XLSX 解析要点**：
- `openpyxl` 逐 Sheet 读取，每个 Sheet 作为一个独立 section
- 识别表头行（第 1 行或前 2 行），后续行作为数据记录
- 输出格式：`{"sheet_name": "预算明细", "headers": ["科目","预算","实际","执行率"], "rows": [["差旅", 50, 42, "84%"], ...]}`

**分块策略（三级，按场景切换）**：

```
Level 1 — 固定大小分块（baseline）
  chunk_size=512 tokens, overlap=64 tokens
  适用：快速原型

Level 2 — 章节语义分块（推荐，企业项目报告最优）
  基于标题层级（一、/(一)/1./1.1）切割，保持章节完整性
  表格独立成 chunk，附带结构化 JSON
  适用：项目报告（含明确的章节结构）

Level 3 — 实体感知分块
  利用 KG 产出的 entity（人员/部门/指标）聚合上下文窗口
  适用：KG 增强检索
```

**元数据 schema（企业版，每个 chunk 必带）**：
```python
@dataclass
class ChunkMetadata:
    chunk_id: str                # c{00001..99999}
    source_file: str             # 来源文件名（如 "XX项目中期报告_v2.docx"）
    source_format: str           # "pdf" | "docx" | "xlsx" | "md"
    page_idx: int | None         # 页码（PDF 专用，其他格式可为 None）
    section_path: list[str]      # 章节路径 ["三、项目进展", "3.1 里程碑完成情况"]
    content_type: str            # "text" | "table" | "mixed"
    table_json: dict | None      # 表格结构数据（仅 table/mixed 类型）
    entity_types: list[str]      # 关联的实体类型
    project_id: str | None       # 项目编号（如有）
    token_count: int
    char_start: int
    char_end: int
```

**`project_id` 自动识别规则**（优先级从高到低）：

```python
def extract_project_id(file_path: str, section_title: str, chunk_text: str) -> str | None:
    """
    从文件路径、章节标题、正文中自动识别项目标识。
    规则优先级:
    1. 文件名中的项目编号模式 → 如 "XX项目中期报告_v2.docx" → "XX"
    2. 章节标题中的项目名称 → 如 "三、XX项目建设进展" → "XX项目"
    3. 正文前 500 字符中的项目编号 → 如 "项目编号: PJ-2026-042" → "PJ-2026-042"
    4. 无匹配 → None，标注 "__unassigned__"
    """
```

对于混合目录（包含多个项目报告），应额外提供一个可选的 `project_id_mapping.json` 配置文件，手动指定文件名到项目 ID 的映射，覆盖自动识别。

#### 输入 / 输出

```
输入：
  - 文件目录: /data/project_reports/
    ├── XX项目立项报告.pdf
    ├── XX项目中期报告_v2.docx
    ├── XX项目预算明细.xlsx
    └── ...

输出：
  - chunks.jsonl（流向 Embedding → ChromaDB 向量检索路）
    每行: {chunk_id, text, content_type, table_json?, metadata: {...}}

  - 同时，对于需要走 KG 路的 PDF 文档，MinerU 解析结果仍然通过
    BridgePipeline → LangExtract 产出节点/边（复用现有 pipeline.py 流程）。
    文档处理模块与 BridgePipeline 共享 MinerU 的缓存解析结果。
```

#### chunks 与 BridgePipeline Documents 的关系

文档处理模块产出两套数据，服务于不同召回路：

```
同一份 MinerU 解析结果
    │
    ├──→ 文档处理模块（分块器）
    │       ├── 按章节语义分块 → chunks.jsonl
    │       └── 流向: Embedding → ChromaDB（Vector 路）
    │                  BM25 倒排索引（BM25 路）
    │                  DuckDB 内存表（Table 路）
    │
    └──→ BridgePipeline（现有流程，不变）
            ├── section 分段 → list[Document]
            ├── LangExtract 实体抽取 → AnnotatedDocument
            └── 流向: KG 构建 → NetworkX（KG 路）
```

**关键约束**：
- **chunks 和 Documents 源自同一份 MinerU 输出**，但加工路径不同。chunks 按章节边界切割为固定结构（附 `ChunkMetadata`），Documents 按 BridgePipeline 现有逻辑分段（附 `PositionMap` 溯源）。
- **KG 路的实体与 Vector 路的 chunk 通过 `entity_type` 标签关联**。在 KG 构建阶段，每个节点标注的 `entity_type` 与 chunk 的 `metadata.entity_types` 使用同一枚举体系，确保 KG 检索返回的实体能通过 `entity_type` 反查相关 chunk。
- DOCX/XLSX 本地解析的 Section 同时产出 chunks 和 Documents，不经过 MinerU 环节。

#### 与现有资产对接

- PDF 路径复用 MinerU API + BridgePipeline
- DOCX/XLSX 路径为新增，需添加 `python-docx` `openpyxl` 依赖

---

### 2.2 Embedding 模块

**必要性：必须** — 向量检索的基础，决定语义匹配的上限。

#### 功能定义

将文档处理模块产出的 chunk 文本转换为固定维度的语义向量。

#### 核心职责

| 职责 | 说明 |
|------|------|
| 文本向量化 | chunk text → float[dim] 向量 |
| 批量处理 | 支持批量 embedding，控制 API 调用频率 |
| 向量归一化 | L2 归一化，保证余弦相似度计算等价于内积 |
| 缓存管理 | 已计算向量落盘缓存，避免重复调用 |

#### 关键实现点

**模型选型决策矩阵**：

| 模型 | 维度 | 中文支持 | 成本 | 推荐场景 |
|------|------|----------|------|----------|
| `text-embedding-3-small` | 1536 | 中 | $0.02/1M tokens | MVP 快速启动 |
| `BGE-M3` (本地) | 1024 | 优 | 免费 | 生产环境，数据不出域 |
| `BGE-large-en` (本地) | 1024 | 英 | 免费 | 英文论文场景 |
| `deepseek-v4-pro` embedding | 4096 | 优 | ? | 统一供应商 |

**推荐方案**：MVP 阶段用 `text-embedding-3-small`（OpenAI 兼容，DeepSeek base_url 可复用）；生产阶段切换 `BGE-M3` 本地部署。

**⚠️ 模型迁移路径（MVP → 生产）**：

两个模型维度不同（1536 vs 1024），ChromaDB collection 创建后维度不可变。迁移需要全量重建索引：

```
迁移步骤（预估耗时：千级文档 ~10 分钟）：
1. 用 BGE-M3 新建 collection "rag_docs_v2"（1024-dim）
2. 遍历所有 chunk，用 BGE-M3 重新向量化
3. 批量写入新 collection
4. 验证检索精度（抽样 50 条 query，对比 old vs new collection Recall@10）
5. 原子切换：更新应用配置指向新 collection
6. 旧 collection 保留 7 天作为回滚备份
```

如果预计短期内会切换到 BGE-M3，建议 MVP 阶段直接使用 BGE-M3（跳过 text-embedding-3-small），避免迁移成本。

```python
# 伪代码：embedding 接口
def embed_chunks(chunks: list[dict], model: str = "text-embedding-3-small") -> list[list[float]]:
    """
    批量向量化 chunk 文本。
    内置：batch_size=20, retry on rate limit, cache hit 跳过。
    """
    ...
```

#### 输入 / 输出

```
输入：
  - chunks.jsonl（来自文档处理模块）
  - 每个 chunk 的 text 字段

输出：
  - embeddings.jsonl    # 每行: {chunk_id, vector: [f32×dim], model, timestamp}
  或直接写入 ChromaDB（省去中间文件）
```

---

### 2.3 向量数据库

**必要性：必须** — RAG 的存储核心，提供高效向量检索。

#### 功能定义

存储 embedding 向量及对应 chunk 元数据，提供 top-k 相似度检索。

#### 核心职责

| 职责 | 说明 |
|------|------|
| 向量持久化 | 向量 + metadata 落盘存储 |
| 近似最近邻检索 | 给定 query vector，返回 top-k 相似 chunk |
| 元数据过滤 | 支持按 entity_type / page_idx / section 预过滤 |
| 数据管理 | 支持增量写入、按 source_file 删除重建 |

#### 关键实现点

**存储引擎选型**：

| 引擎 | 部署 | 规模 | 推荐场景 |
|------|------|------|----------|
| ChromaDB | 嵌入式，零运维 | <100K docs | MVP / 中小规模 |
| Milvus Lite | 嵌入式 | <1M docs | 数据量增长后 |
| pgvector | 依附 PostgreSQL | <10M docs | 已有 PG 基础设施时 |

**索引构建**：
```
Index Schema (ChromaDB collection):
  collection_name: "rag_docs"
  embedding_function: text-embedding-3-small (or local BGE)
  metadata fields:
    - chunk_id: str
    - source_file: str
    - page_idx: int
    - section_title: str
    - entity_types: list[str]   # 来自 KG 的实体类型标签
    - token_count: int
```

**检索性能优化**：
- 默认 HNSW 索引（ChromaDB 内置）
- 元数据预过滤减少搜索空间
- 对高频 query 做结果缓存（TTL 5min）

#### 输入 / 输出

```
输入：
  - chunks.jsonl + embeddings（来自 ①② 模块）

存储：
  - ChromaDB 持久化目录: integration/output/vectordb/

检索输出：
  - top_k 结果列表，每条包含：
    {chunk_id, text, score, metadata: {page_idx, section_title, entity_types}}
```

---

### 2.4 检索模块

**必要性：必须** — 连接用户 Query 与知识库的关键环节，直接影响答案质量。

检索模块内部是 **5 步串行流水线**，每一步有明确的输入/输出契约：

```
User Query
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 1: Query 预处理    → 改写 + 意图 + 实体类型推断         │
│  Step 2: Query 向量化    → 原始/改写 query → embedding vectors│
│  Step 3: 多路召回        → 向量+表格+KG+BM25+多Query 五路并行 │
│  Step 4: Rerank 精排     → RRF 粗排 → Cross-encoder 精排    │
│  Step 5: 冗余过滤+溯源   → 去重/合并/截断 + 溯源标记注入     │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
              RetrievalResult (3~5 chunks, 带溯源)
```

---

#### 2.4.1 Step 1：Query 预处理

**职责**：对原始 Query 做规范化处理，输出改写 query、意图标签、实体类型提示，为后续召回提供约束条件。

| 子步骤 | 说明 |
|--------|------|
| 意图识别 | 判断问题类型：`policy_lookup`（制度查询）/ `process_attribution`（流程归属）/ `metric`（数据指标）/ `hybrid`（综合） |
| Query 改写 | 口语→书面、省略补全、指代消解（如"那个项目的预算花了多少"→"XX项目预算执行率"） |
| 实体类型推断 | 根据意图输出优先检索的 entity_type 列表 |

**实现方式**：轻量 LLM 调用（1 次 round-trip，不依赖检索结果）。

```python
QUERY_PREPROCESS_PROMPT = """\
Analyze the user's question about enterprise project reports and output JSON:
- rewritten: a precise, search-friendly version of the query
- intent: one of [policy_lookup, process_attribution, metric, hybrid]
  * policy_lookup: asking about rules, regulations, standards, procedures
  * process_attribution: asking who is responsible, approval chain, department ownership
  * metric: asking about numbers, budget, progress, completion rates
  * hybrid: combines multiple types above
- entity_types: list of entity types to prioritize (from:
  project_metadata, person_role, process_step, metric,
  milestone, deliverable, risk_item, regulation_ref, department, timeline_event)

User query: {query}
Output ONLY valid JSON:
"""
```

**意图枚举对照表**：

| 意图 | 典型问法 | 优先实体类型 | 优先召回路 |
|------|---------|-------------|-----------|
| `policy_lookup` | "XX项目的变更管理流程是什么" | `regulation_ref`, `process_step` | Vector + BM25 |
| `process_attribution` | "谁负责XX项目的质量审核" | `person_role`, `process_step`, `department` | Vector + KG |
| `metric` | "XX项目的预算执行率" | `metric`, `milestone`, `project_metadata` | KG + Vector |
| `hybrid` | "XX项目延期原因和责任人" | 全面 | 五路并行 |

**输入 / 输出**：

```
输入：
  - raw_query: str
  - chat_history: list[dict] | None   # 多轮对话时用于指代消解

输出：
  - PreprocessedQuery:
    {
      "original": "那个项目的预算花了多少",
      "rewritten": "XX项目预算执行率及明细",
      "intent": "metric",
      "entity_types": ["metric", "project_metadata", "milestone"]
    }
```

**设计决策**：
- Query 预处理不依赖检索结果（与自修正模块的"检索后校验"不同），所以放在 Step 1 而非检索之后
- 用同一个 DeepSeek API 完成改写+意图+类型推断，减少 LLM 调用次数
- 改写后的 query 同时用于向量召回（Step 3 的 Vector 路）和 BM25 分词

---

#### 2.4.2 Step 2：Query 向量化

**职责**：将预处理后的 query 文本转换为语义向量，供 Vector 路召回使用。

**关键约束 — 模型一致性**：Query 向量化必须使用与离线 chunk embedding **完全相同的模型和参数**，否则向量空间不一致，相似度计算无意义。

```python
def embed_query(query_text: str, model_name: str = "text-embedding-3-small") -> list[float]:
    """
    将单条 query 文本转换为向量。

    约束：
    - model_name 必须与 chunk embedding 阶段一致（见 §2.2）
    - 输出向量维度 = chunk embedding 维度（1536 for text-embedding-3-small）
    - 内部调用同一 embedding API/模型的 encode 方法
    - 返回前做 L2 归一化（与 chunk 向量对齐）

    Returns:
        normalized_vector: list[float]  # 1536-dim, ||v||₂ = 1
    """
```

**Query 向量化 vs Chunk 向量化的区别**：

| 维度 | Chunk 向量化（离线） | Query 向量化（在线） |
|------|---------------------|---------------------|
| 触发时机 | 文档入库时，一次性批量 | 每次用户查询，实时 |
| 批量大小 | batch_size=20 | 单条（或改写多 query 时 ≤5 条） |
| 缓存策略 | 落盘缓存（永久） | 不缓存（query 多样性高） |
| 超时要求 | 宽松（分钟级） | 严格（<500ms） |
| 模型 | text-embedding-3-small | **必须同模型** |

**输入 / 输出**：

```
输入：
  - query_texts: list[str]   # [rewritten_query] 或 [original, rewritten, variants...]
  - model_name: str          # 必须与 §2.2 chunk embedding 一致

输出：
  - query_vectors: list[list[float]]   # 每个 query 对应一个归一化向量
```

---

#### 2.4.3 Step 3：多路召回

**职责**：以 query 文本和向量为输入，从多路索引并行召回候选，合并为统一候选池。

**企业项目报告场景的路数决策**：

| 召回路 | 必要性 | 核心价值 |
|--------|--------|----------|
| Vector | 必须 | 语义泛化——"预算花了多少" ≈ "预算执行率" |
| KG | 必须 | 结构化关系——"谁审批了XX项目" = person_role → process_step 关系遍历 |
| BM25 | 必须 | 精确关键词——项目编号"PJ-2026-042"直接命中 |
| **Table（结构化表格）** | **必须** | 数值过滤——"预算执行率 > 80% 的项目"，XLSX/DOCX 表格数据的精确条件查询 |
| 多 Query | 建议 | 企业表述多样性极高——"变更流程" "变更咋走" "变更管理办法" → 三种写法搜三遍 |

**企业 KG 边关系类型扩展**（在现有 3 种基础上增加 4 种）：

现有 `kg_builder.py` 定义了 3 种边类型：`co_occurs_with`（同页共现）、`same_type`（同类型链式连接）、`adjacent_to`（顺序相邻）。企业场景需要以下额外关系：

| 边类型 | 源实体 → 目标实体 | 含义 | 示例 |
|--------|------------------|------|------|
| `co_occurs_with` | 任意 → 任意 | 同页/同 Section 共现 | （现有，保留） |
| `same_type` | 同 entity_type | 同类型链式连接 | （现有，保留） |
| `adjacent_to` | 任意 → 任意 | 顺序相邻 | （现有，保留） |
| **`reports_to`** | `person_role` → `person_role` | 汇报关系 | 项目经理 → 部门负责人 |
| **`owned_by`** | `project_metadata` / `process_step` → `department` | 归属关系 | 变更管理流程 → 质量管理部 |
| **`references`** | `process_step` / `risk_item` → `regulation_ref` | 制度引用 | 变更申请步骤 → 变更管理办法 |
| **`has_milestone`** | `project_metadata` → `milestone` | 包含里程碑 | XX项目 → 中期验收 |
| **`produces`** | `process_step` → `deliverable` | 产出物 | 验收阶段 → 验收报告 |
| **`mitigates`** | `risk_item` → `process_step` | 风险缓解措施 | 进度延误风险 → 周报跟踪 |
| **`has_metric`** | `project_metadata` / `milestone` → `metric` | 关联指标 | XX项目 → 预算执行率 |

新增边类型的构建逻辑应在 `kg_builder.py` 中实现，依据 LangExtract 抽取出的实体关系属性自动生成。其中 `references`、`has_milestone`、`produces` 可通过实体属性中的引用关系推断；`reports_to`、`owned_by` 需要从文档组织结构中推断。

**五路召回架构**：

```
PreprocessedQuery + Query Vector
    │
    ├──► Vector Recall
    │    query_vector → ChromaDB.similarity_search(top_k=20)
    │    → 20 candidate chunks
    │
    ├──► Table Recall [结构化数值查询]
    │    intent=metric → 提取数值条件 → pandas/DuckDB 查询 table_index
    │    → 匹配的数据行（含 source_file + sheet_name + row_number）
    │    → 20 matched rows
    │
    ├──► KG Recall [核心路径，企业实体关系]
    │    entity_types → search_kg_by_type(entity_type, keyword)
    │    → get_entity_neighbors(k_hops=1)
    │    → 20 candidate entities
    │
    ├──► BM25 Recall
    │    rewritten_query → tokenize → 倒排匹配
    │    → 20 candidate chunks
    │
    └──► Multi-Query Recall [§3.1，建议启用]
         原始 Query → LLM 生成 2-3 个变体 → 各路并发 → 取并集
         → 最多 20 candidates
```

**Table Recall — 结构化表格检索**

这是专门为 XLSX/DOCX 表格数据设计的一路召回，解决向量和 BM25 对数值条件查询无效的问题。

**触发条件**：Query 预处理的 intent 为 `metric` 时自动启用。

**实现：DuckDB 内存查询引擎**（比 pandas 更适合本场景）：

```python
import duckdb

class TableIndex:
    """
    结构化表格索引 — 将所有 XLSX/DOCX 表格数据汇入单张 DuckDB 内存表。
    """

    def __init__(self):
        self.conn = duckdb.connect(":memory:")
        # 统一 Schema：每个数据行 = 一条记录
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS table_rows (
                row_id INTEGER PRIMARY KEY,
                source_file VARCHAR,
                source_format VARCHAR,        -- 'xlsx' | 'docx'
                sheet_name VARCHAR,
                row_number INTEGER,
                column_name VARCHAR,          -- 指标名称（如 "预算执行率"）
                column_value VARCHAR,         -- 指标值（如 "84%"）
                unit VARCHAR,                 -- 单位（如 "%", "万元"）
                context_json VARCHAR           -- 同行其他列的 JSON
            )
        """)

    def ingest_section(self, section: dict):
        """
        将文档处理模块产出的 table 类型 chunk 写入索引。
        每个表格的数据行拆分为多条 column_name=value 记录。
        """
        table = section["table_json"]         # {headers: [...], rows: [[...], ...]}
        headers = table["headers"]
        for row_idx, row in enumerate(table["rows"]):
            context = dict(zip(headers, row))
            for col_idx, cell_value in enumerate(row):
                col_name = headers[col_idx]
                self.conn.execute("""
                    INSERT INTO table_rows
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"{section['chunk_id']}_{row_idx}_{col_idx}",
                    section["metadata"]["source_file"],
                    section["metadata"]["source_format"],
                    section.get("sheet_name", ""),
                    row_idx,
                    col_name,
                    str(cell_value),
                    self._infer_unit(col_name, str(cell_value)),
                    json.dumps(context, ensure_ascii=False),
                ))

    def query(self, conditions: list[str], top_k: int = 20) -> list[dict]:
        """
        执行结构化查询。

        Args:
            conditions: 从 query 中提取的条件列表
                如 ["预算执行率 > 0.8", "进度 < 0.5"]
            top_k: 最大返回行数

        Returns:
            匹配的数据行，含 source_file + sheet_name 溯源
        """
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT DISTINCT source_file, sheet_name, row_number,
                   column_name, column_value, unit, context_json
            FROM table_rows
            WHERE {where_clause}
            LIMIT {top_k}
        """
        return self.conn.execute(sql).fetchdf().to_dict("records")
```

**Query → 数值条件提取**（在 Query 预处理阶段同步完成）：

```python
def extract_table_conditions(rewritten_query: str) -> list[str]:
    """
    从 query 中提取数值过滤条件。
    用 LLM 一次性完成，复用 Query 预处理的同一个 API 调用。

    示例：
    "预算执行率超过80%的项目" → ["column_name = '预算执行率' AND column_value_numeric > 0.8"]
    "进度低于50%的里程碑"     → ["column_name = '进度' AND column_value_numeric < 0.5"]
    """
    # 此逻辑内嵌于 QUERY_PREPROCESS_PROMPT 的 JSON 输出中
    # 新增字段: "table_conditions": [...]
```

**EAV 模式的局限与宽表补充**：

EAV（实体-属性-值）模式擅长单列条件查询（`预算执行率 > 80%`），但多列组合条件（`预算 > 100 AND 执行率 < 80%`）需要在 `context_json` 上做二次过滤。对于列数确定的 Sheet（如预算明细表），建议在 `ingest_section` 时额外创建一张以原始列为列的宽表：

```python
def _create_wide_table(self, section: dict):
    """为列结构稳定的 Sheet 创建宽表，支持多列组合 SQL 查询。"""
    table = section["table_json"]
    headers = [h for h in table["headers"] if h]  # 过滤空表头
    if len(headers) < 2:
        return  # 单列表不需要宽表
    # 动态创建宽表: CREATE TABLE sheet_预算明细 AS SELECT ...
    col_defs = ", ".join(f'"{h}" VARCHAR' for h in headers)
    self.conn.execute(f'CREATE TABLE IF NOT EXISTS "{section["sheet_name"]}" ({col_defs})')
    for row in table["rows"]:
        values = [str(cell) if cell is not None else "" for cell in row[:len(headers)]]
        placeholders = ", ".join("?" for _ in values)
        self.conn.execute(f'INSERT INTO "{section["sheet_name"]}" VALUES ({placeholders})', values)
```

查询时优先走宽表（结构清晰、SQL 表达能力完整），降级走 EAV 表（适用于列结构不固定的表格）。

**与 KG metric 实体的分工**：

| | KG metric 实体 | Table Recall |
|------|---------------|--------------|
| 数据来源 | BridgePipeline 从正文中抽取的指标 | XLSX/DOCX 表格原始数据行 |
| 查询方式 | entity_type + keyword 搜索 | SQL-like 数值条件过滤 |
| 输出粒度 | 单个 metric 实体（name/value/unit） | 完整数据行 + 同行上下文 |
| 适用场景 | "XX项目的预算执行率" | "预算执行率 > 80% 的所有项目" |

**企业 KG 实体类型枚举（10 类，替换学术论文体系）**：

| entity_type | 含义 | 典型属性 | 对应查询场景 |
|-------------|------|----------|-------------|
| `project_metadata` | 项目元信息 | `project_id`, `project_name`, `type`, `phase`, `budget_total` | "XX项目的总预算是多少" |
| `person_role` | 人员及角色 | `name`, `role`, `department`, `contact` | "谁负责XX项目的质量审核" |
| `process_step` | 流程步骤 | `step_name`, `order`, `approver`, `deadline_days`, `input_doc`, `output_doc` | "变更管理要走几步审批" |
| `metric` | 数值指标 | `name`, `value`, `unit`, `target`, `actual`, `deviation` | "预算执行率是多少" |
| `milestone` | 里程碑节点 | `name`, `planned_date`, `actual_date`, `status` | "XX项目什么时候验收" |
| `deliverable` | 交付物/成果 | `name`, `type`, `acceptance_criteria`, `status` | "中期报告交付了哪些文档" |
| `risk_item` | 风险项 | `risk_desc`, `level`, `probability`, `impact`, `mitigation` | "XX项目有哪些高风险项" |
| `regulation_ref` | 制度/规范引用 | `title`, `doc_id`, `version`, `effective_date`, `issuing_dept` | "变更管理参照哪个制度文件" |
| `department` | 部门/组织单位 | `dept_name`, `parent_dept`, `head`, `responsibilities` | "XX部门管哪些项目" |
| `timeline_event` | 关键时间节点 | `event_name`, `date`, `related_entities` | "项目立项到验收的时间线" |

**五路详解**：

| 召回路 | 索引 | 匹配方式 | top_k | 核心优势 |
|--------|------|----------|-------|----------|
| Vector | ChromaDB HNSW | 向量余弦相似度 | 20 | 语义泛化，制度/流程类查询的同义表达覆盖 |
| **Table** | **DuckDB 内存表** | **SQL-like 数值条件过滤** | **20** | **"执行率 > 80%" 的精确数值查询，带同行上下文** |
| KG | NetworkX G_grounded | entity_type + keyword + k-hop | 20 | `person_role → process_step` 关系遍历，直接回答"谁负责XX流程" |
| BM25 | rank-bm25 倒排索引 | 词频-逆文档频率 | 20 | 项目编号、制度文号精确命中 |
| Multi-Query | 各路复用 | 多个 query 变体并发 + 结果并集 | 20 | "变更流程""变更咋走""变更管理办法"覆盖表述多样性 |

**KG 路的具体调用序列**（封装 MVP 的 4 个 Tool，使用企业实体类型）：

```python
def kg_recall(preprocessed: PreprocessedQuery) -> list[dict]:
    """
    KG 路召回：利用预处理输出的 enterprise entity_types 精确检索。
    """
    results = []
    for etype in preprocessed.entity_types:
        entities = json.loads(search_kg_by_type(
            entity_type=etype,
            keyword=preprocessed.rewritten,
            max_results=5,
        ))
        for ent in entities[:3]:
            neighbors = json.loads(get_entity_neighbors(
                node_id=ent["node_id"],
                k_hops=1,
                max_results=5,
            ))
            results.append({
                "source": "kg",
                "entity": ent,
                "neighbors": neighbors.get("neighbors", []),
            })
    return results
```

**与多 Query 路的分工（重要）**：

KG 路和多 Query 路解决不同问题，不互斥：

| | KG 结构化召回 | 多 Query 召回 |
|------|-------------|--------------|
| 查询维度 | 实体关系（谁→什么流程→哪个制度） | 表述多样性（不同写法搜不同结果） |
| 输出 | 结构化属性（name/role/value/date） | 文本片段 |
| 关键场景 | "XX部门负责哪些项目的质量审核" | "变更怎么走" vs "变更管理办法" vs "变更申请流程" |

多 Query 路的核心价值在企业场景显著上升——员工不会用标准术语提问，"报销咋搞"和"财务报销管理办法"是同一个问题但关键词完全不重叠。
```

---

#### 2.4.4 Step 4：Rerank 精排

**必要性：必须**（已从可选提升）— 多路召回候选池质量参差不齐，需两阶段排序选出最优上下文。

**两阶段排序流程**：

```
五路候选池（≤100 items：20 vector + 20 table + 20 kg + 20 bm25 + 20 multi-query）
    │
    ▼
┌─────────────────────────────────────────┐
│ Phase 1: RRF 粗排（无模型，纯规则）       │
│                                         │
│ score(doc) = Σ 1/(k + rank_i(doc))      │
│ k=60                                     │
│                                         │
│ 输入: 4~5 路各自排序的 results_lists     │
│ 输出: top-20 合并列表（cross-source）    │
│ 耗时: <1ms                               │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ Phase 2: Cross-encoder 精排（有模型）     │
│                                         │
│ 对每个候选 (query, chunk_text) pair      │
│ 用 BGE-Reranker-v2-m3 做深度相关性打分    │
│                                         │
│ 输入: (query, RRF top-20 chunks)        │
│ 输出: 按 rerank_score 降序的 top-5       │
│ 耗时: ~200ms (20 pairs × 10ms)          │
└─────────────────────────────────────────┘
```

**RRF 算法实现**：

```python
def rrf_fusion(results_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """
    Reciprocal Rank Fusion — 无模型多路融合。
    score(doc) = Σ 1 / (k + rank_i(doc))

    Args:
        results_lists: [vector_results, kg_results, bm25_results]
                      每路已是按原始 score 降序排列
        k: 平滑常数，默认 60（经典取值）
    Returns:
        top-20 合并排序列表
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for result_list in results_lists:
        for rank, doc in enumerate(result_list):
            doc_id = doc.get("chunk_id") or doc.get("entity", {}).get("node_id", str(uuid4()))
            doc_map[doc_id] = doc
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

    sorted_ids = sorted(scores.items(), key=lambda x: -x[1])[:20]
    return [{**doc_map[did], "rrf_score": sc} for did, sc in sorted_ids]
```

**Cross-encoder 精排实现**：

```python
from sentence_transformers import CrossEncoder

class Reranker:
    """Cross-encoder 精排器"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
        """
        对 RRF 粗排结果做 Cross-encoder 精排。

        Args:
            query: 预处理后的 rewritten query
            candidates: RRF top-20
            top_k: 最终保留数量
        Returns:
            按 rerank_score 降序的 top_k 候选
        """
        pairs = [(query, c.get("text", "")[:512]) for c in candidates]
        scores = self.model.predict(pairs)

        for i, c in enumerate(candidates):
            c["rerank_score"] = float(scores[i])

        candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        return candidates[:top_k]
```

**Reranker 选型**：

| 模型 | 参数量 | 语言 | 延迟/pair | 推荐场景 |
|------|--------|------|-----------|----------|
| `BAAI/bge-reranker-v2-m3` | 568M | 多语言(含中英) | ~10ms | 生产推荐 |
| `BAAI/bge-reranker-base` | 278M | 英文 | ~5ms | 纯英文/低延迟 |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | 107M | 英文 | ~3ms | MVP 快速启动 |

**MVP 降级策略**：如果加载 Cross-encoder 模型有困难（GPU 不可用 / 内存不足），可以跳过 Phase 2，直接用 RRF top-5 作为最终结果。RRF 本身已经是高质量的融合排序，Cross-encoder 是锦上添花。

---

#### 2.4.5 Step 5：冗余过滤 + 溯源标记

**职责**：对精排后的候选做去重、合并、截断，并注入溯源元数据。

**冗余过滤规则**：

| 规则 | 条件 | 动作 |
|------|------|------|
| 相邻合并 | `char_start` 差 < chunk_size/2 且同 page | 合并为一个大 chunk，拼接 text |
| 相似去重 | Jaccard(text_a, text_b) > 0.85 | 保留 rerank_score 更高的一条 |
| 跨路数值冲突 | KG metric 与 Table row 引用同一指标但数值不一致 | 保留 Table 路数据（原始表格精度更高），标注冲突警告注入 prompt |
| 同指标去重 | 两个 chunk/entity 描述同一指标（如预算执行率）且来自不同路 | 以 Table 路为准，Vector/KG 路作为补充上下文 |
| Token 截断 | 累计 token 数 > max_context_tokens (4000) | 截断低分结果，优先保留 KG 实体 |

**跨路数值冲突检测**的关键逻辑：
```python
def detect_cross_path_conflicts(candidates: list[dict]) -> list[dict]:
    """
    检测 KG metric 实体与 Table row 之间的数值冲突。
    同名指标（如"预算执行率"）在正文和附表中可能不一致 —
    正文是阶段性摘要，附表是最新数据。
    策略：以 Table（原始表格数据）为准，KG 实体降级为补充信息。
    """
    ...
```

**溯源标记注入**：每个最终候选统一附加以下元数据，供 LLM 生成时引用：

```python
@dataclass
class RetrievalChunk:
    chunk_id: str              # c00042
    text: str                  # chunk 文本
    score: float               # 最终分数（rerank_score 或 rrf_score）
    source: str                # "vector" | "kg" | "keyword"
    page_idx: int | None       # PDF 页码
    section_title: str         # 所属章节
    entity_ids: list[str]      # 关联的 KG entity ID（KG 路必有，其他路可能为空）
    bbox_norm: list[float] | None  # PDF 位置归一化坐标（KG 路）
```

---

#### 检索模块总输入 / 输出

```
输入：
  - raw_query: str
  - chat_history: list[dict] | None
  - retrieval_config:
    {
      "max_total_candidates": 5,
      "max_context_tokens": 4000,
      "enable_cross_encoder": true,      # false → 仅 RRF
      "vector_top_k": 20,
      "table_top_k": 20,
      "kg_top_k": 20,
      "bm25_top_k": 20,
      "multi_query_top_k": 20,
    }

输出：
  - RetrievalResult:
    {
      "chunks": [RetrievalChunk, ...],        # 3~5 条，去重+精排后
      "total_candidates": 5,
      "pipeline": {
        "preprocess_latency_ms": 80,
        "embed_query_latency_ms": 120,
        "vector_recall_latency_ms": 15,
        "kg_recall_latency_ms": 200,
        "bm25_recall_latency_ms": 5,
        "rrf_latency_ms": 1,
        "rerank_latency_ms": 180,             # 0 if disabled
        "total_latency_ms": 601,
      },
      "query_intent": "metric",
      "entity_types_used": ["metric", "model_component"],
    }
```

#### 与 Query 优化模块（原 §3.1）的关系

原 §3.1 "Query 优化模块" 被标记为可选增强。现在其核心功能（改写、意图识别、实体类型推断）已纳入 §2.4.1 成为必须步骤。§3.1 保留的内容缩减为**高级 Query 优化**（多轮对话上下文管理、用户画像适配、领域词典注入），这些属于进阶场景，非 MVP 必需。

---

### 2.5 Prompt 模块

**必要性：必须** — 决定 LLM 生成答案的格式、质量、可控性。

#### 功能定义

将检索模块输出的候选上下文拼接为 LLM 可理解的 Prompt，包含系统指令、上下文资料、用户 Query、输出格式约束。

#### 核心职责

| 职责 | 说明 |
|------|------|
| 系统指令设计 | 角色定义 + 行为规则 + 知识边界声明 |
| 上下文拼接 | 检索结果 → 结构化插入 Prompt template |
| Token 预算控制 | 精确计算各部分 token 分配，防止溢出 |
| 输出格式约束 | 强制 JSON/Markdown Table/溯源标记 |

#### 关键实现点

**Prompt 模板（四段式）**：

```
┌──────────────────────────────────────────────┐
│ [SYSTEM]                                     │
│ 你是一个基于文档知识的问答助手。              │
│ 规则：                                       │
│ 1. 仅用提供的上下文回答，禁止编造            │
│ 2. 每条事实标注来源 [chunk_id, page]         │
│ 3. 上下文不足时明确声明"文档未提及"          │
│ 4. 数值类答案使用 Markdown 表格              │
│ 5. 用提问语言回答                            │
├──────────────────────────────────────────────┤
│ [CONTEXT]                                    │
│ 以下是检索到的相关文档片段：                  │
│                                              │
│ [Chunk c00042 | Page 3 | Section 3.2]       │
│ The base model was trained for 100,000       │
│ steps on 8 NVIDIA P100 GPUs...              │
│                                              │
│ [Chunk c00058 | Page 5 | Section 4.1]       │
│ Beam search with beam size 4 and length      │
│ penalty α=0.6 was used for decoding...      │
│                                              │
│ [KG Entity n0019 | Page 0 | metric]         │
│ Label: 28.4 BLEU                            │
│ Properties: {"task": "WMT 2014 EN-DE"}      │
├──────────────────────────────────────────────┤
│ [QUESTION]                                   │
│ What BLEU scores did the Transformer achieve?│
├──────────────────────────────────────────────┤
│ [OUTPUT FORMAT]                              │
│ 请以 Markdown 表格呈现数值结果，              │
│ 每行标注来源 [chunk_id, page]。              │
└──────────────────────────────────────────────┘
```

**Token 预算分配策略**：

| 模型 | Context Window | System | Context | Query | Output Reserve |
|------|---------------|--------|---------|-------|----------------|
| deepseek-v4-pro | 262144 | ~500 | ~12000 | ~100 | ~4000 |

预算不足时：按 fusion score 截断低分 chunk，优先保留 KG 实体（结构化信息密度高）。

#### 输入 / 输出

```
输入：
  - RetrievalResult（来自检索模块）
  - user_query: str
  - prompt_config: {max_context_tokens, output_language, format_type}

输出：
  - messages: list[dict]   # LangChain 标准消息格式
    [
      {"role": "system", "content": "..."},
      {"role": "user", "content": "[CONTEXT]...\n[QUESTION]..."}
    ]
  - token_budget_report: {total, system, context, query, remaining}
```

---

### 2.6 LLM 生成模块

**必要性：必须** — RAG 系统的最终输出模块，将检索上下文转化为用户可读的答案。

#### 功能定义

调用 LLM（DeepSeek / 其他）基于拼接的 Prompt 生成最终答案，并完成溯源验证和格式校验。

#### 核心职责

| 职责 | 说明 |
|------|------|
| 答案生成 | 调用 LLM API，控制 temperature / max_tokens |
| 引用溯源 | 解析答案中的 chunk_id / page_idx 引用，验证真实性 |
| 格式校验 | 检查输出是否符合指定格式（table / JSON / markdown） |
| 兜底处理 | LLM 调用失败时的降级策略 |

#### 关键实现点

**⚠️ `deepseek-v4-pro` thinking mode 必须禁用**：

使用 `deepseek-v4-pro` 模型时，必须在 API 调用中显式禁用 thinking mode：

```python
# LangChain ChatOpenAI 调用
llm = ChatOpenAI(
    model="deepseek-v4-pro",
    temperature=0.0,
    model_kwargs={"extra_body": {"thinking": {"type": "disabled"}}},
)
```

**原因**：启用 thinking mode 后，API 响应会包含 `reasoning_content` 字段。在 LangGraph multi-turn 工具调用循环中，该字段无法被框架正确回传到下一轮消息，导致工具调用链断裂（表现为 Agent 在第一轮工具调用后静默停止）。此约束同样适用于 §2.4.1 Query 预处理和 §3.1 多 Query 生成中对 v4-pro 的调用。

```python
@dataclass
class GenerationResult:
    answer_text: str            # 最终答案
    cited_sources: list[str]    # 被引用的 chunk_id / entity_id 列表
    token_usage: dict           # {prompt_tokens, completion_tokens}
    latency_ms: int             # 生成耗时
    model: str                  # 使用的模型名
    finish_reason: str          # stop | length | error
```

**溯源验证逻辑**：
```python
def verify_citations(answer: str, context_chunks: list[dict]) -> tuple[bool, list[str]]:
    """
    提取答案中引用的 chunk_id，验证其是否存在于提供的上下文 chunk 中。
    返回：(全部有效, 无效引用列表)
    """
    cited = re.findall(r'\[(c\d{5})\s*,?\s*page\s*(\d+)\]', answer)
    valid_chunk_ids = {c["chunk_id"] for c in context_chunks}
    invalid = [cid for cid, _ in cited if cid not in valid_chunk_ids]
    return (len(invalid) == 0, invalid)
```

**兜底策略**：
| 错误场景 | 处理 |
|----------|------|
| API 超时 (120s) | 重试 1 次，仍失败则返回"系统繁忙，请稍后重试" |
| Token 超限 | 截断 context，保留 top-5 chunk + 所有 KG entity |
| 答案无引用 | 追加系统提示："请重新回答并标注来源"，重新生成 |
| 引用幻觉 | 剔除无效引用，追加警告说明 |

#### 输入 / 输出

```
输入：
  - messages（来自 Prompt 模块）
  - generation_config: {temperature: 0.0, max_tokens: 2048, model: "deepseek-v4-pro"}

输出：
  - GenerationResult（含答案 + 溯源信息 + token 统计）
```

---

## 3. 可选增强模块

---

### 3.1 高级 Query 优化模块（可选）

**必要性：可选** — 基础 Query 预处理（改写、意图识别、实体类型推断）已在 §2.4.1 实现为必须步骤。本模块覆盖进阶场景。

#### 功能定义

在基础 Query 预处理之上，提供多轮对话上下文管理、用户画像适配、领域词典注入等进阶能力。

#### 核心职责

| 职责 | 说明 | 适用场景 |
|------|------|----------|
| 多轮对话管理 | 跟踪对话历史，消解跨轮指代（"它"→"Transformer"） | 聊天式交互 |
| 多 Query 生成 | 原 Query → 3-5 个语义等价变体，多路并发召回取并集 | 高召回需求 |
| 用户画像适配 | 根据用户背景（研究员/学生）调整答案粒度 | 多角色场景 |
| 领域词典注入 | 专业术语映射（"注意力"→"attention mechanism"），提升检索命中 | 跨语言查询 |

#### 与 §2.4.1 的分工

```
§2.4.1 基础预处理（必须，全场景）     §3.1 高级优化（可选，按需启用）
─────────────────────────────────    ─────────────────────────────
单轮 Query 改写 + 意图识别            多轮对话指代消解
基础实体类型推断                      多 Query 变体生成
                                      用户画像适配
                                      领域词典注入
```


---

### 3.2 效果评估模块

**必要性：可选** — 用于系统迭代优化，非运行时必需。

#### 功能定义

对检索结果和生成答案做量化评估，输出指标报告。

#### 核心职责

| 职责 | 说明 |
|------|------|
| 检索评估 | Recall@k, Precision@k, MRR |
| 生成评估 | Faithfulness（答案是否忠于上下文）、Answer Relevance |
| 端到端评估 | 答案正确率（人工标注 ground truth 对比） |

#### 评估指标定义

| 指标 | 计算方式 | 目标值 |
|------|----------|--------|
| Recall@10 | 检索 top-10 中包含 ground truth 的比例 | >0.85 |
| MRR | 第一个相关 chunk 的倒数排名平均值 | >0.7 |
| Faithfulness | 答案中可溯源的陈述占比 | >0.95 |
| Hallucination Rate | 答案中存在但上下文不存在的陈述占比 | <0.05 |

#### 输入 / 输出

```
输入：
  - eval_dataset: list[{query, ground_truth_chunks, ground_truth_answer}]
  - retrieval_results + generation_results

输出：
  - eval_report.json:
    {
      "retrieval": {recall@5, recall@10, precision@10, mrr},
      "generation": {faithfulness, hallucination_rate, avg_latency_ms},
      "summary": "总评"
    }
```

#### 关键实现点

- 复用 `iteration-2/eval-2-existing-components/rag_eval/` 现有评测体系
- Faithfulness 用 RAGAS 库（`pip install ragas`）自动评估
- 每轮迭代后跑一次 eval report

---

### 3.3 自修正模块

**必要性：可选** — 对答案质量要求极高的场景，增加一次校验-修正循环。

#### 功能定义

对 LLM 生成的答案自动校验，发现错误（幻觉引用、逻辑矛盾、数值错误）时触发修正。

#### 核心职责

| 职责 | 说明 |
|------|------|
| 答案校验 | 引用验证 + 事实一致性检查 + 数值核对 |
| 错误识别 | 分类：幻觉引用 / 数值错误 / 逻辑矛盾 / 格式不符 |
| 重生成策略 | 修正 prompt → 重生成 → 再校验（最多 2 轮） |

#### 校验流程

```
GenerationResult
    │
    ▼
┌─────────────┐
│ 引用校验      │── 检查答案中的 chunk_id 是否都在 context 中存在
└──────┬──────┘
       │ pass
       ▼
┌─────────────┐
│ 数值校验      │── 答案中的数值是否与 KG entity 的 value 字段一致
└──────┬──────┘
       │ pass
       ▼
┌─────────────┐
│ 逻辑校验      │── 用 LLM 判断答案是否存在自相矛盾
└──────┬──────┘
       │ fail (任一环节)
       ▼
┌─────────────┐
│ 修正重生成    │── 追加错误描述到 prompt，重新生成
└──────┬──────┘
       │ max_retries=2
       ▼
   最终答案 or 降级警告
```

#### 输入 / 输出

```
输入：
  - GenerationResult（待校验）
  - RetrievalResult（用于引用核对）

输出：
  - CorrectedResult:
    {
      "answer_text": str,
      "correction_rounds": int,      # 修正轮数（0 = 首次通过）
      "corrections_made": [str],     # 修正记录
      "final_passed": bool,
    }
```

---

## 4. 模块间交互流程与数据流

### 4.1 离线索引构建流程

```
                        ┌──────────────────┐
                        │ PDF/DOCX/XLSX    │
                        │ (企业项目报告)    │
                        └──────┬───────────┘
                               │
                               ▼
                   ┌───────────────────────┐
                   │ ① 文档处理模块         │
                   │ PDF→MinerU API        │
                   │ DOCX→python-docx      │
                   │ XLSX→openpyxl(保留表格)│
                   │ 智能分块 + 元数据提取   │
                   └───────────┬───────────┘
                               │
                               │ chunks.jsonl
                               │
        ┌──────────────┼──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│② Embedding   │ │ KG 构建   │ │ BM25 索引│ │ Table 索引   │
│ chunk→向量    │ │(现有资产) │ │(rank-bm25)│ │ (DuckDB)    │
└──────┬───────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘
       │              │            │              │
       ▼              ▼            ▼              ▼
┌──────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│③ 向量数据库│  │ NetworkX  │  │ BM25 倒排  │  │ DuckDB    │
│ ChromaDB  │  │ G_grounded│  │ 索引       │  │ 内存表    │
└──────────┘  └───────────┘  └───────────┘  └───────────┘
       │              │            │              │
       └──────────────┼────────────┼──────────────┘
                      │            │
                      ▼            ▼
                四路索引就绪（可查询状态）
```

### 4.2 在线问答数据流

```
User Query: "XX项目的预算花了多少，谁批的"
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ ④ 检索模块 — 5 步流水线                                           │
│                                                                  │
│  Step 1: Query 预处理                                            │
│    LLM → {"rewritten": "XX项目预算执行率及审批人",                │
│            "intent": "hybrid",                                   │
│            "entity_types": ["metric","project_metadata","person_role"]}
│                                                                  │
│  Step 2: Query 向量化                                            │
│    rewritten_query → text-embedding-3-small → query_vector[1536] │
│                                                                  │
│  Step 3: 多路召回（五路并行）                                     │
│    ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│    │ Vector   │ │ Table     │ │ KG       │ │ BM25     │ │多Query   │ │
│    │ ChromaDB │ │ DuckDB    │ │ "metric" │ │ "PJ-2026 │ │"XX项目   │ │
│    │ top_k=20 │ │ "执行率   │ │"person_  │ │  -042"   │ │ 预算花了  │ │
│    │          │ │  >80%"    │ │ role"    │ │ top_k=20 │ │  多少"   │ │
│    └────┬─────┘ └─────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│         └─────────────┼───────────┼────────────┼────────────┘         │
│                           ▼                      ▼                      │
│  Step 4: Rerank 精排                                                    │
│    RRF 粗排(100→20) → Cross-encoder 精排(20→5)                         │
│                             │                                           │
│  Step 5: 冗余过滤 + 溯源标记                                             │
│    相邻合并/相似去重/Token截断 → 注入 project_id/source_file            │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼ RetrievalResult (3~5 chunks + metadata)
                              │
┌──────────────────────────────────────────────────────────────────┐
│ ⑤ Prompt 模块                                                    │
│                                                                  │
│  Token 预算: total=65536, system=500, context=4000, ...          │
│  拼接: System Prompt + Context Chunks + KG Entities + Query      │
│  输出格式约束: Markdown Table with source citations              │
│                                                                  │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼ messages (LangChain 格式)
                              │
┌──────────────────────────────────────────────────────────────────┐
│ ⑥ LLM 生成模块                                                   │
│                                                                  │
│  ChatOpenAI(model="deepseek-v4-pro", temperature=0.0)              │
│  生成答案 → 溯源验证 → 格式校验                                   │
│  (可选: 自修正模块 → 校验失败重生成, max 2 retries)               │
│                                                                  │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │ Final Answer           │
                  │ "Based on the KG...    │
                  │  | BLEU | Dataset |    │
                  │  | 28.4 | WMT...  |    │
                  │  Sources: [c00042,     │
                  │   page 3], [n0019]..." │
                  └────────────────────────┘
                              │
                              ▼
                  (可选: 效果评估模块 → eval metrics)
```

### 4.3 模块间接口汇总

| 上游模块 | 下游模块 | 数据格式 | 调用方式 |
|----------|----------|----------|----------|
| ① 文档处理 | ② Embedding | `chunks.jsonl` | 文件传递 |
| ① 文档处理 | ③ 向量数据库 | chunk list（内存） | 函数调用 |
| ① 文档处理 | KG 构建 | section texts | BridgePipeline 现有流程 |
| ② Embedding | ③ 向量数据库 | `[{id, vector, metadata}]` | ChromaDB API |
| Query 预处理 (§2.4.1) | Query 向量化 (§2.4.2) | `PreprocessedQuery` | 函数调用 |
| Query 预处理 | 多路召回 (§2.4.3) | `{rewritten, entity_types}` | 函数调用（KG/BM25 路） |
| Query 向量化 | 多路召回 (§2.4.3) | `query_vector: list[float]` | 函数调用（Vector 路） |
| ③ 向量数据库 | 多路召回 | query vector → top_k results | ChromaDB.query() |
| KG (NetworkX) | 多路召回 | entity search → subgraph | Tool 函数调用 |
| BM25 索引 | 多路召回 | keywords → doc scores | BM25.get_scores() |
| 多路召回 (§2.4.3) | Rerank 精排 (§2.4.4) | `{candidates: ≤100 items}`（五路 × 各20） | 函数调用 |
| Rerank 精排 | 冗余过滤 (§2.4.5) | `{candidates: 10 items}` | 函数调用 |
| ④ 检索（完整） | ⑤ Prompt | `RetrievalResult` | 函数调用 |
| ⑤ Prompt | ⑥ LLM 生成 | `messages: list[dict]` | 函数调用 |
| 高级 Query 优化 (§3.1) | Query 预处理 | `{context, profile}` | 函数调用（可选） |
| ⑥ LLM 生成 | 自修正 | `GenerationResult` | 函数调用（可选） |

---

## 5. 技术选型决策

### 5.1 选型总表

| 层 | 技术 | 版本 | 必要性 | 选型理由 |
|----|------|------|--------|----------|
| 文档解析（PDF） | MinerU API (云端) | — | 必须 | 已有，PDF→Markdown 质量最优 |
| 文档解析（DOCX） | `python-docx` | ≥1.1 | 必须 | 纯 Python，保留标题层级+表格结构 |
| 文档解析（XLSX） | `openpyxl` | ≥3.1 | 必须 | 结构化提取 Sheet/表头/数据行 |
| 文本分块 | 自研（章节语义分块） | — | 必须 | 按标题层级切割，表格独立成 chunk |
| Embedding | `BGE-M3` (本地) | — | **推荐首选** | 中文优先，千级文档可用 CPU，零成本 |
| Embedding | `text-embedding-3-small` | — | MVP 可用 | OpenAI 兼容，快速启动 |
| 向量数据库 | ChromaDB | ≥0.5.0 | 必须 | 千级文档嵌入式足够，零运维 |
| 图存储 | NetworkX | ≥3.0 | 必须 | 企业 KG 实体规模可控（10 类×千级） |
| 全文索引 | `rank-bm25` | ≥0.2.0 | 必须 | 项目编号/制度文号精确匹配 |
| 表格查询引擎 | `duckdb` | ≥1.0 | 必须 | 内存 SQL，XLSX/DOCX 表格数据的结构化数值条件查询 |
| 多 Query 生成 | LLM `deepseek-v4-pro` | — | **建议启用** | 企业表述多样性高，边际收益明显 |
| Agent 框架 | LangGraph | ≥1.0 | 必须 | 已有，工具编排 |
| LLM 网关 | `langchain-openai` | ≥0.3.0 | 必须 | DeepSeek OpenAI Compatible |
| LLM | `deepseek-v4-pro` | — | 必须 | 中英文混合企业文档；⚠️ 需禁用 thinking mode（`extra_body={"thinking": {"type": "disabled"}}`），否则 LangGraph multi-turn 工具调用循环无法正确回传 `reasoning_content` |
| Reranker | `BGE-Reranker-v2-m3` | — | 必须 | Cross-encoder 精排；MVP 可降级为 RRF-only |
| Reranker (降级) | RRF-only | — | MVP 可用 | 纯规则融合，零模型依赖 |
| 评估 | RAGAS | ≥0.1.0 | 可选 | 自动评估 faithfulness |
| API 服务 | FastAPI | ≥0.110 | 必须 | 项目规范（`backend/`） |
| Query 预处理 LLM | `deepseek-v4-pro` | — | 必须 | 复用同一 API，改写+意图+类型推断 |

### 5.2 关键决策说明

**为什么 ChromaDB 而不是 Milvus/Pinecone？**
- 千级项目报告（预估 2000-5000 chunks），ChromaDB 嵌入式部署零运维
- Milvus 需要独立服务进程，此规模下过度设计
- 数据量突破 10K 文档后，migration path: ChromaDB → Milvus Lite（同 API 风格）

**为什么必须保留 KG 检索路？（企业场景）**
- 企业查询天然需要关系遍历："谁负责XX项目的质量审核" = `person_role` → `process_step` 的 1-hop 关系，纯向量检索引擎无法渲染这种结构化关系
- KG 路直接返回实体属性（name/role/value/date），LLM 生成答案时无需从文本中"推断"结构化信息
- "XX部门管哪些项目" → KG 反向遍历 `department ← person_role → project_metadata`，向量检索无法做到

**为什么建议启用多 Query 召回？（企业场景新增）**
- 企业员工查询表述多样性远高于论文 QA："变更流程""变更咋走""变更管理办法""变更申请步骤" — 四个词写的是同一个问题
- 多 Query 变体让同一语义从不同表述角度覆盖，比单纯增加单路 top_k 更有效
- 成本可控：每个变体复用已有的四路索引（Vector/Table/KG/BM25），不增加额外索引存储

**为什么 Embedding 推荐 BGE-M3 而非 text-embedding-3-small？（企业场景调整）**
- 中文企业文档（项目报告、政策制度）优先，BGE-M3 中文语义对齐优于 OpenAI 通用模型
- 千级文档规模，BGE-M3 CPU 本地推理完全可承受（~10ms/chunk）
- 零外部 API 成本，数据不出域（部分企业报告含敏感信息）

---

## 6. 实施路线图

### Phase 1：实体类型重构 + 离线索引 + 多格式解析（4-5 天）

```
□ 1.0 企业 KG 实体类型重构（★ 必须在多格式解析之前完成）
    - 定义 10 类企业实体（project_metadata / person_role / process_step /
      metric / milestone / deliverable / risk_item / regulation_ref /
      department / timeline_event），含每类属性 schema
    - 更新 BridgePipeline entity_type 枚举 + DEFAULT_PROMPT
    - 更新 extraction_examples.yaml：4 个学术示例 → 4 个企业项目报告示例
    - 更新 search_kg_by_type 工具的 System Prompt
    - 更新 backend/routes/graph.py TYPE_COLORS + frontend/src/lib/constants.ts
    - 新增 3 种 KG 边关系类型（见 §2.4.3 补充）

□ 1.1 文档处理模块 — 多格式解析
    - DOCX 解析：python-docx，按标题样式分段，保留表格 JSON
    - XLSX 解析：openpyxl，Sheet→section，表头→fields
    - PDF 解析：复用 MinerU API + BridgePipeline
    - 统一 Section 数据结构（跨格式）

□ 1.2 文档处理模块 — 分块 + 元数据
    - 章节语义分块（Level 2，企业项目报告首选）
    - 表格独立成 chunk（content_type="table"，table_json 字段）
    - 元数据 schema 企业版实现（project_id, source_format, section_path）
    - 明确 chunks 与 BridgePipeline Documents 的产出关系（见 §2.1 补充）

□ 1.3 Embedding 模块
    - BGE-M3 本地部署（推荐）或 text-embedding-3-small（MVP）
    - embed_chunks() + 批量处理 + 缓存
    - 记录所选模型维度，为后续迁移做准备（见 §2.2 补充）

□ 1.4 Table 索引
    - DuckDB 内存表 schema 创建（EAV 表 + 宽表双模式，见 §2.4.3 补充）
    - XLSX/DOCX 表格数据 -> table_rows 表批量写入
    - 数值条件查询验证（单列 + 多列组合）

□ 1.5 向量数据库
    - ChromaDB 初始化 + collection "project_reports" 创建
    - 写入 chunks + vectors，验证检索可用
```

### Phase 2：五路检索 + Rerank（4-5 天）

```
□ 2.1 Query 预处理（§2.4.1，企业意图类型）
    - LLM prompt：4 种企业意图枚举（policy_lookup / process_attribution / metric / hybrid）
    - JSON 解析 + 实体类型推断 + 数值条件提取

□ 2.2 Query 向量化（§2.4.2）
    - embed_query() + 模型一致性校验

□ 2.3 五路召回（§2.4.3）
    - Vector recall: ChromaDB.query()
    - Table recall: DuckDB SQL 数值条件查询（intent=metric 时启用；EAV + 宽表双模式）
    - KG recall: 企业实体类型 + k-hop（person_role→process_step 关系遍历）
    - BM25 recall: rank-bm25（项目编号/制度文号精确匹配）
    - Multi-Query recall: LLM 生成 2-3 变体 → 各路并发 → 结果并集
    - 五路并发（asyncio.gather）

□ 2.4 Rerank 精排（§2.4.4）
    - RRF 粗排（100→20，五路输入）
    - Cross-encoder 集成（BGE-Reranker-v2-m3）
    - MVP 降级开关（RRF-only 模式）

□ 2.5 冗余过滤 + 溯源标记（§2.4.5）
    - 相邻合并 + 相似去重 + 跨路数值冲突检测 + Token 截断
    - project_id + source_file 溯源注入

□ 2.6 企业场景测试集
    - 制度查询 3 题 + 流程归属 3 题 + 数据指标 3 题 + 综合 1 题
```
```

### Phase 3：Prompt + Generation 规范化（1-2 天）

```
□ 3.1 Prompt 模块
    - 四段式模板实现
    - Token 预算计算 + 自动截断

□ 3.2 LLM 生成模块
    - 封装 GenerationResult
    - 溯源验证 verify_citations()
    - 兜底策略实现
```

### Phase 4：可选增强 + API 化（2-3 天）

```
□ 4.1 Query 优化模块（可选）
□ 4.2 效果评估模块（可选，对接 RAGAS）
□ 4.3 自修正模块（可选）
□ 4.4 FastAPI 端点: POST /query
□ 4.5 前端接入（对接 frontend/ 现有 UI）
```

---

## 7. 与现有资产的对接关系

### 7.1 复用清单

| 现有资产 | 路径 | 复用方式 |
|----------|------|----------|
| BridgePipeline | `integration/pipeline.py` | 直接调用产出 nodes/edges/jsonl |
| KG 构建 | `integration/kg_builder.py` | 不变，作为检索的 KG 路 |
| Grounding | `integration/grounding.py` | chunk 溯源标注 |
| MVP Agent | `integration/agentic_rag_mvp.py` | 工具函数重构为 retrieval 模块子组件 |
| Agentic-RAG 规范 | `langextract/docs/agentic-kg-rag-specification-v1.0.md` | 本文档继承其输入/输出规范 |
| 架构蓝图 | `integration/Agentic-RAG-Architecture.md` | 本文档是其可落地的工程细化版 |
| RAG 评测体系 | `iteration-2/eval-2-existing-components/rag_eval/` | 对接效果评估模块 |
| 环境隔离 | `langextract/.venv` | 所有 Python 包统一管理 |

### 7.1.1 旧 KG 数据兼容策略

`integration/output/kg/` 中有已构建的 KG 数据（使用学术 10 类实体类型，来自 BridgePipeline + LangExtract + Transformer 论文）。

**决策：旧 KG 数据废弃，不作为企业蓝图的索引输入。**

理由：
- 学术 10 类实体类型与企业 10 类互不兼容（仅 `metric` 共享名称但属性 schema 不同）
- 旧 KG 的边关系仅 3 种，企业场景需要 10 种边关系
- 旧数据基于单篇 Transformer 论文（15 页），信息量为零对于企业项目报告查询

**保留方式**：
- 旧 KG 数据文件（`nodes.json`、`edges.json`、`integrated_*.jsonl`）移动到 `integration/output/.archive/` 目录
- `agentic_rag_mvp.py` 保留但标记为 `@deprecated`，指向归档目录作为 demo 数据源
- 企业蓝图构建的 KG 数据写入新目录 `integration/output/enterprise_kg/`

### 7.2 新增文件清单

```
integration/
├── rag_blueprint/
│   ├── __init__.py
│   ├── config.py               # ★ 全局配置中心（最先创建，所有模块依赖）
│   ├── chunker.py              # ① 文档处理 — 多格式解析+分块逻辑
│   ├── docx_parser.py          # ① DOCX 解析（python-docx）
│   ├── xlsx_parser.py          # ① XLSX 解析（openpyxl，保留表格结构）
│   ├── table_index.py          # ③ Table 索引 — DuckDB 内存表 + 查询引擎
│   ├── embedder.py             # ② Embedding — 向量化（BGE-M3 / text-embedding-3-small）
│   ├── vector_store.py         # ③ 向量数据库 — ChromaDB 封装
│   ├── retriever.py            # ④ 检索 — 五路召回 + RRF + Cross-encoder
│   ├── prompt_builder.py       # ⑤ Prompt — 模板 + token 预算
│   ├── generator.py            # ⑥ LLM 生成 — 溯源 + 兜底
│   ├── query_optimizer.py      # (推荐) 多 Query 生成
│   ├── evaluator.py            # (可选) 效果评估
│   ├── self_corrector.py       # (可选) 自修正
│   └── project_id_mapping.json # (可选) 文件名 → 项目 ID 手动映射
├── output/
│   ├── chunks/                 # chunks.jsonl
│   └── vectordb/               # ChromaDB 持久化
```

**`config.py` 职责规范**（所有模块依赖此文件，Phase 1 最先创建）：

```python
# config.py — 全局配置中心，禁止各模块散发硬编码参数

from dataclasses import dataclass
from enum import Enum

# === 企业实体类型枚举（单一真相源） ===
class EntityType(str, Enum):
    PROJECT_METADATA = "project_metadata"
    PERSON_ROLE = "person_role"
    PROCESS_STEP = "process_step"
    METRIC = "metric"
    MILESTONE = "milestone"
    DELIVERABLE = "deliverable"
    RISK_ITEM = "risk_item"
    REGULATION_REF = "regulation_ref"
    DEPARTMENT = "department"
    TIMELINE_EVENT = "timeline_event"

# === 企业意图类型枚举 ===
class QueryIntent(str, Enum):
    POLICY_LOOKUP = "policy_lookup"
    PROCESS_ATTRIBUTION = "process_attribution"
    METRIC = "metric"
    HYBRID = "hybrid"

# === KG 边关系类型枚举 ===
class RelationType(str, Enum):
    CO_OCCURS_WITH = "co_occurs_with"
    SAME_TYPE = "same_type"
    ADJACENT_TO = "adjacent_to"
    REPORTS_TO = "reports_to"
    OWNED_BY = "owned_by"
    REFERENCES = "references"
    HAS_MILESTONE = "has_milestone"
    PRODUCES = "produces"
    MITIGATES = "mitigates"
    HAS_METRIC = "has_metric"

# === 检索配置 ===
@dataclass
class RetrievalConfig:
    max_total_candidates: int = 5
    max_context_tokens: int = 4000
    enable_cross_encoder: bool = True
    vector_top_k: int = 20
    table_top_k: int = 20
    kg_top_k: int = 20
    bm25_top_k: int = 20
    multi_query_top_k: int = 20
    rrf_k: int = 60

# === Embedding 配置 ===
@dataclass
class EmbeddingConfig:
    model_name: str = "text-embedding-3-small"  # MVP; 生产切换 "BGE-M3"
    dimension: int = 1536  # 与 model_name 联动; BGE-M3 = 1024
    batch_size: int = 20

# === 生成配置 ===
@dataclass
class GenerationConfig:
    model: str = "deepseek-v4-pro"
    temperature: float = 0.0
    max_tokens: int = 2048
```

### 7.3 文件级变更说明

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `integration/rag_blueprint/config.py` | **新增（Phase 1 最先）** | 全局配置中心，EntityType/QueryIntent/RelationType 枚举 + RetrievalConfig/EmbeddingConfig/GenerationConfig 数据类 |
| `integration/agentic_rag_mvp.py` | 废弃标记 | 添加 `@deprecated` 标记，指向旧的学术 KG 示例数据 |
| `integration/pipeline.py` | 扩展 | 增加 `--output-chunks` 选项，产 chunks.jsonl |
| `integration/kg_builder.py` | 扩展 | 新增 7 种企业边关系类型的构建逻辑 |
| `integration/CLAUDE.md` | 更新 | 增加 rag_blueprint 模块的说明 |
| `integration/config/extraction_examples.yaml` | 重写 | 4 个学术示例 → 4 个企业项目报告示例 |
| `backend/worker.py` | 扩展 | 增加 DOCX/XLSX 本地解析路由（当前所有文件走 MinerU API） |
| `backend/routes/graph.py` | 更新 | TYPE_COLORS 移除幽灵类型（task/table/figure/equation_parameter），切换为企业实体类型 |
| `backend/routes/query.py` | 更新 | System Prompt 切换为企业实体类型 + 企业意图 |
| `frontend/src/lib/constants.ts` | 更新 | ENTITY_TYPES/TYPE_COLORS/TYPE_ICONS 切换为企业实体体系 |
| `frontend/src/pages/QueryPage.tsx` | 扩展 | 增加检索来源标识 + 意图类型展示 + Table 路结构化渲染 |
| `frontend/src/pages/GraphPage.tsx` | 更新 | 企业实体配色 + 新边关系类型样式 + source_file 溯源 |
| `langextract/docs/agentic-kg-rag-specification-v1.0.md` | 补充引用 | 添加指向本文档的交叉引用 |
| `langextract/docs/bridge-pipeline-specification-v1.0.md` | 补充引用 | 企业实体类型体系变更说明 |

**⚠️ 代码副本同步策略**：

`backend/` 目录中 6 个文件（pipeline.py / bridge.py / grounding.py / kg_builder.py / schema.py / agentic_rag_mvp.py）是 `integration/` 同名文件的**完全副本**。Phase 1 实施时：
- 优先修改 `integration/` 版本（source of truth）
- 每次修改后通过 `diff` 对比确认 backend 副本已同步
- 长期建议：将共享代码提取到 `integration/` 作为包，`backend/` 通过 `sys.path` 或 pip editable install 引用，消除复制

**⚠️ API Key 环境变量命名不统一**：

当前 `pipeline.py` 使用 `LANGEXTRACT_API_KEY`，`agentic_rag_mvp.py` 使用 `DEEPSEEK_API_KEY`，两者指向同一 DeepSeek API Key。蓝图所有新增模块统一使用 `DEEPSEEK_API_KEY`（更直接、与 LangChain `ChatOpenAI` 约定的 `OPENAI_API_KEY` 模式一致）。旧变量 `LANGEXTRACT_API_KEY` 在 `pipeline.py` 中保留兼容（优先读新变量，回退读旧变量）。

---

## 附录 A：最小可行版本（MVP Scope）

如果按最小可用版本交付，只实现以下 6 个模块的核心路径：

| 模块 | MVP 实现 | 暂不实现 |
|------|----------|----------|
| ① 文档处理 | DOCX 解析（python-docx）+ XLSX 解析（openpyxl）+ 章节语义分块 | entity-aware 分块 |
| ② Embedding | `text-embedding-3-small` | 本地 BGE-M3 |
| ③ 向量数据库 | ChromaDB，单 collection | 多 collection、增量更新 |
| ③ Table 索引 | DuckDB 内存表，基础数值条件查询 | 复杂 SQL 嵌套子查询 |
| ④ 检索 — Query 预处理 | LLM Prompt 改写 + 企业意图识别（4 类）+ 数值条件提取 | 多轮指代消解 |
| ④ 检索 — Query 向量化 | embed_query()，同 chunk embedding 模型 | — |
| ④ 检索 — 多路召回 | 向量 + Table + KG + BM25 四路 | 多 Query 变体路 |
| ④ 检索 — Rerank | RRF 粗排（纯规则，零模型依赖） | Cross-encoder 精排 |
| ④ 检索 — 冗余过滤 | 相邻合并 + Token 截断 | 相似去重（Jaccard） |
| ⑤ Prompt | 两段式（System + Context+Query），固定模板 | Token 预算动态计算 |
| ⑥ LLM 生成 | 基础生成 + source_file/project_id 溯源标记 | 溯源验证、自修正 |

MVP 目标：端到端打通企业文档（DOCX/PDF）→ 答案 全链路，覆盖制度查询/流程归属/数据指标三类场景，每个场景 ≥3 题测试通过。

---

## 附录 B：与现有规范的交叉引用

| 本文档模块 | 引用的上游规范 |
|------------|---------------|
| ① 文档处理 | `bridge-pipeline-specification-v1.0.md` §2-5（BridgePipeline 流程） |
| ① 分块策略 | `MinerU-API-Specification.md` §4（full.md 输出格式） |
| ② Embedding | `LangExtract-Pipeline-Specification.md` §5.3（模型配置） |
| ④ 检索 KG 路 | `agentic-kg-rag-specification-v1.0.md` §5（工具集规范） |
| ⑥ LLM 生成 | `agentic-kg-rag-specification-v1.0.md` §4（大模型接入规范） |

---

## 附录 C：前端适配清单

蓝图切换到企业场景后，前端需要同步变更以下位置：

### C.1 `frontend/src/lib/constants.ts`

| 变更项 | 旧值 | 新值 |
|--------|------|------|
| `ENTITY_TYPES` 枚举 | 学术 10 类 + 硬编码示例 count | 企业 10 类，移除硬编码 count（改为 API 动态获取） |
| `TYPE_COLORS` 映射 | 学术配色 | 企业实体配色（保持暗色主题一致性） |
| `TYPE_ICONS` 映射 | 学术图标 | 企业场景图标（如 `Building2`/`Users`/`GitBranch`/`Gauge`等） |

### C.2 Query 页面 (`QueryPage.tsx`)

- **检索来源展示**：AnswerBubble 底部 SourceChips 需要新增 `source` 字段展示（`"vector"`/`"table"`/`"kg"`/`"keyword"`/`"multi-query"`）
- **意图类型展示**：答案顶部可显示 Query 预处理识别出的意图标签（`policy_lookup`/`process_attribution`/`metric`/`hybrid`）
- **Table 路结果**：当 source=`"table"` 时，SourceCard 应渲染结构化表格而非纯文本

### C.3 Graph 页面 (`GraphPage.tsx`)

- **新实体类型颜色**：LegendFilter 和 GraphCanvas 使用企业 10 类配色
- **新边关系类型**：边的样式（颜色/虚线/粗细）需对应 10 种边关系类型
- **Grounding 展示**：企业场景的溯源信息包含 `source_file` 字段，FloatingPanel 的 NodeDetail 需展示来源文件

### C.4 Upload 页面 (`UploadPage.tsx`)

- **支持格式**：上传白名单增加 `.docx`、`.xlsx`（目前可能仅支持 PDF 格式图标展示）
- **Pipeline 阶段**：阶段名称与新的 Phase 1 流程对齐

### C.5 Documents 页面 (`DocumentsPage.tsx`)

- **列表字段**：表格的 `filename` 列保持不变（后端返回 `filename` schema 不变）
- **KG 统计**：列 "KG 统计" 的数据来源需适配企业 KG 的 `enterprise_kg/` 目录

---

> **文档版本**: v1.1 | **日期**: 2026-06-08 | **状态**: 已评审，待进入 Phase 1 实施
