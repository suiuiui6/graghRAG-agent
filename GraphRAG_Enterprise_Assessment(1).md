# GraphRAG 多模态知识图谱问答系统 — 企业级就绪度评估与改造方案

> **版本**：v1.0  
> **日期**：2026-09-11  
> **评估范围**：后端核心链路、前端交互、基础设施、运维体系、安全合规  
> **评估方式**：代码审查 + 架构对标 + 规范文档核验  
> **原则**：有代码改代码、无代码补代码、最小侵入、渐进式演进

---

## 一、评估结论

**当前阶段**：MVP 验证完成，处于「工程化交付前」阶段  

**核心结论**：  
系统已跑通 **MinerU → LangExtract → Knowledge Graph → Agentic QA** 单文档全链路，目录隔离、环境隔离、规范文档驱动、Agent 协作流等工程基础扎实。但 **存储层、检索层、推理层、认证鉴权、可观测性** 五大核心能力缺失，均为架构层面的结构性缺口，非算法难题。  

**定级**：**不满足企业级生产就绪标准**，需完成关键建设后方可进入生产环境。

---

## 二、名词解释

| 术语 | 定义 |
|------|------|
| **GraphRAG** | 基于知识图谱的检索增强生成，利用实体关系结构提升检索精度与答案可解释性 |
| **MinerU** | 开源文档解析服务，支持 PDF/Office/图片等 11 种格式，输出 Markdown、layout.json、content_list.json |
| **LangExtract** | Google 开源的结构化实体抽取框架，基于少样本提示词从文本中抽取实体及属性 |
| **BridgePipeline** | 本项目自研的格式桥接管道，将 MinerU 输出转为 LangExtract 输入，完成溯源映射与 KG 构建 |
| **KG（Knowledge Graph）** | 知识图谱，由节点与边组成的结构化知识表示，本系统用 NetworkX 内存图 + JSON 文件持久化 |
| **Agentic RAG** | 引入 Agent 编排的 RAG 模式，LLM 自主规划工具调用路径，支持多轮推理与动态检索 |
| **LangGraph** | LangChain 生态的状态图编排框架，用于构建多步骤、有状态的 Agent 应用 |
| **RRF（Reciprocal Rank Fusion）** | 倒数排名融合，无监督混合检索融合算法，常用于向量检索与关键词检索结果合并 |
| **Cross-Encoder / 交叉编码器** | 重排序模型，输入 query+doc 对，输出相关性分数，精度高于 Bi-Encoder 但计算开销大 |
| **Neo4j** | 原生图数据库，支持 ACID 事务、Cypher 查询语言、APOC 过程库，适合亿级节点图存储 |
| **ChromaDB / Milvus** | 向量数据库，支持 HNSW/IVF 索引、元数据过滤、混合检索，用于语义向量存储与检索 |
| **BM25** | 经典概率检索模型，基于词频逆文档频率打分，适合精确关键词匹配场景 |
| **OTel（OpenTelemetry）** | 可观测性标准框架，统一日志、指标、链路追踪的采集与导出规范 |
| **DLQ（Dead Letter Queue）** | 死信队列，收集多次重试仍失败的任务，供人工介入或后续补偿处理 |
| **RBAC（Role-Based Access Control）** | 基于角色的访问控制，按角色分配权限，而非直接给用户授权 |
| **BFF（Backend for Frontend）** | 服务于前端的后端聚合层，按页面需求聚合下游微服务接口，减少前端请求数 |
| **Shadow Testing / 影子测评** | 新旧模型并行跑真实流量，仅记录新模型指标不影响用户，用于上线前验证 |
| **PII（Personally Identifiable Information）** | 个人可识别信息，如姓名、身份证、手机号等，数据治理需脱敏或加密处理 |
| **RPO / RTO** | 恢复点目标 / 恢复时间目标，灾备演练的核心指标，分别指容忍数据丢失量与业务恢复时限 |

---

## 三、关键缺陷清单与解决方案（按严重度分级）

### P0 级 — 架构阻断项，生产环境不可上线

#### D01 图存储：NetworkX → Neo4j

**现状代码**：
```python
# query.py:25-43 _load_single_kg() / _load_all_kgs()
# kg_builder.py:102-151 serialize_kg() 写 JSON
# query.py:81-88 _build_kg_from_full() 内存过滤 grounded 子图
```

**改造方案**：

| 步骤 | 动作 | 代码位置 | 说明 |
|------|------|----------|------|
| 1 | 新增 `stores/graph_store.py` 封装 Neo4j 操作 | 新文件 | 统一 Cypher 模板、事务管理、连接池 |
| 2 | 修改 `kg_builder.py` `serialize_kg()` 双写：JSON(兼容) + Neo4j | `kg_builder.py:102-151` | 保留 JSON 作为离线导出/备份 |
| 3 | 修改 `query.py` `_load_all_kgs()` 从 Neo4j 读取 | `query.py:46-71` | 启动时不再全量加载内存，改按需查询 |
| 4 | `_build_kg_from_full()` 移除，改用 Cypher `WHERE grounding_status='grounded'` | `query.py:81-88` | 推下存储层，减少内存占用 |
| 5 | 新增 `stores/__init__.py` 工厂函数 `get_graph_store()` | 新文件 | 环境变量切换 `GRAPH_BACKEND=neo4j\|networkx` |

**关键 Cypher 模板**（`stores/graph_store.py`）：
```python
# 节点写入（批量 UNWIND）
CREATE_NODES = """
UNWIND $nodes AS n
MERGE (e:Entity {node_id: n.node_id})
SET e.entity_type = n.entity_type,
    e.label = n.label,
    e.properties = n.properties,
    e.page_idx = n.page_idx,
    e.bbox_norm = n.bbox_norm,
    e.grounding_status = n.grounding_status
"""

# 边写入
CREATE_EDGES = """
UNWIND $edges AS e
MATCH (s:Entity {node_id: e.source_node_id})
MATCH (t:Entity {node_id: e.target_node_id})
MERGE (s)-[r:RELATES {relation_type: e.relation_type}]->(t)
SET r.properties = e.properties
"""

# Grounded 子图查询（替代 NetworkX 过滤）
QUERY_GROUNDED_SUBGRAPH = """
MATCH (n:Entity {grounding_status: 'grounded'})
OPTIONAL MATCH (n)-[r:RELATES]->(m:Entity {grounding_status: 'grounded'})
RETURN n, collect({rel: r, target: m}) AS neighbors
"""
```

**兼容性保留**：`GRAPH_BACKEND=networkx` 走现有 JSON 逻辑，开发环境零依赖。

---

#### D02 检索模式：单一 KG → 三路召回融合

**现状代码**：
```python
# query.py:132-168 _make_search_tool() / _make_neighbors_tool()
# agentic_rag_mvp.py:100-212 4 个 KG 工具
```

**改造方案**：

| 步骤 | 动作 | 代码位置 | 说明 |
|------|------|----------|------|
| 1 | 新增 `retrieval/vector_store.py` ChromaDB 封装 | 新文件 | `add_nodes()`、`similarity_search()`、`hybrid_search()` |
| 2 | 新增 `retrieval/keyword_store.py` BM25/SQLite FTS5 | 新文件 | 基于 `integrated_*.jsonl` 全文建索引 |
| 3 | 新增 `retrieval/fusion.py` RRF + Cross-Encoder 重排 | 新文件 | 统一融合入口，配置化权重 |
| 4 | 重构 `query.py` 工具函数为检索编排器 | `query.py:97-168` | `_make_search_tool()` → `HybridRetriever` 类 |
| 5 | Agent 工具集扩展：`search_hybrid` 替代 `search_kg_by_type` | `agentic_rag_mvp.py:96-296` | 保留原工具为内部调用，对外暴露融合工具 |

**检索编排器伪码**（`retrieval/hybrid_retriever.py`）：
```python
class HybridRetriever:
    def __init__(self, kg_store, vector_store, keyword_store, reranker=None):
        self.kg = kg_store
        self.vec = vector_store
        self.kw = keyword_store
        self.reranker = reranker

    def search(self, query: str, entity_type: str = "", k: int = 10, 
               weights: dict = None) -> list[RetrievedNode]:
        # 1. 三路并行召回
        kg_nodes = self.kg.search_by_type(entity_type, query) if entity_type else []
        vec_nodes = self.vec.similarity_search(query, k * 2)
        kw_nodes = self.kw.bm25_search(query, k * 2)

        # 2. RRF 融合
        fused = reciprocal_rank_fusion([kg_nodes, vec_nodes, kw_nodes], weights)

        # 3. 可选重排
        if self.reranker and len(fused) > 5:
            fused = self.reranker.rerank(query, fused[:20])

        return fused[:k]
```

**配置化权重**（`config/retrieval.yaml`）：
```yaml
weights:
  kg: 0.4      # 结构化查询权重最高
  vector: 0.35
  keyword: 0.25
reranker:
  enabled: true
  model: "bge-reranker-large"
  top_n: 20
```

---

#### D03 任务编排：BackgroundTasks → Celery

**现状代码**：
```python
# ingest.py:23-88 _run_indexing() 背景任务
# worker.py:35-159 run_real_pipeline() 同步执行 5 个阶段
# ingest.py:167-183 get_status() 内存字典 _tasks
```

**改造方案**：

| 步骤 | 动作 | 代码位置 | 说明 |
|------|------|----------|------|
| 1 | 新增 `tasks/celery_app.py` Celery 实例 + Redis Broker | 新文件 | `task_routes` 配置优先级队列 |
| 2 | 将 `worker.py` `run_real_pipeline()` 拆分为 5 个 Celery Task | `worker.py:35-159` | 每阶段独立 Task，支持重试、重跑 |
| 3 | `ingest.py` `_run_indexing()` 改为 `chain()` 编排 | `ingest.py:23-88` | 链式调用，自动传递上下文 |
| 4 | 进度回调改为 Celery 信号 + Redis 进度键 | `ingest.py:29-36` | `progress_callback` → `current_task.update_state()` |
| 5 | `get_status()` 读取 Redis + 结果后端 | `ingest.py:167-183` | 不再依赖内存 `_tasks` 字典 |

**Celery Task 定义**（`tasks/indexing_tasks.py`）：
```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60,
                 autoretry_for=(Exception,), retry_backoff=True)
def stage_mineru(self, task_id: str, filepath: str, options: dict):
    # 复用 worker._call_mineru_api() 逻辑
    mineru_dir = _call_mineru_api(...)
    return {"mineru_dir": mineru_dir, "task_id": task_id}

@celery_app.task(bind=True, max_retries=2)
def stage_bridge(self, prev_result: dict, options: dict):
    mineru_dir = prev_result["mineru_dir"]
    # 复用 worker.run_bridge() 逻辑
    return {**prev_result, "documents": docs, "offsets": offsets, ...}

# 以此类推 stage_extraction, stage_grounding, stage_kg_build
```

**链式编排**（`ingest.py`）：
```python
from tasks.indexing_tasks import (stage_mineru, stage_bridge, 
                                   stage_extraction, stage_grounding, stage_kg_build)

def _run_indexing(task_id, filepath, filename, file_size, options):
    workflow = (stage_mineru.s(task_id, filepath, options) |
                stage_bridge.s(options) |
                stage_extraction.s(options) |
                stage_grounding.s(options) |
                stage_kg_build.s(options))
    workflow.apply_async(task_id=task_id)
```

---

#### D04 多文档能力：单文档 → 多文档联合检索

**现状代码**：
```python
# query.py:46-71 _load_all_kgs() 按 doc_id 前缀隔离子图
# query.py:180-267 query() 仅单文档检索
# models.py:38-41 QueryRequest.document_id 可选但未实现跨文档
```

**改造方案**：

| 步骤 | 动作 | 代码位置 | 说明 |
|------|------|----------|------|
| 1 | Neo4j 节点增加 `doc_id` 属性（已在 `_load_single_kg` 写入 `origin_id`） | `query.py:34-38` | 复用现有 `origin_id` 字段 |
| 2 | 新增全局实体链接 Task：Embedding 相似度 + 规则合并 | 新增 `tasks/entity_linking.py` | 离线批量跑，生成 `:SAME_AS` 关系 |
| 3 | `HybridRetriever.search()` 增加 `doc_ids: list[str] | None` 参数 | `retrieval/hybrid_retriever.py` | `None` 表示全库检索 |
| 4 | Query API 增加 `scope: "single" | "global" | "selected"` 参数 | `models.py:38-41`、`query.py:194-267` | 前端控制检索范围 |
| 5 | 跨文档推理：Agent 增加 `compare_documents` 工具 | `agentic_rag_mvp.py` 工具集 | 多文档对比问答专用 |

**实体链接伪码**（`tasks/entity_linking.py`）：
```python
@celery_app.task
def link_entities_across_docs(threshold: float = 0.92):
    """离线任务：跨文档实体去重"""
    # 1. 取所有 grounded 节点向量
    nodes = neo4j.query("MATCH (n:Entity {grounding_status:'grounded'}) RETURN n")
    
    # 2. 同类型实体两两计算余弦相似度
    for etype in ENTITY_TYPES:
        same_type = [n for n in nodes if n["entity_type"] == etype]
        for i, a in enumerate(same_type):
            for b in same_type[i+1:]:
                sim = cosine(a.embedding, b.embedding)
                if sim > threshold:
                    neo4j.run("""
                    MATCH (a:Entity {node_id: $aid}), (b:Entity {node_id: $bid})
                    MERGE (a)-[:SAME_AS {score: $sim}]->(b)
                    """, aid=a.node_id, bid=b.node_id, sim=sim)
```

---

#### D05 推理深度：单轮 Agent → LangGraph StateGraph 多轮推理

**现状代码**：
```python
# agentic_rag_mvp.py:292-338 create_agent() 简易模式
# agentic_rag_mvp.py:349-394 run_query() 单次 invoke
# query.py:97-190 _build_agent() / _get_agent() 创建 Agent
```

**改造方案**：

| 步骤 | 动作 | 代码位置 | 说明 |
|------|------|----------|------|
| 1 | 新增 `agentic_rag/state.py` 定义 `AgentState` TypedDict | 新文件 | 显式状态：query_type、retrieved、reasoning_steps、answer |
| 2 | 新增 `agentic_rag/nodes.py` 实现各节点函数 | 新文件 | classify → retrieve → reason → generate → validate |
| 3 | 新增 `agentic_rag/graph.py` 编译 StateGraph | 新文件 | 条件边、循环、人工介入断点 |
| 4 | `query.py` `_build_agent()` 返回编译后的 `graph` | `query.py:97-106` | 替换 `create_agent()` 返回值 |
| 5 | 保留 `agentic_rag_mvp.py` 作为离线测试脚本 | 现有文件 | 回归验证用 |

**StateGraph 结构**（`agentic_rag/graph.py`）：
```python
from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .nodes import (classify_query, retrieve_kg, retrieve_vector, 
                     retrieve_keyword, fuse_rerank, reason_plan, 
                     generate_answer, validate_answer, needs_retry)

builder = StateGraph(AgentState)

builder.add_node("classify", classify_query)
builder.add_node("retrieve_kg", retrieve_kg)
builder.add_node("retrieve_vec", retrieve_vector)
builder.add_node("retrieve_kw", retrieve_keyword)
builder.add_node("fuse", fuse_rerank)
builder.add_node("reason", reason_plan)      # 多跳规划
builder.add_node("generate", generate_answer)
builder.add_node("validate", validate_answer)

builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route_retrieval, {
    "kg": "retrieve_kg",
    "vector": "retrieve_vec", 
    "keyword": "retrieve_kw",
    "hybrid": ["retrieve_kg", "retrieve_vec", "retrieve_kw"]
})
builder.add_edge(["retrieve_kg", "retrieve_vec", "retrieve_kw"], "fuse")
builder.add_edge("fuse", "reason")
builder.add_edge("reason", "generate")
builder.add_edge("generate", "validate")
builder.add_conditional_edges("validate", needs_retry, {
    "retry": "reason",
    "done": END
})

graph = builder.compile()
```

**分类节点**（`agentic_rag/nodes.py`）：
```python
def classify_query(state: AgentState) -> AgentState:
    query = state["messages"][-1].content
    # 复用现有关键词规则，后续可换分类器
    if any(kw in query for kw in ["多少", "数值", "%", "BLEU", "F1", "准确率"]):
        qtype = "metric"
    elif any(kw in query for kw in ["关系", "组成", "结构", "包含", "连接", "关联"]):
        qtype = "graph"
    elif any(kw in query for kw in ["定义", "什么是", "概念", "解释"]):
        qtype = "concept"
    elif any(kw in query for kw in ["引用", "论文", "作者", "发表"]):
        qtype = "metadata"
    else:
        qtype = "hybrid"
    return {**state, "query_type": qtype}
```

---

#### D06 认证鉴权：无 → OAuth2 + API Key + RBAC

**现状代码**：
```python
# security.py: FILE_ACCESS_TOKEN 单一 token
# routes/documents.py:90-103 serve_uploaded_file() verify_file_token()
# 无任何 API 端点鉴权中间件
```

**改造方案**：

| 步骤 | 动作 | 代码位置 | 说明 |
|------|------|----------|------|
| 1 | 新增 `auth/` 模块：`oauth2.py`、`api_keys.py`、`rbac.py` | 新目录 `backend/auth/` | 独立认证域 |
| 2 | FastAPI 依赖注入：`get_current_user`、`require_permission` | 新增 `backend/auth/dependencies.py` | 统一鉴权入口 |
| 3 | 所有 API 路由添加 `dependencies=[Depends(get_current_user)]` | `server.py:65-70` | 全局挂载或逐路由 |
| 4 | 文档级权限：`documents` 表增加 `owner_id`、`visibility` 字段 | `routes/__init__.py` `add_doc()` | 存储层扩展 |
| 5 | API Key 管理端点：`POST /api/v1/keys`、`GET /api/v1/keys` | 新增 `routes/auth.py` | 用户自助管理 |

**依赖注入示例**（`backend/auth/dependencies.py`）：
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlmodel import Session, select

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    api_key: str = Depends(api_key_header),
    db: Session = Depends(get_db)
) -> User:
    # 优先 API Key，其次 JWT
    if api_key:
        user = db.exec(select(User).where(User.api_key == api_key)).first()
    else:
        payload = decode_jwt(token)
        user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(401, "Invalid credentials")
    return user

def require_permission(permission: str):
    def checker(user: User = Depends(get_current_user)):
        if permission not in user.permissions:
            raise HTTPException(403, f"Missing permission: {permission}")
        return user
    return checker
```

**路由挂载**（`server.py`）：
```python
from auth.dependencies import get_current_user

app.include_router(query_router, prefix="/api/v1", tags=["Query"],
                   dependencies=[Depends(get_current_user)])
app.include_router(ingest_router, prefix="/api/v1", tags=["Ingest"],
                   dependencies=[Depends(get_current_user)])
# 文档下载额外检查所有权
@router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str, user: User = Depends(require_permission("doc:read"))):
    # 检查 doc.owner_id == user.id 或 visibility == public
```

---

#### D07 可观测性：print() → OpenTelemetry 全链路

**现状代码**：
```python
# 所有文件大量 print(f"[stage] ...")
# health.py:67-77 仅打印 token 长度
# 无 metrics、无 traces、无结构化日志
```

**改造方案**：

| 步骤 | 动作 | 代码位置 | 说明 |
|------|------|----------|------|
| 1 | 新增 `observability/` 模块：`tracing.py`、`metrics.py`、`logging.py` | 新目录 `backend/observability/` | 统一 OTel 初始化 |
| 2 | `server.py` lifespan 中 `init_telemetry()` | `server.py:23-34` | 启动时配置 Exporter |
| 3 | 关键函数添加 `@tracer.start_as_current_span` 装饰器 | `worker.py`、`query.py`、`ingest.py` | 自动生成 Span |
| 4 | 结构化日志：`structlog` + JSON 格式 + 关联 trace_id | 替换所有 `print()` | 统一 `logger.info()` 调用 |
| 5 | Prometheus 指标：`HTTP请求延迟`、`任务队列积压`、`KG节点数`、`Token消耗` | `observability/metrics.py` | `/metrics` 暴露端点 |

**OTel 初始化**（`observability/tracing.py`）：
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

def init_telemetry(service_name: str = "graphrag-backend"):
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    
    # 自动埋点
    FastAPIInstrumentor.instrument_app(app)
    RequestsInstrumentor().instrument()
    
    return trace.get_tracer(__name__)
```

**指标定义**（`observability/metrics.py`）：
```python
from prometheus_client import Counter, Histogram, Gauge

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint", "status"]
)

TASK_QUEUE_LENGTH = Gauge(
    "task_queue_length",
    "Number of pending indexing tasks",
    ["stage"]
)

KG_NODES_TOTAL = Gauge(
    "kg_nodes_total",
    "Total nodes in knowledge graph",
    ["doc_id", "entity_type"]
)

LLM_TOKEN_USAGE = Counter(
    "llm_token_usage_total",
    "Total LLM tokens consumed",
    ["model", "operation"]  # operation: embedding / generation
)
```

---

#### D08 数据治理：无 → 血缘 + 版本 + 备份 + PII

**现状代码**：
```python
# kg_builder.py serialize_kg() 直接覆盖写入
# 无迁移脚本、无版本字段、无 PII 扫描、无备份逻辑
```

**改造方案**：

| 步骤 | 动作 | 代码位置 | 说明 |
|------|------|----------|------|
| 1 | `KGNode` 增加 `version`、`created_at`、`updated_at`、`checksum` 字段 | `schema.py:63-70` | 乐观锁 + 变更检测 |
| 2 | `serialize_kg()` 改为增量写入：计算 checksum、仅变更节点 UPSERT | `kg_builder.py:102-151` | Neo4j `MERGE` + `ON CREATE/UPDATE` |
| 3 | 新增 `tasks/backup_kg.py` 定时导出 Neo4j dump + 上传对象存储 | 新文件 | 每日全量 + 每小时增量 |
| 4 | 接入 `presidio-analyzer` PII 扫描，抽取阶段标记敏感实体 | `worker.py:121-128` stage_extraction | `entity_type="pii"` + `properties.pii_category` |
| 5 | 新增 `admin/lineage.py` 数据血缘查询 API | 新文件 | 追踪 node 来源 PDF 页面 |

**PII 扫描集成**（`worker.py` stage_extraction 后）：
```python
from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine()

def scan_pii_entities(grounded_extractions: list[GroundedExtraction]):
    for ext in grounded_extractions:
        if ext.grounding_status != "grounded":
            continue
        results = analyzer.analyze(text=ext.extraction_text, language="zh")
        if results:
            ext.entity_type = "pii"
            ext.attributes = ext.attributes or {}
            ext.attributes["pii_categories"] = [r.entity_type for r in results]
            ext.attributes["pii_scores"] = [r.score for r in results]
```

---

### P1 级 — 工程化交付短板，影响运维效率与扩展性

| 编号 | 缺陷 | 补缺清单 | 优先级 |
|------|------|----------|--------|
| **D09** | 部署运维：无容器化/K8s | `Dockerfile` 多阶段、`docker-compose.yml` 全栈、`helm/graphrag/` K8s 清单、`health.py` 拆分 live/ready | P1 |
| **D10** | CI/CD：流水线简陋 | `.github/workflows/ci.yml` 新增集成测试/契约测试/性能基线/安全扫描、性能回归阈值 ±20%、依赖审计阻断 | P1 |
| **D11** | 错误处理：无重试/DLQ | Celery Task 统一重试策略、`task_acks_late=True`、死信队列配置、PrometheusRule 告警 | P1 |
| **D12** | 评测体系：仅离线 | `shadow_eval.py` 影子测评、`ab_test.py` 分流实验、`drift_monitor.py` 指标漂移告警 | P1 |
| **D13** | 前端架构：无 BFF/优化 | `services/` 统一 API 客户端、TanStack Query 替代 useState、大图 Canvas/WebGL 渲染、离线队列 | P1 |

---

### P2 级 — 产品能力深化项（标记补缺）

| 编号 | 能力项 | 状态 | 实施提示 |
|------|--------|------|----------|
| **D14** | 表格/公式/图表结构化入图 | 🔴 **补缺** | `extraction_examples.yaml` 增加示例、`kg_builder.py` 新增类型、Pipeline 接入 Table Transformer |
| **D15** | 国际化 | 🔴 **补缺** | `i18next` 初始化、`SYSTEM_PROMPT` 模板化、前端文案提取到 `locales/` |
| **D16** | 成本控制 | 🔴 **补缺** | 中间件统计 Token、LiteLLM Router 分级、GPTCache 语义缓存 |
| **D17** | 溯源体验增强 | 🟡 **部分有代码** | `QueryPage.tsx` 已有 page_idx/bbox，需集成 PDF.js 高亮、Range 请求支持 |

---

## 四、架构对标差距图

```
当前架构 (MVP)                          企业级目标架构
─────────────────────────                ─────────────────────────
┌──────────────┐                         ┌──────────────┐
│  FastAPI     │                         │  API Gateway │ (Kong/Traefik)
│  单实例      │                         │  多实例+熔断 │
└──────┬───────┘                         └──────┬───────┘
       │                                        │
       ▼                                        ▼
┌──────────────┐                         ┌──────────────┐
│ Background   │                         │  Task Queue  │ (Celery + Redis)
│ Tasks        │                         │  优先级+重试+DLQ│
└──────┬───────┘                         └──────┬───────┘
       │                                        │
       ▼                                        ▼
┌──────────────┐                         ┌──────────────┐
│ MinerU API   │                         │  MinerU      │ (私有化/云端)
│ BridgePipe   │                         │  BridgePipe  │ (幂等+检查点)
│ agentic_rag  │                         │  Agentic RAG │ (LangGraph)
└──────┬───────┘                         └──────┬───────┘
       │                                        │
       ▼                                        ▼
┌──────────────┐                         ┌──────────────┐
│ NetworkX     │                         │  Neo4j       │ (图存储)
│ + JSON文件   │                         │  ChromaDB    │ (向量)
└──────────────┘                         │  BM25/SQLite │ (全文)
                                         │  Object Store│ (原文件)
                                         └──────────────┘
```

---

## 五、技术债与风险点（需立即关注）

| 风险编号 | 风险描述 | 触发条件 | 影响后果 | 缓解建议 |
|----------|----------|----------|----------|----------|
| **R1** | 单点故障 | 进程崩溃/重启 | 全站不可用，进行中任务丢失 | 引入任务队列 + 多实例部署 + 状态外部化 |
| **R2** | 数据丢失 | 磁盘故障/误删除/并发写冲突 | KG 数据不可恢复，需重跑 Pipeline | Neo4j 持久化 + 定时快照 + WAL + 只读副本 |
| **R3** | 提示词注入 | 恶意 Query 包含指令覆盖 | 系统提示词失效，越权访问/数据泄露 | 输入消毒 + 指令分离架构 + 沙箱执行环境 |
| **R4** | 依赖漂移 | `requirements.txt` 无锁文件、无漏洞扫描 | 供应链攻击、版本冲突、构建不可复现 | `uv lock` + `pip-audit` + Dependabot + 供应链签名验证 |
| **R5** | 供应商锁定 | MinerU 云 API 单一依赖，无降级方案 | 服务不可用/涨价/合规限制导致业务停摆 | 评估本地化部署 / 备选解析器 / 多云抽象层 |
| **R6** | 评测数据污染 | `ground_truth.json` 被推理脚本误写 | 评测指标失真，版本回归无基线 | 只读权限 + CI 校验 hash + 数据版本管理 |
| **R7** | 前端 CDN 依赖 | vis.js 走 CDN，离线/内网环境 | 图谱渲染白屏，交付受限 | 本地化 npm 依赖 + 打包内联 + 离线构建验证 |
| **R8** | 配置泄露 | `.env.example` 含真实 Key 模板 | 凭证误提交 GitHub，资产被盗用 | `git-secrets` + pre-commit hook + 密钥轮换机制 + 扫描告警 |

---

## 六、技能包评估（已上传 GitHub 的两个 Skill）

| Skill | 定位 | 成熟度 | 复用价值 | 评估意见 |
|-------|------|--------|----------|----------|
| **harness-engineering** | 方法论框架（Layer 0-7 全生命周期） | 高 | 极高 — 已指导本项目从组件验证到工程化交付的全流程 | 作为团队标准化研发流程沉淀，建议持续维护版本化，配套模板与检查单 |
| **skill-evaluation** | 评测体系（A1 检索 / A2 忠实 / A3 鲁棒 / A4 多跳 / A5 性能） | 中 | 高 — 覆盖 RAG 核心质量维度，已形成可执行脚本与指标定义 | 接入 CI 作为回归门禁；扩展在线影子评测与 A/B 测试框架，形成闭环 |

**两者互补关系明确**：
- `harness-engineering` 解决「怎么做」—— 过程规范与交付标准
- `skill-evaluation` 解决「做得如何」—— 质量度量与持续改进

建议打包为组织级能力包，对外按「方法论 + 评测体系」双轨交付。

---

## 七、代码变更清单汇总（按文件）

| 文件 | 变更类型 | 涉及缺陷 | 优先级 |
|------|----------|----------|--------|
| `backend/query.py` | 重构 | D01、D02、D04、D05 | P0 |
| `backend/kg_builder.py` | 修改 | D01 | P0 |
| `backend/worker.py` | 拆分重构 | D03 | P0 |
| `backend/ingest.py` | 修改 | D03 | P0 |
| `backend/routes/__init__.py` | 扩展 | D04、D08 | P0 |
| `backend/models.py` | 扩展 | D04、D06 | P0 |
| `backend/security.py` | 重写 | D06 | P0 |
| `backend/agentic_rag_mvp.py` | 替换为目录 `agentic_rag/` | D05 | P0 |
| `backend/schema.py` | 扩展 | D01、D08 | P0 |
| `backend/observability/` | 新增目录 | D07 | P0 |
| `backend/auth/` | 新增目录 | D06 | P0 |
| `backend/stores/` | 新增目录 | D01、D02 | P0 |
| `backend/retrieval/` | 新增目录 | D02 | P0 |
| `backend/tasks/` | 新增目录 | D03、D04、D11 | P0 |
| `backend/config/retrieval.yaml` | 新增 | D02 | P0 |
| `docker-compose.yml` | 新增 | D09 | P1 |
| `Dockerfile` | 新增 | D09 | P1 |
| `helm/graphrag/` | 新增目录 | D09 | P1 |
| `.github/workflows/ci.yml` | 扩展 | D10 | P1 |
| `frontend/src/services/` | 新增目录 | D13 | P1 |
| `frontend/src/pages/QueryPage.tsx` | 重构 | D13 | P1 |
| `frontend/src/pages/GraphPage.tsx` | 重构 | D13 | P1 |
| `integration/extraction_examples.yaml` | 扩展 | D14 | P2 |
| `frontend/src/locales/` | 新增目录 | D15 | P2 |

---

## 八、演进路径建议（最小可行增量）

### 阶段 1：存储与检索地基
1. `docker-compose.yml` 起 Neo4j + ChromaDB + Redis
2. `stores/graph_store.py` + `stores/vector_store.py` 基础 CRUD
3. `kg_builder.py` 双写 JSON + Neo4j
4. `query.py` 读取 Neo4j，移除内存全量加载
5. 验证：单文档 KG 问答功能不回归

### 阶段 2：三路召回融合
1. `retrieval/keyword_store.py` 基于现有 JSONL 建 BM25
2. `retrieval/fusion.py` RRF 算法
3. `retrieval/hybrid_retriever.py` 编排三路
4. `query.py` 工具函数替换为 `HybridRetriever`
5. `agentic_rag_mvp.py` 工具集增加 `search_hybrid`
6. 验证：Recall@10 提升、混合查询正确

### 阶段 3：推理重构 + 任务队列
1. `agentic_rag/` 目录建立 StateGraph
2. `query.py` `_build_agent()` 返回 Graph
3. `tasks/celery_app.py` + 5 个索引 Task
4. `ingest.py` 链式编排
5. 验证：多跳问答、异步索引、进度回调

### 阶段 4：认证 + 可观测 + 多文档
1. `auth/` 模块 + 全局依赖注入
2. `observability/` OTel 接入 + Prometheus 指标
3. 实体链接离线 Task + `:SAME_AS` 关系
4. `HybridRetriever` 支持 `doc_ids=None` 全库检索
5. 验证：多文档联合问答、鉴权生效、Grafana 看板

### 后续阶段：CI/CD、K8s、评测在线化、前端优化、多模态、国际化

---

## 九、回归验证清单（每阶段必跑）

| 测试类型 | 覆盖范围 | 通过标准 |
|----------|----------|----------|
| 单元测试 | `stores/`、`retrieval/`、`auth/`、`observability/` | 覆盖率 > 80% |
| 集成测试 | Ingest → Pipeline → KG → Query 全链路 | 15 页论文 < 120s、答案准确 |
| 契约测试 | API Request/Response Schema | Pact 验证通过 |
| 性能基线 | Query P95、Ingest 吞吐、KG 写入速度 | 不劣于基线 ±20% |
| 安全扫描 | 依赖漏洞、密钥泄露、注入风险 | 0 高危、0 密钥泄露 |
| 回归对比 | `rag_eval` A1-A5 指标 | 核心指标不回退 |

---

## 十、配置管理（环境变量新增）

```bash
# .env 新增项
# 存储后端
GRAPH_BACKEND=neo4j                    # networkx | neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=***
CHROMA_HOST=chromadb
CHROMA_PORT=8000

# 任务队列
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# 检索融合
RETRIEVAL_WEIGHTS_KG=0.4
RETRIEVAL_WEIGHTS_VECTOR=0.35
RETRIEVAL_WEIGHTS_KEYWORD=0.25
RERANKER_ENABLED=true
RERANKER_MODEL=bge-reranker-large

# 认证
JWT_SECRET_KEY=***
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
API_KEY_PREFIX=grk_

# 可观测性
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=graphrag-backend
PROMETHEUS_METRICS_PORT=9090

# 功能开关
ENABLE_MULTI_DOC=true
ENABLE_ENTITY_LINKING=true
ENABLE_PII_DETECTION=true
```

---

## 十一、风险控制

| 风险 | 应对 |
|------|------|
| Neo4j 引入导致现有单文档问答回归 | 保留 `GRAPH_BACKEND=networkx` 开关，灰度切换 |
| Celery 迁移导致进度回调丢失 | 先在 Staging 环境跑 100 份真实文档对比 |
| 三路召回融合延迟增加 | 异步并行召回 + 可选重排（默认关闭，逐步开启） |
| 认证改造破坏现有前端调用 | 先加中间件放行模式，前端适配后再强制 |
| 数据量增长导致 Neo4j 启动慢 | 仅加载 grounded 索引、分页查询、Connection Pool 调优 |

---

## 十二、立即行动清单（建议尽快启动）

| 序号 | 行动项 | 产出物 | 优先级 |
|------|--------|--------|--------|
| 1 | 引入 `uv lock` + `pip-audit` + `pre-commit` + `git-secrets` | 锁文件、审计报告、Git Hook | P0 |
| 2 | 编写 `docker-compose.yml`（Neo4j + ChromaDB + Redis + API + Worker） | 本地一体化开发环境 | P0 |
| 3 | 将 `agentic_rag_mvp.py` 重构为 LangGraph StateGraph 显式状态机 | 多轮推理基础框架 | P0 |
| 4 | 补全 `backend/tests/` 契约测试 + 集成测试（覆盖 Ingest/Query/Status 全链路） | CI 门禁基线 | P0 |
| 5 | 接入 OpenTelemetry Python 自动埋点（日志/指标/链路三位一体） | 可观测性基线 | P0 |
| 6 | 评估 Neo4j Aura / Milvus 云托管方案，完成选型 PoC | 选型决策记录 | P0 |
| 7 | 梳理 API 认证鉴权矩阵，设计 OAuth2 + API Key 分级方案 | 安全设计文档 | P0 |

---

## 十三、结语

本文档以**现有代码为基线**，每项改造都给出了具体的文件定位、代码片段、兼容性策略。核心原则：

1. **不重写、改造** — 复用 `bridge.py`、`grounding.py`、`kg_builder.py`、`worker.py` 核心逻辑
2. **接口不变、实现替换** — `query.py` 对外 API 保持稳定，内部存储/检索/推理替换
3. **开关隔离、渐进切换** — 所有新基础设施通过环境变量开关，支持回滚
4. **测试先行、指标对标** — 每阶段必跑回归套件，性能指标有基线可比

按阶段节奏执行，可达成企业级核心能力交付。两个 Skill 包已具备对外交付条件，建议作为组织级知识资产沉淀与复用。