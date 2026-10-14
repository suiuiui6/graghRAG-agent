# 多模态 RAG 问答系统 — 后端服务架构与 API 接口规范 v1.0

> **版本**: v1.0 | **日期**: 2026-05-24
>
> 基于 MinerU → BridgePipeline → Agentic KG-RAG 三阶段链路，
> 定义工程化后端服务的完整架构与 RESTful API 规范。

---

## 2026-10-12 安全修订：资料授权与任务隔离

2026-10-13维护补充：项目归档须先验证项目存在且`org_id`等于已授权请求组织；跨组织项目与不存在项目均404，不产生归档副作用。飞书告警使用`build_error_card(message=...)`构造卡片，再设置严重度标题；供应商不可用走统一503错误边界，不能因内部参数不匹配返回500。供应商接收尚未实测。

飞书回调遵循官方SDK认证模式（含URL verification）：配置Encrypt Key时，必须提供timestamp/nonce/signature三头，缺头401，使用SHA256(timestamp + nonce + encrypt_key + 原始body bytes)及常量时间比较，错误签名403；同时配置两项时Encrypt Key优先。仅配置Verification Token时核验消息体token（schema事件使用header.token，按官方优先序），缺失或不匹配401，不能将Verification Token充当签名密钥。两项均未配置的旧开发兼容模式不能视为生产鉴权。签名有效性不等于防重放；现实现尚无时间窗及去重承诺，重复旧签名请求测试结果单独记录。算法来源：`https://github.com/larksuite/node-sdk/blob/main/dispatcher/request-handle.ts`。

KG版本创建、激活及生命周期清理共享文档级`.versions.lock`跨进程锁。版本清单用同目录临时文件、flush/fsync和原子替换写入；`next_version`须为正整数，版本标识为非负整数（均拒绝bool），下一版本同时高于清单及磁盘现存版本，历史号不复用。激活仅接受清单中存在且位于文档目录内的真实版本目录；链接及junction拒绝。具体保留与失败恢复遵循企业蓝图的2026-10-13补充。

本节覆盖下文旧示例中与认证、资源范围、删除和缓存有关的宽松行为，适用于当前后端。

- 受保护请求默认 401。管理密钥、真实用户 JWT、托管 API key 共存；JWT 必须有 sub、数值 exp、issuer=graphrag-backend、正确 type，refresh 不能访问资料。每次请求读取当前用户和角色，禁用用户立即使其 JWT 和托管 key 失效。安全 JWT_SECRET_KEY 至少 32 字符且不得使用公开开发默认值；仅显式 AUTH_ALLOW_ANONYMOUS=true 的非生产环境允许匿名开发与本地任意密码登录。
- 认证先于租户解析与资源守卫。CORS 预检由最外层 CORS 处理，实际请求仍经过认证。公开路径按精确集合匹配，含健康、认证入口、API 文档与 /static/chat-widget.js；不允许公共前缀扩大到资料或管理接口。
- 入库的 owner_id 来自可信身份。X-Project-Id 仅作选择器，须核验项目、活跃组织与当前真实成员；项目入库要求编辑能力。任务状态、文档列表、下载、删除、chunk_count、文件和图谱复用同一资源规则；未知或不可见对象统一 404。旧资料缺归属只向管理员开放，不猜测归属或默认公开。尚无资源过滤的目录、导出、血缘等接口暂限管理员。
- /query 在调用模型前按授权文档加载独立 KG 快照；节点及来源携带真实 document_id、document_version，按 active_version 读取。无 document_id 表示全部授权资料，无可用授权节点直接返回 metadata.status=no_data，不调用模型。
- /rag/query 的指定文档、指定项目及非管理员请求仅走授权 KG，禁用全局 vector/BM25/table 与旧未绑定会话。显式要求无法隔离的来源返回 503，旧 session_id 返回 409。管理员无范围限制保留既有全局 RAG 路径。metadata.retrieval_scope=authorized_kg 说明受限来源；完整多来源隔离与绑定会话是后续工作。
- 删除先查授权记录再解析全部受控资产，仅删除登记的精确 filepath 与文档 KG 目录；拒绝越界、symlink、Windows junction，未知 doc_ 不产生副作用。清理失败返回错误并保留记录以便重试；成功后使查询运行时失效。外部本地原始资料不属于可删除上传资产。
- 所有入库入口使用 ingest_ 加完整 UUID；MinerU 产物发布到 output/mineru/<完整task_id>/result，独占任务目录，工作目录不作为运行时恢复来源，已有/残留任务目录拒绝覆盖。allow_cached_mineru_output 字段保留兼容，true 在产生入库副作用前返回 400；工作器绝不复用未能证明输入归属的历史产物。

本地文件、JSON、图谱和认证测试不能替代真实 MinerU/OIDC/生成供应商验收；验证记录与限制见 docs/testing/2026-10-12-p0-verification.md。

## 目录

1. [系统架构总览](#1-系统架构总览)
2. [服务拓扑与部署](#2-服务拓扑与部署)
3. [API 接口规范](#3-api-接口规范)
4. [数据模型定义](#4-数据模型定义)
5. [异步任务状态机](#5-异步任务状态机)
6. [错误处理规范](#6-错误处理规范)
7. [实施路线](#7-实施路线)

---

## 1. 系统架构总览

```
                          Multi-Modal RAG Backend
═══════════════════════════════════════════════════════════════════════════

  CLIENT                          API GATEWAY                   PIPELINE ENGINE
 ────────                        ────────────                  ───────────────
                                                              
  Web UI ─┐                   ┌─────────────────┐           ┌──────────────────┐
          │   HTTP/REST       │                 │           │                  │
  cURL ───┼──────────────────►│  FastAPI Server  │──────────►│  Task Queue      │
          │                   │  :8000           │           │  (Background)    │
  SDK  ───┘                   │                 │           │                  │
                              └────────┬────────┘           └────────┬─────────┘
                                       │                             │
                                       │                             ▼
                              ┌────────▼────────┐           ┌──────────────────┐
                              │  File Storage   │           │  Indexing Worker │
                              │  ./uploads/     │           │  ┌────────────┐  │
                              └─────────────────┘           │  │ MinerU API │  │
                                                            │  └─────┬──────┘  │
                                                            │        ▼         │
                                                            │  BridgePipeline  │
                                                            │  ┌─────┬──────┐  │
                                                            │  │ KG  │ JSON │  │
                                                            │  └──────┴──────┘  │
                                                            └────────┬─────────┘
                                                                     │
                                       ┌─────────────────────────────┘
                                       ▼
                              ┌──────────────────┐
                              │  Query Engine    │
                              │  ┌────────────┐  │
                              │  │ Agentic-RAG │  │
                              │  │ (LangGraph) │  │
                              │  └────────────┘  │
                              └──────────────────┘
```

### 1.1 核心服务模块

| 模块 | 技术 | 职责 |
|---|---|---|
| **API Gateway** | FastAPI + Pydantic v2 | 请求路由、参数校验、认证 |
| **File Manager** | Python `aiofiles` + `python-multipart` | 多格式文件上传、临时存储 |
| **Task Queue** | `asyncio` BackgroundTasks / Celery | 异步索引任务编排 |
| **Indexing Worker** | 复用 `integration/pipeline.py` | MinerU → BridgePipeline → KG |
| **Query Engine** | 复用 `integration/agentic_rag_mvp.py` | LangGraph Agent → KG QA |
| **KG Store** | NetworkX (内存) + JSON 文件 (持久化) | 知识图谱存储与加载 |

### 1.2 数据流向

```
POST /ingest   →  save file  →  background task  →  MinerU  →  BridgePipeline  →  KG
                                                                                    │
GET  /query    →  check status →  Agentic-RAG  ←───────────────────────────────────┘
                   │
                   ▼
              200 { answer, sources, kg_stats }
```

---

## 2. 服务拓扑与部署

### 2.1 目录结构

```
D:\graghRAG-agent\
├── integration\
│   ├── server.py                  ← ★ FastAPI 主入口
│   ├── models.py                  ← Pydantic 数据模型
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── ingest.py              ← POST /ingest
│   │   ├── query.py               ← POST /query
│   │   └── status.py              ← GET /status/{task_id}
│   ├── worker.py                  ← 后台索引任务编排
│   ├── pipeline.py                ← 已有: BridgePipeline
│   ├── agentic_rag_mvp.py         ← 已有: Agentic KG-RAG
│   ├── bridge.py                  ← 已有: Format Bridge
│   ├── grounding.py               ← 已有: Grounding
│   ├── kg_builder.py              ← 已有: KG Builder
│   ├── uploads/                   ← 上传文件暂存
│   └── output/kg/                 ← KG 数据持久化
└── docs/
    ├── backend-api-architecture-v1.0.md  ← 本文档
    ├── agentic-kg-rag-specification-v1.0.md
    ├── bridge-pipeline-specification-v1.0.md
    └── ...
```

### 2.2 部署方式

```bash
# 启动服务
source D:/graghRAG-agent/langextract/.venv/Scripts/activate
cd D:/graghRAG-agent/integration
pip install fastapi uvicorn aiofiles python-multipart
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# API 文档自动生成
# Swagger UI: http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc
```

---

## 3. API 接口规范

### 3.1 接口总览

| Method | Path | 说明 | 请求体 | 响应 |
|---|---|---|---|---|
| `POST` | `/api/v1/ingest` | 上传文档并触发索引 | `multipart/form-data` | `IngestResponse` |
| `GET` | `/api/v1/status/{task_id}` | 查询索引任务状态 | — | `StatusResponse` |
| `POST` | `/api/v1/query` | 知识图谱问答 | `application/json` | `QueryResponse` |
| `GET` | `/api/v1/health` | 健康检查 | — | `HealthResponse` |
| `GET` | `/api/v1/documents` | 列出已索引文档 | — | `DocumentListResponse` |
| `DELETE` | `/api/v1/documents/{doc_id}` | 删除文档及 KG 数据 | — | `DeleteResponse` |

### 3.2 接口详情

---

#### 3.2.1 POST /api/v1/ingest — 文档上传与索引

上传文档文件，触发离线索引管道 (MinerU → BridgePipeline → KG)。

**Request**:

```
POST /api/v1/ingest
Content-Type: multipart/form-data
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `file` | `file` (binary) | ✅ | — | 文档文件，支持 `.pdf` `.docx` `.pptx` `.xlsx` `.png` `.jpg` `.epub` `.html` |
| `language` | `string` | 否 | `"ch"` | 文档语言: `ch` / `en` / `ja` |
| `enable_ocr` | `bool` | 否 | `false` | 是否启用 OCR (扫描件必开) |
| `enable_formula` | `bool` | 否 | `true` | 是否识别公式 |
| `enable_table` | `bool` | 否 | `true` | 是否识别表格 |
| `model_version` | `string` | 否 | `"pipeline"` | MinerU 引擎: `pipeline` / `vlm` |
| `extraction_model` | `string` | 否 | `"deepseek-chat"` | LangExtract 模型 |
| `metadata` | `string` (JSON) | 否 | `"{}"` | 自定义元数据 |

**文件限制**:
- 最大: 200 MB
- 支持格式: PDF, DOCX, DOC, PPTX, PPT, XLSX, PNG, JPG, JPEG, EPUB, HTML

**Response** (`201 Created`):

```json
{
  "task_id": "ingest_a1b2c3d4",
  "status": "pending",
  "filename": "transformer_paper.pdf",
  "file_size_bytes": 2127679,
  "created_at": "2026-05-24T17:30:00Z",
  "estimated_duration_seconds": 60,
  "links": {
    "status": "/api/v1/status/ingest_a1b2c3d4"
  }
}
```

**Response** (`400 Bad Request`):

```json
{
  "error": {
    "code": "UNSUPPORTED_FORMAT",
    "message": "File format '.docm' is not supported. Supported: pdf, docx, pptx, xlsx, png, jpg, epub, html"
  }
}
```

**Response** (`413 Payload Too Large`):

```json
{
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "File size 250MB exceeds maximum 200MB",
    "max_size_bytes": 209715200
  }
}
```

---

#### 3.2.2 GET /api/v1/status/{task_id} — 查询索引状态

查询文档索引管道的进度。

**Request**:

```
GET /api/v1/status/ingest_a1b2c3d4
```

**Response** (`200 OK` — 进行中):

```json
{
  "task_id": "ingest_a1b2c3d4",
  "status": "running",
  "stage": "bridgepipeline",
  "progress": {
    "stage_name": "BridgePipeline: LangExtract Extraction",
    "current_step": 3,
    "total_steps": 5,
    "details": {
      "mineru": "done",
      "bridge": "done",
      "extraction": "running",
      "grounding": "pending",
      "kg_build": "pending"
    }
  },
  "created_at": "2026-05-24T17:30:00Z",
  "updated_at": "2026-05-24T17:30:45Z"
}
```

**Response** (`200 OK` — 完成):

```json
{
  "task_id": "ingest_a1b2c3d4",
  "status": "done",
  "stage": "completed",
  "progress": {
    "stage_name": "Complete",
    "current_step": 5,
    "total_steps": 5,
    "details": {
      "mineru": "done",
      "bridge": "done",
      "extraction": "done",
      "grounding": "done",
      "kg_build": "done"
    }
  },
  "result": {
    "document_id": "doc_a1b2c3d4",
    "kg_nodes": 310,
    "kg_edges": 1529,
    "grounded_entities": 214,
    "entity_types": 10,
    "pages_parsed": 15,
    "kg_path": "/output/kg/ingest_a1b2c3d4/"
  },
  "created_at": "2026-05-24T17:30:00Z",
  "updated_at": "2026-05-24T17:31:49Z",
  "duration_seconds": 109
}
```

**Response** (`200 OK` — 失败):

```json
{
  "task_id": "ingest_a1b2c3d4",
  "status": "failed",
  "stage": "mineru",
  "error": {
    "code": "MINERU_API_ERROR",
    "message": "MinerU API returned: File is corrupted or password-protected"
  },
  "created_at": "2026-05-24T17:30:00Z",
  "updated_at": "2026-05-24T17:30:30Z"
}
```

---

#### 3.2.3 POST /api/v1/query — 知识图谱问答

对已索引文档的知识图谱执行自然语言问答。

**Request**:

```
POST /api/v1/query
Content-Type: application/json
```

```json
{
  "query": "What BLEU scores did the Transformer achieve?",
  "document_id": "doc_a1b2c3d4",
  "options": {
    "max_tool_calls": 10,
    "temperature": 0.0,
    "language": "en",
    "include_sources": true
  }
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `query` | `string` | ✅ | — | 自然语言问题 |
| `document_id` | `string` | 否 | — | 限定查询的文档范围。空 = 全部已索引文档 |
| `options.max_tool_calls` | `int` | 否 | `10` | Agent 最大工具调用次数 |
| `options.temperature` | `float` | 否 | `0.0` | LLM 温度 |
| `options.language` | `string` | 否 | `"en"` | 期望的回答语言 |
| `options.include_sources` | `bool` | 否 | `true` | 是否返回溯源信息 |

**Response** (`200 OK`):

```json
{
  "query": "What BLEU scores did the Transformer achieve?",
  "answer": "Based on the Knowledge Graph, the Transformer achieved:\n\n| BLEU Score | Dataset |\n|:----------:|:--------|\n| **28.4 BLEU** | **WMT 2014 English-to-German** |\n| **41.8 BLEU** | **WMT 2014 English-to-French** |\n\nBoth scores are associated with the Transformer model (node: n0018).",
  "sources": [
    {
      "node_id": "n0019",
      "entity_type": "metric",
      "label": "28.4 BLEU",
      "properties": {
        "name": "BLEU",
        "value": "28.4",
        "task": "translation"
      },
      "page_idx": 0,
      "bbox_norm": [150, 400, 280, 415],
      "grounding_status": "grounded",
      "relevance_score": 0.95
    },
    {
      "node_id": "n0020",
      "entity_type": "metric",
      "label": "41.8 BLEU",
      "properties": {
        "name": "BLEU",
        "value": "41.8",
        "task": "translation"
      },
      "page_idx": 0,
      "bbox_norm": [200, 500, 330, 515],
      "grounding_status": "grounded",
      "relevance_score": 0.92
    }
  ],
  "subgraph": {
    "nodes": [ ... ],
    "edges": [ ... ]
  },
  "metadata": {
    "document_id": "doc_a1b2c3d4",
    "model": "deepseek-chat",
    "tool_calls": 2,
    "duration_ms": 3200,
    "timestamp": "2026-05-24T17:32:00Z"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query` | `string` | ✅ | 原始问题回显 |
| `answer` | `string` | ✅ | 自然语言答案 (含 node ID 引用) |
| `sources` | `array[SourceNode]` | 否 | 答案引用的 KG 节点列表 (含 `page_idx` + `bbox_norm` 溯源) |
| `subgraph` | `object` | 否 | 相关子图 (nodes + edges) |
| `metadata.model` | `string` | ✅ | 使用的 LLM 模型 |
| `metadata.tool_calls` | `int` | ✅ | Agent 实际工具调用次数 |
| `metadata.duration_ms` | `int` | ✅ | 问答耗时 (毫秒) |
| `metadata.timestamp` | `string` | ✅ | ISO 8601 时间戳 |

**SourceNode 结构**:

| 字段 | 类型 | 说明 |
|---|---|---|
| `node_id` | `string` | KG 节点 ID |
| `entity_type` | `string` | 实体类别 |
| `label` | `string` | 实体文本 |
| `properties` | `dict` | 实体属性 |
| `page_idx` | `int \| null` | PDF 页码 |
| `bbox_norm` | `[float×4] \| null` | 归一化包围框 |
| `grounding_status` | `string` | `"grounded"` / `"ungrounded"` |
| `relevance_score` | `float` | 相关性分数 (0.0-1.0) |

**Response** (`404 Not Found`):

```json
{
  "error": {
    "code": "DOCUMENT_NOT_INDEXED",
    "message": "Document 'doc_a1b2c3d4' has not been indexed yet. Current status: pending"
  }
}
```

---

#### 3.2.4 GET /api/v1/health — 健康检查

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "components": {
    "api_server": "ok",
    "mineru_api": "ok",
    "deepseek_api": "ok",
    "kg_store": "ok"
  },
  "stats": {
    "total_documents": 1,
    "total_kg_nodes": 310,
    "total_queries_served": 5
  }
}
```

#### 3.2.5 GET /api/v1/documents — 已索引文档列表

```json
{
  "documents": [
    {
      "document_id": "doc_a1b2c3d4",
      "filename": "transformer_paper.pdf",
      "status": "indexed",
      "kg_nodes": 310,
      "kg_edges": 1529,
      "pages": 15,
      "indexed_at": "2026-05-24T17:31:49Z",
      "file_size_mb": 2.0
    }
  ],
  "total": 1
}
```

#### 3.2.6 DELETE /api/v1/documents/{doc_id} — 删除文档

```json
{
  "document_id": "doc_a1b2c3d4",
  "status": "deleted",
  "deleted_at": "2026-05-24T18:00:00Z"
}
```

---

## 4. 数据模型定义

### 4.1 Pydantic Models

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

# ---- Enums ----
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

class PipelineStage(str, Enum):
    UPLOAD = "upload"
    MINERU = "mineru"
    BRIDGE = "bridge"
    EXTRACTION = "extraction"
    GROUNDING = "grounding"
    KG_BUILD = "kg_build"
    COMPLETED = "completed"

class DocumentFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    PPTX = "pptx"
    PPT = "ppt"
    XLSX = "xlsx"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"
    EPUB = "epub"
    HTML = "html"

SUPPORTED_FORMATS = {f.value for f in DocumentFormat}
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB

# ---- Request Models ----
class QueryOptions(BaseModel):
    max_tool_calls: int = Field(default=10, ge=1, le=50)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    language: str = Field(default="en", pattern="^(en|ch|ja)$")
    include_sources: bool = Field(default=True)
    enabled_sources: list[Literal["vector", "kg", "bm25", "table", "multi_query"]] | None = None

class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    document_id: Optional[str] = None
    options: QueryOptions = Field(default_factory=QueryOptions)

# ---- Response Models ----
class SourceNode(BaseModel):
    node_id: str
    entity_type: str
    label: str
    properties: dict
    page_idx: Optional[int]
    bbox_norm: Optional[list[float]]
    grounding_status: str
    relevance_score: float

class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: Optional[list[SourceNode]] = None
    subgraph: Optional[dict] = None
    metadata: dict

class StageProgress(BaseModel):
    stage_name: str
    current_step: int
    total_steps: int = 5
    details: dict

class TaskResult(BaseModel):
    document_id: Optional[str] = None
    kg_nodes: Optional[int] = None
    kg_edges: Optional[int] = None
    grounded_entities: Optional[int] = None
    entity_types: Optional[int] = None
    pages_parsed: Optional[int] = None
    kg_path: Optional[str] = None

class TaskError(BaseModel):
    code: str
    message: str

class StatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    stage: Optional[PipelineStage] = None
    progress: Optional[StageProgress] = None
    result: Optional[TaskResult] = None
    error: Optional[TaskError] = None
    created_at: datetime
    updated_at: datetime
    duration_seconds: Optional[int] = None

class IngestResponse(BaseModel):
    task_id: str
    status: TaskStatus
    filename: str
    file_size_bytes: int
    created_at: datetime
    estimated_duration_seconds: int
    links: dict
```

### 4.2 支持的文件格式

遵循 `MinerU_MVP测试配置指南.md_v1.0.md` §2.1:

| 格式 | 扩展名 | MIME Type | MinerU 后端 |
|---|---|---|---|
| **PDF** | `.pdf` | `application/pdf` | pipeline / vlm |
| Word | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | pipeline |
| Word | `.doc` | `application/msword` | pipeline |
| PowerPoint | `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | pipeline |
| PowerPoint | `.ppt` | `application/vnd.ms-powerpoint` | pipeline (需转 PDF) |
| Excel | `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | pipeline |
| Image | `.png`, `.jpg`, `.jpeg` | `image/png`, `image/jpeg` | pipeline (auto OCR) |
| EPUB | `.epub` | `application/epub+zip` | pipeline |
| HTML | `.html` | `text/html` | MinerU-HTML |

### 4.3.0a 请求级证据追踪增量合同（M4-P2，2026-10-07）

`QueryOptions.include_evidence_trace` 为 strict boolean，默认 `false`，不接受字符串代替布尔值。query / summarize / retrieve 仅在显式开启时返回 `metadata.evidence_trace`；effective_config.flags 同时记录开关。显式追踪在主 pipeline 不可用时返回 503，不降级到无追踪的 legacy Agent。关闭开关的普通响应不返回追踪全文。此开关不是授权控制；追踪包含输入上下文/证据/答案全文，应沿用端点访问控制，并由调用者控制留存、脱敏与分享。

身份版本为 `evidence-v1`，规范 ID 为 `ev1_<64位小写SHA256>`。定位基底按文档 namespace（document_sha256 → document_id → source_file → 可识别的原 node 文档前缀）、对象类型、声明 span/source_item_id/原 ID/文本摘要构建，再结合完整观测内容哈希生成 ID。Vector 与 storage rescue 必须在1200字符投影之前识别全文；无文档 namespace 为 unknown_document，不能由 ID 反推可靠文档来源。content_sha256 对应投影前观测全文，observed_text_sha256 对应该阶段保留文本。同位置同内容多路径合并 source_paths、provenance、original_scores；同位置内容不同保留不同 ID 和 identity_conflicts。声明位置不等于核实位置：仅显式 span_verified=true 且长度一致才生成 original_span，否则为 null；KG JSON 原文映射保持未核实。

固定来源优先次序 vector / kg / bm25 / table / multi_query / community，加 canonical ID 作同分二级键；合并保留 protected_evidence，RRF/rerank 的重复观测采用最大已观测值，同时保存 score_observations，不虚构重算得分。唯一 legacy chunk_id 可保留为 citation alias，缺失或冲突 alias 改为 canonical ID；canonical 引用验证只能 exact match，不能采用 legacy 子串兼容。此验证只证明引用身份存在，不证明语义支持。

检索追踪依次记录 path_hits、rescue_hits、fusion_and_rescue、pre_rerank、post_rerank、retrieval_final；每次选择记录保留对象及相对上一观测面的 dropped ID/阶段原因。阶段原因是粗粒度规则，不伪造逐对象精确解释。retrieval_final 不等于实际模型可见上下文。

生成追踪区分 generation_mode、model_call_attempted、model_output_received、serialized_model_context、decision_evidence、raw_model_answer、answer_stages、final_answer；generator_decision_candidates 记录生成前补证候选。serialized_model_context 记录实际消息与 canonical JSON（UTF-8、排序键、紧凑分隔符）SHA256、context 文本/哈希和 visible_evidence。span 单位为 Python Unicode codepoint，半开区间；context_span 指序列化 context 中的可见正文，observed_span 指观测正文前缀，original_span 仅在来源已核实时给出。标题、domain hint、合成省略号不能计入可见原文证据。预算仍按约4字符/token估算，并非 tokenizer 精确预算。

provider_output 保存 strip/提示/修补前真实接收值；后续可记录 strip_whitespace、length_notice、citation_notice、repair、complete、supplement 和 API 的 api_response_limit（4000字符）。provider 失败不得把 fallback 复制为 raw；未接收模型输出为 null。确定性拒答/纠错未调用模型时 context/raw=null，单列 decision_evidence；模型失败但已构造消息时 context 仍为尝试调用的消息，不能称为已被模型消费。API trace.final_answer 必须等于返回答案。

实现与软件验收见 `docs/superpowers/plans/paper-m4-p2-verification.md`。P2 不实现持久化 trace 存储、跨请求生命周期、语义裁决、冻结 runner 或完整成本账本，不证明模型完整集成或公平实验通过。

### 4.3.0 生产 RAG 来源控制增量合同（M4-P1，2026-10-07）

本合同适用于 `/api/v1/rag/query`、`/api/v1/rag/retrieve`、`/api/v1/rag/summarize`，不改变历史 `/api/v1/query` 的 legacy 契约。

- `options.enabled_sources` 省略或为 null 时兼容原默认行为；显式列表为非空 allowlist，只接受 `vector`、`kg`、`bm25`、`table`、`multi_query`，按此顺序去重。空列表、未知来源、字符串替代列表返回 422。`per_source_caps` 是数量预算，不替代权限开关。
- 普通召回、global/community、global 的 local 回退、retrieval rescue（KG/BM25/Table）和 generator rescue（KG/storage-vector）均在调用前应用同一请求级权限。候选图谱补投影也受 KG 权限约束；输入节点 ID 不授予 KG 查询权限。配置及记录不得修改共享 pipeline.config。
- Multi-Query 还需 feature flag 开启、vector 权限、已有 embedding/vector 依赖和原文与改写不同。community 归属 KG，不接受独立开关；KG 禁用时跳过 global 并选择允许来源的 local。
- 显式列表下 Table 普通召回和补证均要求 metric intent；null 保留旧 Table 补证条件。补证还须满足自身查询条件和正 top-k。storage-vector 补证仅在储能/产量降低的核实问句触发。
- 显式来源请求的主 pipeline 不可用时返回 503，禁止悄悄使用 legacy fallback；null 仍兼容旧回退。该开关不承诺禁用一般查询预处理或模型生成服务。

生产 RAG 响应 `metadata.effective_config` 的 `schema_version` 为 `1.0`，记录 requested_sources（null 或规范列表）、allowed_sources、eligible_sources（权限和 feature 依赖通过，不保证资源或题型满足）、flags、budget、query_mode、stages、attempted_sources、executed_sources、skipped_sources、cross_encoder。query_mode 是所选路由；global 无有效后代命中时可回退 local，具体来源以 stages 为准。

stages 分 normal/global/retrieval_rescue/generator_rescue，各入口记录 status、reason、candidate_count。executed/count=0 是真实执行但零命中；skipped 表示未调用，含 source_disabled、query_condition、intent_condition、resource_unavailable 等原因；failed/count=null 表示调用失败而不是零命中。attempted 包括执行和失败，executed 只包括成功执行，community 汇总为 KG；skipped_sources 只汇总从未执行或失败的来源，逐入口原因以 stages 为准。cross_encoder 分 requested/attempted/executed/skip_reason，超时或不可用回退不算成功重排。

budget 记录来源 top-k/caps、pre-rerank cap、最终候选/context 上限及重排预算；生成响应另记 prompt_max_context_tokens（prompt 构造实参，不与 retrieval 上限混同）。raw_candidates_total 当前为 null（未锁总原始预算）。Multi-Query 合法空变体记 skipped/query_variants_empty，变体请求或解析失败记 failed；不向执行账本写入异常内容或凭据。本增量不等于稳定证据身份、实际模型可见上下文、完整成本账本或七变体公平实验通过，后续按 P2/P3 验收。评测口径详见 `iteration-2/eval-2-existing-components/rag_eval/RAG-EVAL-SPECIFICATION.md` 的 M4-P1 合同。

### 4.3 输出数据与规范文档的对应关系

| API 响应字段 | 来源规范文档 | 章节 |
|---|---|---|
| `QueryResponse.sources[].node_id` | `agentic-kg-rag-specification-v1.0.md` | §3.1.1 |
| `QueryResponse.sources[].entity_type` | `bridge-pipeline-specification-v1.0.md` | §7.4 |
| `QueryResponse.sources[].properties` | `LangExtract-Pipeline-Specification.md` | §3.2 |
| `QueryResponse.sources[].page_idx` | `bridge-pipeline-specification-v1.0.md` | §7.2 |
| `QueryResponse.sources[].bbox_norm` | `bridge-pipeline-specification-v1.0.md` | §7.2 |
| `StatusResponse.result.kg_nodes` | `agentic-kg-rag-specification-v1.0.md` | §3.1.1 |
| `IngestResponse` 文件格式 | `MinerU_MVP测试配置指南.md_v1.0.md` | §2.1 |

---

## 5. 异步任务状态机

### 5.1 状态流转图

```
  upload ──────────────────────────────────────────────────────────────┐
    │                                                                   │
    ▼                                                                   │
 ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌────────┐
 │ pending │───►│ mineru  │───►│  bridge  │───►│extraction│───►│  done  │
 └─────────┘    └────┬────┘    └────┬─────┘    └────┬────┘    └────────┘
                     │              │               │
                     ▼              ▼               ▼
                ┌─────────┐   ┌─────────┐    ┌─────────┐
                │ failed  │   │ failed  │    │ failed  │
                └─────────┘   └─────────┘    └─────────┘
```

### 5.2 各阶段任务

| Stage | 执行内容 | 输入 | 输出 | 预计耗时 |
|---|---|---|---|---|
| `pending` | 文件接收 + 校验 | PDF/DOCX binary | 保存到 `uploads/` | < 1s |
| `mineru` | 上传公网 URL → MinerU API → 下载 ZIP | `uploads/{task_id}.pdf` | `full.md` + `content_list.json` + `layout.json` | 10-60s |
| `bridge` | Format Bridge: section 分段 + PositionMap | MinerU output | `list[Document]` + `PositionMap` | 1-2s |
| `extraction` | LangExtract + DeepSeek 实体抽取 | Documents + examples | `list[AnnotatedDocument]` | 30-120s |
| `grounding` | 溯源解析: char → bbox + page | AnnotatedDocuments + PositionMap | `list[GroundedExtraction]` | 1-2s |
| `kg_build` | KG 构建: nodes.json + edges.json | GroundedExtractions | `nodes.json` + `edges.json` | 2-5s |
| `done` | KG 加载到内存 | nodes.json + edges.json | NetworkX Graph 就绪 | < 1s |

### 5.3 任务超时与重试

| 阶段 | 超时 (秒) | 最大重试 | 重试策略 |
|---|---|---|---|
| `mineru` | 600 | 3 | 指数退避 (5s, 10s, 20s) |
| `extraction` | 300 | 2 | 切换 temperature (0.0 → 0.1 → 0.3) |
| `bridge` / `grounding` / `kg_build` | 30 | 0 | 无重试 (确定性逻辑) |

---

## 6. 错误处理规范

### 6.1 HTTP 状态码

| Code | 含义 | 场景 |
|---|---|---|
| `200` | 成功 | 查询/状态正常返回 |
| `201` | 已创建 | 文档上传成功 |
| `400` | 请求错误 | 格式不支持、参数校验失败 |
| `404` | 未找到 | document_id 不存在或未索引 |
| `413` | 文件过大 | 超过 200MB |
| `422` | 参数校验失败 | Pydantic 验证错误 |
| `429` | 频率限制 | 超过 API 调用限额 |
| `500` | 服务器内部错误 | 未预期的异常 |
| `503` | 服务不可用 | MinerU / DeepSeek API 不可达 |

### 6.2 错误响应格式

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "details": {
      "field": "optional field-level detail",
      "suggestion": "How to fix"
    }
  }
}
```

### 6.3 错误码枚举

| Code | HTTP | 说明 |
|---|---|---|
| `UNSUPPORTED_FORMAT` | 400 | 文件格式不支持 |
| `FILE_TOO_LARGE` | 413 | 文件超过大小限制 |
| `DOCUMENT_NOT_INDEXED` | 404 | 文档尚未索引完成 |
| `DOCUMENT_NOT_FOUND` | 404 | 文档 ID 不存在 |
| `MINERU_API_ERROR` | 502 | MinerU API 调用失败 |
| `DEEPSEEK_API_ERROR` | 502 | DeepSeek API 调用失败 |
| `KG_NOT_LOADED` | 503 | KG 未加载到内存 |
| `TASK_TIMEOUT` | 500 | 任务超时 |
| `INTERNAL_ERROR` | 500 | 未预期的服务器错误 |
| `RATE_LIMITED` | 429 | 请求频率超限 |

---

## 7. 实施路线

### Phase 1: FastAPI 骨架 (1 天)

```
□ server.py — FastAPI app 初始化 + CORS + lifespan
□ models.py — 所有 Pydantic 模型
□ routes/ingest.py — POST /ingest (文件接收 + 格式校验)
□ routes/status.py — GET /status/{task_id} (内存任务状态查询)
□ routes/query.py — POST /query (加载 KG + 调用 agentic_rag_mvp)
□ routes/health.py — GET /health (组件健康检查)
```

### Phase 2: 异步任务引擎 (1 天)

```
□ worker.py — BackgroundTasks 封装 5 个 pipeline stage
□ TaskStore — 内存 dict 存储任务状态 (生产环境换 Redis/DB)
□ Stage progress 回调机制
□ 超时控制 + 重试逻辑
```

### Phase 3: 集成与测试 (1 天)

```
□ 端到端测试: POST /ingest → poll /status → POST /query
□ 错误场景覆盖: 无效文件 / 超大文件 / API 故障
□ 性能基准: < 200ms API 响应 (不含 pipeline 异步耗时)
```

### Phase 4: 生产加固 (1-2 天)

```
□ File storage → 对象存储 (S3/MinIO)
□ Task queue → Celery + Redis
□ KG 持久化 → 数据库 (Neo4j / PostgreSQL)
□ 认证 → API Key / JWT
□ 日志 → structlog / OpenTelemetry
□ 监控 → Prometheus metrics endpoint
```

---

## 附录 A: 完整调用示例

```bash
# 1. 上传 PDF 文档
curl -X POST http://localhost:8000/api/v1/ingest \
  -F "file=@transformer_paper.pdf" \
  -F "language=en" \
  -F "enable_formula=true" \
  -F "enable_table=true"

# Response: {"task_id": "ingest_abc123", "status": "pending", ...}

# 2. 轮询索引状态
curl http://localhost:8000/api/v1/status/ingest_abc123

# Response: {"task_id": "ingest_abc123", "status": "running", "stage": "extraction", ...}
# ...等待...
# Response: {"task_id": "ingest_abc123", "status": "done", "result": {"kg_nodes": 310, ...}}

# 3. KG 问答
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What BLEU scores did the Transformer achieve?",
    "document_id": "doc_abc123",
    "options": {"include_sources": true}
  }'

# Response: {"query": "...", "answer": "...28.4 BLEU...", "sources": [...], "metadata": {...}}
```

## 附录 B: 文档修订记录

| 版本 | 日期 | 修订内容 |
|---|---|---|
| v1.0 | 2026-05-24 | 初始版本: 完整定义后端服务架构、6 个 API 端点、Pydantic 数据模型、异步任务状态机、错误处理规范、4 Phase 实施路线 |
| v1.0.1 | 2026-05-29 | 追加"已知陷阱"章节，回流自历史排障报告 |

---

## 已知陷阱（来自历史排障报告回流，2026-05-29）

### 启动顺序：`load_dotenv` 必须在导入业务模块之前

**症状**：`backend/server.py` 启动后报 `AccessKeyId not found`，但 `.env` 文件中已配置。
**根因**：业务模块在 `load_dotenv()` 之前被 import，模块级常量已读取空字符串。
**约束**：`backend/server.py` 顶部必须按以下顺序：
1. `from dotenv import load_dotenv; load_dotenv()`
2. 然后才能 `from backend.api import ...`

### 三处 Critical 后端约束

1. 任何调用 OSS 的代码必须先校验 `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` / `OSS_BUCKET` / `OSS_ENDPOINT` 四个环境变量都非空；任一为空时**立即抛出**，不要降级到默认值
2. 健康检查接口 `/health` 必须只返回服务自身状态，**不要**级联检查下游（Neo4j / OSS）—— 那是 `/readyz` 的职责
3. 文档列表接口必须按 `created_at DESC` 排序，前端依赖此顺序渲染最近上传

### 文件上传链路约束

- 上传体积上限：单文件 100 MB，由 FastAPI `max_request_size` 控制
- 后端 `/api/upload` 必须返回 `{file_id, oss_url, filename}` 三字段（前端按此 schema 渲染列表）
- 文档名字段名为 `filename`，**不是** `name` / `title` / `original_name`，全链路保持一致

### 查询接口稳定性

- `/api/query` 在 KG 为空时返回 `{answer: "", citations: [], status: "no_kg"}`，不要抛 500
- Embedding 调用必须设 30 秒超时，超时回退到纯文本检索
