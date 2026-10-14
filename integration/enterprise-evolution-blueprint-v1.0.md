# GraphRAG 企业级演进蓝图 v1.0

> **版本**: v1.4 | **日期**: 2026-06-09 | **状态**: Phase 0-3 已实施, Phase 4 蓝图完成
>
> 基于当前系统能力审计，规划多租户隔离、容器化部署、CI/CD 自动化三大方向的演进路径。

---

## 2026-10-12 认证与租户安全修订

§3、§6.1、§6.6、§7.1 的旧代码示例如与本节冲突，以本节及 [当前后端安全契约](backend-api-architecture-v1.0.md#2026-10-12-安全修订资料授权与任务隔离) 为准。

默认拒绝未认证请求，不以 ADMIN_API_KEY 缺失视为匿名授权。JWT 的签名、sub、exp、issuer、access/refresh 类型均须校验；当前用户存在与当前角色是每次授权依据，失效用户和撤销成员不得沿用签发时权限。托管 key 同时要求有效 key、存活 owner、HTTP 方法权限与对象权限，不因 sk- 前缀跳过校验。默认拒绝公开开发 JWT 密钥；仅明确开启且非生产的开发模式允许开发登录。

X-Project-Id 不是可信租户身份；必须验证项目所属活跃组织及真实当前成员。无成员不能虚构 default/org_admin。历史资料未登记 owner/org/project 时仅管理员可访问，新入库由服务端身份写入归属。无法证明隔离的全局接口限管理员；受限查询只用独立授权 KG，显式不支持的索引来源拒绝，不静默扩大范围。

本修订属于已有故障的安全边界回流，不表示全部企业能力或供应商集成已经验收。

## 目录

1. [当前基线](#1-当前基线)
2. [三支柱总览](#2-三支柱总览)
3. [Phase 0: 基础治理](#3-phase-0-基础治理)
4. [Phase 1: 协作闭环](#4-phase-1-协作闭环)
5. [Phase 2: 数据资产](#5-phase-2-数据资产)
6. [Phase 3: 生态集成](#6-phase-3-生态集成)
7. [Phase 4: 企业就绪](#7-phase-4-企业就绪)
8. [实施路线总图](#8-实施路线总图)

---

## 1. 当前基线

### 1.1 已有能力（v1.0 已验证）

| 维度 | 状态 | 证据 |
|------|------|------|
| **检索精度** | 已验证 | Recall 3.9/5, Precision 4.6/5, Accuracy 5.0/5, Faithfulness 43.4% |
| **多路召回** | 已上线 | Vector + KG + BM25 + Table + Multi-Query → RRF + Cross-Encoder |
| **文档解析** | 已上线 | PDF(MinerU) + DOCX(python-docx) + XLSX(openpyxl) |
| **KG 构建** | 已上线 | 10 实体类型 × 10 关系类型, NetworkX + JSON 持久化 |
| **前端 UI** | 已上线 | 6 页面 (Upload/Documents/Query/Graph/Health/404) |
| **API 文档** | 已上线 | Swagger UI + ReDoc, 10 个端点 |

### 1.2 关键缺口（本次蓝图覆盖）

```
检索精度 ──────── ✅ 已有
协作闭环 ──────── ❌ 缺失 (反馈/审核/会话)
数据资产 ──────── ❌ 缺失 (版本/血缘/目录/备份)
生态集成 ──────── ❌ 缺失 (SSO/Bot/Webhook/监控)
```

---

## 2. 三支柱总览

```
                    GraphRAG 企业级平台
 ════════════════════════════════════════════════════════════

  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
  │   📋 协作闭环    │ │   🗄️ 数据资产   │ │   🔌 生态集成    │
  │                 │ │                 │ │                 │
  │ 反馈收集与闭环  │ │ KG 版本管理     │ │ SSO/统一认证     │
  │ 实体审核工作流  │ │ 数据血缘追踪    │ │ 消息平台 Bot     │
  │ 查询历史与会话  │ │ 数据资产目录    │ │ Webhook 事件     │
  │ 标注任务协作    │ │ 标准格式导出    │ │ Prometheus 监控  │
  │ 知识更新回路    │ │ 备份与容灾      │ │ 结构化日志       │
  └─────────────────┘ └─────────────────┘ └─────────────────┘

  ┌─────────────────────────────────────────────────────────┐
  │                   🏗️ 基础治理 (Phase 0)                  │
  │  结构化日志 | Prometheus Metrics | API Key 认证          │
  │  KG 版本管理 | 数据模型标准化                            │
  └─────────────────────────────────────────────────────────┘
```

### 2.1 Phase 依赖关系

```
Phase 0: 基础治理 ─────────────────────────────────────────────┐
  │                         │                         │        │
  ▼                         ▼                         ▼        │
Phase 1: 协作闭环    Phase 2: 数据资产      Phase 3: 生态集成   │
  │                         │                         │        │
  └─────────────────────────┴─────────────────────────┘        │
                              │                                 │
                              ▼                                 ▼
                      Phase 4: 企业就绪 ◄──────────────────────┘
```

---

## 3. Phase 0: 基础治理

> **目标**：在三个方向开工之前，统一基础设施。没有可观测性和数据版本管理，后续所有工作都不可靠。
>
> **周期**：2 周

### 3.1 结构化日志

**现状**：`logging.getLogger(__name__)` + `print()`，无统一格式。

**设计**：

```
日志格式 (JSON Lines):
{
  "timestamp": "2026-06-08T10:23:45.123Z",
  "level": "INFO",
  "logger": "backend.retrieval",
  "request_id": "req_a1b2c3",
  "user_id": null,
  "action": "retrieval_complete",
  "latency_ms": 342,
  "extra": {
    "path": "multi_path_recall",
    "candidates": 62,
    "sources": ["vector", "kg", "bm25"]
  }
}
```

**实施要点**：

| 文件 | 变更 |
|------|------|
| `backend/logging_config.py` (新建) | `structlog` 配置，JSON 格式输出到 `stdout` + `output/logs/app.log` |
| `backend/server.py` | 中间件注入 `request_id`，记录请求/响应 |
| `backend/retrieval.py` | 替换 `print()` 为结构化日志 |
| `backend/worker.py` | Pipeline 各阶段日志结构化 |

```python
# backend/logging_config.py — 核心接口
import structlog
import logging
import json
from datetime import datetime, timezone

def setup_logging(log_dir: str = "output/logs"):
    """配置结构化日志：JSON → stdout；滚动文件 → log_dir"""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
```

**Gate 标准**：
- [ ] 所有模块日志输出为 JSON 格式
- [ ] 每个请求携带 `request_id`
- [ ] 关键操作（retrieval/generation/ingestion）有 latency 字段
- [ ] 日志文件按天轮转，保留 30 天

---

### 3.2 Prometheus Metrics

**现状**：只有 `GET /api/v1/health` 返回组件状态，无时序指标。

**设计**：

```
新增端点: GET /metrics (Prometheus 格式)

核心指标:
# 请求量
rag_requests_total{endpoint="query|rag_query|ingest|graph"} 15

# 延迟 (Histogram)
rag_request_duration_seconds_bucket{endpoint="rag_query", le="0.5"} 8
rag_request_duration_seconds_bucket{endpoint="rag_query", le="1.0"} 12
rag_request_duration_seconds_bucket{endpoint="rag_query", le="2.0"} 15

# 检索指标
rag_retrieval_candidates{source="vector|kg|bm25|table|multi_query"} 20

# 业务指标
rag_documents_total 5
rag_kg_nodes_total 439
rag_kg_edges_total 1537

# 错误
rag_errors_total{type="mineru_timeout|deepseek_429|kg_load_error"} 1
```

**实施要点**：

| 文件 | 变更 |
|------|------|
| `backend/metrics.py` (新建) | `prometheus_client` 初始化，Counter/Histogram/Gauge 注册 |
| `backend/server.py` | 挂载 `GET /metrics`，请求中间件自动计数+计时 |
| `backend/retrieval.py` | 各路径召回量打点 |
| `backend/requirements.txt` | 加 `prometheus-client` |

**Gate 标准**：
- [ ] `GET /metrics` 返回 Prometheus 格式数据
- [ ] Grafana 可抓取并展示基础 Dashboard（请求 QPS / P95 延迟 / 错误率）
- [ ] 检索路径覆盖率指标正常

---

### 3.3 API Key 认证

**现状**：无认证，`allow_origins=["*"]`。

**设计**：

```
认证层级:
  Level 0 — 无认证 (现有，/health + /metrics 保留)
  Level 1 — API Key (Phase 0 实现)
  Level 2 — OAuth2/JWT (Phase 3 实现)

API Key 机制:
  - 请求头: Authorization: Bearer sk-xxxxxxxx
  - Key 管理: .env 中 ADMIN_API_KEY + 数据库中的 API Key 表
  - 速率限制: 复用现有 rate limiter，按 API Key 粒度
```

**实施要点**：

| 文件 | 变更 |
|------|------|
| `backend/auth.py` (新建) | `verify_api_key()` 依赖注入，从 Header 提取并校验 |
| `backend/server.py` | 除 `/health` `/metrics` `/docs` 外全局挂载认证中间件 |
| `backend/models.py` | 加 `ApiKey` 模型 (id, key_hash, name, created_at, is_active) |

```python
# backend/auth.py — 核心接口
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import hashlib
import os

security = HTTPBearer(auto_error=False)

async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> str | None:
    """验证 API Key。/health /metrics /docs 跳过。"""
    if credentials is None:
        return None  # 允许匿名（后续 Phase 收紧）
    key_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    # Phase 0: 仅校验 ADMIN_API_KEY
    admin_key = os.getenv("ADMIN_API_KEY", "")
    admin_hash = hashlib.sha256(admin_key.encode()).hexdigest()
    if key_hash != admin_hash:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return "admin"
```

**Gate 标准**：
- [ ] 非白名单端点要求 `Authorization: Bearer` 头（开发模式可选）
- [ ] API Key 哈希存储，不出现在日志中
- [ ] 错误 Key 返回 403，不含 Key 返回 401

---

### 3.4 KG 版本管理

2026-10-13维护契约（同时约束生命周期清理）：创建/激活/清理使用同一文档级FileLock；清单原子写入并保存单调`next_version`，拒绝bool、浮点和无效版本元数据。清理始终保留当前active及最新9个inactive，仅处理清单已知、规范vN名称且位于KG根内的真实目录；清单损坏、active缺失或链接/junction时停止该文档清理。持锁重新选择后先将目标重命名为`.retired-vN-...`，提交移除记录和高水位，再物理删除；清单提交失败恢复原目录，物理删除失败保留隔离目录并告警。清理返回数为逻辑移除版本数，不代表释放字节；空间统计仍包含残留隔离目录。未知目录不擅自删除。

2026-10-12加载约束：版本图谱添加文档id_prefix前必须拒绝原始空source/target，不能把空值变成非空前缀后交给NetworkX自动生成虚构节点；有效节点/边身份及版本选择保持原契约。

**现状**：每次 ingest 直接覆盖 `output/kg/doc_xxx/nodes.json` + `edges.json`。

**设计**：

```
存储结构变更:
  output/kg/doc_{task_id}/
    ├── v1/
    │   ├── nodes.json      ← 首次 ingest
    │   └── edges.json
    ├── v2/
    │   ├── nodes.json      ← 修正后 re-ingest
    │   └── edges.json
    └── versions.json        ← 版本元数据

versions.json:
{
  "doc_id": "doc_abc123",
  "versions": [
    {"version": 1, "created_at": "2026-06-01T10:00:00Z", "nodes": 220, "edges": 310, "status": "active"},
    {"version": 2, "created_at": "2026-06-05T14:00:00Z", "nodes": 225, "edges": 318, "status": "active"}
  ],
  "active_version": 2
}
```

**API 扩展**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/documents/{doc_id}/versions` | 列出版本历史 |
| `POST` | `/api/v1/documents/{doc_id}/versions/{v}/activate` | 切换活跃版本 |
| `GET` | `/api/v1/documents/{doc_id}/versions/{v}/diff` | 查看两个版本间 KG 差异 |

**实施要点**：

| 文件 | 变更 |
|------|------|
| `backend/kg_store.py` (新建) | `KgVersionManager` — 写入时自动递增版本号，读取时加载 active 版本 |
| `backend/routes/documents.py` | 加版本管理端点 |
| `backend/kg_builder.py` | `serialize_kg()` 改为写入 `v{N}/` 子目录 |

**Gate 标准**：
- [ ] 重复 ingest 同一文档不覆盖旧版本
- [ ] 可通过 API 切换活跃版本
- [ ] 版本列表 API 返回时间戳和节点/边数

---

### Phase 0 总 Gate

```
[PASS] 结构化日志 JSON 输出 + request_id 全链路
[PASS] GET /metrics 可被 Prometheus 抓取
[PASS] API Key 认证中间件挂载，白名单端点除外
[PASS] KG 版本目录结构生效，重复 ingest 产生 v2
─────────────────────────────────────────────────────
全部 PASS → 进入 Phase 1/2/3 并行开发
```

---

## 4. Phase 1: 协作闭环

> **目标**：建立"用户反馈 → 知识修正 → 质量提升"的人机协作回路。
>
> **周期**：3 周
> **前置依赖**：Phase 0 (API Key + 结构化日志)

### 4.1 答案反馈系统

2026-10-12更新约束：FeedbackUpdate.comment非None时必须持久化；空字符串可清空备注，None保持原备注。单独更新备注不能隐式改变状态。

**设计**：

```
            用户提问
               │
               ▼
         RAG 生成答案
               │
               ▼
      ┌─────────────────┐
      │  答案展示 + 溯源   │
      │                  │
      │  👍 有帮助  👎 无帮助 │
      │  [反馈文字框]     │
      └────────┬─────────┘
               │
               ▼
      POST /api/v1/feedback
      {
        "query_id": "...",
        "rating": "positive|negative",
        "comment": "答案中氢气产量数据有误",
        "correction": "正确值应为 280kg/h",
        "chunks_cited": ["c00042", "c00017"]
      }
               │
               ▼
      ┌─────────────────┐
      │  反馈聚合看板     │
      │  - 低分答案 Top N │
      │  - 高频纠正词云   │
      │  - 按文档/实体分布 │
      └────────┬─────────┘
               │
               ▼
         人工触发 KG 修正
             或 Re-ingest
```

**数据模型**：

```python
# backend/models.py — 新增
class FeedbackCreate(BaseModel):
    query_id: str
    rating: Literal["positive", "negative"]
    comment: str | None = None          # 用户文字反馈
    correction: str | None = None       # 用户提供的正确值
    chunks_cited: list[str] | None = None
    user_id: str | None = None          # Phase 3 启用

class FeedbackRecord(FeedbackCreate):
    feedback_id: str
    created_at: str
    query_text: str                     # 冗余存储原问题
    answer_text: str                    # 冗余存储原答案
    status: str = "open"                # open | acknowledged | resolved
```

**API 扩展**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/feedback` | 提交反馈 |
| `GET` | `/api/v1/feedback?status=open&limit=50` | 列出反馈 |
| `GET` | `/api/v1/feedback/stats` | 反馈统计 (正/负比率、趋势) |
| `PATCH` | `/api/v1/feedback/{feedback_id}` | 更新状态 (acknowledged/resolved) |

**前端变更**：

| 组件 | 变更 |
|------|------|
| `QueryPage.tsx` | 答案下方加 👍/👎 按钮 + 可展开的反馈文字框 |
| `FeedbackPage.tsx` (新建) | 反馈管理看板：低分答案列表、趋势图、按实体分布 |

**实施要点**：

| 文件 | 变更 |
|------|------|
| `backend/routes/feedback.py` (新建) | 反馈 CRUD 端点 |
| `backend/services/feedback_store.py` (新建) | JSON 文件持久化（Phase 0 SQLite 迁移后可切换） |
| `frontend/src/pages/FeedbackPage.tsx` (新建) | 反馈管理看板 |
| `frontend/src/stores/useAppStore.ts` | 加 `useFeedbackStore` |

**Gate 标准**：
- [ ] 用户可在答案下方提交 👍/👎 + 文字反馈
- [ ] 反馈数据持久化到 `output/feedback/`
- [ ] 反馈看板可查看低分答案 Top 10
- [ ] 反馈统计 API 返回正/负比率

---

### 4.2 实体审核工作流

**设计**：

```
LangExtract 抽取实体
       │
       ▼
┌──────────────────┐
│  实体状态机       │
│                  │
│  pending ────────│── 人工审核 ──► approved
│    │             │                 │
│    └─────────────│── 人工审核 ──► rejected (含原因)
│                  │
│  approved ───────│── 关联修正 ──► pending (实体被修改)
└──────────────────┘
       │
       ▼
  KG 仅包含 approved 状态的实体参与检索
```

**API 扩展**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/entities/review?status=pending&type=metric&limit=20` | 获取待审核实体列表 |
| `POST` | `/api/v1/entities/{entity_id}/approve` | 审核通过 |
| `POST` | `/api/v1/entities/{entity_id}/reject` | 驳回 (含 reason) |
| `PUT` | `/api/v1/entities/{entity_id}` | 修正实体内容 |

**前端变更**：

| 组件 | 变更 |
|------|------|
| `EntityReviewPage.tsx` (新建) | 实体审核界面：实体卡片 + 原文溯源 + 通过/驳回按钮 |

**Gate 标准**：
- [ ] 新抽取实体默认 `pending` 状态
- [ ] 审核界面可查看实体溯源（原文片段 + PDF 页码）
- [ ] 通过/驳回操作实时更新 KG（仅 approved 参与检索）
- [ ] 驳回原因记录可追溯

---

### 4.3 查询历史与会话

**设计**：

```
POST /api/v1/query  →  自动保存查询记录

QueryRecord:
  query_id: "q_abc123"
  query_text: "项目预算执行率是多少"
  answer_text: "..."
  intent: "metric"
  sources: ["c00042", "n0019"]
  latency_ms: 342
  feedback: null (未被评价)
  created_at: "2026-06-08T10:23:45Z"
  session_id: "sess_xyz" | null
```

**API 扩展**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/queries/history?limit=20&offset=0` | 查询历史 |
| `GET` | `/api/v1/queries/{query_id}` | 查询详情 (含完整 answer + sources) |
| `DELETE` | `/api/v1/queries/{query_id}` | 删除单条历史 |
| `GET` | `/api/v1/queries/stats` | 查询统计 (高频词、意图分布、延迟趋势) |

**前端变更**：

| 组件 | 变更 |
|------|------|
| `QueryPage.tsx` | 左侧加查询历史列表，点击回填历史查询 |
| `QueryHistoryPanel.tsx` (新建) | 查询历史侧边栏 |

**Gate 标准**：
- [ ] 每次查询自动持久化记录
- [ ] 查询历史支持分页查看
- [ ] 历史记录可点击回看完整答案

---

### 4.4 知识修正回路

> 这是协作闭环的"闭环"关键——反馈和审核的结果要能回流到 KG。

```
反馈/审核发现问题
       │
       ▼
┌──────────────────────┐
│  修正动作             │
│                      │
│  1. 修正实体属性      │ → PUT /api/v1/entities/{id} → 更新 nodes.json
│  2. 新增缺失实体      │ → POST /api/v1/entities → 追加到 nodes.json
│  3. 删除错误实体      │ → DELETE /api/v1/entities/{id} → 标记 deleted
│  4. 触发 Re-ingest   │ → POST /api/v1/documents/{id}/reingest → 重新抽取
│  5. 修正实体关系      │ → PUT /api/v1/edges/{id} → 更新 edges.json
└──────────────────────┘
       │
       ▼
  KG 版本号 +1
  重新加载到 NetworkX
  清除相关 Embedding 缓存
```

**API 扩展**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/entities` | 手动创建实体 |
| `PUT` | `/api/v1/entities/{entity_id}` | 修正实体属性 |
| `DELETE` | `/api/v1/entities/{entity_id}` | 删除实体 (软删除) |
| `PUT` | `/api/v1/edges/{edge_id}` | 修正关系 |
| `POST` | `/api/v1/documents/{doc_id}/reingest` | 触发重新索引 |

**Gate 标准**：
- [ ] 手动修正的实体自动标记 `source=manual`
- [ ] 修正操作产生 KG 新版本
- [ ] 修正后检索结果在 5 分钟内反映变更（内存 KG 热重载）

---

### Phase 1 总 Gate

```
[PASS] 反馈收集闭环可用 (提交→存储→看板)
[PASS] 实体审核工作流可用 (pending→approved/rejected)
[PASS] 查询历史可追溯
[PASS] 知识修正回路可运行 (修正→新版本→检索生效)
─────────────────────────────────────────────────────
全部 PASS → 协作闭环达成
```

---

## 5. Phase 2: 数据资产

> **目标**：让 KG 数据可管理、可审计、可迁移，从"文件堆"变成"数据资产"。
>
> **周期**：3 周
> **前置依赖**：Phase 0 (KG 版本管理)

### 5.1 数据血缘追踪

**设计**：

```
数据血缘链路 (端到端可追溯):

  原始文档 (PDF page 5, bbox [120, 340, 580, 420])
    │
    ├─ MinerU 解析 → full.md line 234
    │
    ├─ BridgePipeline 分段 → Section 3.2 "预算分析"
    │
    ├─ LangExtract 抽取 → Entity "预算执行率 = 84%"
    │     │
    │     └─ Grounding 溯源 → page_idx=5, bbox_norm=[0.15, 0.42, 0.72, 0.53]
    │
    ├─ KG Builder → Node {id: "n0217", type: "metric", name: "预算执行率", value: "84%"}
    │     │
    │     └─ 上下文 window → 前后 512 chars 原文片段
    │
    ├─ Retrieval → Query "预算执行" → 命中 chunk c00042 (来自 Section 3.2)
    │     │
    │     └─ RRF score: 0.087, Cross-encoder score: 0.994
    │
    └─ Generation → Answer "...预算执行率 84% [c00042]..."
          │
          └─ 用户反馈 → 👍 / "数据正确"

  每个节点保留上游指针 → 任一跳转可向上追溯
```

**数据模型**：

```python
# backend/models.py — 新增
class LineageNode(BaseModel):
    """血缘图中的节点"""
    node_id: str
    node_type: str  # document | section | extraction | entity | chunk | answer | feedback
    label: str
    metadata: dict
    parent_ids: list[str]  # 上游节点 ID
    child_ids: list[str]   # 下游节点 ID

class LineageTrace(BaseModel):
    """从文档到答案的完整血缘追踪"""
    entity_id: str
    trace: list[LineageNode]
```

**API 扩展**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/lineage/entity/{entity_id}` | 查看实体的完整血缘链路 |
| `GET` | `/api/v1/lineage/answer/{query_id}` | 查看答案的血缘链路（引用了哪些实体→段落→文档） |
| `GET` | `/api/v1/lineage/document/{doc_id}` | 查看文档产出了哪些实体和关系 |

**前端变更**：

| 组件 | 变更 |
|------|------|
| `EntityDetailPanel.tsx` | 加 "血缘追踪" Tab，展示实体从文档到答案的完整链路 |
| `LineageGraph.tsx` (新建) | DAG 可视化组件，展示血缘链路上下游 |

**实施要点**：

| 文件 | 变更 |
|------|------|
| `backend/services/lineage_store.py` (新建) | `LineageStore` — ingest 时记录每步 parent/child 关系 |
| `backend/routes/lineage.py` (新建) | 血缘查询端点 |
| `backend/kg_builder.py` | 构建时写入 lineage 记录 |
| `backend/generator.py` | 生成时写入 answer→entity 引用关系到 lineage |

**Gate 标准**：
- [ ] 每个实体可追溯到原始文档 page_idx + bbox
- [ ] 每个答案可追溯到引用的实体
- [ ] 血缘查询 API 可用
- [ ] 前端可视化血缘链路

---

### 5.2 数据资产目录

**设计**：

```
GET /api/v1/catalog

{
  "summary": {
    "total_documents": 5,
    "total_entities": 439,
    "total_edges": 1537,
    "total_chunks": 31,
    "by_entity_type": {
      "metric": 87,
      "process_step": 64,
      ...
    },
    "by_project": {
      "电氢氨园区": {"documents": 1, "entities": 220, "edges": 310},
      ...
    }
  },
  "documents": [...],
  "quality_metrics": {
    "grounded_rate": 0.87,
    "avg_confidence": 0.76,
    "entities_without_edges": 12,
    "orphan_entities": 5
  },
  "last_updated": "2026-06-08T10:00:00Z"
}
```

**API 扩展**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/catalog` | 数据资产总览 |
| `GET` | `/api/v1/catalog/entities?type=metric&project=xxx` | 按维度的实体目录 |
| `GET` | `/api/v1/catalog/search?q=预算` | 跨文档搜索实体 |

**前端变更**：

| 组件 | 变更 |
|------|------|
| `CatalogPage.tsx` (新建) | 数据资产看板：总览卡片 + 实体类型饼图 + 项目分布 + 质量指标 |

**Gate 标准**：
- [ ] 资产目录总览 API 返回完整统计数据
- [ ] 可按实体类型/项目/文档筛选
- [ ] 质量指标（覆盖率、置信度分布）可视化

---

### 5.3 标准格式导出

**设计**：

```
导出格式支持:

GET /api/v1/export/kg?format=json     → 当前格式 (JSON)
GET /api/v1/export/kg?format=csv      → CSV (nodes.csv + edges.csv 两个文件)
GET /api/v1/export/kg?format=rdf      → RDF/Turtle (语义网标准)
GET /api/v1/export/kg?format=neo4j    → Neo4j Cypher INSERT 语句
GET /api/v1/export/kg?format=zip      → 以上所有格式打包下载
```

**实施要点**：

| 文件 | 变更 |
|------|------|
| `backend/services/kg_exporter.py` (新建) | `KgExporter` — JSON/CSV/RDF/Neo4j 四种格式转换器 |
| `backend/routes/export.py` (新建) | 导出端点 |

**Gate 标准**：
- [ ] 至少支持 JSON / CSV / Neo4j Cypher 三种格式
- [ ] 导出大图（>1000 节点）不超时（流式输出）
- [ ] CSV 导出中文不乱码（UTF-8 BOM）

---

### 5.4 备份与容灾

**设计**：

```
备份策略:
  - 自动: 每日凌晨 2 点全量备份 output/ → output/backups/YYYY-MM-DD/
  - 手动: POST /api/v1/system/backup 触发即时备份
  - 保留: 最近 7 天日备 + 最近 4 周周备

恢复:
  - POST /api/v1/system/restore?date=2026-06-07
  - 恢复前自动创建当前状态快照
  - 恢复失败的 RestoreResult 必须保留可选 error 诊断字段；不能因模型忽略额外字段丢弃失败原因。

备份内容:
  output/kg/          ← 所有 KG 版本
  output/vectordb/    ← ChromaDB 持久化数据
  output/feedback/    ← 反馈数据
  output/queries/     ← 查询历史
  output/docs_store.json
  output/tasks_store.json
```

**API 扩展**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/system/backup` | 即时全量备份 |
| `GET` | `/api/v1/system/backups` | 列出历史备份 |
| `POST` | `/api/v1/system/restore` | 恢复到指定备份 |

**Gate 标准**：
- [ ] 自动日备正常运行（cron）
- [ ] 手动备份/恢复 API 可用
- [ ] 恢复操作自动创建回滚快照

---

### Phase 2 总 Gate

```
[PASS] 实体血缘端到端可追溯 (文档→抽取→KG→检索→答案→反馈)
[PASS] 数据资产目录 API 可用 (含词典/反馈/会话统计)
[PASS] 至少 3 种格式导出可用 (含词典/反馈/会话)
[PASS] 备份/恢复流程验证通过 (覆盖全部 7 个数据目录)
[PASS] 数据质量监控可运行 (质量评分 + 低质量告警)
[PASS] 生命周期管理生效 (TTL清理 + 旧版本归档)
─────────────────────────────────────────────────────
全部 PASS → 数据资产可管理
```

---

### 5.5 数据血缘追踪（v1.2 补强）

> **v1.2 变更**：Phase 0+1 新增了 domain_dict / conversation / feedback_store / kg_store / metrics 五个模块。
> 数据血缘追踪需从单纯的"文档→实体→答案"扩展为覆盖完整协作闭环的溯源链路。

**新模块血缘节点**：

```
扩展后的血缘链路:

  [领域词典]
  domain_dict.expand_query("JSA执行情况检查")
    │  → 展开: 同义[作业安全分析] + 缩写[JSA→Job Safety Analysis]
    │  → 注入: 相关概念[风险辨识, 控制措施, 作业许可]
    │  LineageNode: {type: "domain_expand", term: "JSA", synonyms: [...], timestamp}
    │
    ▼
  [会话上下文]
  Conversation(session_id, turns=3)
    │  → Turn 1: "高处作业安全措施" → answer_1
    │  → Turn 2: "安全带标准" → answer_2 (指代消解: "里面提到的"→"高处作业")
    │  → Turn 3: "对比前两条" (指代消解: "前两条"→answer_1+answer_2)
    │  LineageNode: {type: "conversation", session_id, turn_id, rewritten_query}
    │
    ▼
  [检索管道 — 已有]
  RetrievalPipeline.retrieve()
    │  → preprocess: domain_dict expanded query
    │  → coreference: conversation-aware rewriting
    │  → 5-path recall: vector + kg + bm25 + table + multi_query
    │  → RRF fusion + cross-encoder rerank
    │  LineageNode: {type: "retrieval", paths_hit, candidates, rerank_scores}
    │
    ▼
  [生成]
  RAGGenerator.generate()
    │  → prompt: domain_hint + conversation_summary + chunks
    │  → answer with citations [c00042]
    │  LineageNode: {type: "generation", citations: ["c00042", "n0019"]}
    │
    ▼
  [反馈闭环]
  FeedbackStore.submit(rating="negative", correction="...")
    │  → feedback_id → tracks back to query_id → conversation turn
    │  → chunks_cited tracked for citation accuracy audit
    │  LineageNode: {type: "feedback", rating, status}
    │
    ▼
  [版本追踪]
  KgVersionManager(doc_id)
    │  → v1: initial extraction (2026-05-25)
    │  → v2: re-ingest after correction (2026-06-10)
    │  → Which version was the entity retrieved from?
    │  LineageNode: {type: "kg_version", version, active}
```

**增强数据模型**：

```python
# 新增节点类型
class LineageNodeType(str, Enum):
    DOCUMENT = "document"
    SECTION = "section"
    EXTRACTION = "extraction"
    ENTITY = "entity"
    CHUNK = "chunk"
    RETRIEVAL = "retrieval"
    GENERATION = "generation"
    ANSWER = "answer"
    FEEDBACK = "feedback"              # 新增
    DOMAIN_EXPAND = "domain_expand"     # 新增
    CONVERSATION_TURN = "conv_turn"     # 新增
    KG_VERSION = "kg_version"           # 新增

# 增强 LineageNode
class LineageNode(BaseModel):
    node_id: str
    node_type: LineageNodeType
    label: str
    metadata: dict
    parent_ids: list[str]
    child_ids: list[str]
    # 新增
    session_id: str | None = None      # conversation scope
    kg_version: int | None = None      # KG version at time of retrieval
    domain_terms: list[str] | None = None  # terms matched in domain dict
    feedback_id: str | None = None     # feedback link
```

**新增 API**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/lineage/feedback/{feedback_id}` | 反馈→答案→实体→文档完整溯源 |
| `GET` | `/api/v1/lineage/conversation/{session_id}` | 会话维度血缘（各轮次检索路径对比） |
| `GET` | `/api/v1/lineage/term/{term}` | 某领域术语在哪些查询中被使用 |
| `GET` | `/api/v1/lineage/export?entity_id=xxx` | 导出单个实体的完整血缘为 DOT 图 |

---

### 5.6 数据资产目录（v1.2 补强）

> **v1.2 变更**：目录需覆盖 Phase 0+1 新增模块的统计维度。

**增强目录响应**：

```json
GET /api/v1/catalog

{
  "summary": {
    "total_documents": 5,
    "total_entities": 439,
    "total_edges": 1537,
    "total_chunks": 31,
    "total_conversations": 128,
    "total_feedback": 45,
    "domain_terms": 60,
    "by_entity_type": { "metric": 87, "process_step": 64, "risk_item": 52 },
    "by_project": { "电氢氨园区": {"documents": 1, "entities": 220} }
  },
  "domain_dict": {
    "total_terms": 60,
    "by_category": {"safety": 23, "equipment": 11, "ppe": 10, "regulation": 16},
    "most_matched": ["动火作业", "高处作业", "JSA"],
    "unused_terms": 5
  },
  "conversations": {
    "total_sessions": 128,
    "active_sessions": 12,
    "avg_turns_per_session": 3.2,
    "max_turns_session": 15,
    "top_queries": ["高处作业安全措施", "动火作业许可证流程"]
  },
  "feedback": {
    "total": 45,
    "positive_ratio": 0.73,
    "trend_7d": "improving",
    "most_negative_queries": ["应急预案编制要求"],
    "avg_resolution_hours": 18.5
  },
  "retrieval": {
    "avg_candidates_per_query": 62,
    "source_hit_rate": {"kg": 0.70, "vector": 0.95, "bm25": 0.45},
    "avg_latency_ms": 3420,
    "cross_encoder_enabled": true
  },
  "quality_metrics": {
    "grounded_rate": 0.87,
    "avg_confidence": 0.76,
    "entities_without_edges": 12,
    "orphan_entities": 5,
    "low_quality_docs": [
      {"doc_id": "doc_xxx", "issue": "grounding_rate < 0.5", "value": 0.32}
    ]
  },
  "last_updated": "2026-06-09T10:00:00Z"
}
```

**新增 API**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/catalog/summary` | 总览卡片（轻量，Dashboard 用） |
| `GET` | `/api/v1/catalog/trends?days=30` | 趋势数据（实体增长、查询量、反馈率） |
| `GET` | `/api/v1/catalog/low-quality` | 低质量数据清单（grounding_rate < 阈值） |

---

### 5.7 标准格式导出（v1.2 补强）

> **v1.2 变更**：为新增数据资产提供导出格式。

**新增导出端点**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/export/domain-dict?format=yaml\|csv\|json` | 领域词典导出 |
| `GET` | `/api/v1/export/feedback?format=csv\|json&status=open` | 反馈数据导出（可筛选状态） |
| `GET` | `/api/v1/export/conversations?format=zip` | 所有会话批量导出为 Markdown ZIP |
| `GET` | `/api/v1/export/lineage/{entity_id}` | 单实体血缘 DOT 图导出 |

---

### 5.8 备份与容灾（v1.2 补强）

> **v1.2 变更**：覆盖 Phase 0+1 新增的 4 个数据目录。

**完整备份范围**：

```
output/
├── kg/                  ← KG 版本 (Phase 0 已覆盖)
├── vectordb/            ← ChromaDB (Phase 0 已覆盖)
├── feedback/            ← 反馈数据 (新增)
├── conversations/       ← 会话数据 (新增)
├── logs/                ← 结构化日志 (新增)
├── embedding_cache/     ← Embedding 缓存 (新增)
├── docs_store.json      ← 文档索引 (Phase 0 已覆盖)
└── tasks_store.json     ← 任务状态 (Phase 0 已覆盖)
```

**备份实现方案**：

```python
# backend/services/backup.py

BACKUP_MANIFEST = {
    "kg": {"path": "output/kg/", "strategy": "incremental_version"},
    "vectordb": {"path": "output/vectordb/", "strategy": "full"},
    "feedback": {"path": "output/feedback/", "strategy": "full"},
    "conversations": {"path": "output/conversations/", "strategy": "full"},
    "logs": {"path": "output/logs/", "strategy": "rotate_only"},
    "embedding_cache": {"path": "output/embedding_cache/", "strategy": "skip"},
}

def create_backup(backup_dir: Path, manifest: dict) -> BackupResult:
    """按 manifest 策略创建备份。
    - full: 全量 tar.gz
    - incremental_version: 仅打包当前 active 版本 + versions.json
    - rotate_only: 不备份，依赖日志轮转
    - skip: 跳过（可重新计算）
    """
```

**定时任务实现**：

```
方式 A (推荐): APScheduler 集成到 FastAPI lifespan
  - 服务启动时注册每日 02:00 的 backup job
  - 不依赖外部 cron，容器友好

方式 B: 外部 cron 调 API
  - crontab: 0 2 * * * curl -X POST http://localhost:8000/api/v1/system/backup
```

**备份验证**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/system/backup/verify/{backup_id}` | 验证备份完整性（节点数/边数/文件数校验） |
| `GET` | `/api/v1/system/backup/{backup_id}/manifest` | 查看备份内容清单 |

---

### 5.9 数据质量监控（新增 §5.5）

> **v1.2 新增**：基于 Prometheus 指标 + 反馈数据，建立数据质量可观测性。

**质量指标体系**：

```
维度 1: 抽取质量
  - grounding_rate: grounded实体 / 总实体 (目标 ≥ 0.80)
  - confidence_avg: LLM 抽取置信度均值 (目标 ≥ 0.70)
  - extraction_error_rate: 解析失败文档 / 总文档 (目标 ≤ 0.05)

维度 2: 检索质量
  - path_covers: 每次查询命中的检索路径数 (目标 ≥ 2.0)
  - zero_result_rate: 返回"未提及"的查询比例 (目标 ≤ 0.15)
  - avg_rerank_score: Cross-encoder 平均分 (目标 ≥ 0.60)

维度 3: 用户反馈质量
  - positive_ratio: 好评率 (目标 ≥ 0.70)
  - negative_cluster: 低分答案集中在哪些文档/实体
  - correction_rate: 用户提供纠正的比例 → 指示 KG 错误率

维度 4: 数据新鲜度
  - days_since_last_ingest: 距上次新文档索引的天数
  - stale_entities: 超过 N 天未在检索中命中的实体数
  - conversation_activity: 日活会话数趋势
```

**Prometheus 新增指标**：

```python
# backend/metrics.py 新增

rag_grounding_rate = Gauge("rag_grounding_rate", "Entity grounding rate")
rag_positive_feedback_ratio = Gauge("rag_positive_feedback_ratio", "Positive feedback ratio 7d")
rag_zero_result_queries = Counter("rag_zero_result_queries_total", "Queries with no results found")
rag_stale_entities = Gauge("rag_stale_entities", "Entities not retrieved in last 30 days")
rag_data_freshness_days = Gauge("rag_data_freshness_days", "Days since last document ingest")
```

**低质量告警规则**（`deploy/prometheus/alerts.yml`）：

```yaml
groups:
  - name: rag_data_quality
    rules:
      - alert: LowGroundingRate
        expr: rag_grounding_rate < 0.5
        for: 1h
        labels: { severity: warning }
        annotations: { summary: "Grounding rate dropped below 50%" }

      - alert: FeedbackRatioDrop
        expr: rag_positive_feedback_ratio < 0.5
        for: 24h
        labels: { severity: critical }
        annotations: { summary: "Positive feedback ratio below 50% over 24h" }

      - alert: DataStaleness
        expr: rag_data_freshness_days > 30
        labels: { severity: warning }
        annotations: { summary: "No new documents ingested in 30 days" }
```

**前端变更**：

| 组件 | 变更 |
|------|------|
| `QualityDashboard.tsx` (新建) | 数据质量看板：接地率/好评率/检索覆盖 趋势图 |
| `CatalogPage.tsx` | 加 "质量预警" 标记（低接地率文档红色高亮） |

---

### 5.10 数据生命周期管理（新增 §5.6）

> **v1.2 新增**：定义每种数据的保留策略和自动清理规则。

**保留策略矩阵**：

| 数据类型 | 保留周期 | 清理方式 | 特殊规则 |
|---------|---------|---------|---------|
| **会话** | 活跃: 30min TTL; 非活跃: 7天 | `conversation.py cleanup()` | 有反馈的会话永久保留 |
| **反馈** | 永久 | 手动删除 | — |
| **KG 旧版本** | 最多保留 10 个版本 | 超过时删除最旧非 active 版本 | active 版本永不删除 |
| **查询历史** | 90 天 | 定时清理 | 有反馈关联的保留 |
| **日志** | 30 天 | 日轮转，自动删除 | — |
| **Embedding 缓存** | 永久 | 随文档删除清理 | SHA256 key，无关联时自动失效 |
| **备份** | 日备: 7天; 周备: 4周 | 定时清理过期备份 | — |

**自动清理实现**：

```python
# backend/services/lifecycle.py

class DataLifecycleManager:
    """Centralized data retention policy enforcement."""

    def __init__(self):
        self.policies = {
            "conversations": {"max_age_days": 7, "keep_if_feedback": True},
            "query_history": {"max_age_days": 90, "keep_if_feedback": True},
            "kg_versions": {"max_versions": 10, "keep_active": True},
            "logs": {"max_age_days": 30},
            "backups": {"daily_keep": 7, "weekly_keep": 4},
        }

    def run_cleanup(self) -> dict:
        """Execute all retention policies. Returns cleanup report."""
        report = {}
        for category, policy in self.policies.items():
            removed = self._clean_category(category, policy)
            report[category] = removed
        return report
```

**API**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/system/cleanup` | 手动触发全局清理 |
| `GET` | `/api/v1/system/cleanup/preview` | 预览将被清理的数据（dry-run） |
| `GET` | `/api/v1/system/storage` | 各目录磁盘使用量统计 |

**定时任务**（APScheduler）：

```
每日 03:00 — lifecycle.cleanup() 
  → 清理过期会话、旧版本、过期备份
每日 03:30 — metrics 更新
  → 更新 rag_data_freshness_days, rag_stale_entities
```

---

### Phase 2 完整文件清单（v1.2 更新）

| 模块 | 文件 | 说明 |
|------|------|------|
| §5.1 血缘 | `backend/services/lineage_store.py` | LineageStore — ingest/retrieval/generation 全链路记录 |
| §5.1 血缘 | `backend/routes/lineage.py` | 血缘查询 API (entity/answer/feedback/conversation) |
| §5.2 目录 | `backend/services/catalog.py` | CatalogBuilder — 多维统计聚合 |
| §5.2 目录 | `backend/routes/catalog.py` | 资产目录 API |
| §5.3 导出 | `backend/services/kg_exporter.py` | KgExporter — JSON/CSV/RDF/Neo4j |
| §5.3 导出 | `backend/routes/export.py` | 导出 API |
| §5.4 备份 | `backend/services/backup.py` | BackupManager — 备份/恢复/验证 |
| §5.5 质量 | `backend/services/quality.py` | QualityMonitor — 质量指标计算 + 告警 |
| §5.5 质量 | 前端 `QualityDashboard.tsx` | 质量看板 |
| §5.6 生命周期 | `backend/services/lifecycle.py` | DataLifecycleManager — 保留策略 + 自动清理 |
| **合计** | **10 个新文件** | (6 backend + 1 config + 1 frontend) |

---

## 6. Phase 3: 生态集成

> **目标**：从孤立 Web 应用变为可嵌入企业生态的知识服务。
>
> **周期**：4 周
> **前置依赖**：Phase 0 (API Key 认证)

### 6.1 SSO / 统一认证

**设计**：

```
认证架构:

  ┌──────────┐     ┌──────────────┐     ┌──────────────┐
  │  Web UI  │────►│  API Gateway │────►│  OAuth2       │
  │          │     │  (FastAPI)   │     │  Provider     │
  │  JWT     │     │              │     │  (Keycloak/   │
  │  Session │     │  POST /api/v1/auth/login          │
  │          │     │  POST /api/v1/auth/refresh        │
  └──────────┘     │  GET  /api/v1/auth/me             │
                   └──────────────────────────────────┘

支持协议:
  - OAuth2 Authorization Code (企业统一认证，如 Keycloak/Auth0)
  - OIDC (OpenID Connect)
  - LDAP (企业 AD 域)
  - 本地账号 (过渡期，Phase 0 API Key 升级)

配置方式 (.env):
  AUTH_PROVIDER=keycloak|auth0|ldap|local
  OIDC_ISSUER=https://sso.company.com/realms/graphrag
  OIDC_CLIENT_ID=graphrag-web
  OIDC_CLIENT_SECRET=xxx
```

**数据模型**：

```python
# backend/models.py — 新增
class User(BaseModel):
    user_id: str
    username: str
    email: str
    roles: list[str]  # admin | editor | viewer
    department: str | None
    created_at: str
    last_login: str | None

class UserRole(str, Enum):
    ADMIN = "admin"        # 全权限：系统配置、用户管理、所有数据
    EDITOR = "editor"      # 可上传、可标注、可修正实体
    VIEWER = "viewer"      # 只读：查询、查看图谱
```

**权限矩阵**：

| 操作 | Admin | Editor | Viewer |
|------|-------|--------|--------|
| 上传文档 | ✅ | ✅ | ❌ |
| 查询问答 | ✅ | ✅ | ✅ |
| 提交反馈 | ✅ | ✅ | ✅ |
| 审核实体 | ✅ | ✅ | ❌ |
| 修正 KG | ✅ | ✅ | ❌ |
| 导出数据 | ✅ | ✅ | ❌ |
| 用户管理 | ✅ | ❌ | ❌ |
| 系统配置 | ✅ | ❌ | ❌ |

**API 扩展**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/auth/login` | OAuth2 登录重定向 |
| `GET` | `/api/v1/auth/callback` | OAuth2 回调，签发 JWT |
| `POST` | `/api/v1/auth/refresh` | 刷新 JWT |
| `GET` | `/api/v1/auth/me` | 当前用户信息 |
| `POST` | `/api/v1/auth/logout` | 登出 |

**前端变更**：

| 组件 | 变更 |
|------|------|
| `LoginPage.tsx` (新建) | 登录页面，支持 SSO 重定向 |
| `AppShell.tsx` | 加用户头像/姓名/登出按钮 |
| `frontend/src/lib/api.ts` | 自动附带 JWT Header，401 时自动刷新 |

**Gate 标准**：
- [ ] 至少支持 1 种 OAuth2 Provider（Keycloak 或 Auth0）
- [ ] JWT 签发/刷新/过期机制正常
- [ ] 权限矩阵在前端+后端双层校验
- [ ] 无权限操作返回 403

---

### 6.2 消息平台 Bot

飞书回调鉴权的2026-10-13有效契约见后端API规范维护补充：Encrypt Key签名优先、token-only验证消息token、URL验证同样认证。历史“签名验证通过”Gate不自动证明防重放、供应商接收或生产安全配置；当前无时间窗口/去重证据，重复旧签名仍可通过。

**设计**：

```
架构:

  飞书/钉钉/企微 ──Webhook──► POST /api/v1/bot/{platform}
                                    │
                                    ▼
                              ┌──────────────┐
                              │  Bot Router  │
                              │              │
                              │  消息解密/验签 │
                              │  意图路由     │
                              │  格式化回复   │
                              └──────┬───────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │  RAG Query   │
                              │  Pipeline    │
                              └──────────────┘
                                     │
                                     ▼
                              格式化答案 (Markdown → 平台消息卡片)
                              返回给 Bot
```

**一期支持平台**：飞书 (Lark)

**消息格式**：

```
用户 @机器人: 项目预算执行率是多少

机器人回复 (飞书卡片):
┌─────────────────────────────┐
│ 📊 项目预算执行率              │
│                             │
│ 预算总额: 500 万元            │
│ 已执行: 420 万元 (84%)        │
│ 剩余: 80 万元 (16%)           │
│                             │
│ 📄 来源: 2025年项目中期报告    │
│    第 12 页, 预算分析章节      │
│                             │
│ [查看详情] [👍] [👎]         │
└─────────────────────────────┘
```

**API 扩展**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/bot/feishu` | 飞书事件回调（消息接收 + 卡片回复） |
| `POST` | `/api/v1/bot/feishu/register` | 注册飞书 Bot 配置 (App ID / Secret / 验证 Token) |

**实施要点**：

| 文件 | 变更 |
|------|------|
| `backend/routes/bot.py` (新建) | Bot 回调端点、消息解密、签名验证 |
| `backend/services/bot_handler.py` (新建) | 消息路由：@提及 → 提取问题 → RAG 查询 → 卡片格式化 |
| `backend/services/feishu_client.py` (新建) | 飞书 SDK 封装 (tenant_access_token、发消息、卡片模板) |

**Gate 标准**：
- [ ] 飞书 Bot 可接收 @消息并返回答案
- [ ] 答案以富文本卡片形式呈现（含溯源链接）
- [ ] Bot 消息签名验证通过（防伪造请求）
- [ ] Bot 答案支持 👍/👎 反馈 (回调到 Phase 1 反馈系统)

---

### 6.3 Webhook 事件系统

2026-10-12异常恢复约束：投递历史中单条损坏JSON/无效模型仅跳过该条，继续较旧有效记录并保持倒序/limit；读文件失败单独降级。事件worker每次成功queue.get后，无论投递成功、失败或处理期间取消，都须恰好一次task_done；等待get时取消不得误扣队列计数。单次失败不阻止后续事件，重试/签名契约保持不变。

**设计**：

```
事件类型:

  doc.ingested       文档索引完成
  doc.deleted        文档被删除
  kg.updated         KG 版本更新
  entity.approved    实体审核通过
  entity.rejected    实体被驳回
  feedback.received  收到新反馈

订阅方式:

  POST /api/v1/webhooks
  {
    "url": "https://my-system.com/hooks/graphrag",
    "events": ["doc.ingested", "kg.updated"],
    "secret": "wh_shared_secret"  // 用于 HMAC 签名
  }

投递格式:
  POST {webhook.url}
  Header: X-GraphRAG-Event: doc.ingested
  Header: X-GraphRAG-Signature: sha256=...
  Body: {
    "event": "doc.ingested",
    "timestamp": "2026-06-08T10:23:45Z",
    "data": {
      "doc_id": "doc_abc123",
      "filename": "2025年项目中期报告.pdf",
      "kg_nodes": 220,
      "kg_edges": 310
    }
  }
```

**API 扩展**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/webhooks` | 注册 Webhook |
| `GET` | `/api/v1/webhooks` | 列出已注册 Webhook |
| `DELETE` | `/api/v1/webhooks/{id}` | 删除 Webhook |
| `POST` | `/api/v1/webhooks/{id}/test` | 测试发送 |

**实施要点**：

| 文件 | 变更 |
|------|------|
| `backend/services/event_bus.py` (新建) | `EventBus` — 发布/订阅，异步投递，失败重试 (3 次指数退避) |
| `backend/services/webhook_manager.py` (新建) | Webhook 注册、HMAC 签名、投递状态追踪 |
| `backend/routes/webhooks.py` (新建) | Webhook CRUD 端点 |
| `backend/worker.py` | ingest 完成时 `event_bus.publish("doc.ingested", ...)` |
| `backend/routes/feedback.py` | 收到反馈时 `event_bus.publish("feedback.received", ...)` |

**Gate 标准**：
- [ ] Webhook 注册/删除 API 可用
- [ ] 事件触发后 30s 内投递到订阅 URL
- [ ] 投递失败自动重试 3 次
- [ ] HMAC 签名验证可用

---

### 6.4 监控与告警集成

> 在 Phase 0 Prometheus Metrics 基础上，加上告警规则和 Grafana Dashboard。

**设计**：

```
监控栈:
  应用层: 结构化日志 (Phase 0) → stdout
  指标层: Prometheus Metrics (Phase 0) → GET /metrics
  可视化: Grafana Dashboard (Phase 3)
  告警: AlertManager → 飞书/邮件通知

关键告警规则:
  - RAG 查询 P95 延迟 > 5s → Warning
  - MinerU API 错误率 > 10% → Critical
  - KG 加载失败 → Critical
  - DeepSeek API 429 频率 > 5次/小时 → Warning
  - 磁盘使用率 > 80% → Warning
```

**交付物**：

| 文件 | 说明 |
|------|------|
| `deploy/grafana/dashboards/rag-overview.json` | RAG 系统概览 Dashboard |
| `deploy/grafana/dashboards/retrieval-detail.json` | 检索路径详情 Dashboard |
| `deploy/prometheus/alerts.yml` | 告警规则文件 |
| `deploy/docker-compose.monitoring.yml` | Grafana + Prometheus 容器编排 |

**Gate 标准**：
- [ ] Grafana Dashboard 可展示：QPS、P50/P95/P99 延迟、错误率、召回路径分布
- [ ] 告警规则配置完成
- [ ] 告警可投递到飞书 Webhook

---

### Phase 3 总 Gate

```
[PASS] SSO 登录可走通完整 OAuth2 流程
[PASS] 飞书 Bot 可接收消息并返回 RAG 答案
[PASS] Webhook 事件可投递到外部 URL
[PASS] Grafana Dashboard + 告警规则就绪
[PASS] 审计日志记录所有敏感操作 (CRUD/权限变更/数据导出)
[PASS] 外部 API Key 可独立管理 (创建/撤销/限额)
[PASS] 系统集成健康检查覆盖全部外部依赖
─────────────────────────────────────────────────────
全部 PASS → 生态集成可对接
```

---

### 6.5 SSO / 统一认证（v1.3 补强）

> **v1.3 变更**：Phase 0 已实施 API Key SHA-256 Bearer Token 认证 + 白名单路径。
> SSO 需与现有认证中间件共存，提供渐进式迁移路径。Phase 1 的反馈系统已有 user_id 字段，SSO 上线后可直接关联真实用户身份。

**与现有 auth.py 的共存策略**：

```
认证优先级 (auth_middleware 改造):

  请求进入
    │
    ├─ 1. Cookie/Session (OAuth2 JWT) → 验证 → req.state.user = User
    │     └─ 失败 → 继续
    │
    ├─ 2. Authorization: Bearer <token>
    │     ├─ token 以 "sk-" 开头 → API Key 验证 (Phase 0 逻辑)
    │     │     └─ 通过 → req.state.user = api_key_user
    │     ├─ token 为 JWT → JWT 验证 (Phase 3 新增)
    │     │     └─ 通过 → req.state.user = jwt_user
    │     └─ 均失败 → 继续
    │
    └─ 3. 白名单路径 (Phase 0 已有) → 放行
          └─ 非白名单 + 无有效凭据 → 401
```

**增强数据模型**：

```python
# backend/models.py — Phase 3 新增
class User(BaseModel):
    user_id: str                    # SSO sub claim 或本地 UUID
    username: str
    email: str
    display_name: str
    roles: list[str]                # admin | editor | viewer
    department: str | None
    avatar_url: str | None
    created_at: str
    last_login: str | None
    auth_provider: str              # keycloak | auth0 | ldap | local

class UserRole(str, Enum):
    ADMIN = "admin"                 # 全权限：系统配置、用户管理、所有数据
    EDITOR = "editor"               # 可上传、可标注、可修正实体
    VIEWER = "viewer"               # 只读：查询、查看图谱

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600          # 1 小时

class OAuth2Config(BaseModel):
    provider: str                   # keycloak | auth0 | ldap | local
    issuer_url: str                 # OIDC discovery endpoint
    client_id: str
    client_secret: str              # 仅 .env，不出现在响应中
    redirect_uri: str
    scopes: list[str] = ["openid", "profile", "email"]
```

**权限矩阵（基于现有 API 端点扩增）**：

| 操作 | Admin | Editor | Viewer | 对应端点 |
|------|-------|--------|--------|----------|
| 上传文档 | ✅ | ✅ | ❌ | `POST /api/v1/ingest` |
| 查询问答 | ✅ | ✅ | ✅ | `POST /api/v1/query`, `/rag/query` |
| 提交反馈 | ✅ | ✅ | ✅ | `POST /api/v1/feedback` |
| 查看血缘 | ✅ | ✅ | ✅ | `GET /api/v1/lineage/*` |
| 数据目录 | ✅ | ✅ | ✅ | `GET /api/v1/catalog` |
| 实体 CRUD | ✅ | ✅ | ❌ | Phase 1 实体审核 |
| 导出数据 | ✅ | ✅ | ❌ | `GET /api/v1/export/*` |
| 词典管理 | ✅ | ✅ | ❌ | `/api/v1/domain-dict` CRUD |
| 备份/恢复 | ✅ | ❌ | ❌ | `POST /api/v1/system/backup` |
| 系统清理 | ✅ | ❌ | ❌ | `POST /api/v1/system/cleanup` |
| 用户管理 | ✅ | ❌ | ❌ | Phase 3 新增 |
| Webhook 管理 | ✅ | ❌ | ❌ | Phase 3 新增 |
| API Key 管理 | ✅ | ❌ | ❌ | Phase 3 新增 |

**增强 API**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/auth/login` | OAuth2 登录重定向 |
| `GET` | `/api/v1/auth/callback` | OAuth2 回调，签发 JWT |
| `POST` | `/api/v1/auth/refresh` | 刷新 JWT |
| `GET` | `/api/v1/auth/me` | 当前用户信息 |
| `POST` | `/api/v1/auth/logout` | 登出，吊销 refresh_token |
| `GET` | `/api/v1/users` | 用户列表 (admin only) |
| `PUT` | `/api/v1/users/{id}/roles` | 修改角色 (admin only) |
| `DELETE` | `/api/v1/users/{id}` | 禁用用户 (admin only) |

**环境变量 (.env 新增)**：

```bash
AUTH_PROVIDER=keycloak              # keycloak | auth0 | ldap | local
OIDC_ISSUER=https://sso.company.com/realms/graphrag
OIDC_CLIENT_ID=graphrag-web
OIDC_CLIENT_SECRET=xxx
JWT_SECRET_KEY=xxx                  # 用于签发本地 JWT (至少 32 字符)
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**前端变更**：

| 组件 | 变更 |
|------|------|
| `LoginPage.tsx` (新建) | SSO 登录页面，OAuth2 重定向 |
| `AuthGuard.tsx` (新建) | 路由守卫，未登录重定向到 /login |
| `AppShell.tsx` | 侧边栏底部加用户头像/姓名/登出下拉 |
| `frontend/src/lib/api.ts` | 自动附带 JWT Header (Authorization: Bearer)；401 时自动尝试 refresh |

**JWT 刷新策略**：

```
前端拦截器:
  response 401
    → 如果有 refresh_token
      → POST /api/v1/auth/refresh { refresh_token }
        → 成功: 更新 access_token, 重试原请求
        → 失败: 清除 token, 重定向 /login
    → 无 refresh_token
      → 重定向 /login
```

**渐进迁移路径**：

```
Stage 1 (本周): API Key 为主，增加 JWT 签发/验证逻辑，两者共存
Stage 2 (下周): 前端接入 SSO 登录页面，管理员可创建用户
Stage 3 (下月): 废弃 API Key 白名单，全部迁移到 JWT + RBAC
```

---

### 6.6 消息平台 Bot（v1.3 补强）

> **v1.3 变更**：Phase 1 反馈系统已上线（submit/list/stats/patch），Phase 2 检索管道已稳定。
> Bot 需复用现有 RAG 管道并回调反馈接口。一期仅支持飞书，二期扩展钉钉/企微。

**增强架构（对接 Phase 0-2 现有组件）**：

```
  飞书事件
    │
    ▼
  POST /api/v1/bot/feishu
    │
    ├─ 签名验证 (飞书 SDK — feishu_client.py)
    ├─ 消息解密 (AES-256-CBC)
    │
    ├─ 事件类型路由:
    │   ├─ url_verification → 返回 challenge
    │   ├─ im.message.receive_v1
    │   │   ├─ 提取 @提及文本
    │   │   ├─ → RAG Pipeline (现有 retrieval + generator)
    │   │   ├─ → 格式化卡片回复 (feishu_card_builder.py)
    │   │   ├─ → 发送消息 (feishu_client.reply_card())
    │   │   └─ → 记录查询 (现有 query_history 或 lineage_store)
    │   └─ im.message.reaction.created
    │       └─ → 回调现有 POST /api/v1/feedback (👍/👎 映射)
    │
    └─ 异常处理 → 飞书错误卡片 + 日志告警
```

**增强数据模型**：

```python
class BotConfig(BaseModel):
    platform: str           # feishu | dingtalk | wecom
    app_id: str
    app_secret: str         # 仅 .env
    verification_token: str | None   # 飞书事件验证
    encrypt_key: str | None          # 飞书消息加密
    webhook_url: str | None          # 主动消息 Webhook
    enabled: bool = True
    daily_limit: int = 500           # 每人每日查询上限

class BotMessage(BaseModel):
    platform: str
    event_type: str
    sender_id: str
    sender_name: str
    chat_id: str
    text: str               # 提取后的纯文本问题
    raw: dict               # 原始事件 payload
    timestamp: str

class BotReply(BaseModel):
    answer_text: str
    card_json: dict         # 平台卡片格式
    citations: list[str]    # 引用来源
    feedback_actions: bool  # 是否附带 👍👎 按钮
```

**增强 API**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/bot/feishu` | 飞书事件回调 |
| `POST` | `/api/v1/bot/feishu/card-reply` | 飞书卡片消息主动推送（内部） |
| `GET` | `/api/v1/bot/config` | Bot 配置列表 |
| `PUT` | `/api/v1/bot/config/{id}` | 更新 Bot 配置 |
| `POST` | `/api/v1/bot/config/{id}/test` | 发送测试消息 |

**飞书卡片模板（对接 Phase 2 导出）**：

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {"tag": "plain_text", "content": "📊 预算执行率查询"},
      "template": "blue"
    },
    "elements": [
      {
        "tag": "markdown",
        "content": "**预算总额**: 500 万元\n**已执行**: 420 万元 (84%)\n**剩余**: 80 万元 (16%)\n\n---\n📄 来源: 2025年项目中期报告 · 第 12 页"
      },
      {
        "tag": "action",
        "actions": [
          {"tag": "button", "text": {"tag": "plain_text", "content": "👍"}, "value": "positive"},
          {"tag": "button", "text": {"tag": "plain_text", "content": "👎"}, "value": "negative"},
          {"tag": "button", "text": {"tag": "plain_text", "content": "📎 查看来源"}, "url": "{{graphrag_url}}/query/{{query_id}}"}
        ]
      },
      {
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "由 GraphRAG 知识引擎驱动 · 如有误请反馈"}]
      }
    ]
  }
}
```

**多平台扩展设计**：

| 平台 | SDK/协议 | 特色功能 | 优先级 |
|------|---------|---------|--------|
| 飞书 Lark | OpenAPI SDK | 富卡片 + 消息卡片 + 审批流 | P0 (一期) |
| 钉钉 DingTalk | Stream Mode | 机器人回调 + 群机器人 Webhook | P1 (二期) |
| 企业微信 WeCom | 回调 URL + Token | 群机器人 + 图文消息 | P1 (二期) |
| Slack | Events API | Block Kit + Slash Commands | P2 (按需) |
| Teams | Bot Framework | Adaptive Cards | P2 (按需) |

**安全措施**：

- 飞书: Event 签名验证 (`X-Lark-Signature`) + 消息体解密 (AES-256-CBC)
- 钉钉: Stream Mode 长连接 + outTrackId 去重
- 企微: msg_signature 验证 + AES 解密
- 通用: Bot 请求不计入用户速率限制 (使用独立 `bot_rate_limit`)
- Bot 响应不包含 API Key / 内部错误详情

**Gate 标准**：
- [ ] 飞书 Bot 可接收 @消息并返回富卡片答案
- [ ] 卡片 👍/👎 按钮可回调反馈系统 (Phase 1)
- [ ] 消息签名验证可用 (防伪造)
- [ ] Bot 配置可通过 API 动态开关
- [ ] 单用户日查询上限可配置

---

### 6.7 Webhook 事件系统（v1.3 补强）

> **v1.3 变更**：Phase 0-2 已积累大量可触发事件的操作点。Webhook 系统需对准现有代码中的事件发布点 (ingest 完成、feedback 提交、backup 完成、cleanup 执行、KG 版本变更)，设计标准化事件 schema。

**现有触发点映射**：

| 事件类型 | 触发位置 | 现有代码 |
|----------|---------|---------|
| `doc.ingested` | 文档索引完成 | `worker.py` → task DONE |
| `doc.deleted` | 文档被删除 | `routes/documents.py` → DELETE |
| `kg.version_created` | KG 新版本生成 | `kg_store.py` → `create_version()` |
| `kg.version_switched` | 活跃版本切换 | `kg_store.py` → activate |
| `feedback.received` | 收到新反馈 | `services/feedback_store.py` → `submit()` |
| `feedback.resolved` | 反馈状态变更 | `services/feedback_store.py` → `update()` |
| `backup.completed` | 备份完成 | `services/backup.py` → `create_backup()` |
| `backup.failed` | 备份失败 | `services/backup.py` → 异常 |
| `cleanup.executed` | 生命周期清理执行 | `services/lifecycle.py` → `run_cleanup()` |
| `quality.alert` | 质量评分触达告警阈值 | `services/quality.py` → `compute()` |

**事件 schema 标准化**：

```python
# 所有事件统一 envelope
class WebhookEvent(BaseModel):
    event_id: str               # UUID4, 幂等去重
    event_type: str             # doc.ingested | kg.version_created | ...
    timestamp: str              # ISO 8601 UTC
    source: str                 # "graphrag-backend"
    version: str = "1.0"
    data: dict                  # 事件具体 payload

# 各事件 data schema 示例
class DocIngestedData(BaseModel):
    doc_id: str
    filename: str
    task_id: str
    kg_nodes: int
    kg_edges: int
    kg_version: int
    pages_parsed: int
    duration_seconds: int

class FeedbackReceivedData(BaseModel):
    feedback_id: str
    query_id: str
    rating: str                 # positive | negative
    comment: str | None
    user_id: str | None
    session_id: str | None

class BackupCompletedData(BaseModel):
    backup_id: str
    backup_type: str            # daily | weekly | manual
    total_files: int
    total_size_bytes: int
    kg_nodes: int | None
    checksum: str

class QualityAlertData(BaseModel):
    alert_level: str            # warning | critical
    metric: str                 # grounding_rate | positive_ratio | ...
    value: float
    threshold: float
    overall_score: float
```

**增强架构**：

```
EventBus (services/event_bus.py)
  │
  ├─ publish(event_type, data)
  │     ├─ 写入事件日志 output/events/{date}.jsonl (审计用)
  │     ├─ 查找匹配订阅 (webhook_manager)
  │     └─ 放入投递队列 (asyncio.Queue)
  │
  ├─ 后台 Worker (asyncio.Task, lifespan 启动)
  │     ├─ 从队列取出事件
  │     ├─ 对每个匹配 Webhook 执行 HTTP POST
  │     │   ├─ Header: X-GraphRAG-Event, X-GraphRAG-Signature (HMAC-SHA256)
  │     │   ├─ Body: WebhookEvent JSON
  │     │   ├─ 超时: 10s
  │     │   ├─ 成功 (2xx) → 记录 delivery_log
  │     │   └─ 失败 → 指数退避重试 (1s → 5s → 25s → 125s, 最多3次)
  │     └─ 3次全失败 → delivery_log 标记 failed + 日志告警
  │
  └─ delivery_log 查询: GET /api/v1/webhooks/{id}/deliveries
```

**增强 API**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/webhooks` | 注册 Webhook (url + events + secret) |
| `GET` | `/api/v1/webhooks` | 列出已注册 Webhook |
| `GET` | `/api/v1/webhooks/{id}` | 查看 Webhook 详情 |
| `PUT` | `/api/v1/webhooks/{id}` | 更新 Webhook 配置 |
| `DELETE` | `/api/v1/webhooks/{id}` | 删除 Webhook |
| `POST` | `/api/v1/webhooks/{id}/test` | 发送测试事件 (ping) |
| `GET` | `/api/v1/webhooks/{id}/deliveries` | 投递历史记录 |

**HMAC 签名规范**：

```
Client 验证:
  Header: X-GraphRAG-Signature: sha256=<hex_digest>
  
  签名计算: HMAC-SHA256(webhook_event_body_bytes, webhook_secret)
  
  Python 实现:
    import hmac, hashlib
    signature = hmac.new(
        secret.encode('utf-8'),
        event_body_bytes,
        hashlib.sha256
    ).hexdigest()
```

---

### 6.8 监控告警集成（v1.3 补强）

> **v1.3 变更**：Phase 0 metrics.py 已有 14 个 Prometheus 指标，Phase 2 quality.py 已生成质量评分。
> Phase 3 需要将指标可视化 (Grafana Dashboard) 并配置多渠道告警投递。

**Grafana Dashboard 设计（对接现有指标）**：

```
Dashboard 1: RAG 系统概览 (rag-overview.json)

  Row 1 — 服务健康:
    - Stat: QPS (当前) ← rag_requests_total rate
    - Stat: P95 Latency ← rag_request_duration_seconds histogram
    - Stat: Error Rate ← rag_errors_total / rag_requests_total
    - Stat: Quality Score ← rag_quality_score

  Row 2 — 检索管道:
    - TimeSeries: Candidates per source (kg/vector/bm25/table) ← rag_retrieval_candidates
    - TimeSeries: Retrieval step latency ← rag_retrieval_latency_ms
    - Stat: Zero-result rate ← rag_zero_result_queries rate

  Row 3 — 数据资产:
    - Stat: Total Documents ← rag_documents_total
    - Stat: Total KG Nodes ← rag_kg_nodes_total
    - Stat: Total KG Edges ← rag_kg_edges_total
    - Stat: Grounding Rate ← rag_grounding_rate
    - Stat: Positive Feedback ← rag_positive_feedback_ratio

  Row 4 — 数据新鲜度:
    - Stat: Days Since Ingest ← rag_data_freshness_days
    - Stat: Stale Entities ← rag_stale_entities
```

**告警规则（扩展现有 deploy/prometheus/alerts.yml）**：

```yaml
# Phase 3 新增告警规则
groups:
  - name: rag_service_alerts
    rules:
      - alert: HighQueryLatency
        expr: histogram_quantile(0.95, rate(rag_request_duration_seconds_bucket[5m])) > 30
        for: 10m
        labels: { severity: warning }
        annotations: { summary: "P95 query latency > 30s", description: "当前 P95: {{ $value }}s" }

      - alert: HighErrorRate
        expr: rate(rag_errors_total[5m]) / rate(rag_requests_total[5m]) > 0.05
        for: 5m
        labels: { severity: critical }
        annotations: { summary: "Error rate > 5%", description: "当前: {{ $value | humanizePercentage }}" }

      - alert: DiskUsageWarning
        expr: (node_filesystem_size_bytes{mountpoint="/data"} - node_filesystem_free_bytes{mountpoint="/data"}) / node_filesystem_size_bytes{mountpoint="/data"} > 0.8
        for: 5m
        labels: { severity: warning }
        annotations: { summary: "Disk usage > 80%" }
```

**告警投递渠道**：

| 渠道 | 配置 | 用途 |
|------|------|------|
| 飞书 Webhook | AlertManager webhook_config | 发送告警卡片到运维群 |
| 邮件 | AlertManager email_config (SMTP) | 日汇总报告 |
| 钉钉/企微 | AlertManager webhook_config | 备用通知渠道 |

**监控部署**：

```yaml
# deploy/docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus:v2.50.0
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alerts.yml:/etc/prometheus/alerts.yml
      - prometheus_data:/prometheus
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana:10.4.0
    volumes:
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
      - grafana_data:/var/lib/grafana
    ports: ["3000:3000"]
    depends_on: [prometheus]
```

---

### 6.9 审计日志（新增 §6.5）

> **v1.3 新增**：Phase 0 已实现结构化操作日志 (JSON → stdout + 文件轮转)。
> 审计日志分离"谁在什么时候做了什么"的安全/合规事件，独立于运维日志。

**审计事件分类**：

| 类别 | 事件 | 记录字段 |
|------|------|---------|
| 认证 | `user.login`, `user.logout`, `user.login_failed` | user_id, ip, user_agent |
| 数据操作 | `entity.created`, `entity.updated`, `entity.deleted` | user_id, entity_id, before/after |
| 文档 | `doc.uploaded`, `doc.deleted`, `doc.reingested` | user_id, doc_id, filename |
| 配置 | `config.updated`, `dict.term_added`, `dict.term_removed` | user_id, key, old/new value |
| 系统 | `backup.triggered`, `restore.executed`, `cleanup.executed` | user_id, backup_id, result |
| 权限 | `user.role_changed`, `api_key.created`, `api_key.revoked` | admin_id, target_user_id |
| 导出 | `data.exported` | user_id, format, estimated_rows |

**实现**：

```python
# backend/services/audit_logger.py

class AuditLogger:
    """Security/compliance audit log. Writes JSONL to output/audit/."""

    def __init__(self, audit_dir: Path = Path("output/audit")):
        self.audit_dir = audit_dir
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, user_id: str, **kwargs):
        record = {
            "event": event,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip": kwargs.pop("ip", ""),
            "user_agent": kwargs.pop("user_agent", ""),
            "details": kwargs,
        }
        # 按日期分文件
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = self.audit_dir / f"audit-{date_str}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

# 在现有端点中注入审计记录:
# - kg_store.create_version() → audit.log("kg.version_created", ...)
# - feedback_store.submit() → audit.log("feedback.received", ...)
# - backup_manager.create_backup() → audit.log("backup.triggered", ...)
```

**审计查询 API**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/audit?event=xxx&user_id=xxx&from=&to=` | 查询审计事件 |
| `GET` | `/api/v1/audit/export?from=&to=&format=csv` | 导出审计日志 |

**保留策略**：审计日志保留 365 天（lifecycle.py 新增 `audit` 策略）。

---

### 6.10 外部 API Key 管理（新增 §6.6）

> **v1.3 新增**：Phase 0 仅支持单一 ADMIN_API_KEY。生态集成场景需要为第三方服务分配独立的 API Key，支持独立限额和撤销。

**API Key 模型**：

```python
class ApiKey(BaseModel):
    key_id: str                    # 唯一标识
    name: str                      # "Engine-Vue集成" | "钉钉Bot" | "数据导出脚本"
    key_prefix: str                # "sk-graphrag-" (用于前端显示)
    key_hash: str                  # SHA-256 哈希
    created_by: str                # user_id
    created_at: str
    expires_at: str | None
    last_used_at: str | None
    revoked: bool = False
    scopes: list[str]              # ["read:query", "read:catalog", "write:ingest"]
    rate_limit_per_minute: int = 60

class ApiKeyCreate(BaseModel):
    name: str
    expires_at: str | None = None  # ISO 8601, None = 永不过期
    scopes: list[str] = ["read:query"]
    rate_limit_per_minute: int = 60

class ApiKeyResponse(BaseModel):
    key_id: str
    name: str
    key_prefix: str
    full_key: str                  # 仅创建时返回一次! 之后不可获取
    created_at: str
    expires_at: str | None
    scopes: list[str]
```

**OAuth2 Scopes 映射**：

| Scope | 对应权限 |
|-------|---------|
| `read:query` | 查询问答 (query + rag/query) |
| `read:catalog` | 数据目录 + 血缘查看 |
| `read:export` | 数据导出 |
| `write:ingest` | 文档上传 |
| `write:feedback` | 提交反馈 |
| `write:dict` | 词典管理 |
| `admin:system` | 系统管理 (备份/清理/用户) |
| `admin:keys` | API Key 管理 |

**API**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/api-keys` | 创建 API Key (返回完整 Key 仅此一次) |
| `GET` | `/api/v1/api-keys` | 列出所有 API Key (不返回完整 Key) |
| `GET` | `/api/v1/api-keys/{id}` | 查看单个 Key 元数据 |
| `POST` | `/api/v1/api-keys/{id}/revoke` | 撤销 Key |
| `POST` | `/api/v1/api-keys/{id}/rotate` | 轮换 Key (新 Key 返回一次) |

---

### 6.11 系统集成健康检查（新增 §6.7）

> **v1.3 新增**：Phase 1 health 端点 (`GET /api/v1/health`) 只检查基本组件。
> 企业集成需要深度健康检查覆盖全部外部依赖。

**增强 Health 响应**：

```json
GET /api/v1/health
{
  "status": "healthy",           // healthy | degraded | unhealthy
  "version": "1.2.0",
  "uptime_seconds": 86400,
  "components": {
    "api_server": "ok",
    "deepseek_api": "ok",
    "mineru_api": "ok",
    "kg_store": "ok",
    "chromadb": "ok",
    "oauth2_provider": "ok",      // Phase 3 新增
    "feishu_bot": "ok",            // Phase 3 新增
    "prometheus": "ok",            // Phase 3 新增
    "scheduler": "ok"              // Phase 2 (APScheduler)
  },
  "stats": {
    "total_kg_nodes": 439,
    "total_kg_edges": 1537,
    "total_documents": 5,
    "total_queries_served": 3078,
    "queries_today": 42,
    "quality_score": 72.5          // Phase 2 新增
  },
  "dependencies": {                // Phase 3 新增
    "deepseek_api": {"status": "ok", "latency_ms": 234},
    "mineru_api": {"status": "ok", "latency_ms": 567},
    "chromadb": {"status": "ok", "collections": 3, "documents": 31},
    "oauth2_provider": {"status": "ok", "connected": true},
    "feishu_bot": {"status": "ok", "webhook_registered": true}
  }
}
```

**内部定时检查**：(APScheduler 每 5 分钟)
- DeepSeek API: HEAD 请求 → 记录延迟
- MinerU API: 健康端点探活
- ChromaDB: collection count 查询
- OAuth2 Provider: OIDC discovery endpoint 可达性
- 飞书 Bot: tenant_access_token 是否有效

---

### Phase 3 完整文件清单（v1.3 更新）

| 模块 | 文件 | 说明 |
|------|------|------|
| §6.1 SSO | `backend/services/auth_service.py` | OAuth2/OIDC 集成 + JWT 签发 + 用户管理 |
| §6.1 SSO | `backend/routes/auth.py` (扩展现有) | 登录/回调/刷新/用户信息/登出 |
| §6.1 SSO | `backend/middleware/jwt_middleware.py` | JWT 验证中间件 (与 auth.py 共存) |
| §6.1 SSO | 前端 `LoginPage.tsx` | SSO 登录页面 |
| §6.1 SSO | 前端 `AuthGuard.tsx` | 路由守卫 |
| §6.2 Bot | `backend/routes/bot.py` | Bot 回调端点 (飞书/钉钉/企微) |
| §6.2 Bot | `backend/services/feishu_client.py` | 飞书 SDK 封装 (token/消息/卡片) |
| §6.2 Bot | `backend/services/bot_handler.py` | 消息路由 + 回复格式化 |
| §6.2 Bot | `backend/services/card_builder.py` | 飞书/钉钉/企微 卡片模板 |
| §6.3 Webhook | `backend/services/event_bus.py` | 事件发布/订阅 + 异步投递 |
| §6.3 Webhook | `backend/services/webhook_manager.py` | Webhook CRUD + HMAC 签名 |
| §6.3 Webhook | `backend/routes/webhooks.py` | Webhook 管理端点 |
| §6.4 监控 | `deploy/grafana/dashboards/rag-overview.json` | RAG 系统概览 Dashboard |
| §6.4 监控 | `deploy/grafana/dashboards/retrieval-detail.json` | 检索管道详情 Dashboard |
| §6.4 监控 | `deploy/prometheus/alerts.yml` (更新) | 扩增告警规则 (已有 Phase 2 质量告警) |
| §6.4 监控 | `deploy/docker-compose.monitoring.yml` | Prometheus + Grafana 编排 |
| §6.5 审计 | `backend/services/audit_logger.py` | 审计日志 JSONL 写入 |
| §6.5 审计 | `backend/routes/audit.py` | 审计查询/导出端点 |
| §6.6 API Key | `backend/services/api_key_manager.py` | 多 API Key 管理 + 配额 + 撤销 |
| §6.6 API Key | `backend/routes/api_keys.py` | API Key 管理端点 |
| §6.7 健康 | `backend/services/health_checker.py` | 定时依赖探活 (apscheduler) |
| **合计** | **21 个新文件** | (12 backend + 4 frontend + 5 deploy) |

---

### Phase 3 总 Gate（v1.3 更新）

```
[PASS] SSO 登录可走通完整 OAuth2 流程 + JWT 刷新
[PASS] 权限矩阵前端+后端双层校验 (admin/editor/viewer)
[PASS] 飞书 Bot 可接收 @消息并返回富卡片答案
[PASS] Bot 答案 👍/👎 可回调 Phase 1 反馈系统
[PASS] Webhook 事件可发布/订阅/投递，支持重试
[PASS] 10 种标准事件 schema 定义完整
[PASS] Grafana Dashboard 展示 QPS/P95/错误率/检索路径/数据资产
[PASS] 告警可投递到至少 1 个外部渠道 (飞书/邮件/钉钉)
[PASS] 审计日志记录所有敏感操作
[PASS] 外部 API Key 可独立创建/管理/撤销
[PASS] 健康检查覆盖全部外部依赖
─────────────────────────────────────────────────────
全部 PASS → 生态集成可对接
```

---

## 7. Phase 4: 企业就绪

> **目标**：多租户隔离、容器化部署、CI/CD 自动化，从单机开发环境升级为生产级企业平台。
>
> **周期**：3 周
> **前置依赖**：Phase 1 + Phase 2 + Phase 3

### 7.1 多租户数据隔离 (v1.4 补强)

#### 7.1.1 现有基础

当前代码已具备项目概念雏形：

| 现有资产 | 位置 | 形态 |
|---------|------|------|
| 项目 ID 映射 | `backend/config/project_id_mapping.json` | 手动映射表，key=文件名→value=项目ID |
| 文档级隔离 | `output/kg/doc_{task_id}/` | 每文档独立目录，含 v{N}/ 版本子目录 |
| 用户角色 | `backend/models.py::UserRole` | admin / editor / viewer 三级 |
| JWT 中间件 | `backend/middleware/jwt_middleware.py` | 已从 token 提取 user_id + roles |
| API Key Scope | `backend/middleware/jwt_middleware.py::SCOPE_PATH_MAP` | 8 scope → 端点前缀映射 |

缺失：租户感知的存储隔离、查询隔离、跨租户访问控制。

#### 7.1.2 隔离架构

```
                         ┌──────────────────────────┐
                         │     GraphRAG Platform     │
                         │                          │
       user (admin) ────►│  Organization "中油吉林化建" │
                         │    │                     │
                         │    ├── Project "HSE-2026" │
                         │    │   ├── 文档 A (PDF)   │
                         │    │   ├── 文档 B (DOCX)  │
                         │    │   └── KG (isolated)  │
                         │    │                     │
                         │    └── Project "QHSE月报"  │
                         │        ├── 文档 C (XLSX)  │
                         │        └── KG (isolated)  │
                         │                          │
       user (editor) ───►│  Organization "吉林建工总部" │
                         │    └── Project "安全管理"   │
                         │        └── KG (isolated)  │
                         └──────────────────────────┘

隔离粒度:
  ┌──────────┬──────────────────────────────────────────────┐
  │ 资源     │ 隔离方式                                      │
  ├──────────┼──────────────────────────────────────────────┤
  │ KG 图    │ 按 project_id 独立 NetworkX graph             │
  │ 向量库   │ ChromaDB collection: {org_id}_{project_id}    │
  │ 文档索引 │ docs_store.json → 按 project_id 分片           │
  │ BM25     │ 按 project_id 独立索引                         │
  │ 血缘     │ lineage 记录携带 project_id                    │
  │ 反馈     │ feedback 记录携带 project_id                   │
  │ 会话     │ conversation 记录携带 project_id              │
  │ 审计     │ audit 记录携带 org_id + project_id            │
  │ 导出     │ 按 project_id 筛选导出                        │
  │ 备份     │ 按 org_id 粒度全量备份，支持单 project 恢复     │
  └──────────┴──────────────────────────────────────────────┘
```

#### 7.1.3 增强数据模型

```python
# backend/models.py — Phase 4 新增

class Organization(BaseModel):
    """租户组织"""
    org_id: str                          # UUID4, 如 "org_a1b2c3d4"
    name: str                            # "中油吉林化建工程有限公司"
    slug: str                            # URL-safe 标识, "jilin-huajian"
    contact_email: str | None = None
    plan: str = "free"                   # free | pro | enterprise
    max_projects: int = 5
    max_users: int = 20
    max_storage_mb: int = 500
    created_at: str
    updated_at: str | None = None
    is_active: bool = True

class Project(BaseModel):
    """组织下的项目"""
    project_id: str                      # UUID4, 如 "proj_e5f6g7h8"
    org_id: str                          # 所属组织
    name: str                            # "HSE-2026"
    description: str = ""
    project_code: str | None = None      # 业务编号, "HSE-2026-Q1"
    created_by: str                      # user_id
    created_at: str
    updated_at: str | None = None
    is_archived: bool = False            # 归档后只读

class OrgMembership(BaseModel):
    """用户在组织中的角色（一个用户可在不同组织有不同角色）"""
    membership_id: str
    org_id: str
    user_id: str
    role: str                            # org_admin | org_editor | org_viewer
    joined_at: str
    invited_by: str | None = None

class TenantContext(BaseModel):
    """请求上下文中的租户信息（中间件注入 request.state.tenant）"""
    org_id: str
    project_id: str | None = None        # None = 跨项目
    user_id: str
    org_role: str
    permissions: list[str]               # 细粒度权限列表
```

#### 7.1.4 租户中间件设计

```python
# backend/middleware/tenant_middleware.py — 新建

def create_tenant_middleware():
    """租户上下文中间件 — 从 X-Project-Id Header 或 JWT claims 解析租户信息。
    在 JWT 中间件之后执行（依赖 request.state.user）。
    """

    async def tenant_middleware(request: Request, call_next):
        path = request.url.path

        # 白名单跳过
        if path in ("/", "/docs", "/redoc", "/openapi.json", "/metrics",
                     "/api/v1/health", "/api/v1/auth/login",
                     "/api/v1/auth/callback", "/api/v1/bot/feishu"):
            return await call_next(request)

        user = getattr(request.state, "user", None)
        if not user:
            return await call_next(request)

        # 从 Header 解析 project_id
        project_id = request.headers.get("X-Project-Id")

        # 从用户信息解析 org_id（JWT claims 或用户 profile）
        org_id = user.get("org_id", "default")

        # Admin 可跨项目查询（不传 X-Project-Id 时）
        if not project_id and "admin" not in user.get("roles", []):
            # 非 admin 必须指定项目
            project_id = user.get("default_project_id")

        request.state.tenant = {
            "org_id": org_id,
            "project_id": project_id,
            "user_id": user.get("user_id", ""),
            "org_role": user.get("org_role", "viewer"),
            "permissions": user.get("permissions", []),
        }
        return await call_next(request)

    return tenant_middleware
```

#### 7.1.5 现有模块租户化改造

| 模块 | 文件 | 改造内容 |
|------|------|---------|
| KG 存储 | `backend/kg_store.py` | `load_all_kg_graphs()` 接受 `org_id + project_id` 过滤；`create_version()` 传入 tenant context |
| 向量存储 | `backend/vector_store.py` | `VectorStore.collection_name` 改为 `{org_id}_{project_id}_chunks` |
| BM25 索引 | `backend/index_registry.py` | 按 `{org_id}_{project_id}` 分片存储 BM25 索引 |
| 检索管道 | `backend/retrieval.py` | `retrieve()` 接受 `tenant: TenantContext`，仅检索当前项目 scope |
| 文档列表 | `backend/routes/documents.py` | `list_documents()` 按 `project_id` 过滤 |
| 血缘查询 | `backend/routes/lineage.py` | 血缘链路按 `project_id` 筛选 |
| 数据目录 | `backend/services/catalog.py` | `build()` 按 `org_id` 聚合，可选 `project_id` 下钻 |
| 导出 | `backend/services/kg_exporter.py` | 导出按 `project_id` 范围限定 |
| 备份 | `backend/services/backup.py` | 备份路径加 `org_id/` 前缀；支持单 project 恢复 |
| 审计 | `backend/services/audit_logger.py` | `log()` 自动注入当前 `org_id + project_id` |
| 质量 | `backend/services/quality.py` | 质量指标按 `project_id` 分组计算 |

#### 7.1.6 租户管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/orgs` | 创建组织 (admin only) |
| `GET` | `/api/v1/orgs` | 列出用户所属组织 |
| `GET` | `/api/v1/orgs/{org_id}` | 组织详情 |
| `PUT` | `/api/v1/orgs/{org_id}` | 更新组织配置 (org_admin) |
| `POST` | `/api/v1/orgs/{org_id}/projects` | 创建项目 |
| `GET` | `/api/v1/orgs/{org_id}/projects` | 列出组织下项目 |
| `PUT` | `/api/v1/orgs/{org_id}/projects/{project_id}` | 更新项目 |
| `POST` | `/api/v1/orgs/{org_id}/projects/{project_id}/archive` | 归档项目 |
| `POST` | `/api/v1/orgs/{org_id}/members` | 邀请成员 (org_admin) |
| `GET` | `/api/v1/orgs/{org_id}/members` | 成员列表 |
| `PUT` | `/api/v1/orgs/{org_id}/members/{user_id}/role` | 修改成员角色 |
| `DELETE` | `/api/v1/orgs/{org_id}/members/{user_id}` | 移除成员 |

#### 7.1.7 权限矩阵 (Phase 4 增强)

| 操作 | org_admin | org_editor | org_viewer | 全局 admin |
|------|-----------|------------|------------|-----------|
| 创建项目 | ✅ | ❌ | ❌ | ✅ |
| 上传文档 (本组织) | ✅ | ✅ | ❌ | ✅ |
| 查询问答 (本组织) | ✅ | ✅ | ✅ | ✅ |
| 跨项目查询 | ✅ | ❌ | ❌ | ✅ |
| 管理成员 | ✅ | ❌ | ❌ | ✅ |
| 删除项目 | ✅ | ❌ | ❌ | ✅ |
| 导出数据 | ✅ | ✅ | ❌ | ✅ |
| 修改组织配置 | ✅ | ❌ | ❌ | ✅ |
| 查看审计日志 | ✅ | ❌ | ❌ | ✅ |

**Gate 标准 (§7.1)**：
- [ ] 创建两个组织、各含两个项目，数据完全隔离（KG / 向量 / 文档列表不可见）
- [ ] 非 admin 用户不带 `X-Project-Id` 时自动限定默认项目
- [ ] 跨项目查询仅 admin 可用
- [ ] 租户中间件注入 `request.state.tenant`，所有下游模块通过它获取 scope
- [ ] 备份支持按 org_id 全量 + 按 project_id 单项目恢复

---

### 7.2 容器化部署 (v1.4 补强)

#### 7.2.1 现有基础

| 已有资产 | 位置 | 说明 |
|---------|------|------|
| 监控编排 | `deploy/docker-compose.monitoring.yml` | Prometheus + Grafana + AlertManager |
| 监控配置 | `deploy/prometheus/` + `deploy/grafana/` | 完整监控栈配置 |
| Python 依赖 | `backend/requirements.txt` | 26 个包，锁定版本下限 |
| 前端依赖 | `frontend/package.json` | React 18 + TypeScript + Vite + Tailwind + Zustand |
| 健康检查 | `backend/routes/health.py` | 含 5 个外部依赖探活结果 |
| 环境变量 | `backend/.env.example` | 部分配置模板 |

缺失：生产级 Dockerfile、完整服务编排（含 backend/frontend/ChromaDB）、.dockerignore。

#### 7.2.2 容器化架构

```
                    ┌──────────────────────────────┐
                    │    docker-compose.yml         │
                    │                              │
    Port 80 ───────►│  nginx (frontend)            │
                    │    ├── /          → React SPA │
                    │    └── /api/*     → proxy     │
                    │         │                     │
    Port 8000 ─────►│  backend (FastAPI + uvicorn)  │
                    │    ├── /api/v1/*   (REST)     │
                    │    ├── /docs       (Swagger)  │
                    │    └── /metrics    (Prometheus)│
                    │         │                     │
                    │  chromadb (内部)              │
                    │    └── /output/vectordb/      │
                    │                              │
    Port 9090 ─────►│  prometheus                   │
    Port 3000 ─────►│  grafana                      │
    Port 9093 ─────►│  alertmanager                 │
                    └──────────────────────────────┘
```

#### 7.2.3 Dockerfile.backend

2026-10-12维护更新：后端构建与CI必须消费 `backend/uv.lock`，不得用浮动 `requirements.txt` 代替。保留 `/app` 运行目录；本地依赖位于 `/langextract`，构建上下文包含子模块且继续排除其环境、密钥及生成物。当前镜像配置已修改，Docker引擎不可用，实际容器验收待验证。

```dockerfile
# Dockerfile.backend
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/

WORKDIR /app

# System dependencies for MinerU curl calls
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip && rm -rf /var/lib/apt/lists/*

# Python dependencies
ENV UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/
COPY langextract/ /langextract/
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
ENV PATH="/app/.venv/bin:${PATH}"

# Application code
COPY backend/ .

# Runtime
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 7.2.4 Dockerfile.frontend

```dockerfile
# Dockerfile.frontend — multi-stage build
FROM node:22-alpine AS build

WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ .
RUN pnpm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
```

#### 7.2.5 完整服务编排

```yaml
# docker-compose.yml — 根目录，全服务编排
version: "3.8"

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: graphrag-backend
    env_file: backend/.env
    environment:
      - CHROMADB_HOST=chromadb
      - OUTPUT_DIR=/data/output
    volumes:
      - graphrag_data:/data/output
      - ./backend/config:/app/config:ro
    ports:
      - "8000:8000"
    depends_on:
      chromadb:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    container_name: graphrag-frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped

  chromadb:
    image: chromadb/chroma:0.5.23
    container_name: graphrag-chromadb
    volumes:
      - chromadb_data:/chroma/chroma
    environment:
      - IS_PERSISTENT=TRUE
      - ANONYMIZED_TELEMETRY=FALSE
    ports:
      - "8001:8000"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v2/heartbeat"]
      interval: 30s
      timeout: 5s
      retries: 3

  prometheus:
    image: prom/prometheus:v2.50.0
    container_name: graphrag-prometheus
    volumes:
      - ./deploy/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./deploy/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.4.0
    container_name: graphrag-grafana
    volumes:
      - ./deploy/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./deploy/grafana/datasources/datasource.yml:/etc/grafana/provisioning/datasources/datasource.yml:ro
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:v0.27.0
    container_name: graphrag-alertmanager
    volumes:
      - ./deploy/prometheus/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    ports:
      - "9093:9093"
    restart: unless-stopped

volumes:
  graphrag_data:
  chromadb_data:
  prometheus_data:
  grafana_data:
```

#### 7.2.6 Nginx 前端配置

```nginx
# deploy/nginx/default.conf
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy to backend
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    # Backend docs proxy
    location /docs {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
    }

    location /redoc {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
    }

    location /metrics {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
    }

    # Static assets with long cache
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

#### 7.2.7 环境变量扩展

```bash
# backend/.env — Phase 4 新增字段

# ── 部署模式 ──
DEPLOY_MODE=production              # development | staging | production
FRONTEND_URL=http://localhost       # SSO 回调 + Bot 卡片跳转

# ── 多租户 ──
DEFAULT_ORG_ID=default              # 单租户模式默认组织
MULTI_TENANT_ENABLED=false          # 启用后强制 X-Project-Id

# ── ChromaDB ──
CHROMADB_HOST=localhost             # 开发: localhost, 容器: chromadb
CHROMADB_PORT=8000

# ── 数据目录 ──
OUTPUT_DIR=./output                 # 开发: ./output, 容器: /data/output

# ── 容器资源限制 ──
MAX_UPLOAD_SIZE_MB=200
WORKER_CONCURRENCY=4
```

#### 7.2.8 .dockerignore

```
# .dockerignore
**/.venv/
**/node_modules/
**/__pycache__/
**/.pytest_cache/
**/*.pyc
**/.git/
**/output/
**/uploads/
**/.env
**/.env.*
!**/.env.example
**/*.log
**/dist/
**/.claude/
**/plans/
**/docs/
**/iteration-*/
**/mineru-mvp-test/
**/langextract/
**/harness-engineering/
```

**Gate 标准 (§7.2)**：
- [ ] `docker-compose up` 一键启动 6 个服务（backend / frontend / chromadb / prometheus / grafana / alertmanager）
- [ ] Nginx 反向代理 `/api/*` → backend，SPA fallback 正常
- [ ] 健康检查 `/api/v1/health` 返回 ChromaDB 真实连接状态（非 localhost 文件检查）
- [ ] 数据卷持久化：`docker-compose down && up` 后 KG + 向量数据不丢失
- [ ] 前端 `pnpm build` 产物可独立部署到 Nginx

---

### 7.3 CI/CD 集成 (v1.4 补强)

2026-10-12维护有效约束：后端测试/audit/build签出子模块；安装统一 `uv sync --locked`，执行用 `uv run --no-sync`；audit由锁导出完整registry依赖（仅去除本地langextract包本身、不去除其依赖），保留Chroma未修复发现，不自动套历史例外。前端Node22、packageManager固定pnpm10.33.3，以 `pnpm-lock.yaml` 冻结安装；旧npm锁原样保存在 `docs/archive/frontend-package-lock.pre-pnpm-2026-10-12.json`，不可用于部署。镜像发布依赖test/dependency-audit/bandit-sast/secret-scan全部成功。以下7.3.1–7.3.3为历史设计示例，浮动pip安装/旧Node/仅test后发布已被本段替代；当前配置以 `.github/workflows/ci.yml` 对应这些约束验收。双覆盖门槛仍按根AGENTS；此变更不代表覆盖CI与保护分支已完备。

#### 7.3.1 现有基础

| 已有资产 | 位置 | 说明 |
|---------|------|------|
| Python 测试 | `backend/tests/test_phase2.py` + `test_phase3.py` | 71 tests, pytest |
| TypeScript 检查 | `tsc --noEmit` | 零错误通过 |
| 锁文件 | `requirements.txt` (版本下限) | 无 `uv.lock` |
| 前端构建 | `pnpm build` (tsc + vite) | 支持生产构建 |

缺失：完整 CI 流水线 YAML、test 步骤的自动化脚本、Docker build/push 步骤。

#### 7.3.2 CI Pipeline (GitHub Actions)

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [master, develop]
  pull_request:
    branches: [master]

env:
  PYTHON_VERSION: "3.12"
  NODE_VERSION: "20"

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Ruff (Python lint)
        uses: chartboost/ruff-action@v1
        with:
          src: "./backend"

      - name: ESLint (Frontend lint)
        working-directory: ./frontend
        run: |
          corepack enable
          pnpm install --frozen-lockfile
          pnpm run lint || true  # non-blocking until rules finalized

  test:
    needs: lint
    runs-on: ubuntu-latest
    services:
      chromadb:
        image: chromadb/chroma:0.5.23
        env:
          IS_PERSISTENT: TRUE
        ports:
          - 8000:8000

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Backend tests
        working-directory: ./backend
        env:
          CHROMADB_HOST: localhost
          CHROMADB_PORT: 8000
        run: |
          pip install -r requirements.txt
          pytest tests/ -v --tb=short --timeout=60

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}

      - name: Frontend typecheck
        working-directory: ./frontend
        run: |
          corepack enable
          pnpm install --frozen-lockfile
          npx tsc --noEmit

  build-and-push:
    needs: test
    if: github.ref == 'refs/heads/master'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build & push backend
        uses: docker/build-push-action@v6
        with:
          context: .
          file: Dockerfile.backend
          push: true
          tags: ghcr.io/${{ github.repository }}/graphrag-backend:${{ github.sha }}

      - name: Build & push frontend
        uses: docker/build-push-action@v6
        with:
          context: .
          file: Dockerfile.frontend
          push: true
          tags: ghcr.io/${{ github.repository }}/graphrag-frontend:${{ github.sha }}
```

#### 7.3.3 CI Pipeline (GitLab CI — 备选)

```yaml
# .gitlab-ci.yml
stages:
  - lint
  - test
  - build
  - deploy

variables:
  PYTHON_VERSION: "3.12"

ruff:
  stage: lint
  image: python:${PYTHON_VERSION}-slim
  script:
    - pip install ruff
    - ruff check backend/

pytest:
  stage: test
  image: python:${PYTHON_VERSION}-slim
  services:
    - name: chromadb/chroma:0.5.23
      alias: chromadb
  variables:
    CHROMADB_HOST: chromadb
  script:
    - pip install -r backend/requirements.txt
    - cd backend && pytest tests/ -v --tb=short

typescript:
  stage: test
  image: node:20-alpine
  script:
    - cd frontend
    - corepack enable
    - pnpm install --frozen-lockfile
    - npx tsc --noEmit

docker-build:
  stage: build
  only: [master]
  script:
    - docker build -t graphrag-backend:$CI_COMMIT_SHA -f Dockerfile.backend .
    - docker build -t graphrag-frontend:$CI_COMMIT_SHA -f Dockerfile.frontend .
    - docker push registry.example.com/graphrag-backend:$CI_COMMIT_SHA
    - docker push registry.example.com/graphrag-frontend:$CI_COMMIT_SHA
```

#### 7.3.4 CD 部署脚本

```bash
#!/bin/bash
# deploy/cd-deploy.sh — 目标服务器拉取镜像并重启服务

set -e

REGISTRY="${REGISTRY:-ghcr.io/org/graphrag}"
TAG="${1:-latest}"

echo "[CD] Deploying tag: $TAG"

# Pull latest images
docker pull ${REGISTRY}/graphrag-backend:${TAG}
docker pull ${REGISTRY}/graphrag-frontend:${TAG}

# Restart services
cd /opt/graphrag
TAG=${TAG} docker-compose up -d --remove-orphans

# Wait for health
echo "[CD] Waiting for health check..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo "[CD] Deploy successful — backend healthy"
        exit 0
    fi
    sleep 2
done

echo "[CD] ERROR: Backend did not become healthy within 60s"
exit 1
```

**Gate 标准 (§7.3)**：
- [ ] GitHub Actions / GitLab CI 包含 lint → test → build 三阶段
- [ ] Backend 71 个测试在 CI 环境中全绿（含 ChromaDB service container）
- [ ] Frontend TypeScript 编译零错误
- [ ] Docker 镜像推送到 registry (ghcr.io 或私有)
- [ ] CD 脚本可一键部署到目标服务器

---

### 7.4 最终验收 (v1.4 补强)

#### 7.4.1 全 Phase 验收矩阵

| # | 验收项 | Phase | 验证方式 | 当前状态 |
|---|--------|-------|---------|---------|
| 1 | 结构化日志 — JSON 格式, request_id 全链路 | 0 | 检查 `output/logs/app.log` | ✅ 已实施 |
| 2 | Prometheus Metrics — `/metrics` 可抓取 | 0 | `curl localhost:8000/metrics` | ✅ 已实施 |
| 3 | API Key 认证 — 非白名单端点需认证 | 0 | 请求无 Key → 401 | ✅ 已实施 |
| 4 | KG 版本管理 — 重复 ingest 不覆盖 | 0 | 同一文档 ingest 两次 → v1 + v2 | ✅ 已实施 |
| 5 | 答案反馈 — 👍/👎 + 文字, 反馈看板 | 1 | POST /api/v1/feedback → GET /api/v1/feedback | ✅ 已实施 |
| 6 | 领域词典 — HSE 术语展开提升召回 | 1 (§10.1) | Query "JSA执行" → 命中 "作业安全分析" | ✅ 已实施 |
| 7 | 多轮对话 — 指代消解 + 上下文连续追问 | 1 (§10.2) | 3 轮追问测试 | ✅ 已实施 |
| 8 | 数据血缘 — 实体→文档→答案全链路 | 2 | GET /api/v1/lineage/entity/{id} → trace 完整 | ✅ 已实施 |
| 9 | 数据目录 — 多维统计, 含质量预警 | 2 | GET /api/v1/catalog → 含 domains/feedback/quality | ✅ 已实施 |
| 10 | 格式导出 — JSON/CSV/Neo4j/RDF + 词典/反馈 | 2 | GET /api/v1/export/kg?format=neo4j | ✅ 已实施 |
| 11 | 备份恢复 — tar.gz 含 manifest, 日备 02:00 | 2 | POST /api/v1/system/backup → verify → restore | ✅ 已实施 |
| 12 | 质量监控 — 4 维评分 + Prometheus 告警 | 2 | GET /api/v1/system/quality → overall_score > 0 | ✅ 已实施 |
| 13 | 生命周期 — 7 类数据保留策略 + 自动清理 | 2 | APScheduler 每日 03:00 cleanup | ✅ 已实施 |
| 14 | SSO — OAuth2 完整流程 + JWT 刷新 | 3 | GET /auth/login → redirect → callback → JWT tokens | ✅ 已实施 |
| 15 | 消息 Bot — 飞书 @机器人问答 + 卡片反馈 | 3 | 飞书发消息 → 返回卡片 → 点击👍👎回调 feedback | ✅ 已实施 |
| 16 | Webhook — 10 事件投递 + HMAC 重试 | 3 | POST /webhooks 注册 → 触发事件 → delivery_log 2xx | ✅ 已实施 |
| 17 | 监控 — Grafana Dashboard + 多渠道告警 | 3 | docker-compose.monitoring.yml up, 3000 端口 | ✅ 已实施 |
| 18 | 审计日志 — JSONL 按日, 365 天保留 | 3 | GET /audit → 含敏感操作记录 | ✅ 已实施 |
| 19 | API Key 管理 — Scope 执行 + 限流 + 撤销 | 3 | `read:query` Key → POST /ingest → 403 | ✅ 已实施 |
| 20 | 健康检查 — 5 外部依赖探活 | 3 | GET /health → dependencies 含各服务状态+延迟 | ✅ 已实施 |

#### 7.4.2 Phase 4 验收项

| # | 验收项 | 验证方式 |
|---|--------|---------|
| 21 | 多租户隔离 — 两组织数据不可见 | 创建 orgA+projX 和 orgB+projY，各自索引文档，用不同 token 查询确认隔离 |
| 22 | 容器化 — docker-compose 一键启动 | `docker-compose up -d` → 6 服务 Running → `/health` 返回 healthy |
| 23 | CI/CD — lint→test→build 流水线 | push 到 master → Actions 三阶段全绿 → 镜像推送 registry |
| 24 | 数据持久化 — 容器重启不丢数据 | `docker-compose down && docker-compose up -d` → KG 数据完整 |

#### 7.4.3 性能基线

| 指标 | 目标 | 测试方法 |
|------|------|---------|
| API P95 延迟 (查询) | < 10s | `hey -z 30s -c 5 POST /api/v1/rag/query` |
| Ingest 吞吐 (PDF) | < 5min / 文档 | 上传 10 页标准 PDF，计时 |
| 并发查询 | 10 QPS 不降级 | `hey -c 10` 同时压测 |
| 容器冷启动 | < 30s | `docker-compose up` 到 health OK |
| 磁盘占用 | < 2GB / 100 文档 | `GET /api/v1/system/storage` |

#### 7.4.4 安全扫描清单

- [ ] `git diff --cached | grep -i "api[_-]key\|secret\|token\|password"` 无泄露
- [ ] `.env` 不在 Docker 镜像中 (`.dockerignore` 已排除)
- [ ] API Key 仅创建时返回一次完整值
- [ ] JWT secret ≥ 32 字符 (生产环境覆盖 `JWT_SECRET_KEY`)
- [ ] CORS `allow_origins` 在生产环境锁定为具体域名
- [ ] 审计日志不包含 API Key / Token 明文
- [ ] Docker 镜像非 root 运行 (`USER 1000`)

#### 7.4.5 GraphRAG 正式交付门禁

正式从试点 / MVP 升级为企业正式交付前，必须同时满足以下 **代码化 release gate**，且评测对象统一为主生产链路 `POST /api/v1/rag/query`：

| 指标 | 门槛 | 证据来源 |
|------|------|---------|
| A1 final-context surface ready | `surface_data_coverage > 0` | `metrics_a1_retrieval.json -> surfaces.final_context.surface_data_coverage` |
| A1 final-context recall | `>= 0.35` | `metrics_a1_retrieval.json -> surfaces.final_context.global.recall_macro` |
| A2 keyword coverage | `>= 0.75` | `metrics_a2_faithfulness.json -> global.keyword_coverage_macro` |
| A2 cited-in-retrieved | `>= 0.98` | `metrics_a2_faithfulness.json -> global.cited_in_retrieved_rate_macro` |
| A5 p95 latency | `<= 6000ms` | `metrics_a5_performance.json -> latency_ms.global.p95` |
| A5 p99 latency | `<= 15000ms` | `metrics_a5_performance.json -> latency_ms.global.p99` |

执行方式：

1. 先运行 `run_inference.py` 生成最新 `raw_runs.jsonl`
2. 再运行 `metrics_a1_retrieval.py`、`metrics_a2_faithfulness.py`、`metrics_a5_performance.py`
3. 最后运行 `release_gate.py` 生成 `release_gate_report.json` 与 `release_gate_report.md`

治理规则：

- 若 `final_context` surface 无数据，视为评测证据失效，不得以旧的 `retrieval_node_ids` 或历史报告替代正式放行依据
- 任一门槛未达标，结论必须是 `NO-GO`，只能进入整改或提交明确 waiver，禁止口头放行
- waiver 必须绑定具体风险、负责人、失效时间和补救计划，不能作为长期常态

---

### Phase 4 总 Gate (v1.4 更新)

```
[PASS] 多租户数据隔离生效 (两个组织数据互不可见)
[PASS] docker-compose up 一键启动 6 个服务
[PASS] Nginx 反向代理 + SPA fallback 正常
[PASS] 数据卷持久化 (docker-compose down && up 数据不丢失)
[PASS] CI 流水线包含 lint → test → build → push 四阶段
[PASS] 71 个测试在 CI 环境全绿
[PASS] release_gate.py 对 `/api/v1/rag/query` 最新评测产物给出 GO
[PASS] 全部 24 项验收通过
─────────────────────────────────────────────────────
全部 PASS → 企业就绪，可生产部署
```

---

### Phase 4 完整文件清单

| 模块 | 文件 | 说明 |
|------|------|------|
| §7.1 多租户 | `backend/services/tenant_service.py` | Organization/Project CRUD + 成员管理 |
| §7.1 多租户 | `backend/middleware/tenant_middleware.py` | 租户上下文注入 (X-Project-Id → request.state.tenant) |
| §7.1 多租户 | `backend/routes/tenants.py` | 组织/项目管理端点 (12 endpoints) |
| §7.1 多租户 | `backend/models.py` (扩增) | Organization, Project, OrgMembership, TenantContext |
| §7.2 容器 | `Dockerfile.backend` | 后端 FastAPI 容器 |
| §7.2 容器 | `Dockerfile.frontend` | 前端 Nginx + React 多阶段构建 |
| §7.2 容器 | `docker-compose.yml` (根目录) | 6 服务编排 |
| §7.2 容器 | `deploy/nginx/default.conf` | Nginx SPA + API 反向代理配置 |
| §7.2 容器 | `.dockerignore` | 构建排除规则 |
| §7.2 容器 | `backend/.env` (扩增) | 新增 DEPLOY_MODE, CHROMADB_HOST 等 8 个字段 |
| §7.3 CI/CD | `.github/workflows/ci.yml` | GitHub Actions CI 流水线 |
| §7.3 CI/CD | `.gitlab-ci.yml` (备选) | GitLab CI 流水线 |
| §7.3 CI/CD | `deploy/cd-deploy.sh` | CD 部署脚本 |
| §7.4 验收 | — | 验收矩阵 + 性能基线 + 安全清单 (本文档) |
| **合计** | **14 个新文件** | (8 backend/ infra + 3 deploy + 3 CI/CD) |

---

## 8. 实施路线总图

```
Month 1          Month 2          Month 3          Month 4
═══════════════════════════════════════════════════════════════════

Week 1-2:        Week 3-6:        Week 7-10:        Week 11-14:
┌──────────┐    ┌──────────┐     ┌──────────┐      ┌──────────┐
│ Phase 0  │    │ Phase 1  │     │ Phase 3  │      │ Phase 4  │
│ 基础治理  │    │ 协作闭环  │     │ 生态集成  │      │ 企业就绪  │
│          │    │          │     │          │      │          │
│ 日志     │    │ 反馈系统  │     │ SSO      │      │ 多租户   │
│ 监控     │    │ 实体审核  │     │ 飞书Bot  │      │ Docker   │
│ 认证     │    │ 查询历史  │     │ Webhook  │      │ CI/CD    │
│ KG版本   │    │ 修正回路  │     │ Grafana  │      │ 最终验收  │
└──────────┘    └──────────┘     └──────────┘      └──────────┘
     │               │                │                   │
     │          ┌──────────┐          │                   │
     │          │ Phase 2  │          │                   │
     │          │ 数据资产  │          │                   │
     │          │          │          │                   │
     │          │ 数据血缘  │          │                   │
     │          │ 资产目录  │          │                   │
     │          │ 格式导出  │          │                   │
     │          │ 备份恢复  │          │                   │
     │          └──────────┘          │                   │
     │               │                │                   │
     └───────────────┴────────────────┴───────────────────┘
                     │
                     ▼
              ┌──────────────┐
              │ Enterprise   │
              │ GraphRAG     │
              │ Platform v2.0│
              └──────────────┘

实施状态:
  Phase 0 ✅ 已完成 (2026-05)
  Phase 1 ✅ 已完成 (2026-05)
  Phase 2 ✅ 已完成 (2026-06)
  Phase 3 ✅ 已完成 (2026-06)
  Phase 4 📋 蓝图完成 (2026-06)

并行策略:
  Phase 1 (协作闭环) 与 Phase 2 (数据资产) 可并行 → Phase 3 在 1+2 完成后开始
  Phase 0 完成前任何 Phase 不得开工
  Phase 4 部署与 Engine-Vue 集成可并行推进
```

### 8.1 Phase 依赖矩阵

| | Phase 0 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|---------|---------|---------|---------|---------|
| **硬依赖** | — | Phase 0 | Phase 0 | Phase 0 | Phase 1+2+3 |
| **软依赖** | — | — | — | Phase 2 | Phase 3 (SSO对多租户有价值) |
| **可并行** | — | Phase 2 | Phase 1 | — | Engine-Vue Stage 1 |
| **状态** | ✅ | ✅ | ✅ | ✅ | 📋 |

---

## 9. Engine-Vue 集成专项

> **背景**：Engine-Vue (若依 v3.9.1) 是中油吉林化建工程有限公司的数字化平台，核心业务为 HSE（健康/安全/环境）管理系统。
> GraphRAG 作为 AI 知识底座嵌入 Engine-Vue，提供 HSE 文档智能问答 + 报表数据分析。
>
> **策略**：分两阶段 — 先轻量嵌入验证价值，再深度整合打通全链路。

### 9.1 Engine-Vue 现状速览

```
Engine-Vue (若依 v3.9.1)
├── 后端: Spring Boot 4.x + MyBatis + MySQL + Redis + JWT
│   ├── Engine-admin/     → Controller 层 (含 HseController)
│   ├── Engine-system/    → Service + Domain 层
│   ├── Engine-framework/ → Security / Filter / Config
│   └── Engine-quartz/    → 定时任务
│
├── 前端: Vue 2.6 + Element UI + Vuex + Vue Router
│   ├── views/hse/        → HSE 业务页面
│   │   ├── qhse/         → QHSE 月报 (10张报表)
│   │   ├── supervision/  → 监督月报 (10张报表)
│   │   ├── branch/       → 分公司资料盒
│   │   ├── professional/ → 专业资料盒
│   │   ├── secure/       → 安全资料盒
│   │   └── task/         → 任务管理
│   └── components/       → HseModulePage, HseBoxManager, HseReportSubmit
│
└── 数据库: MySQL (ENGINE-vue)
    ├── sys_*             → 系统表 (用户/角色/菜单/部门)
    ├── hse_file          → HSE 文件
    ├── hse_file_version  → 文件版本管理
    ├── hse_folder        → 多级目录
    ├── hse_box_template  → 20卷标准资料盒模板
    ├── hse_report_owner  → 报表负责人配置
    ├── hse_report_task   → 报表任务
    └── hse_project_dept  → 项目部
```

**HSE 20 卷资料盒体系**：工作规划 / 目标责任 / 组织机构 / 法规标准 / 制度建设 / 教育培训 / 危险源管理 / 方案措施 / 设备设施 / 职业健康 / 劳动防护 / 应急管理 / 检查考核 / 隐患排查 / 事故管理 / 安全投入 / 相关方管理 / 信息报送 / 专项活动 / 文件归档

### 9.2 Stage 1: 轻量嵌入（2 周）

> **目标**：在 Engine-Vue HSE 页面右下角挂载 AI 助手浮窗，可问答已索引的 HSE 文档。
> 零侵入现有 Engine-Vue 代码，通过独立 JS 打包注入。

**架构**：

```
Engine-Vue (现有)                          GraphRAG (新增)
─────────────────                          ────────────────

engine-ui/
  └── public/
        └── index.html
              │
              └── <script src="http://localhost:8000/static/chat-widget.js">
                     │
                     ▼
              ┌──────────────────────┐
              │  AI 助手浮窗 (Shadow DOM)  │
              │  ┌──────────────────┐│
              │  │ 💬 HSE 知识问答    ││
              │  │                  ││
              │  │ 用户: 高空作业    ││
              │  │ 安全带使用规范?   ││
              │  │                  ││
              │  │ AI: 根据HSE制度  ││
              │  │ 汇编第3章...     ││
              │  │ [👍] [👎]       ││
              │  └──────────────────┘│
              └──────────────────────┘
                     │
                     ▼ POST /api/v1/rag/query
              ┌──────────────────────┐
              │  GraphRAG Backend    │
              │  (localhost:8000)    │
              │                     │
              │  KG: HSE法规标准     │
              │  + 安全操作规程      │
              │  + 应急预案汇编      │
              └──────────────────────┘
```

**交付物**：

| 文件 | 说明 |
|------|------|
| `frontend/public/chat-widget.js` | 独立打包的聊天浮窗，零依赖（纯 JS + CSS），Shadow DOM 隔离样式 |
| `frontend/src/components/ChatWidget.tsx` | React 版聊天组件（GraphRAG 自身前端用） |
| `backend/routes/static.py` (新建) | 静态资源服务，`GET /static/chat-widget.js` |

**chat-widget.js 核心接口**：

```javascript
// Engine-Vue 嵌入方式 — 一行 <script> 即可
// engine-ui/public/index.html 底部加入:
// <script src="http://localhost:8000/static/chat-widget.js"></script>

(function() {
  // Shadow DOM 隔离，不污染 Engine-Vue 的 Element UI 样式
  const host = document.createElement('div');
  document.body.appendChild(host);
  const shadow = host.attachShadow({ mode: 'open' });

  // 浮窗 UI (纯 DOM 操作，无框架依赖)
  // - 右下角 48px 圆形按钮，点击展开 380×520 聊天面板
  // - 输入框 + 发送按钮 + 加载动画 + Markdown 渲染
  // - 答案下方 👍/👎 反馈按钮
  // - 支持配置: data-endpoint, data-title, data-theme

  // API 调用
  async function ask(question) {
    const res = await fetch(config.endpoint + '/api/v1/rag/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: question }),
    });
    return res.json();
  }
})();
```

**HSE 文档初始化流程**（一次性）：

```bash
# 1. 将 Engine-Vue 的 HSE 文档导出为 PDF/Word 放入目录
# 2. 通过 GraphRAG ingest API 批量索引
for f in hse_docs/*.pdf; do
  curl -X POST http://localhost:8000/api/v1/ingest \
    -F "file=@$f" \
    -F "language=zh"
done

# 3. 验证 KG 构建
curl http://localhost:8000/api/v1/graph/all | jq '.stats'
# 预期: nodes > 500, edges > 2000 (HSE领域法规条文关联密)
```

**Gate 标准 (Stage 1)**：
- [ ] `chat-widget.js` 通过 `<script>` 标签嵌入 Engine-Vue 页面
- [ ] 浮窗可展开/收起，样式不冲突 Element UI
- [ ] 输入问题 → 返回答案 + 溯源引用
- [ ] 至少 3 份 HSE 文档已索引并可通过浮窗问答

---

### 9.3 Stage 2: 深度整合（4 周）

> **目标**：GraphRAG 成为 Engine-Vue 的原生功能模块，复用若依的认证/权限/文件体系。

**架构**：

```
┌─────────────────────────────────────────────────────────────────┐
│                    Engine-Vue (若依)                              │
│                                                                  │
│  engine-ui/                          Engine-admin/               │
│  ┌──────────────────────┐           ┌──────────────────────┐    │
│  │  views/hse/ai/       │           │  HseController        │    │
│  │  ├── index.vue       │           │                       │    │
│  │  ├── chat.vue        │  HTTP     │  /hse/ai/query        │    │
│  │  └── knowledge.vue   │──────────►│  /hse/ai/ingest       │    │
│  │                      │  JWT      │  /hse/ai/feedback     │    │
│  └──────────────────────┘           └───────────┬──────────┘    │
│                                                  │               │
│                                        内部转发 (RestTemplate)   │
│                                                  │               │
│                                                  ▼               │
│                                        ┌──────────────────────┐ │
│                                        │  GraphRAG Backend    │ │
│                                        │  (localhost:8000)    │ │
│                                        │                      │ │
│                                        │  /api/v1/rag/query   │ │
│                                        │  /api/v1/ingest      │ │
│                                        │  /api/v1/feedback    │ │
│                                        └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**引擎层变更 (Engine-Vue 后端)**：

| 变更 | 文件 | 说明 |
|------|------|------|
| **AI 代理 Controller** | `Engine-admin/.../controller/hse/HseAiController.java` | `/hse/ai/query`, `/hse/ai/ingest`, `/hse/ai/feedback` — 转发到 GraphRAG |
| **RestTemplate Bean** | `Engine-framework/.../config/AiClientConfig.java` | 配置 GraphRAG 连接 (baseUrl, timeout, apiKey) |
| **文件自动索引** | `Engine-system/.../service/impl/HseFileServiceImpl.java` | 文件上传成功 → 异步调 GraphRAG ingest API |
| **权限标识** | 数据库菜单表 | 新增 `hse:ai:query`, `hse:ai:ingest`, `hse:ai:admin` |

**AI 代理 Controller 参考实现**：

```java
// HseAiController.java — Engine-Vue 后端 AI 代理
@RestController
@RequestMapping("/hse/ai")
public class HseAiController extends BaseController {

    @Autowired
    private RestTemplate graphragClient;  // baseUrl = http://localhost:8000/api/v1

    @PreAuthorize("@ss.hasPermi('hse:ai:query')")
    @PostMapping("/query")
    public AjaxResult aiQuery(@RequestBody Map<String, Object> body) {
        // 注入当前用户/部门上下文
        body.put("user_id", SecurityUtils.getUserId());
        body.put("dept_id", SecurityUtils.getDeptId());
        body.put("roles", SecurityUtils.getRoles());

        // 转发到 GraphRAG
        ResponseEntity<Map> res = graphragClient.postForEntity(
            "/rag/query", body, Map.class);

        return success(res.getBody());
    }

    @PreAuthorize("@ss.hasPermi('hse:ai:ingest')")
    @PostMapping("/ingest")
    public AjaxResult aiIngest(@RequestParam("fileId") Long fileId) {
        // 从 hse_file 表获取文件路径
        HseFile file = hseService.getFileById(fileId);
        // 构造 multipart 请求转发到 GraphRAG ingest
        // 返回 task_id 用于轮询进度
        return success(Map.of("task_id", taskId));
    }
}
```

**HSE 文件上传后自动索引**（关键改造）：

```java
// HseFileServiceImpl.java — 修改 uploadFile 方法
@Override
public Long uploadFile(MultipartFile file, HseFile hseFile) {
    // ... 原有文件存储逻辑 ...

    // 新增: 异步触发 AI 索引
    CompletableFuture.runAsync(() -> {
        try {
            aiClient.ingestDocument(savedFileId);
        } catch (Exception e) {
            log.warn("AI索引触发失败, fileId={}, error={}", savedFileId, e.getMessage());
        }
    });

    return savedFileId;
}
```

**前端变更 (Engine-Vue engine-ui)**：

| 变更 | 文件 | 说明 |
|------|------|------|
| **AI 助手页面** | `views/hse/ai/index.vue` | 完整 RAG 问答界面（替代 Stage 1 浮窗） |
| **侧边栏菜单** | `views/layout/components/Sidebar/SidebarItem.vue` | HSE 菜单下加 "AI助手" 子菜单项 |
| **API 模块** | `api/hse/ai.js` | `aiQuery()`, `aiFeedback()`, `aiHistory()` |
| **知识库管理** | `views/hse/ai/knowledge.vue` | 已索引文档列表 + 实体统计 |

**Gate 标准 (Stage 2)**：
- [ ] Engine-Vue 左侧菜单出现 "HSE → AI助手"
- [ ] 页面内可问答，答案溯源到原始 HSE 文件
- [ ] HSE 文件上传后 60s 内可被 AI 检索到
- [ ] 问答权限与若依角色权限一致（如安全员可见事故报告，普通员工不可）
- [ ] 反馈数据回写到 Engine-Vue 数据库

---

### 9.4 对接价值量化预估

基于中油吉林化建 HSE 业务特征：

| 场景 | 传统方式 | AI 辅助后 | 提效 |
|------|---------|-----------|------|
| 查找安全操作规程 | 翻阅 20 卷资料盒 | 自然语言提问，秒级定位 | **10×** |
| 报表数据对比 | 打开多张 Excel 逐项对比 | "今年Q1与去年Q1安全事故率对比" | **20×** |
| 新员工安全培训 | 逐份阅读制度文件 | "我需要了解高空作业的全部安全要求" | **5×** |
| 合规审查 | 人工逐条核对法规 | "这个项目的安全措施是否满足法规要求" | **8×** |

---

### 9.5 知识库维护策略

```
文档生命周期管理:

Engine-Vue HSE 文件                    GraphRAG KG
─────────────────                      ────────────
文件上传 (hse_file.insert)
    │                                       │
    ├── 自动触发 ──────────────────────────►  ingest → KG v1
    │                                       │
文件更新 (hse_file_version.insert)
    │                                       │
    ├── 自动触发 ──────────────────────────►  re-ingest → KG v2
    │                                       │
文件删除 (hse_file.delete)
    │                                       │
    ├── 自动触发 ──────────────────────────►  delete_document
    │                                       │
    └── 知识库与文件库始终同步
```

### 9.6 Phase 4 融合策略 (v1.4 新增)

> **v1.4 变更**：Engine-Vue 集成与 Phase 4 多租户/容器化天然衔接。Stage 2 深度整合时，GraphRAG 将作为独立容器运行在 Engine-Vue 同网段，通过 API Key + JWT 双重认证通信。

**多租户与 Engine-Vue 机构对应**：

```
Engine-Vue                          GraphRAG Phase 4
──────────                          ────────────────
sys_dept (部门)         ──映射──►   Organization
   │                                   │
   └── hse_project_dept (项目部) ──►   Project
                                        │
用户 sys_user            ──映射──►   User (OAuth2 sub)
角色 sys_role            ──映射──►   org_admin / editor / viewer
数据权限 sys_data_scope  ──映射──►   X-Project-Id Header
```

**容器部署拓扑 (Stage 2)**：

```
┌──────────────────────────────────────────────────────┐
│  目标服务器 (CentOS / Ubuntu)                         │
│                                                      │
│  ┌─────────────────────┐  ┌────────────────────────┐ │
│  │ Engine-Vue           │  │ GraphRAG               │ │
│  │ (若依 v3.9.1)        │  │ (Phase 4 容器)          │ │
│  │                      │  │                        │ │
│  │ Tomcat :8080         │  │ backend :8000          │ │
│  │ MySQL :3306           │  │ frontend :80 (Nginx)   │ │
│  │ Redis :6379           │  │ chromadb :8001         │ │
│  └──────────────────────┘  └────────────────────────┘ │
│            │                         │                │
│            └──── 同网段 HTTP ────────┘                │
│           HseAiController → RestTemplate             │
│           认证: X-API-Key Header                      │
└──────────────────────────────────────────────────────┘
```

**Engine-Vue 侧栏菜单扩展**：

```
HSE 管理系统
├── 📋 资料盒管理
├── 📊 月报管理
├── 📁 文件管理
├── 🤖 AI 助手          ← Phase 4 / Stage 2 新增
│   ├── 知识问答         ← /hse/ai/index
│   ├── 知识库管理       ← /hse/ai/knowledge
│   └── 索引任务         ← /hse/ai/tasks
└── ⚙️ 系统管理
```

**权限标识 (新增到 sys_menu 表)**：

```sql
INSERT INTO sys_menu (menu_name, parent_id, order_num, path, perms, menu_type, icon)
VALUES
  ('AI助手',    0, 5, 'ai',        '',            'M', 'robot'),
  ('知识问答',   1, 1, 'index',     'hse:ai:query',    'C', 'chat'),
  ('知识库管理', 1, 2, 'knowledge', 'hse:ai:catalog',  'C', 'database'),
  ('索引任务',   1, 3, 'tasks',     'hse:ai:ingest',   'C', 'upload');
```

---

## 10. 检索增强模块（蓝图补充 v1.1）

> **背景**：Phase 1 协作闭环依赖两个检索增强能力——领域词典提升 HSE 术语匹配精度，
> 多轮对话支持上下文连续问答。此二模块为蓝图 v1.0 未覆盖的新增设计。
>
> **日期**：2026-06-09

### 10.1 领域词典

2026-10-12搜索约束：关键词与术语、同义词、英文缩写、描述在比较时统一大小写归一；持久化及展示保留原字符串。英文缩写JSA可由jsa/JSA检索，不能只lower关键词而漏归一候选字段。

**问题**：HSE 领域术语（JSA、LOTO、动火作业、受限空间）在通用 Embedding 中向量表示弱，
检索容易漏。查询"高处作业安全规范"可能漏掉标题为"高空作业管理制度"的文档。

**设计**：

```
领域词典三层结构:

┌─────────────────────────────────────────────┐
│  Layer 1: 同义词映射 (Query Expansion)       │
│  "高处作业" → ["高处作业", "高空作业", "登高作业"]  │
│  查询时自动展开，提升召回                       │
├─────────────────────────────────────────────┤
│  Layer 2: 缩写展开 (Abbreviation)            │
│  "JSA" → "作业安全分析 (Job Safety Analysis)" │
│  查询时替换为标准术语                          │
├─────────────────────────────────────────────┤
│  Layer 3: 关联术语 (Term Association)         │
│  "动火作业" → ["消防器材", "可燃气体检测",        │
│                 "动火许可证", "监护人"]         │
│  不在查询时展开，但注入 Prompt 作为上下文提示     │
└─────────────────────────────────────────────┘
```

**数据模型**：

```python
class DomainTerm(BaseModel):
    term: str                     # 标准术语
    synonyms: list[str] = []      # 同义词
    abbreviations: list[str] = [] # 缩写/英文
    related: list[str] = []       # 关联术语
    entity_type: str | None = None  # 对应 KG 实体类型
    category: str                 # safety | equipment | process | regulation
    description: str = ""         # 简短定义
```

**种子数据（HSE 4 类 ~80 条）**：

```
安全作业类:
  动火作业: 同义[热工作业] 缩写[Hot Work] 关联[消防器材, 可燃气体检测, 动火许可证, 监护人]
  高处作业: 同义[高空作业, 登高作业] 缩写[] 关联[安全带, 脚手架, 安全网, 坠落防护]
  受限空间: 同义[有限空间, 密闭空间] 缩写[] 关联[气体检测, 通风, 救援预案, 作业许可]
  临时用电: 同义[施工用电, 临时供电] 缩写[] 关联[配电箱, 漏电保护, 接地保护]
  JSA: 同义[工作安全分析, 作业安全分析] 缩写[Job Safety Analysis] 关联[风险辨识, 控制措施]
  LOTO: 同义[上锁挂牌, 能量隔离] 缩写[Lockout/Tagout] 关联[隔离确认, 试车确认]
  ...

设备设施类:
  起重机: 同义[行车, 天车] 关联[限位器, 钢丝绳, 吊钩, 荷载试验]
  压力容器: 同义[储气罐, 压缩罐] 关联[安全阀, 压力表, 定期检验]
  ...

防护用品类(PPE):
  安全帽: 同义[头部防护] 关联[帽衬, 帽壳, 有效期]
  安全带: 同义[坠落悬挂安全带, 全身式安全带] 关联[缓冲器, 挂点, 高挂低用]
  ...

制度法规类:
  安全生产法: 同义[] 缩写[] 关联[主要负责人职责, 三管三必须, 违法处罚]
  HSE管理体系: 同义[安全管理体系, 职业健康安全体系] 关联[方针目标, 危险源辨识, 合规性评价]
  ...
```

**检索集成点**：

```
Query 预处理 (现有 retrieval.py §4.1):
  原始查询: "JSA执行情况检查"
     │
     ├─ 缩写展开: "JSA" → "作业安全分析 (Job Safety Analysis)"
     ├─ 同义展开: "检查" → ["检查", "审核", "查验"]
     │
     ▼
  改写查询: "作业安全分析 执行情况 检查 审核"
     │
     ▼
  语义关联注入 (Prompt 增强):
  "注意: JSA (作业安全分析) 的相关概念包括: 风险辨识、控制措施、作业许可"
```

**API**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/domain-dict` | 列出所有领域术语 |
| `GET` | `/api/v1/domain-dict/search?q=动火` | 搜索 |
| `POST` | `/api/v1/domain-dict` | 新增术语 |
| `PUT` | `/api/v1/domain-dict/{id}` | 更新 |
| `DELETE` | `/api/v1/domain-dict/{id}` | 删除 |
| `POST` | `/api/v1/domain-dict/import` | 批量导入 YAML |

**文件**：

| 文件 | 说明 |
|------|------|
| `backend/domain_dict.py` | DomainDict 类：加载 YAML → 内存索引 → Query 改写 |
| `backend/config/domain_dict.yaml` | 种子数据 ~80 条 HSE 术语 |
| `backend/routes/domain_dict.py` | CRUD 端点 |

---

### 10.2 多轮对话

**问题**：当前每次查询是无状态的。用户无法追问"那第二条呢？"或"对比一下第一条和第三条"，
因为没有会话上下文。

**设计**：

```
多轮对话流程:

第 1 轮: "高处作业需要哪些安全措施"
  session_id = new UUID
  context = []
  retrieval 正常执行 → answer_1 + sources_1
  存储: Turn(1, q=原始问题, a=answer_1, sources=sources_1)

第 2 轮: "里面提到的安全带标准是什么"
  session_id = same
  context = [Turn(1)]
  │
  ├─ 指代消解 (LLM):
  │   输入: History + 当前问题
  │   输出: "高处作业安全措施中提到的安全带标准是什么"
  │
  ├─ retrieval 用改写后查询执行
  │
  └─ 存储: Turn(2, q=原始问题, rewritten=改写查询, a=answer_2, sources=sources_2)

第 3 轮: "第一条和第二条对比一下"
  session_id = same
  context = [Turn(1), Turn(2)]
  │
  ├─ 指代消解: "第一条(高处作业安全措施)和第二条(安全带标准)对比"
  ├─ Prompt 注入前两轮摘要:
  │   "之前你问了关于高处作业安全措施和安全带标准的问题，答案如下摘要..."
  └─ 存储: Turn(3, ...)
```

**数据模型**：

```python
class ConversationTurn(BaseModel):
    turn_id: int
    question: str
    rewritten_query: str | None = None  # 指代消解后
    answer: str
    sources: list[str] = []
    created_at: str

class Conversation(BaseModel):
    session_id: str
    title: str = ""                    # 自动生成: 首轮问题截断
    turns: list[ConversationTurn] = []
    created_at: str
    last_active: str
    user_id: str | None = None         # Phase 3 启用
    is_active: bool = True
```

**会话生命周期**：

```
创建: 首次查询不带 session_id → 自动创建
续接: 后续查询带 session_id → 追加 turn
超时: 30 分钟无活动 → is_active = False
清理: 超过 7 天的非活跃会话 → 自动删除
```

**检索集成（`retrieval.py` 修改点）**：

```python
async def preprocess_query(
    query: str,
    conversation: Conversation | None = None,
    domain_dict: DomainDict | None = None,
) -> str:
    """Query preprocessing with domain dict + conversation context."""
    # Step 1: Domain dict expansion
    if domain_dict:
        query = domain_dict.expand(query)  # 同义+缩写展开

    # Step 2: Coreference resolution (if conversation exists)
    if conversation and len(conversation.turns) > 0:
        query = await _resolve_coreference(query, conversation)

    return query
```

**API 变更**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/rag/query` | 新增可选字段 `session_id: str \| None` |
| `GET` | `/api/v1/conversations` | 列出所有会话（分页） |
| `GET` | `/api/v1/conversations/{id}` | 会话详情（含全部轮次） |
| `DELETE` | `/api/v1/conversations/{id}` | 删除会话 |
| `GET` | `/api/v1/conversations/{id}/export` | 导出为 Markdown |

**前端变更**：

| 组件 | 变更 |
|------|------|
| `QueryPage.tsx` | 左侧会话列表 + 右侧对话区 + 输入框支持连续追问 |
| `ConversationList.tsx` (新建) | 会话列表组件，显示标题/时间/轮次数 |

**文件**：

| 文件 | 说明 |
|------|------|
| `backend/conversation.py` | ConversationManager：创建/追加/查询/超时清理 |
| `backend/services/query_history.py` | 查询记录持久化（Phase 1.3 共用） |

---

### 10.3 三模块集成总览

```
                     用户查询
                        │
                        ▼
              ┌──────────────────┐
              │  Query 预处理     │
              │                  │
              │  1. 领域词典展开  │ ← domain_dict.yaml
              │  2. 指代消解      │ ← 读取会话上下文
              │  3. 意图分类      │ ← 现有
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  多路检索         │ ← 现有 retrieval.py
              │  (改写后查询)     │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  Prompt 构建      │
              │  + 关联术语提示   │ ← 领域词典 Layer 3
              │  + 对话历史摘要   │ ← 会话上下文
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  LLM 生成         │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  答案 + 溯源       │
              │  + 反馈按钮       │ ← Phase 1.1
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  持久化            │
              │  → 查询历史 (Phase 1.3)
              │  → 会话 Turn       │
              │  → 反馈数据 (Phase 1.1)
              └──────────────────┘
```

### 10.4 依赖关系

```
领域词典 ──────────────── 独立，无上游依赖
多轮对话 ── 依赖 ── 查询历史持久化 (Phase 1.3)
反馈闭环 ── 依赖 ── 多轮对话会话管理
知识修正 ── 依赖 ── 反馈数据 + kg_store (Phase 0)
```

### 10.5 实施序列

```
阶段 A (先做): 领域词典
  backend/domain_dict.py
  backend/config/domain_dict.yaml
  backend/routes/domain_dict.py
  检索管道集成: retrieval.py preprocess_query

阶段 B (再): 多轮对话
  backend/conversation.py
  retrieval.py 指代消解
  prompt_builder.py 历史摘要注入
  前端 QueryPage 会话 UI

阶段 C (后): 反馈闭环
  backend/routes/feedback.py (Phase 1.1-1.4)
  前端反馈 UI
  知识修正回路
```

---

## 附录 A: 新增 API 端点汇总

| Phase | 方法 | 路径 | 说明 |
|-------|------|------|------|
| 0 | `GET` | `/metrics` | Prometheus 指标 |
| 0 | `GET` | `/api/v1/documents/{id}/versions` | KG 版本列表 |
| 0 | `POST` | `/api/v1/documents/{id}/versions/{v}/activate` | 切换活跃版本 |
| 1 | `POST` | `/api/v1/feedback` | 提交反馈 |
| 1 | `GET` | `/api/v1/feedback` | 反馈列表 |
| 1 | `GET` | `/api/v1/feedback/stats` | 反馈统计 |
| 1 | `PATCH` | `/api/v1/feedback/{id}` | 更新反馈状态 |
| 1 | `GET` | `/api/v1/entities/review` | 待审核实体 |
| 1 | `POST` | `/api/v1/entities/{id}/approve` | 审核通过 |
| 1 | `POST` | `/api/v1/entities/{id}/reject` | 驳回实体 |
| 1 | `PUT` | `/api/v1/entities/{id}` | 修正实体 |
| 1 | `POST` | `/api/v1/entities` | 手动创建实体 |
| 1 | `DELETE` | `/api/v1/entities/{id}` | 删除实体 |
| 1 | `PUT` | `/api/v1/edges/{id}` | 修正关系 |
| 1 | `POST` | `/api/v1/documents/{id}/reingest` | 重新索引 |
| 1 | `GET` | `/api/v1/queries/history` | 查询历史 |
| 1 | `GET` | `/api/v1/queries/{id}` | 查询详情 |
| 2 | `GET` | `/api/v1/lineage/entity/{id}` | 实体血缘 |
| 2 | `GET` | `/api/v1/lineage/answer/{id}` | 答案血缘 |
| 2 | `GET` | `/api/v1/catalog` | 数据资产总览 |
| 2 | `GET` | `/api/v1/catalog/entities` | 实体目录 |
| 2 | `GET` | `/api/v1/export/kg?format=json\|csv\|rdf\|neo4j` | 格式导出 |
| 2 | `POST` | `/api/v1/system/backup` | 即时备份 |
| 2 | `GET` | `/api/v1/system/backups` | 备份列表 |
| 2 | `POST` | `/api/v1/system/restore` | 恢复备份 |
| 2 | `POST` | `/api/v1/system/backup/verify/{id}` | 备份完整性验证 |
| 2 | `GET` | `/api/v1/catalog/summary` | 资产总览轻量版 |
| 2 | `GET` | `/api/v1/catalog/trends?days=30` | 趋势数据 |
| 2 | `GET` | `/api/v1/catalog/low-quality` | 低质量数据清单 |
| 2 | `GET` | `/api/v1/lineage/feedback/{id}` | 反馈→答案血缘 |
| 2 | `GET` | `/api/v1/lineage/conversation/{id}` | 会话维度血缘 |
| 2 | `GET` | `/api/v1/lineage/term/{term}` | 领域术语使用追踪 |
| 2 | `GET` | `/api/v1/lineage/export?entity_id=` | DOT 图导出 |
| 2 | `GET` | `/api/v1/export/domain-dict?format=` | 词典导出 |
| 2 | `GET` | `/api/v1/export/feedback?format=` | 反馈导出 |
| 2 | `GET` | `/api/v1/export/conversations?format=zip` | 会话批量导出 |
| 2 | `POST` | `/api/v1/system/cleanup` | 触发全局清理 |
| 2 | `GET` | `/api/v1/system/cleanup/preview` | 清理预览 dry-run |
| 2 | `GET` | `/api/v1/system/storage` | 磁盘使用统计 |
| 3 | `GET` | `/api/v1/auth/login` | OAuth2 登录 |
| 3 | `GET` | `/api/v1/auth/callback` | OAuth2 回调 |
| 3 | `POST` | `/api/v1/auth/refresh` | 刷新 JWT |
| 3 | `GET` | `/api/v1/auth/me` | 当前用户 |
| 3 | `POST` | `/api/v1/auth/logout` | 登出 |
| 3 | `GET` | `/api/v1/users` | 用户列表 (admin) |
| 3 | `PUT` | `/api/v1/users/{id}/roles` | 修改角色 (admin) |
| 3 | `DELETE` | `/api/v1/users/{id}` | 禁用用户 (admin) |
| 3 | `POST` | `/api/v1/bot/feishu` | 飞书 Bot 回调 |
| 3 | `PUT` | `/api/v1/bot/config/{id}` | 更新 Bot 配置 |
| 3 | `POST` | `/api/v1/bot/config/{id}/test` | 测试 Bot 消息 |
| 3 | `POST` | `/api/v1/webhooks` | 注册 Webhook |
| 3 | `GET` | `/api/v1/webhooks` | Webhook 列表 |
| 3 | `GET` | `/api/v1/webhooks/{id}` | Webhook 详情 |
| 3 | `PUT` | `/api/v1/webhooks/{id}` | 更新 Webhook |
| 3 | `DELETE` | `/api/v1/webhooks/{id}` | 删除 Webhook |
| 3 | `POST` | `/api/v1/webhooks/{id}/test` | 测试事件 |
| 3 | `GET` | `/api/v1/webhooks/{id}/deliveries` | 投递历史 |
| 3 | `POST` | `/api/v1/api-keys` | 创建 API Key |
| 3 | `GET` | `/api/v1/api-keys` | API Key 列表 |
| 3 | `GET` | `/api/v1/api-keys/{id}` | Key 元数据 |
| 3 | `POST` | `/api/v1/api-keys/{id}/revoke` | 撤销 Key |
| 3 | `POST` | `/api/v1/api-keys/{id}/rotate` | 轮换 Key |
| 3 | `GET` | `/api/v1/audit?event=&user_id=` | 审计事件查询 |
| 3 | `GET` | `/api/v1/audit/export` | 导出审计日志 |
| §10.1 | `GET` | `/api/v1/domain-dict` | 领域词典列表 |
| §10.1 | `GET` | `/api/v1/domain-dict/search?q=` | 词典搜索 |
| §10.1 | `POST` | `/api/v1/domain-dict` | 新增术语 |
| §10.1 | `PUT` | `/api/v1/domain-dict/{id}` | 更新术语 |
| §10.1 | `DELETE` | `/api/v1/domain-dict/{id}` | 删除术语 |
| §10.1 | `POST` | `/api/v1/domain-dict/import` | 批量导入 |
| §10.2 | `GET` | `/api/v1/conversations` | 会话列表 |
| §10.2 | `GET` | `/api/v1/conversations/{id}` | 会话详情 |
| §10.2 | `DELETE` | `/api/v1/conversations/{id}` | 删除会话 |
| §10.2 | `GET` | `/api/v1/conversations/{id}/export` | 导出会话 |
| 4 | `POST` | `/api/v1/orgs` | 创建组织 (admin) |
| 4 | `GET` | `/api/v1/orgs` | 用户所属组织列表 |
| 4 | `GET` | `/api/v1/orgs/{org_id}` | 组织详情 |
| 4 | `PUT` | `/api/v1/orgs/{org_id}` | 更新组织配置 |
| 4 | `POST` | `/api/v1/orgs/{org_id}/projects` | 创建项目 |
| 4 | `GET` | `/api/v1/orgs/{org_id}/projects` | 项目列表 |
| 4 | `PUT` | `/api/v1/orgs/{org_id}/projects/{project_id}` | 更新项目 |
| 4 | `POST` | `/api/v1/orgs/{org_id}/projects/{project_id}/archive` | 归档项目 |
| 4 | `POST` | `/api/v1/orgs/{org_id}/members` | 邀请成员 |
| 4 | `GET` | `/api/v1/orgs/{org_id}/members` | 成员列表 |
| 4 | `PUT` | `/api/v1/orgs/{org_id}/members/{user_id}/role` | 修改成员角色 |
| 4 | `DELETE` | `/api/v1/orgs/{org_id}/members/{user_id}` | 移除成员 |
| — | — | — | — |
| **合计** | | **94 个新增端点** (现有 10 个 → 共 104 个) |

---

## 附录 B: 新增前端页面

| Phase | 页面 | 路由 | 说明 |
|-------|------|------|------|
| 1 | `FeedbackPage` | `/feedback` | 反馈管理看板 |
| 1 | `EntityReviewPage` | `/entities/review` | 实体审核界面 |
| 1 | `QueryHistoryPanel` | (QueryPage 内嵌) | 查询历史侧边栏 |
| 2 | `CatalogPage` | `/catalog` | 数据资产看板 |
| 2 | `LineageGraph` | (EntityDetailPanel 内嵌) | 血缘链路 DAG 图 |
| 3 | `LoginPage` | `/login` | SSO 登录页面 |
| 3 | `AuthGuard` | (路由守卫) | 未登录重定向 |
| 3 | `WebhookSettingsPage` | `/settings/webhooks` | Webhook 管理 |
| 3 | `ApiKeySettingsPage` | `/settings/api-keys` | API Key 管理 |
| 3 | `AuditLogPage` | `/admin/audit` | 审计日志查询 |
| 4 | `OrgSettingsPage` | `/settings/org` | 组织/项目设置 |
| 4 | `AdminDashboard` | `/admin` | 管理总览 |
| 4 | `ProjectSelector` | (AppShell 内嵌) | 项目切换下拉选择器 |
| 4 | `MemberManagementPage` | `/settings/org/members` | 成员与角色管理 |
| §10.1 | `DomainDictPage` | `/domain-dict` | 领域词典管理 |
| §10.2 | `ConversationList` | (QueryPage 内嵌) | 会话列表 + 对话区 |
| 2 | `QualityDashboard` | `/quality` | 数据质量看板 |
| 2 | `CatalogPage` | `/catalog` | 数据资产看板 (增强版) |
| — | — | — | — |
| **合计** | | **16 个新增页面** (现有 6 个 → 共 22 个) |

---

## 附录 C: 新增后端模块

| Phase | 模块 | 文件 | 说明 |
|-------|------|------|------|
| 0 | 日志 | `backend/logging_config.py` | structlog 结构化日志 |
| 0 | 指标 | `backend/metrics.py` | Prometheus metrics |
| 0 | 认证 | `backend/auth.py` | API Key / JWT 认证中间件 |
| 0 | KG 版本 | `backend/kg_store.py` | 版本管理 |
| 1 | 反馈 | `backend/routes/feedback.py` | 反馈端点 |
| 1 | 反馈存储 | `backend/services/feedback_store.py` | 反馈持久化 |
| 1 | 查询历史 | `backend/services/query_history.py` | 查询记录存储 |
| 2 | 血缘 | `backend/services/lineage_store.py` | 血缘追踪 |
| 2 | 血缘 | `backend/routes/lineage.py` | 血缘查询端点 |
| 2 | 导出 | `backend/services/kg_exporter.py` | KG 格式导出 |
| 2 | 导出 | `backend/routes/export.py` | 导出端点 |
| 2 | 备份 | `backend/services/backup.py` | 备份/恢复逻辑 |
| 3 | SSO 认证 | `backend/services/auth_service.py` | OAuth2/OIDC + JWT 签发 |
| 3 | JWT 中间件 | `backend/middleware/jwt_middleware.py` | JWT 验证中间件 |
| 3 | 飞书 Bot SDK | `backend/services/feishu_client.py` | 飞书 SDK 封装 (token/消息/卡片) |
| 3 | Bot 处理 | `backend/services/bot_handler.py` | 消息路由 + RAG 调用 + 回复格式化 |
| 3 | 卡片模板 | `backend/services/card_builder.py` | 多平台消息卡片模板 |
| 3 | Bot 路由 | `backend/routes/bot.py` | Bot 回调端点 (飞书/钉钉/企微) |
| 3 | 事件总线 | `backend/services/event_bus.py` | 发布/订阅 + 异步投递 + 重试 |
| 3 | Webhook 管理 | `backend/services/webhook_manager.py` | Webhook CRUD + HMAC 签名 |
| 3 | Webhook 路由 | `backend/routes/webhooks.py` | Webhook 管理端点 |
| 3 | 审计日志 | `backend/services/audit_logger.py` | 审计 JSONL 写入 |
| 3 | 审计路由 | `backend/routes/audit.py` | 审计查询/导出端点 |
| 3 | API Key 管理 | `backend/services/api_key_manager.py` | 多 Key 管理 + 配额 + 撤销 |
| 3 | API Key 路由 | `backend/routes/api_keys.py` | API Key 管理端点 |
| 3 | 健康检查 | `backend/services/health_checker.py` | 外部依赖定时探活 |
| 3 | 监控部署 | `deploy/docker-compose.monitoring.yml` | Prometheus + Grafana |
| 3 | Grafana Dashboard | `deploy/grafana/dashboards/rag-overview.json` | RAG 概览 + 检索详情 |
| §10.1 | 领域词典 | `backend/domain_dict.py` | DomainDict 类 |
| §10.1 | 词典配置 | `backend/config/domain_dict.yaml` | ~80 条 HSE 种子数据 |
| §10.1 | 词典路由 | `backend/routes/domain_dict.py` | 词典 CRUD 端点 |
| §10.2 | 多轮对话 | `backend/conversation.py` | ConversationManager |
| §10.2 | 会话路由 | `backend/routes/conversation.py` | 会话端点 |
| 2 | 血缘存储 | `backend/services/lineage_store.py` | 全链路血缘记录 |
| 2 | 血缘路由 | `backend/routes/lineage.py` | 血缘查询端点 |
| 2 | 资产目录 | `backend/services/catalog.py` | 多维统计聚合 |
| 2 | 目录路由 | `backend/routes/catalog.py` | 资产目录 API |
| 2 | 导出服务 | `backend/services/kg_exporter.py` | KG 多格式导出 |
| 2 | 导出路由 | `backend/routes/export.py` | 导出端点 |
| 2 | 备份服务 | `backend/services/backup.py` | 备份/恢复/验证 |
| 2 | 系统路由 | `backend/routes/system.py` | 备份/清理/存储/质量 |
| 2 | 质量监控 | `backend/services/quality.py` | 质量指标 + 告警 |
| 2 | 生命周期 | `backend/services/lifecycle.py` | 保留策略 + 自动清理 |
| 4 | 租户服务 | `backend/services/tenant_service.py` | Organization/Project CRUD + 成员管理 |
| 4 | 租户中间件 | `backend/middleware/tenant_middleware.py` | 租户上下文注入 (X-Project-Id) |
| 4 | 租户路由 | `backend/routes/tenants.py` | 组织/项目管理端点 (12 endpoints) |
| 4 | 容器部署 | `Dockerfile.backend` | FastAPI 容器 (Python 3.12-slim) |
| 4 | 容器部署 | `Dockerfile.frontend` | Nginx + React 多阶段构建 |
| 4 | 容器部署 | `docker-compose.yml` | 6 服务编排 (backend/frontend/chromadb/monitoring) |
| 4 | 容器部署 | `deploy/nginx/default.conf` | Nginx SPA + API 反向代理 |
| 4 | CI/CD | `.github/workflows/ci.yml` | GitHub Actions lint→test→build→push |
| 4 | CI/CD | `.gitlab-ci.yml` | GitLab CI 备选方案 |
| 4 | CI/CD | `deploy/cd-deploy.sh` | CD 部署脚本 + 健康检查等待 |
| — | — | — | — |
| **合计** | | **54 个新增模块** |

---

> **文档维护约定**：
> - 本文档与 `rag-engineering-blueprint-v1.0.md` 互补——前者定义检索核心，本文档定义企业化演进
> - 各 Phase 实施完成后，在此文档末尾追加 `## Phase N 实施记录` 章节
> - 蓝图变更需同步更新 `CLAUDE.md` 中的规范文档索引
