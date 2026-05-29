# 多模态 RAG 问答系统 — 后端服务架构与 API 接口规范 v1.0

> **版本**: v1.0 | **日期**: 2026-05-24
>
> 基于 MinerU → BridgePipeline → Agentic KG-RAG 三阶段链路，
> 定义工程化后端服务的完整架构与 RESTful API 规范。

---

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
