# Agentic-RAG 完整技术架构方案

> **版本**: v1.0 | **日期**: 2026-05-24
>
> 基于 BridgePipeline (MinerU → LangExtract → KG) 输出，
> 借助 LangGraph/LangChain 构建 Agentic-RAG 完整流程。
> 严格遵循 `docs/bridge-pipeline-specification-v1.0.md` 规范。

---

## 目录

1. [架构总览](#1-架构总览)
2. [索引构建层 (离线)](#2-索引构建层-离线)
3. [Agentic-RAG 运行时 (在线)](#3-agentic-rag-运行时-在线)
4. [多 Agent 协作架构](#4-多-agent-协作架构)
5. [工具定义与实现](#5-工具定义与实现)
6. [技术栈与依赖](#6-技术栈与依赖)
7. [实施路线图](#7-实施路线图)

---

## 1. 架构总览

```
                          Agentic-RAG 完整架构
┌──────────────────────────────────────────────────────────────────────────┐
│                         OFFLINE INDEXING LAYER                           │
│                                                                          │
│  PDF/DOCX ──► BridgePipeline ──► nodes.json + edges.json + JSONL        │
│                   │                    │                    │             │
│                   ▼                    ▼                    ▼             │
│            Vector Index         Graph Index         Full-Text Index      │
│          (ChromaDB/Milvus)      (Neo4j/NetworkX)     (BM25/SQLite)      │
│            embeddings             KG entities          raw text           │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                          ONLINE QUERY LAYER                              │
│                                                                          │
│   User Query                                                             │
│       │                                                                  │
│       ▼                                                                  │
│   ┌──────────────────┐                                                   │
│   │  Supervisor Agent │── 路由决策: type of question → tool selection     │
│   │  (LangGraph)      │                                                   │
│   └──────┬───────────┘                                                   │
│          │                                                               │
│    ┌─────┼─────────┬──────────┐                                         │
│    ▼     ▼         ▼          ▼                                          │
│  ┌────┐┌─────┐┌─────────┐┌──────────┐                                  │
│  │KG  ││Vector││Full-Text││Metadata  │  ← 工具层 (每个是 LangChain Tool) │
│  │Tool││Tool  ││Tool     ││Tool      │                                   │
│  └──┬─┘└──┬──┘└────┬────┘└────┬─────┘                                  │
│     │     │        │          │                                          │
│     ▼     ▼        ▼          ▼                                          │
│  ┌──────────────────────────────────────┐                               │
│  │        Fusion & Rerank Layer         │ ← 多路召回融合 + 重排序         │
│  └────────────────┬─────────────────────┘                               │
│                   ▼                                                      │
│  ┌──────────────────────────────────────┐                               │
│  │        Generation (DeepSeek/GPT)     │ ← 最终答案合成                  │
│  └──────────────────────────────────────┘                               │
│                   │                                                      │
│                   ▼                                                      │
│  Final Answer (with source citations + PDF page references)              │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 索引构建层 (离线)

### 2.1 输入数据源

BridgePipeline 输出三份数据：

| 数据 | 格式 | 数量 (实测) | 用途 |
|---|---|---|---|
| `nodes.json` | JSON | 310 nodes | KG 实体索引 + 向量化 |
| `edges.json` | JSON | 1,529 edges | KG 关系遍历 |
| `integrated_*.jsonl` | JSONL | 24 sections | 全文本索引 + 原文回溯 |

### 2.2 三维索引构建

#### 2.2.1 Vector Index — 语义向量检索

```python
# 伪代码: 向量索引构建
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    base_url="https://api.deepseek.com",  # 或使用 BGE 本地模型
)

vector_store = Chroma(
    collection_name="bridgepipeline_kg",
    embedding_function=embeddings,
)

# 每个 KG node → 一条向量记录
for node in nodes:
    doc = f"[{node['entity_type']}] {node['label']}"
    metadata = {
        "node_id": node["node_id"],
        "entity_type": node["entity_type"],
        "page_idx": node["page_idx"],
        "bbox_norm": json.dumps(node["bbox_norm"]),
        "properties": json.dumps(node["properties"]),
        "grounding_status": node["grounding_status"],
    }
    vector_store.add_texts([doc], metadatas=[metadata])
```

**数据量估算**: 310 nodes × 1536 dims × 4 bytes ≈ 1.9 MB

#### 2.2.2 Graph Index — 知识图谱结构检索

```python
# 伪代码: 图索引构建 (使用 NetworkX 内存图)
import networkx as nx

G = nx.Graph()
for node in nodes:
    G.add_node(node["node_id"], **node)

for edge in edges:
    G.add_edge(
        edge["source_node_id"],
        edge["target_node_id"],
        relation=edge["relation_type"],
        **edge["properties"],
    )
```

**图检索操作**:
- 1-hop neighbor query: 查询某实体的直接关联
- k-hop subgraph: 扩展上下文窗口
- Shortest path: 两个实体之间的关联路径
- Entity type filter: 限制检索到特定类别

#### 2.2.3 Full-Text Index — 精确关键词检索

```python
# 使用 BM25 (rank_bm25) 或 SQLite FTS5
from rank_bm25 import BM25Okapi

# 每 section 作为一篇文档
sections = [doc["text"] for doc in jsonl_docs]
tokenized = [s.split() for s in sections]
bm25 = BM25Okapi(tokenized)
```

---

## 3. Agentic-RAG 运行时 (在线)

### 3.1 核心 Agent 结构

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from typing import TypedDict, Annotated
import operator

# ---- 状态定义 ----
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]   # 对话历史
    query_type: str                            # 问题类型 (factual/graph/metric/overview)
    retrieved_nodes: list                      # KG 节点检索结果
    retrieved_chunks: list                     # 向量检索结果
    retrieved_text: list                       # 全文检索结果
    final_answer: str                          # 最终答案

# ---- 模型配置 ----
model = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key="sk-xxx",
    temperature=0.0,
)
```

### 3.2 Agent 工具集

| 工具 | 描述 | 输入 | 输出 |
|---|---|---|---|
| `search_kg` | 知识图谱结构化查询 | entity_type, keyword, k_hops | 子图节点 + 边 |
| `search_vector` | 语义相似度检索 | query_text, top_k | 相关 entity 列表 (含 score) |
| `search_keyword` | BM25 关键词检索 | keywords, top_k | 原文片段 + page_idx |
| `get_entity_detail` | 获取实体完整信息 | node_id | 属性 + 关联 + 页面位置 |
| `get_page_context` | 获取 PDF 页面上下文 | page_idx, entity_bbox | 原文包围区域文本 |

### 3.3 路由逻辑 (Supervisor)

```python
def classify_query(state: AgentState) -> str:
    """判断问题类型 → 决定首次调用哪类工具"""
    query = state["messages"][-1].content

    if any(kw in query for kw in ["多少", "数值", "%", "BLEU", "F1", "准确率"]):
        return "metric_search"       # 数值类 → 优先 KG + vector
    elif any(kw in query for kw in ["关系", "组成", "结构", "包含", "连接"]):
        return "graph_traversal"     # 结构类 → 优先 KG traversal
    elif any(kw in query for kw in ["定义", "什么是", "概念", "解释"]):
        return "semantic_search"     # 概念类 → 优先 vector
    elif any(kw in query for kw in ["引用", "论文", "作者", "发表"]):
        return "metadata_search"     # 元数据类 → 优先 keyword
    else:
        return "hybrid_all"          # 混合检索
```

### 3.4 LangGraph StateGraph 流程

```
                          ┌─────────────┐
                          │   START     │
                          └──────┬──────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  classify_query  │  ← 问题分类节点
                        └────────┬────────┘
                                 │
                   ┌─────────────┼─────────────┐
                   ▼             ▼             ▼
            ┌──────────┐ ┌──────────┐  ┌──────────┐
            │kg_search │ │vec_search│  │kw_search │  ← 并行检索
            └────┬─────┘ └────┬─────┘  └────┬─────┘
                 │             │             │
                 └─────────────┼─────────────┘
                               ▼
                      ┌──────────────────┐
                      │   fusion_rerank  │ ← 融合 + 重排序
                      └────────┬─────────┘
                               │
                               ▼
                      ┌──────────────────┐
                      │    generate      │ ← LLM 生成最终答案
                      └────────┬─────────┘
                               │
                               ▼
                      ┌──────────────────┐
                      │ needs_followup?  │ ← 是否需要追加检索
                      └───┬─────────┬────┘
                          │ yes     │ no
                          │         ▼
                          │    ┌─────────┐
                          └───►│  END    │
                               └─────────┘
```

```python
# LangGraph 实现
from langgraph.graph import StateGraph, START, END

builder = StateGraph(AgentState)

# 添加节点
builder.add_node("classify", classify_query)
builder.add_node("kg_search", kg_search_node)
builder.add_node("vec_search", vector_search_node)
builder.add_node("kw_search", keyword_search_node)
builder.add_node("fusion", fusion_rerank_node)
builder.add_node("generate", generate_answer_node)

# 添加边
builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", router, {
    "kg": "kg_search",
    "vector": "vec_search",
    "keyword": "kw_search",
    "hybrid": "kg_search",  # hybrid → 并行触发所有
})
builder.add_edge("kg_search", "fusion")
builder.add_edge("vec_search", "fusion")
builder.add_edge("kw_search", "fusion")
builder.add_edge("fusion", "generate")
builder.add_conditional_edges("generate", needs_followup, {
    "retry": "kg_search",
    "done": END,
})

agent = builder.compile()
```

---

## 4. 多 Agent 协作架构

当查询复杂度增加时，采用 Supervisor + Sub-agent 模式：

```
                        ┌───────────────────┐
                        │  Supervisor Agent  │
                        │  (router + merge) │
                        └──────┬─────┬──────┘
                               │     │
               ┌───────────────┘     └───────────────┐
               ▼                                     ▼
    ┌──────────────────────┐            ┌──────────────────────┐
    │  KG Specialist Agent │            │  Text QA Agent       │
    │                      │            │                      │
    │  Tools:              │            │  Tools:              │
    │  - traverse_graph    │            │  - search_vector     │
    │  - find_path         │            │  - search_keyword    │
    │  - get_subgraph      │            │  - read_page_context │
    │  - entity_lookup     │            │  - summarize_section │
    └──────────────────────┘            └──────────────────────┘
```

### 4.1 Supervisor 的职责

1. **解析用户 query**：识别需要哪些 Agent 参与
2. **任务分发**：将子任务路由到对应的 Specialist Agent
3. **结果整合**：合并各个 Agent 的返回结果
4. **最终生成**：基于合并结果生成带引用的答案

### 4.2 Agent 间通信协议

```python
class AgentTask(TypedDict):
    task_id: str
    agent_type: str        # "kg" | "text_qa"
    instruction: str       # 具体任务描述
    context: dict          # 所需上下文 (entity IDs, page ranges, etc.)
    expected_output: str   # "entity_list" | "text_chunks" | "subgraph"

class AgentResult(TypedDict):
    task_id: str
    status: str            # "success" | "partial" | "failed"
    data: dict             # 具体结果数据
    confidence: float      # 0-1
    sources: list          # 引用溯源 [node_id, page_idx, bbox]
```

---

## 5. 工具定义与实现

### 5.1 KG 遍历工具

```python
from langchain.tools import tool

@tool
def search_kg(
    entity_type: str = "",
    keyword: str = "",
    k_hops: int = 1,
    max_nodes: int = 20,
) -> dict:
    """
    Search the Knowledge Graph built from the document.

    Args:
        entity_type: Filter by entity type (e.g., 'metric', 'model_component')
        keyword: Search label or properties for this keyword
        k_hops: Number of neighbor hops to expand
        max_nodes: Maximum nodes to return

    Returns:
        Subgraph with nodes and edges, each with page_idx and bbox
    """
    # 1. Match nodes by type + keyword
    matched = [
        n for n in G.nodes(data=True)
        if (not entity_type or n[1]["entity_type"] == entity_type)
        and (not keyword or keyword.lower() in n[1]["label"].lower())
    ]

    # 2. k-hop expansion
    subgraph_nodes = set()
    for node_id, _ in matched[:5]:
        neighbors = nx.ego_graph(G, node_id, radius=k_hops)
        subgraph_nodes.update(neighbors.nodes())

    # 3. Extract subgraph (limited to max_nodes)
    result_nodes = []
    for nid in list(subgraph_nodes)[:max_nodes]:
        node_data = G.nodes[nid]
        result_nodes.append({
            "node_id": nid,
            "entity_type": node_data["entity_type"],
            "label": node_data["label"],
            "properties": node_data["properties"],
            "page_idx": node_data["page_idx"],
            "bbox_norm": node_data["bbox_norm"],
        })

    return {"nodes": result_nodes, "count": len(result_nodes)}
```

### 5.2 向量检索工具

```python
@tool
def search_vector(query: str, top_k: int = 10) -> dict:
    """
    Semantic similarity search over the KG entity embeddings.

    Args:
        query: Natural language query
        top_k: Number of results to return

    Returns:
        Ranked list of entities with similarity scores
    """
    results = vector_store.similarity_search_with_score(query, k=top_k)
    return {
        "results": [
            {
                "content": r[0].page_content,
                "score": float(r[1]),
                "metadata": r[0].metadata,
            }
            for r in results
        ]
    }
```

### 5.3 溯源解析工具

```python
@tool
def get_page_context(node_id: str) -> dict:
    """
    Get the original PDF page context for a KG entity.

    Args:
        node_id: The KG node identifier (e.g., 'n0001')

    Returns:
        Page index, normalized bbox, and surrounding text context
    """
    node = G.nodes[node_id]
    page_idx = node["page_idx"]
    bbox = node["bbox_norm"]

    # 从 layout.json 或 full.md 获取对应页面上下文
    context_text = page_context_cache.get(page_idx, "")

    return {
        "node_id": node_id,
        "label": node["label"],
        "page_idx": page_idx,
        "bbox_norm": bbox,
        "page_context_preview": context_text[:500],
    }
```

---

## 6. 技术栈与依赖

### 6.1 核心库

| 层 | 技术 | 版本 | 用途 |
|---|---|---|---|
| Agent 框架 | `langgraph` | ≥1.0 | StateGraph 构建 + Agent 编排 |
| Agent API | `langchain` | ≥1.2 | `create_agent` + Tool 定义 |
| LLM | `langchain-openai` | latest | DeepSeek via OpenAI Compat |
| 向量存储 | `langchain-chroma` | latest | 语义向量检索 |
| Embedding | `text-embedding-3-small` 或 `BGE-M3` | — | 文本向量化 |
| 图计算 | `networkx` | ≥3.0 | 内存图结构 + 遍历 |
| 全文本 | `rank-bm25` | latest | BM25 关键词检索 |
| 数据库(可选) | `chromadb` / `neo4j` | — | 生产级持久化 |

### 6.2 Python 依赖清单

```bash
# integration/requirements-agentic-rag.txt
langgraph>=1.0.0
langchain>=1.2.0
langchain-openai>=0.3.0
langchain-chroma>=0.2.0
chromadb>=0.5.0
networkx>=3.0
rank-bm25>=0.2.0
numpy>=1.20.0
pyyaml>=6.0
```

### 6.3 部署架构

```
容器 1: BridgePipeline (离线批处理)
  ├── MinerU API (云端)
  ├── LangExtract + DeepSeek (本地)
  └── → nodes.json + edges.json + JSONL

容器 2: Indexing Service (离线批处理)
  ├── ChromaDB (向量)
  ├── NetworkX (图)
  └── BM25 (全文)

容器 3: Agentic-RAG Runtime (在线)
  ├── LangGraph Agent
  ├── LangSmith Tracing
  └── FastAPI (REST endpoint)
```

---

## 7. 实施路线图

### Phase 1: 索引构建 (1-2 天)

```
□ 1.1 从 nodes.json 构建 NetworkX 图索引
□ 1.2 从 nodes.json 构建 ChromaDB 向量索引
□ 1.3 从 JSONL 构建 BM25 全文索引
□ 1.4 编写索引构建脚本 indexing/build_indices.py
```

### Phase 2: 核心 Agent (2-3 天)

```
□ 2.1 实现 5 个 LangChain Tool (search_kg / search_vector / search_keyword / get_entity_detail / get_page_context)
□ 2.2 实现 LangGraph StateGraph (classify → search → fusion → generate)
□ 2.3 实现问题分类路由逻辑
□ 2.4 实现多路召回融合 + 重排序
□ 2.5 编写核心 Agent 脚本 agentic_rag/agent.py
```

### Phase 3: 多 Agent 扩展 (1-2 天)

```
□ 3.1 实现 Supervisor Agent 路由
□ 3.2 实现 KG Specialist sub-agent
□ 3.3 实现 Text QA sub-agent
□ 3.4 Agent 间通信协议
```

### Phase 4: 端到端集成测试 (1 天)

```
□ 4.1 用 arXiv Transformer 论文测试完整流程
□ 4.2 覆盖 6 种 query 类型 (metric / graph / concept / metadata / hybrid / multi-hop)
□ 4.3 验证 source citation 准确性 (page_idx + bbox → PDF 位置)
□ 4.4 性能基准: < 5s 端到端延迟
```

### Phase 5: API 化 + 可视化 (1-2 天)

```
□ 5.1 FastAPI REST endpoint (POST /query)
□ 5.2 答案格式: {answer, sources, subgraph, confidence}
□ 5.3 前端可视化: 答案 + 高亮 PDF 位置 + 子图渲染
```

---

## 附录 A: 与 BridgePipeline 规范的映射

| BridgePipeline 输出 (§7) | Agentic-RAG 使用 |
|---|---|
| `nodes[].node_id` | 图索引键 + 向量 ID |
| `nodes[].entity_type` | 检索过滤维度 |
| `nodes[].label` | 向量化文本 + 展示标签 |
| `nodes[].properties` | 结构化属性过滤器 |
| `nodes[].page_idx` + `bbox_norm` | 溯源定位到 PDF 页面 |
| `nodes[].grounding_status` | 只使用 "grounded" 节点 |
| `edges[].relation_type` | 图遍历权重 |
| `integrated_*.jsonl` | 全文检索原始语料 |

## 附录 B: 预期查询示例

| 用户 Query | Agent 路径 | 预期结果 |
|---|---|---|
| "Transformer 的 BLEU 分数是多少？" | classify→metric → kg_search → generate | "28.4 BLEU on WMT 2014 EN-DE" + source [page 7, bbox...] |
| "Multi-Head Attention 是什么？" | classify→definition → vec_search → generate | 概念定义 + 关联公式 + 引用原文 |
| "有哪些正则化方法？" | classify→graph → kg_search(entity_type=method) → generate | Dropout, Label Smoothing + 参数列表 |
| "Encoder 和 Decoder 的关系？" | classify→graph → kg_search(k_hops=2) → generate | 子图结构 + 文本描述 |
| "这篇论文引用了哪些工作？" | classify→metadata → kg_search(entity_type=reference) → generate | 引用列表 + 上下文 |
