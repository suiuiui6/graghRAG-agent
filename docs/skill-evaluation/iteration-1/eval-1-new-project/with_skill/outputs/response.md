# 多模态知识管理平台 — 项目搭建规划

> 基于驾驭工程 8 层递进方法论，从零搭建一个支持 PDF/Word/PPT 文档上传、自动解析、实体关系抽取、知识图谱构建和自然语言问答的多模态知识管理平台。

---

## 项目概述

你要搭建的是一个**多模态知识管理平台**，核心用户流程如下：

```
用户上传文档（PDF/Word/PPT）
  → 系统自动解析文档内容（文档解析层）
    → 抽取实体和关系（信息抽取层）
      → 构建知识图谱（图谱存储层）
        → 基于图谱的自然语言问答（检索与生成层）
          → 前端可视化展示与交互（展示层）
```

这个系统涉及 **5 个核心技术组件**，每个组件独立选型和验证，最终通过桥接管道串联为完整系统。

---

## 驾驭工程 8 层规划

以下按驾驭工程的 8 层递进流程，逐层说明每一层要做什么、产出什么、如何验证。**必须按顺序推进，不跳步**——每一层都在验证上一层的假设是否正确，跳步的代价是后期返工。

---

### Layer 0: 能力边界摸底

**目标**：搞清楚每个备选组件的真实能力边界，为后续架构决策提供依据。

#### 需要评估的 5 类候选组件

| 组件类别 | 职责 | 候选方案（供调研） |
|---|---|---|
| **文档解析引擎** | PDF/Word/PPT → 结构化文本 | MinerU（云端 API / 本地部署）、PyMuPDF、Unstructured、Apache Tika |
| **实体关系抽取** | 纯文本 → 实体 + 关系 | LangExtract（LLM 驱动）、spaCy + LLM、OpenAI Structured Outputs、GLiNER |
| **知识图谱存储** | 存储和查询图结构数据 | Neo4j、Amazon Neptune、ArangoDB、NetworkX（轻量级） |
| **向量检索引擎** | 语义检索、RAG 上下文召回 | ChromaDB、FAISS、Qdrant、Elasticsearch |
| **LLM 生成服务** | 自然语言理解与生成 | OpenAI API、Anthropic API、本地部署模型（Ollama/vLLM） |

#### 对每个候选组件，按以下步骤摸底

1. **拉取源码**（如 GitHub 仓库）或通读官方文档
2. **通读核心模块**，重点关注：
   - 输入格式（支持哪些文件类型？需要什么预处理？）
   - 输出格式（输出什么样的数据结构？）
   - 支持的功能范围（哪些能力显式提供？）
   - **显式不支持的功能**（同样重要——决定是否需要额外组件）
   - 依赖清单（是否引入了不相关的重型库？）
3. 使用 Grep 搜素否定项：搜索组件不包含的能力关键词（如 `pdf|docx|embedding|neo4j|chromadb`）
4. **将结论写入项目 Memory**（`.claude/projects/<project>/memory/`）

#### 产出

- 能力边界评估 Memory 条目（每类组件一份），包含：
  - 一句话能力边界描述
  - 显式支持的能力列表
  - 显式不支持的能力列表
  - 关键文件/函数路径

#### 验证标准

能否用一句话说清楚每个候选组件的核心能力边界？例如：

> "MinerU 负责 PDF/Word/PPT → Markdown + 结构化 JSON 的文档解析，不涉及实体抽取、Embedding 或图谱存储。"

#### 已有可参考的知识

本环境中的 GraphRAG 项目已完成了 MinerU 和 LangExtract 的能力边界评估，你可以直接参考以下成果（但不要照搬——自己通读源码验证一遍）：
- MinerU：PDF/Word/PPT/Excel/HTML/EPUB → `full.md` + `content_list.json` + `layout.json`（不含抽取/索引/检索）
- LangExtract：纯文本 → 结构化实体/关系/事件抽取（不含文档解析/Embedding/索引/数据库）

---

### Layer 1: 文档解析引擎 MVP 实测

**目标**：用最小可行测试验证文档解析引擎的核心能力。

#### 做什么

1. 在项目根目录下创建 `document-parser-mvp/` 独立目录
2. 使用 `uv` 初始化独立虚拟环境：`uv venv .venv --python 3.12`
3. 安装最小依赖（仅 MVP 必需的 HTTP 客户端和文件处理库）
4. 创建 `.env` 管理 API Key/Token，创建 `.env.example` 模板
5. 配置 `.gitignore`（排除 `.venv/`、`.env`、`output/`）
6. 创建组件的 `CLAUDE.md`（记录环境激活、运行命令）
7. 准备 3 种最小测试数据：
   - 1 个 **PDF 文件**（含文字、表格、图片）
   - 1 个 **Word 文件**（`.docx`，含标题层级和表格）
   - 1 个 **PPT 文件**（`.pptx`，含多页文字和图表）
8. 编写 MVP 脚本（`run_mvp.py`），只验证核心链路：
   - 输入文件 → 调用解析 API/库 → 获取结构化输出
9. 实际运行测试，**保留实测输出文件作为证据**
10. 基于实测结果，生成**文档解析引擎规范文档 v1**

#### 规范文档应包含

- 支持的输入文件格式列表（标注是文档说的还是实测验证的）
- 每个格式的实测输出结构（JSON schema、字段说明、示例）
- 输出文件清单（ZIP 包含哪些文件、各自用途）
- 关键参数说明（哪些是必传、哪些影响输出质量）
- 实测参数推荐组合（标准文档 / 扫描件 / 高精度 / 办公文档 各自场景）
- **实测与官方文档的差异标注**（以实测为准）

#### 关键原则

- MVP 越小越好——能用 3 个 sample 文件验证的就不要用 30 个
- 配置信息永远放在 `.env`，绝不硬编码
- 规范文档必须基于**实测结果**，不是基于文档猜测
- 如果实测结果与官方文档不一致，以实测为准并在规范文档中标注

#### 产出

- `document-parser-mvp/` 目录（含 `.venv`、`.env.example`、`CLAUDE.md`、`run_mvp.py`）
- 文档解析引擎规范文档 v1（有实测数据支撑）

---

### Layer 2: 实体关系抽取引擎 MVP 实测

**目标**：用最小可行测试验证信息抽取组件的核心能力。

#### 做什么

1. 在项目根目录下创建 `entity-extraction-mvp/` 独立目录
2. 使用 `uv` 初始化**新的独立虚拟环境**（与 Layer 1 完全隔离）
3. 安装最小依赖
4. 创建 `.env`（LLM API Key）、`.env.example`、`.gitignore`、`CLAUDE.md`
5. 准备测试数据：从 Layer 1 的实测输出中提取 **Markdown 格式的纯文本**（模拟文档解析后的文本输入）
6. 编写 MVP 脚本，验证核心链路：
   - 纯文本输入 → 调用抽取 API → 结构化实体 + 关系列表
7. 基于实测结果，生成**实体抽取引擎规范文档 v1**

#### 规范文档应包含

- 支持的输入格式（纯文本 / Markdown / JSON / 其他）
- 输出格式（实体 schema：id、type、name、properties；关系 schema：source、target、type、evidence）
- 支持的实体类型和关系类型（Schema 定义）
- LLM Provider 配置（OPENAI_API_KEY 等）
- 实测输出示例
- 已知局限（如最大输入长度、不支持的文件格式等）

#### 特别注意

- 组件 B 必须使用**独立虚拟环境**，与 Layer 1 的文档解析组件隔离
- 规范文档的格式应与 Layer 1 保持一致（方便后续桥接）
- **此时不要试图让两个组件通信**——那是 Layer 3 的事
- 实测输入应直接取自 Layer 1 的输出（模拟真实 Pipeline 上下游关系）

#### 产出

- `entity-extraction-mvp/` 目录（含独立 `.venv`、配置、测试脚本）
- 实体抽取引擎规范文档 v1（有实测数据支撑）

---

### Layer 3: 桥接管道（多份规范联动）

**目标**：让文档解析引擎和实体抽取引擎通过格式转换桥接起来，形成完整的文档→图谱 pipeline。

#### 做什么

1. 将 Layer 1 和 Layer 2 的规范文档作为**只读上游约束**（显式引用）
2. 定义从文档解析输出到实体抽取输入的格式转换规则：
   - 从 `content_list.json` 提取纯文本内容
   - 按 section/page 分段策略
   - 保留位置信息（page_idx、bbox）用于后续追溯
3. 定义 Pipeline 各阶段的输入/输出 schema：
   ```
   Stage 1: PDF/Word/PPT → MinerU 解析 → full.md + content_list.json + layout.json
   Stage 2: content_list.json → 按 section 分段 → List[TextChunk]
   Stage 3: TextChunk → 实体抽取 → List[Entity] + List[Relation]
   Stage 4: Entity + Relation → 位置映射（文本位置 → 页面/bbox） → PositionedEntity
   Stage 5: Entity + Relation → 图数据库导入 → Knowledge Graph
   ```
4. 编写 Bridge Pipeline 代码（放在 `integration/` 目录）：
   - `pipeline.py`（主线编排）
   - `document_parser.py`（封装 Layer 1 组件）
   - `entity_extractor.py`（封装 Layer 2 组件）
   - `position_mapper.py`（位置追溯映射）
   - `kg_builder.py`（图谱构建）
5. 支持 `--cached` 模式：跳过已完成的 Stage，只重新执行下游（方便独立调试）
6. 端到端测试：从原始文档到图谱节点的完整链路验证

#### 桥接规范文档应包含

- 数据流图（Pipeline stage 拓扑）
- 每个 Stage 的输入/输出 JSON schema
- 格式转换规则（MinerU content_list → LangExtract text 的映射表）
- 位置映射算法说明（字符 offset → page_idx + bbox 的反向查找）
- 缓存策略说明

#### 验证标准

从原始文档（PDF/Word/PPT）输入到知识图谱节点/边的完整链路可追溯，每一阶段的中间产物有 schema 约束，Pipeline 的 `--cached` 模式可跳过上游独立运行下游。

#### 产出

- `integration/` 目录（含 Pipeline 代码 + 端到端测试）
- BridgePipeline 规范文档（显式引用 Layer 1 + Layer 2 规范文档）

---

### Layer 4: 外部知识引入

**目标**：引入知识图谱构建和 RAG 问答所需的外部框架知识，设计完整技术架构。

#### 做什么

1. **确定需要的外部框架/工具**：
   - 图数据库客户端（Neo4j Python Driver）
   - 向量数据库客户端（ChromaDB / FAISS）
   - LLM 框架（OpenAI SDK / Anthropic SDK / LangChain）
2. **安装对应的 MCP 工具**（如 LangChain MCP）
3. **进行连通性测试**（确认能连接到 Neo4j、ChromaDB、LLM API）
4. 基于 Layer 3 的桥接 Pipeline 输出，设计完整技术架构：
   - 数据流：文档上传 → 解析 → 抽取 → 图谱存储 → 向量化 → 检索 → 生成回答
   - 服务拓扑：API Gateway / 前端 / 文档解析服务 / 抽取服务 / 图谱服务 / 向量服务 / LLM 代理
5. 编写 MVP 验证代码（如 `agentic_kg_rag_mvp.py`），验证端到端问答链路
6. 将验证结果反哺回 BridgePipeline 规范文档

#### 技术架构方案文档应包含

- 整体架构图（服务拓扑 + 数据流）
- 各组件选型依据和理由（不是凭感觉，要有具体理由）
- 接口协议规范（RESTful API vs gRPC vs 直接调用）
- 数据存储方案（图数据库 schema + 向量数据库 collection 设计）
- 检索策略（混合检索：关键词 + 向量 + 图谱遍历）
- 安全与权限方案

#### 验证标准

有一个端到端的 MVP 验证脚本，能从文档解析结果中构建图谱，并通过图谱检索回答问题。

#### 产出

- MCP 连通性验证记录
- 技术架构方案文档
- MVP 验证脚本（`agentic_kg_rag_mvp.py`）

---

### Layer 5: 产品/架构蓝图

**目标**：在写任何产品代码之前，把产品设计、后端架构、前端设计全部以规范文档形式确定下来。**这是施工前最后一次可以低成本修改架构的机会。**

#### 按以下顺序编写三份文档（顺序重要——每份依赖上一份）

---

#### 5a. 产品需求文档（PRD）

**内容要求**：

1. **产品定义**：一句话描述产品是什么、解决什么问题
2. **用户角色**：普通用户、管理员（如需要）
3. **用户流程**（从打开页面到完成任务的完整路径）：
   - 上传文档流程：选择文件 → 预览 → 确认上传 → 查看解析进度 → 查看图谱
   - 知识问答流程：输入问题 → 查看检索过程 → 阅读 AI 回答 → 查看引用源
   - 图谱浏览流程：搜索实体 → 展开关系 → 查看详情 → 跳转原文位置
4. **页面/模块清单**（每个标注 P0/P1/P2 优先级）：
   - P0（必须有）：文档上传与管理、知识图谱可视化、自然语言问答
   - P1（应该有）：文档解析状态追踪、实体/关系详情面板、源文档定位
   - P2（可以有）：批量导入、图谱编辑、导出共享、权限管理
5. **核心交互逻辑**：每个页面的交互流程、状态转换、边界条件

---

#### 5b. 后端 API 架构规范

**内容要求**：

1. **系统架构总览图**：服务拓扑（API Gateway + 各微服务/模块）
2. **服务拓扑与部署方案**：各服务的端口、依赖关系、启动顺序
3. **RESTful API 端点列表**，每个包含：
   - method + path
   - request body/params schema（JSON schema 格式）
   - response body schema
   - 错误响应格式
4. **数据模型定义**：
   - Document（id, name, type, upload_time, parse_status, pages, chunks）
   - Entity（id, name, type, properties, source_doc, source_position）
   - Relation（id, source_entity, target_entity, type, evidence, source_doc）
   - Conversation（id, messages, referenced_entities, referenced_docs）
5. **异步任务状态机**（文档解析为异步任务）：
   ```
   pending → queued → parsing → extracting → building_graph → done
                                                      ↘ failed
   ```
6. **错误处理规范**：统一的错误码体系、错误响应格式
7. **实施路线**：按 P0 → P1 → P2 的优先级拆分开发阶段

---

#### 5c. 前端系统设计规范

**内容要求**：

1. **前端架构分层**：页面层 → 组件层 → 状态管理层 → API 层
2. **UI 布局风格**：颜色方案、字体体系、间距规范、暗色/亮色模式
3. **完整页面清单 + 组件树**：
   - 文档管理页 → UploadZone, DocList, DocCard, ParseStatusBadge
   - 图谱浏览页 → GraphCanvas, SearchBar, EntityPanel, RelationPanel, FilterBar
   - 知识问答页 → ChatPanel, MessageBubble, SourceReference, SearchPreview
4. **详细交互逻辑**：每个组件的状态定义、事件处理、loading/empty/error 状态
5. **数据流与状态管理方案**：
   - 全局状态：当前用户、已选文档、图谱查询状态
   - 局部状态：表单输入、UI 展开/折叠
   - API 请求状态：loading、data、error 三态
6. **技术选型**：框架（React/Vue）、构建工具（Vite）、UI 库、图谱可视化库（D3.js/vis-network/Cytoscape.js）、状态管理（Zustand/Pinia）
7. **响应式适配方案**：桌面端优先，图谱布局的自适应策略

#### 三份文档验证标准

任意两个开发人员分别读这三份文档，对系统设计应达成一致理解。三份文档之间不应有任何矛盾——前端组件依赖的每个 API 端点都在 Backend API Spec 中有明确定义，每个后端 API 的功能都在 PRD 中有对应的用户需求。

#### 产出

- `PRD-v1.0.md`（产品需求文档）
- `Backend-API-Architecture-v1.0.md`（后端 API 架构规范）
- `Frontend-System-Design-v1.0.md`（前端系统设计规范）

---

### Layer 6: 项目开发规范确立

**目标**：确立项目的工程纪律，所有后续施工行为受这些规则约束。这是驾驭工程的"宪章"。

#### 核心规范（4 条铁律）

1. **前端所有代码统一放在 `frontend/` 文件夹下**
2. **后端所有代码统一放在 `backend/` 文件夹下**
3. **后端敏感配置（API Key 等）统一在 `.env` 文件管理，`.env` 必须加入 `.gitignore`**
4. **后端服务必须使用 `uv` 创建独立虚拟环境**

#### 附加规范（根据项目需要）

- **环境隔离架构**：各组件目录 + 虚拟环境的关系：
  ```
  project-root/
  ├── frontend/                     # 前端（npm/pnpm 管理）
  ├── backend/                      # 后端服务
  │   └── .venv/                    # 后端专用虚拟环境
  ├── document-parser-mvp/          # 文档解析 MVP（独立 .venv）
  ├── entity-extraction-mvp/        # 实体抽取 MVP（独立 .venv）
  ├── integration/                  # 桥接管道
  │   └── .venv/                    # 集成测试虚拟环境
  ├── .env                          # 全局敏感配置（.gitignore）
  ├── .gitignore                    # 排除 .venv/ .env output/
  └── CLAUDE.md                     # 项目宪章
  ```
- **数据库 schema 管理方式**：使用 migration 工具（如 Alembic）管理图数据库和向量数据库的 schema 变更
- **Git 分支策略**：`main`（稳定）/ `develop`（集成分支）/ `feature/<name>`（功能分支）
- **Commit message 格式**：`<type>: <description>`（type: feat/fix/docs/refactor/test）

#### CLAUDE.md 必须包含

- 项目概述（一句话说明项目是什么）
- 虚拟环境隔离规范（激活方式 + 验证方式 + 首次创建方式）
- 项目文件结构（完整目录树）
- 环境约束规则（启动前要做什么、依赖变更流程）
- 规范文档索引（列出所有 Layer 0-5 产出的文档路径 + 简要说明）
- 常用命令（启动前端/后端/测试/数据库）

#### 产出

- 项目根目录的 `CLAUDE.md`（含完整环境约束规则 + 规范文档索引）
- 各组件的 `CLAUDE.md`
- 项目级 `.gitignore`

---

### Layer 7: 前后端施工 + 联调闭环

**目标**：严格按照 Layer 5 的蓝图和 Layer 6 的规范，完成前后端代码实现，并通过联调验证完整用户流程。

#### 施工顺序：先前端、后后端、再联调

原因：前端可以先 mock 数据独立开发验证界面和交互，后端接口开发好后再替换 mock，降低联调时期的阻塞。

---

#### 7a. 前端施工

1. 基于 PRD + Frontend Design Spec，编写前端代码
2. **先 mock 后端数据**（模拟 API 返回），验证页面渲染和交互逻辑
3. 前端代码放入 `frontend/` 目录
4. 验证前端可独立启动（`npm run dev` / `pnpm dev`）

#### 7b. 后端施工

1. 基于 Backend API Spec，编写后端代码
2. 后端代码放入 `backend/` 目录
3. 使用 `uv` 创建独立虚拟环境并安装依赖
4. 数据库初始化（Neo4j schema + ChromaDB collection）
5. 挂载 BridgePipeline（文档解析 → 实体抽取 → 图谱构建）
6. 实现知识问答的检索与生成逻辑
7. 验证后端可独立启动

#### 7c. 联调

1. 启动后端服务
2. 启动前端开发服务器
3. 从前端发起真实用户操作，追踪完整数据流：
   - 上传 PDF → 查看解析进度 → 解析完成
   - 查看知识图谱 → 展开实体 → 查看关系
   - 输入问题 → 获得基于图谱的回答 → 查看引用源
4. 记录每个发现的 Bug
5. Bug 修复后，检查是否需要在规范文档中补充说明

#### 7d. 审查

对施工代码进行全面审查，覆盖以下维度：
- **代码规范**：命名、注释、代码复用
- **逻辑漏洞**：边界条件、空值处理、异步时序
- **安全风险**：注入攻击、敏感信息泄露、权限校验
- **性能问题**：N+1 查询、内存泄漏、不必要的前端渲染
- **业务匹配度**：每个 API 端点是否与 Backend API Spec 一致，每个组件是否与 Frontend Design Spec 一致

---

### 验证标准（终极验收）

从文档上传到知识图谱可视化再到自然语言问答的完整用户流程可走通：

1. 上传一个 PDF/Word/PPT →
2. 系统返回解析进度（pending → done） →
3. 知识图谱可视化页面展示抽取的实体和关系 →
4. 用户在问答界面输入"这份文档讲了什么？" →
5. 系统返回基于图谱的准确回答，附引用源（原文段落 + 页面位置）

---

## 关键原则总结

| 原则 | 说明 |
|---|---|
| **MVP 优先于完美** | Layer 0-2 不要追求完美，50 行跑通的脚本比 500 行的完整实现更有价值 |
| **规范文档是唯一真相源** | 代码行为与规范不一致时，要么改代码要么改规范，不允许双轨并存 |
| **每次迭代都沉淀** | 每轮测试后问自己：是否有新认知需要写入规范文档？ |
| **施工严格参照蓝图** | Layer 7 的每个端点/组件都应能追溯到 Layer 5 的定义 |
| **环境隔离是纪律** | 每个独立组件使用独立 `uv` 虚拟环境，不混用依赖 |

---

## 禁止跳步的常见反模式

| 反模式 | 后果 |
|---|---|
| 跳过 Layer 0 直接写代码 | 做到一半发现组件不支持需要的能力，推倒重来 |
| Layer 2 就试图桥接两个组件 | 调试时无法判断是哪个组件的问题 |
| 规范文档基于猜测而非实测 | 实际运行时发现 API 返回格式与文档描述不符 |
| Layer 5 蓝图跳过直接施工 | 前后端接口对不上，遗漏关键功能 |
| 规范文档更新滞后于代码 | 后来的开发者（包括自己）只能读代码理解意图 |
| 跳过审查直接交付 | "看起来能跑" =/= 真的能跑 |

---

## 下一步行动

现在，请从 **Layer 0** 开始：为上述 5 类候选组件（文档解析、实体抽取、图谱存储、向量检索、LLM 服务）逐一进行能力边界摸底。每完成一个组件的评估，将结论写入项目 Memory，然后进入 Layer 1。
