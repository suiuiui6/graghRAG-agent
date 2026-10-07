# Agentic KG-RAG 规范文档 v1.0

> **版本**: v1.0 | **日期**: 2026-05-24 | **状态**: ✅ 已通过 MVP 实测验证
>
> 本文档定义基于 LangGraph + DeepSeek 的 Agentic KG-RAG 完整规范，
> 上游对接 BridgePipeline (MinerU → LangExtract → KG)，
> 下游输出结构化问答结果。

---

## 目录

1. [系统架构总览](#1-系统架构总览)
2. [测试脚本路径与执行流程](#2-测试脚本路径与执行流程)
3. [输入规范](#3-输入规范)
4. [大模型接入规范](#4-大模型接入规范)
5. [Agent 工具集规范](#5-agent-工具集规范)
6. [核心交互逻辑](#6-核心交互逻辑)
7. [输出规范](#7-输出规范)
8. [关键技术架构详解](#8-关键技术架构详解)
9. [运行环境与依赖](#9-运行环境与依赖)

---

## 1. 系统架构总览

```
                         Agentic KG-RAG 架构
┌──────────────────────────────────────────────────────────────────────┐
│                         OFFCHAIN (离线批处理)                         │
│                                                                      │
│  PDF ──► [MinerU API] ──► [BridgePipeline] ──► nodes.json           │
│                                                    edges.json         │
│                                                    integrated_*.jsonl │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                          ONCHAIN (在线问答)                          │
│                                                                      │
│   User Query                                                         │
│       │                                                              │
│       ▼                                                              │
│   ┌──────────────────────────────────────────────────────┐          │
│   │  LangGraph Agent (create_agent)                      │          │
│   │                                                      │          │
│   │  Model: ChatOpenAI (DeepSeek via OpenAI Compat)      │          │
│   │  System Prompt: KG entity type registry + rules      │          │
│   │                                                      │          │
│   │  ┌──────────────────────────────────────────┐       │          │
│   │  │          Agent Tool Loop                  │       │          │
│   │  │                                           │       │          │
│   │  │  LLM ──(tool_call)──► Tool ──(result)──► LLM      │       │
│   │  │   │                    │                  │       │          │
│   │  │   └──(finish)──► Final Answer             │       │          │
│   │  └──────────────────────────────────────────┘       │          │
│   │                                                      │          │
│   │  Tools:                                              │          │
│   │    ├── search_kg_by_type  (entity type filter)      │          │
│   │    ├── get_entity_neighbors (k-hop traversal)       │          │
│   │    ├── get_entity_detail   (single node lookup)     │          │
│   │    └── get_kg_statistics   (global stats)           │          │
│   └──────────────────────────────────────────────────────┘          │
│       │                                                              │
│       ▼                                                              │
│   Final Answer (text + cited node_ids + page references)            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.1 与 BridgePipeline 的关系

Agentic KG-RAG 是 BridgePipeline 的**下游消费端**：

```
BridgePipeline (§7 output)          Agentic KG-RAG (this spec)
──────────────────────────          ──────────────────────────
nodes.json   ──────────────►  NetworkX Graph (G + G_grounded)
edges.json   ──────────────►  k-hop traversal edges
JSONL        ──────────────►  (reserved for future text hybrid)
```

> 严格遵循 `bridge-pipeline-specification-v1.0.md` §7 输出参数规范。
> 上游任一输出字段变更需同步更新本文档对应章节。

---

## 2. 测试脚本路径与执行流程

### 2.1 脚本存放路径

| 文件 | 绝对路径 | 说明 |
|---|---|---|
| **MVP 脚本** | `D:\graghRAG-agent\integration\agentic_rag_mvp.py` | Agentic KG-RAG 主入口 |
| **架构方案** | `D:\graghRAG-agent\integration\Agentic-RAG-Architecture.md` | 完整技术架构设计 |
| **可视化工具** | `D:\graghRAG-agent\integration\visualizer.html` | KG 图可视化前端 |
| **KG 数据** | `D:\graghRAG-agent\integration\output\kg\` | nodes.json + edges.json |
| **本规范** | `D:\graghRAG-agent\langextract\docs\agentic-kg-rag-specification-v1.0.md` | 本文档 |

### 2.2 完整执行流程

```
agentic_rag_mvp.py 执行时序
═══════════════════════════════════════════════════════════

[Phase 1] 加载 KG 数据 (L50-94)
    ├── 读取 nodes.json → 遍历 nodes[], 构建 NetworkX Graph
    │   每个 node 存储: entity_type, label, properties, page_idx, bbox_norm, grounding_status
    ├── 读取 edges.json → 遍历 edges[], 添加图的边
    │   每条 edge 存储: relation (co_occurs_with/same_type/adjacent_to)
    └── 筛选 G_grounded = G.subgraph(grounding_status == "grounded")
        输出: 310 nodes (214 grounded), 1138 edges (986 grounded)

[Phase 2] 定义 LangChain Tools (L100-289)
    ├── search_kg_by_type:    按 entity_type + keyword 搜索实体
    ├── get_entity_neighbors: 给定 node_id → k-hop 邻居子图
    ├── get_entity_detail:    给定 node_id → 完整属性 + 直接关联
    └── get_kg_statistics:    全局 KG 统计 (node/edge/type 分布)

[Phase 3] 构建 LangGraph Agent (L296-338)
    ├── ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com")
    ├── create_agent(model, tools=TOOLS, system_prompt=...)
    └── Agent 循环: LLM ⇄ Tool (直到 finish 或 max_iterations)

[Phase 4] 执行测试查询 (L349-375)
    ├── 对每个 query 调用 agent.invoke({"messages": [("user", query)]})
    ├── 从 result["messages"][-1].content 提取最终答案
    └── 打印答案 (含 node ID 引用 + page 溯源)
```

### 2.3 运行命令

```bash
# 激活 LangExtract 虚拟环境 (Agentic-RAG 共用此环境)
source D:/graghRAG-agent/langextract/.venv/Scripts/activate

# 进入集成目录并执行
cd D:/graghRAG-agent/integration
python agentic_rag_mvp.py
```

---

## 3. 输入规范

### 3.1 数据输入：Knowledge Graph 文件

Agentic KG-RAG 接收 BridgePipeline 输出的两份 JSON 文件作为数据源。

#### 3.1.1 nodes.json 节点输入

**来源**: BridgePipeline Stage 5 (`kg_builder.py`), 遵循 `bridge-pipeline-specification-v1.0.md` §7.2

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `node_id` | `string` | ✅ | 唯一标识，格式 `n{0001..9999}` |
| `entity_type` | `string` | ✅ | 实体类别，10 种枚举值 (见 §3.2) |
| `label` | `string` | ✅ | 实体文本标签 |
| `properties` | `dict` | ✅ | 实体属性键值对 |
| `page_idx` | `int \| null` | ✅ | PDF 页码 (0-based), `null` = 未接地 |
| `bbox_norm` | `[float×4] \| null` | ✅ | 0-1000 归一化包围框 |
| `grounding_status` | `string` | ✅ | `"grounded"` / `"ungrounded"` |

**加载逻辑** (`agentic_rag_mvp.py` L61-74):
```python
G.add_node(
    node["node_id"],
    entity_type=node["entity_type"],
    label=node["label"],
    properties=node.get("properties", {}),
    page_idx=node.get("page_idx"),
    bbox_norm=node.get("bbox_norm"),
    grounding_status=node.get("grounding_status", "ungrounded"),
)
```

#### 3.1.2 edges.json 边输入

**来源**: BridgePipeline Stage 5 (`kg_builder.py`), 遵循 `bridge-pipeline-specification-v1.0.md` §7.3

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `edge_id` | `string` | ✅ | 唯一标识，格式 `e{0001..9999}` |
| `source_node_id` | `string` | ✅ | 源节点 ID |
| `target_node_id` | `string` | ✅ | 目标节点 ID |
| `relation_type` | `string` | ✅ | `co_occurs_with` / `same_type` / `adjacent_to` |
| `properties` | `dict` | ✅ | 边属性 (含 `rule` 生成策略标识) |

**加载逻辑** (`agentic_rag_mvp.py` L77-83):
```python
G.add_edge(
    edge["source_node_id"],
    edge["target_node_id"],
    relation=edge["relation_type"],
    **edge.get("properties", {}),
)
```

### 3.2 实体类别枚举 (entity_type)

| entity_type | 含义 | 典型属性 |
|---|---|---|
| `paper_metadata` | 论文元信息 | `field: "title"/"author"/"affiliation"` |
| `section_header` | 章节标题 | `level: 1-6` |
| `model_component` | 模型组件 | `component_type`, `parameter` |
| `metric` | 数值指标 | `name`, `value`, `unit`, `task` |
| `dataset` | 数据集 | `name`, `version`, `task`, `language_pair` |
| `method` | 方法/技术 | `category`, `parameter` |
| `definition` | 概念定义 | `concept` |
| `equation` | 公式 | `name`, `latex` |
| `reference` | 引用 | `citation_key`, `authors` |
| `claim` | 论断/结论 | `claim_type`, `confidence` |

### 3.3 用户查询输入

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query` | `string` | ✅ | 自然语言问题 |
| `messages` | `list[tuple[str,str]]` | ✅ | LangChain 消息格式: `[("user", query)]` |

---

## 4. 大模型接入规范

### 4.1 模型配置

| 参数 | 值 | 说明 |
|---|---|---|
| **Provider** | OpenAI Compatible | LangChain `ChatOpenAI` 封装 |
| **Model** | `deepseek-chat` | DeepSeek-V3 标准模型 |
| **Base URL** | `https://api.deepseek.com` | DeepSeek API 端点 |
| **Temperature** | `0.0` | 确定性输出 (KG 查询场景) |
| **Timeout** | `120s` | 单次 API 调用超时 |

**配置代码** (`agentic_rag_mvp.py` L299-305):
```python
model = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key="sk-xxx",
    temperature=0.0,
    timeout=120,
)
```

### 4.2 模型兼容性矩阵

| 模型 | 支持状态 | 注意事项 |
|---|---|---|
| `deepseek-chat` | ✅ 已验证 | MVP 推荐，5/5 查询通过 |
| `deepseek-v4-pro` | ⚠️ 需适配 | 启用 thinking mode，`create_agent` 的 multi-turn 循环无法正确回传 `reasoning_content`，需自定义 `ChatOpenAI` 子类或 API 层禁用 thinking |

### 4.3 System Prompt 规范

Agent 的 System Prompt 定义在脚本 L307-332，包含三个核心部分：

1. **角色定义**: "Knowledge Graph QA agent"
2. **Entity Type Registry**: 10 种实体类别及含义说明
3. **行为规则**:
   - 必须使用工具搜索 KG → 禁止幻觉
   - 搜索策略: `search_kg_by_type` → `get_entity_neighbors` → `get_entity_detail`
   - 用用户语言回答
   - 引用 node ID 和页码
   - KG 无信息时明确告知

### 4.4 关键参数对照 (与 MinerU-API-Specification 对接)

| MinerU 参数 | Agentic-RAG 对应 |
|---|---|
| `MINERU_MODEL_VERSION=pipeline` | 影响 KG 节点 `grounding_status` 比例 |
| `MINERU_ENABLE_TABLE=true` | 影响 `metric` 类实体抽取质量 |
| `MINERU_ENABLE_FORMULA=true` | 影响 `equation` 类实体数量 |
| `MINERU_LANGUAGE=en` | 影响 System Prompt 语言选择 |
| `LANGEXTRACT_MODEL_ID=deepseek-chat` | 影响 Agent 的 LLM 推理质量 |
| `SECTION_MIN_LEVEL=2` | 影响 Agent 的 `section_header` 粒度 |

---

## 5. Agent 工具集规范

### 5.1 工具一览

| 工具名 | 类型 | 输入 | 输出 | 用途 |
|---|---|---|---|---|
| `search_kg_by_type` | `@tool` | entity_type, keyword, max_results | JSON string | 按类型+关键词搜索实体 |
| `get_entity_neighbors` | `@tool` | node_id/label_keyword, k_hops, max_results | JSON string | k-hop 邻域遍历 |
| `get_entity_detail` | `@tool` | node_id | JSON string | 单实体完整信息 |
| `get_kg_statistics` | `@tool` | (无) | JSON string | 全局 KG 统计 |

### 5.2 search_kg_by_type

**功能**: 在 grounded 子图中按 `entity_type` 和 `keyword` 过滤节点。

**参数**:

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `entity_type` | `str` | `""` | 实体类型过滤。空 = 搜索所有类型 |
| `keyword` | `str` | `""` | 关键词 (大小写不敏感)，匹配 `label` 和 `properties` 值 |
| `max_results` | `int` | `15` | 最大返回条数 |

**返回格式**:
```json
[
  {
    "node_id": "n0019",
    "entity_type": "metric",
    "label": "28.4 BLEU",
    "properties": {"name": "BLEU", "value": "28.4", "task": "translation"},
    "page_idx": 0
  }
]
```

**搜索范围**: `G_grounded` (仅 grounded nodes)

### 5.3 get_entity_neighbors

**功能**: 给定一个实体，返回其 k-hop 邻域子图。

**参数**:

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `node_id` | `str` | `""` | 精确 node_id |
| `label_keyword` | `str` | `""` | 按 label 模糊匹配 (node_id 为空时使用) |
| `k_hops` | `int` | `1` | 扩展跳数. 1=直接邻居, 2=邻居的邻居 |
| `max_results` | `int` | `15` | 最大邻居数 |

**返回格式**:
```json
{
  "source": {
    "node_id": "n0018",
    "entity_type": "model_component",
    "label": "Transformer",
    "properties": {"component_type": "model"},
    "page_idx": 0
  },
  "neighbors_count": 8,
  "neighbors": [
    {
      "node_id": "n0019",
      "entity_type": "metric",
      "label": "28.4 BLEU",
      "relation": "co_occurs_with"
    }
  ],
  "k_hops": 1
}
```

**实现**: `nx.ego_graph(G_grounded, source_id, radius=k_hops)`

### 5.4 get_entity_detail

**功能**: 获取单个实体的完整属性和直接关系。

**参数**:

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `node_id` | `str` | (必填) | 节点标识 |

**返回格式**:
```json
{
  "node_id": "n0074",
  "entity_type": "model_component",
  "label": "multi-head self-attention mechanism",
  "properties": {"component_type": "mechanism"},
  "page_idx": 2,
  "grounding_status": "grounded",
  "relationships": [
    {
      "target_node_id": "n0075",
      "target_label": "positionwise fully connected feed-forward...",
      "target_type": "model_component",
      "relation": "adjacent_to"
    }
  ]
}
```

### 5.5 get_kg_statistics

**功能**: 返回全局 KG 统计信息。

**返回格式**:
```json
{
  "total_nodes": 310,
  "grounded_nodes": 214,
  "ungrounded_nodes": 96,
  "grounding_rate": "69.0%",
  "total_edges": 1138,
  "entity_type_distribution": {
    "reference": 76,
    "claim": 48,
    "model_component": 40,
    "metric": 35,
    "paper_metadata": 31,
    "method": 23,
    "section_header": 18,
    "equation": 16,
    "definition": 13,
    "dataset": 10
  },
  "relation_type_distribution": {
    "co_occurs_with": 695,
    "adjacent_to": 309,
    "same_type": 134
  }
}
```

---

## 6. 核心交互逻辑

### 6.1 Agent 循环模型

```
┌──────────────────────────────────────────────┐
│              LangGraph Agent Loop            │
│                                              │
│  1. User sends query                         │
│       │                                      │
│       ▼                                      │
│  2. LLM analyzes query + context             │
│       │                                      │
│       ├── needs KG data? ──► calls Tool      │
│       │       │                    │         │
│       │       ▼                    ▼         │
│       │   Tool executes     returns JSON    │
│       │       │                    │         │
│       │       └────────────────────┘         │
│       │              │                       │
│       ▼              ▼                       │
│  3. LLM receives tool result                 │
│       │                                      │
│       ├── needs more data? ──► goto 2        │
│       │                                      │
│       └── has enough? ──► FINISH             │
│              │                               │
│              ▼                               │
│  4. Return final answer                      │
│                                              │
└──────────────────────────────────────────────┘
```

**实现**: LangChain `create_agent()` 内置此循环。Agent 持续运行直到 LLM 输出最终答案或达到迭代上限。

### 6.2 问答交互流程 (实测 Tracing)

以 Query 2 "What BLEU scores did the Transformer achieve?" 为例：

```
Step 1: Agent.invoke({"messages": [("user", "What BLEU scores...")]})
Step 2: LLM → tool_call: search_kg_by_type(entity_type="metric", keyword="BLEU")
Step 3: Tool → returns 2 matching nodes (28.4 BLEU, 41.8 BLEU)
Step 4: LLM → tool_call: get_entity_neighbors(label_keyword="Transformer", k_hops=1)
Step 5: Tool → returns Transformer's neighbor entities
Step 6: LLM → FINISH: structured answer with table + node IDs + page numbers
```

### 6.3 Agent 决策规则

| 查询类型 | 首选工具 | 备选工具 |
|---|---|---|
| 数值/指标类 | `search_kg_by_type(entity_type="metric")` | `get_entity_detail` |
| 结构/关系类 | `get_entity_neighbors(k_hops=2)` | `search_kg_by_type(entity_type="model_component")` |
| 概念/定义类 | `search_kg_by_type(entity_type="definition")` | `get_entity_detail` |
| 元数据类 | `search_kg_by_type(entity_type="paper_metadata")` | — |
| 统计类 | `get_kg_statistics` | — |
| 综合类 | `search_kg_by_type` → `get_entity_neighbors` → `get_entity_detail` | — |

---

## 7. 输出规范

### 7.1 最终问答输出格式

Agentic KG-RAG 返回的最终答案包含以下要素：

```
┌─────────────────────────────────────────┐
│          Final Answer Structure         │
│                                         │
│  [1] Synthesized Answer Text           │
│      └── Natural language response     │
│                                         │
│  [2] Inline Source Citations           │
│      └── node_id (n0019)               │
│      └── page_idx (page 0)             │
│                                         │
│  [3] Optional Structured Data          │
│      └── Tables (markdown)             │
│      └── Bullet lists                  │
│      └── JSON blocks                   │
│                                         │
│  [4] Traceability                      │
│      └── All claims backed by KG nodes │
│      └── "not found in KG" disclaimer  │
│                                         │
└─────────────────────────────────────────┘
```

### 7.2 程序化输出 (agent.invoke 返回值)

```python
result = agent.invoke({"messages": [("user", query)]})

# result 结构:
{
    "messages": [
        HumanMessage(content="What BLEU scores..."),
        AIMessage(content="", tool_calls=[...]),      # LLM 工具调用
        ToolMessage(content='[{"node_id":...}]'),       # 工具返回
        AIMessage(content="Based on the KG..."),        # 最终答案
    ]
}
```

**最终答案提取** (`agentic_rag_mvp.py` L363-368):

```python
messages = result.get("messages", [])
final_msg = messages[-1]
answer_text = final_msg.content  # str
```

### 7.3 答案质量标准

| 指标 | 要求 | 验证方式 |
|---|---|---|
| 可溯源 | 每条事实关联至少 1 个 node_id | 检查 node_id 是否存在于 KG |
| 无幻觉 | KG 无信息时明确声明 "not found in the KG" | 对比 KG 实际内容 |
| 多语言 | 用问题语言回答 (中/英) | 系统提示指示 |
| 结构化 | 数值类答案使用表格 | 正则匹配 markdown table |
| 完整性 | 综合类答案覆盖所有相关实体类型 | 对比预期 entity type 覆盖 |

### 7.4 实测输出示例 (2026-05-24)

**Query**: "What BLEU scores did the Transformer achieve and on which datasets?"

**输出**:
```
Based on the Knowledge Graph, here are the BLEU scores:

| BLEU Score | Dataset | Details |
|:----------:|:--------|:--------|
| **28.4 BLEU** | **WMT 2014 EN-DE** | Improved over existing best results... (Node: n0019, Page 0) |
| **41.8 BLEU** | **WMT 2014 EN-FR** | New single-model state-of-the-art... (Node: n0020, Page 0) |

Both scores are associated with the **Transformer** model (node: n0018).
```

**输出字段映射**:

| 输出内容 | 来源 | 字段路径 |
|---|---|---|
| "28.4 BLEU" | nodes.json | `nodes[].label` |
| "WMT 2014 EN-DE" | nodes.json | `nodes[].properties.task` |
| "n0019" | nodes.json | `nodes[].node_id` |
| "Page 0" | nodes.json | `nodes[].page_idx` |
| Transformer relation | edges.json | `edges[].relation_type = co_occurs_with` |

---

## 8. 关键技术架构详解

### 8.1 三层数据流架构

```
Layer 1: DATA (文件系统)
  nodes.json + edges.json
      │
      ▼
Layer 2: GRAPH (NetworkX 内存图)
  G = nx.Graph()                   # 全量图 (310 nodes)
  G_grounded = G.subgraph(...)     # 接地子图 (214 nodes)
      │
      ▼
Layer 3: AGENT (LangGraph + LLM)
  create_agent(model, tools)
  Agent Loop: LLM ⇄ Tool
```

### 8.2 Graph 构建关键决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 图类型 | 无向图 (`nx.Graph`) | `co_occurs_with` / `same_type` 均为对称关系 |
| 节点存储 | `entity_type`, `label`, `properties`, `page_idx`, `bbox_norm`, `grounding_status` | 继承 BridgePipeline 全部输出字段 |
| 边存储 | `relation` (edge attribute) | 保留原始关系类型供遍历权重使用 |
| 子图策略 | `G_grounded` (仅 grounded) | 所有工具查询只操作 grounded 子图，确保答案可溯源 |

### 8.3 工具设计原则

1. **只返回 grounded 数据**: 所有工具查询 `G_grounded`，确保答案可追溯到 PDF 页面
2. **JSON 序列化**: 工具函数返回 JSON 字符串，便于 LLM 解析
3. **上限控制**: `max_results` 限制返回大小，避免 context window 溢出
4. **单一职责**: 每个工具只做一件事 (filter / traverse / detail / stats)

### 8.4 DeepSeek 兼容性

| 特性 | 兼容状态 | 处理方式 |
|---|---|---|
| `tools` (function calling) | ✅ 支持 | LangChain `create_agent` 自动处理 |
| `response_format` JSON mode | ❌ 不支持 | 不影响 agent 流程 (工具通过 function call 返回) |
| `reasoning_content` (thinking mode) | ⚠️ v4-pro 需适配 | MVP 使用 `deepseek-chat` |
| `base_url` 自定义 | ✅ 支持 | `ChatOpenAI(base_url="https://api.deepseek.com")` |

### 8.5 与上游组件对接关系

```
MinerU-API-Specification.md (§4)
  │  task_id, full_zip_url
  ▼
BridgePipeline (§2-5)
  │  full.md → content_list → sections → LangExtract → KG
  ▼
nodes.json + edges.json  ← Agentic KG-RAG 的输入
  │
  ▼
agentic_kg_rag_mvp.py
  │
  ▼
Final Answer ← 本文档 §7 定义
```

---

## 9. 运行环境与依赖

### 9.1 虚拟环境

Agentic KG-RAG 与 LangExtract 共用虚拟环境。

```bash
source D:/graghRAG-agent/langextract/.venv/Scripts/activate
```

### 9.2 核心依赖

| 包 | 版本 | 用途 |
|---|---|---|
| `langgraph` | ≥1.2.1 | Agent StateGraph 运行时 |
| `langchain` | ≥1.3.1 | `create_agent` + `@tool` 装饰器 |
| `langchain-openai` | ≥1.2.2 | ChatOpenAI (DeepSeek 兼容) |
| `networkx` | ≥3.6.1 | KG 内存图结构与遍历 |
| `openai` | ≥2.38.0 | 底层 HTTP 客户端 |

### 9.3 首次安装

```bash
cd D:/graghRAG-agent/integration
source ../langextract/.venv/Scripts/activate
uv pip install "langgraph>=1.0" "langchain>=1.2" "langchain-openai>=0.3" "networkx>=3.0"
```

### 9.4 组件隔离架构

```
D:\graghRAG-agent\
├── integration\                  ← Agentic KG-RAG (共用 langextract .venv)
│   ├── agentic_rag_mvp.py        ← ★ MVP 主脚本
│   ├── bridge.py / grounding.py  ← BridgePipeline 模块
│   └── output/kg/                ← KG 数据
├── langextract\
│   └── .venv\                    ← 82 个包 (langgraph, langchain, networkx...)
└── mineru-mvp-test\
    └── .venv\                    ← 10 个包 (独立)
```

---

## 附录 A: 与相关规范文档对照

| 本文档章节 | 引用的上游规范 |
|---|---|
| §3.1 输入规范 (nodes/edges) | `bridge-pipeline-specification-v1.0.md` §7.2-7.3 |
| §3.2 entity_type 枚举 | `bridge-pipeline-specification-v1.0.md` §7.4 |
| §4.4 MinerU 参数对应 | `MinerU-API-Specification.md` §4 |
| §4.2 模型兼容矩阵 | `LangExtract-Pipeline-Specification.md` §5.3 |
| §6 交互逻辑 | `bridge-pipeline-specification-v1.0.md` §1, §6 |
| §8.5 上游对接关系 | `MinerU_MVP测试配置指南.md_v1.0.md` §2.4 |

## 附录 B: 文档修订记录

| 版本 | 日期 | 修订内容 |
|---|---|---|
| v1.0 | 2026-05-24 | 初始版本: 基于 `agentic_rag_mvp.py` 源码 + BridgePipeline 规范 + MinerU API 规范，完整定义 Agentic KG-RAG 的执行流程、输入输出规范、工具集、交互逻辑、技术架构 |
