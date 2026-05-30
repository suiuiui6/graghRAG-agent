# GraphRAG 问答系统整合方案

> 基于驾驭工程（harness-engineering）8 层递进方法论，针对"已有 MinerU + LangExtract 两个独立服务，需整合为 RAG 问答系统"的场景。

---

## 一、当前状态评估

你现在处于驾驭工程方法论中的**关键转折点**。根据已有产出判断：

| 层次 | 内容 | 状态 |
|---|---|---|
| Layer 0 | 能力边界摸底（LangExtract 能力边界、MinerU 部署配置） | 已完成 |
| Layer 1 | MinerU MVP 实测（API 规范文档、MVP 测试指南） | 已完成 |
| Layer 2 | LangExtract MVP 实测（Pipeline 规范文档、DeepSeek 实测） | 已完成 |
| Layer 3 | 桥接管道（BridgePipeline 规范文档、端到端实测、KG 输出） | 已完成 |
| Layer 4 | 外部知识引入（Agentic KG-RAG 规范、LangGraph Agent 实测） | 已完成 |
| **Layer 5** | **产品/架构蓝图（PRD + 后端 API + 前端设计）** | **待做** |
| **Layer 6** | **项目开发规范确立（根目录 CLAUDE.md）** | **待做** |
| **Layer 7** | **前后端施工 + 联调闭环** | **待做** |

你已经完成了底层能力的验证和组件对接（Layer 0-4），现在需要**向上构建面向用户的产品层**。

---

## 二、目录结构建议

基于驾驭工程的目录规范原则（前端统一 `frontend/`，后端统一 `backend/`，已有组件保持不变），推荐如下目录结构：

```
D:\graghRAG-agent\
│
├── CLAUDE.md                          ← Layer 6: 项目根规范（环境约束+文档索引）
├── .gitignore                         ← 排除 .env, .venv, __pycache__, node_modules
├── .env.example                       ← 环境变量模板（不含真实密钥）
│
├── langextract\                       ← [已有] LangExtract 组件，独立 .venv
│   ├── .venv\
│   ├── CLAUDE.md
│   ├── docs\
│   │   ├── LangExtract-Pipeline-Specification.md
│   │   ├── MinerU-API-Specification.md
│   │   ├── MinerU_MVP测试配置指南.md_v1.0.md
│   │   ├── bridge-pipeline-specification-v1.0.md
│   │   └── agentic-kg-rag-specification-v1.0.md
│   └── ...
│
├── mineru-mvp-test\                   ← [已有] MinerU 组件，独立 .venv
│   ├── .venv\
│   └── ...
│
├── integration\                       ← [已有] BridgePipeline + Agentic KG-RAG
│   ├── pipeline.py
│   ├── bridge.py
│   ├── grounding.py
│   ├── kg_builder.py
│   ├── agentic_rag_mvp.py
│   ├── schema.py
│   ├── .env
│   ├── config\
│   │   └── extraction_examples.yaml
│   └── output\
│       └── kg\
│           ├── nodes.json
│           └── edges.json
│
├── backend\                           ← [新建] Layer 5b + Layer 7b: 后端服务
│   ├── .venv\                         ← uv 独立虚拟环境
│   ├── CLAUDE.md
│   ├── requirements.txt
│   ├── app\
│   │   ├── main.py                    ← FastAPI 入口
│   │   ├── config.py                  ← 配置管理（从 .env 加载）
│   │   ├── routers\
│   │   │   ├── upload.py              ← POST /api/upload  文档上传
│   │   │   ├── parse.py               ← POST /api/parse   解析任务
│   │   │   ├── extract.py             ← POST /api/extract 实体抽取
│   │   │   ├── build_kg.py            ← POST /api/kg/build 图谱构建
│   │   │   ├── query.py               ← POST /api/query   RAG 问答
│   │   │   └── tasks.py               ← GET  /api/tasks/{id} 任务状态
│   │   ├── services\
│   │   │   ├── mineru_service.py      ← 封装 MinerU API 调用
│   │   │   ├── langextract_service.py ← 封装 LangExtract 抽取逻辑
│   │   │   ├── pipeline_service.py    ← 编排 BridgePipeline
│   │   │   ├── rag_service.py         ← Agentic KG-RAG 问答
│   │   │   └── storage_service.py     ← 文件存储/缓存管理
│   │   ├── models\
│   │   │   ├── task.py                ← 任务状态机模型
│   │   │   ├── document.py            ← 文档模型
│   │   │   └── query.py               ← 问答请求/响应模型
│   │   └── db\
│   │       ├── database.py            ← SQLite / PostgreSQL 连接
│   │       └── models.py              ← ORM 模型（tasks, documents, queries）
│   ├── tests\
│   │   ├── test_upload.py
│   │   ├── test_parse.py
│   │   ├── test_query.py
│   │   └── conftest.py
│   └── .env                           ← 后端敏感配置（不入 git）
│
├── frontend\                          ← [新建] Layer 5c + Layer 7a: 前端界面
│   ├── package.json
│   ├── CLAUDE.md
│   ├── src\
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── api\
│   │   │   └── client.ts             ← Axios 封装，对接后端 API
│   │   ├── pages\
│   │   │   ├── UploadPage.tsx         ← 文档上传页
│   │   │   ├── ParseProgressPage.tsx  ← 解析进度页
│   │   │   ├── KGVisualizePage.tsx    ← 图谱可视化页
│   │   │   └── QAPage.tsx             ← 问答交互页
│   │   ├── components\
│   │   │   ├── FileUploader.tsx
│   │   │   ├── ProgressBar.tsx
│   │   │   ├── EntityCard.tsx
│   │   │   ├── KGGraph.tsx            ← 基于 D3.js / vis-network 的图谱渲染
│   │   │   ├── ChatPanel.tsx
│   │   │   └── SourceHighlight.tsx    ← 溯源高亮组件
│   │   └── styles\
│   │       └── global.css
│   ├── public\
│   └── .env                           ← API_BASE_URL 等前端配置
│
├── docs\                              ← [新建] Layer 5 蓝图文档集中存放
│   ├── PRD.md                         ← 产品需求文档
│   ├── backend-api-spec.md            ← 后端 API 架构规范
│   └── frontend-design-spec.md        ← 前端系统设计规范
│
└── memory\                            ← 项目 Memory（.claude 体系）
    ├── project_langextract_capability_boundary.md
    ├── reference_mineru_deployment_config.md
    ├── project_env_isolation.md
    └── MEMORY.md
```

---

## 三、执行顺序：先做什么后做什么

按照驾驭工程方法论，必须严格按层次推进。以下是针对你的具体情况的执行路线图：

### 阶段 1: 产品/架构蓝图（Layer 5）—— 立即开始

这是你当前所在的阶段。在写任何产品代码之前，先把三份蓝图文档写清楚。

#### 1a. 编写 PRD（产品需求文档）

以 `docs/PRD.md` 形式沉淀，至少覆盖：

- **产品定义**：这是一个"文档上传 -> 自动解析 -> 知识图谱构建 -> 自然语言问答"的 RAG 系统。
- **用户角色**：知识工作者（研究员、分析师、医生），需要从大量 PDF 中快速提取结构化知识并提问。
- **核心用户流程**：
  1. 用户上传 PDF/DOCX 文档
  2. 系统自动调用 MinerU 解析为 Markdown + 结构化 JSON
  3. 系统自动运行 BridgePipeline，将解析结果分段、抽取实体、构建知识图谱
  4. 用户在前端看到图谱可视化，可在图谱中浏览实体
  5. 用户在问答面板输入自然语言问题，Agent 遍历图谱返回可溯源答案
- **页面/模块清单**：
  - 文档上传页
  - 解析任务进度页
  - 知识图谱可视化页
  - 问答交互页
- **非功能性需求**：响应时间目标、并发用户数、文件大小上限等。

#### 1b. 编写后端 API 架构规范

以 `docs/backend-api-spec.md` 形式沉淀，至少覆盖：

- **服务拓扑**：
  ```
  Frontend (React) ──HTTP──> Backend (FastAPI) ──内部调用──> MinerU API
                                                              LangExtract
                                                              BridgePipeline
                                                              Agentic KG-RAG
                                   │
                                   └── SQLite / PostgreSQL（任务状态、历史记录）
  ```
- **API 端点清单**（需逐个定义 Request/Response schema）：
  - `POST /api/upload` -- 文档上传
  - `POST /api/parse` -- 启动 MinerU 解析任务
  - `GET /api/tasks/{task_id}` -- 查询任务状态
  - `POST /api/kg/build` -- 启动知识图谱构建
  - `POST /api/query` -- RAG 问答
  - `GET /api/documents` -- 文档列表
  - `GET /api/documents/{id}/entities` -- 文档实体列表
  - `GET /api/documents/{id}/graph` -- 文档图谱数据
- **任务状态机**：
  ```
  uploaded -> parsing -> parsed -> extracting -> extracted -> building_kg -> ready
                   ↘ failed                   ↘ failed                ↘ failed
  ```
- **错误处理规范**：统一的错误响应格式 `{"error": {"code": "...", "message": "..."}}`

#### 1c. 编写前端系统设计规范

以 `docs/frontend-design-spec.md` 形式沉淀，至少覆盖：

- **技术选型**：React + TypeScript + Tailwind CSS（或你偏好的框架）
- **架构分层**：Pages -> Components -> API Client
- **UI 布局**：左侧导航 + 主内容区（上传/进度/图谱/问答四个 Tab 或独立路由）
- **组件树**：从 App 到叶子组件的完整层级
- **数据流**：
  - 上传文件 -> POST /api/upload -> 获得 document_id
  - document_id -> POST /api/parse -> 轮询任务状态 -> 状态变为 ready
  - document_id -> GET /api/documents/{id}/graph -> 渲染图谱
  - 用户问题 -> POST /api/query -> 流式返回答案（含 node_id 引用）
- **图谱可视化需求**：节点按 entity_type 着色、悬停显示详情、点击高亮邻居节点、从节点溯源到 PDF 页面位置

### 阶段 2: 项目开发规范确立（Layer 6）

在 Layer 5 蓝图完成后，**在项目根目录**创建 `CLAUDE.md`，确立工程纪律。必须包含：

1. **4 条铁律**：
   - 前端代码统一放在 `frontend/` 目录
   - 后端代码统一放在 `backend/` 目录
   - 后端敏感配置（API Key 等）统一在 `.env` 文件管理，`.env` 必须加入 `.gitignore`
   - 后端服务使用 `uv` 创建独立虚拟环境

2. **环境约束**：
   - 项目共有 3 个独立虚拟环境：`langextract/.venv`、`mineru-mvp-test/.venv`、`backend/.venv`
   - 启动后端前必须 `source backend/.venv/Scripts/activate`
   - 前端使用 `npm` 管理依赖

3. **规范文档索引**（所有后续施工必须参照）：
   - `docs/PRD.md`
   - `docs/backend-api-spec.md`
   - `docs/frontend-design-spec.md`
   - `langextract/docs/LangExtract-Pipeline-Specification.md`
   - `langextract/docs/MinerU-API-Specification.md`
   - `langextract/docs/bridge-pipeline-specification-v1.0.md`
   - `langextract/docs/agentic-kg-rag-specification-v1.0.md`

4. **Git 规范**：分支策略、commit message 格式

### 阶段 3: 后端施工（Layer 7b）

严格按照 `docs/backend-api-spec.md` 实现。核心工作：

1. 创建 `backend/.venv`，安装 FastAPI + uvicorn + sqlite 依赖
2. 实现 `config.py`：从 `.env` 加载 MinerU Token、DeepSeek API Key 等
3. 实现 `services/` 层的 5 个服务模块，**复用已有的 integration/ 代码**：
   - `mineru_service.py` 直接调用已有的 MinerU API 逻辑
   - `langextract_service.py` 封装 LangExtract 抽取调用
   - `pipeline_service.py` 编排已有的 `bridge.py` + `kg_builder.py`
   - `rag_service.py` 封装已有的 `agentic_rag_mvp.py` 逻辑
4. 实现 `routers/` 层的 REST API 端点
5. 实现数据库模型（存储任务状态、历史记录，注意 KG 数据保持文件存储即可）
6. 编写 `backend/tests/` 下的测试用例

### 阶段 4: 前端施工（Layer 7a）

严格按照 `docs/frontend-design-spec.md` 实现：

1. 初始化 React 项目（Vite + TypeScript + Tailwind CSS）
2. 实现 API Client 层
3. 实现 4 个页面组件
4. 实现图谱可视化组件（使用 vis-network 或 cytoscape.js，从 `nodes.json` / `edges.json` 格式渲染）
5. 实现 ChatPanel 问答组件（支持流式响应）
6. 验证前端可独立启动（使用 mock 数据）

### 阶段 5: 联调闭环（Layer 7c）

1. 启动后端 `uvicorn app.main:app --reload`
2. 启动前端 `npm run dev`
3. 走通完整用户流程：上传 PDF -> 等待解析 -> 查看图谱 -> 提问 -> 获得可溯源答案
4. 每个 Bug 修复后，检查是否需要在规范文档中补充说明

### 阶段 6: 代码审查（Layer 7d）

使用审查 agent 对施工代码进行全面检查：代码规范、逻辑漏洞、安全风险、性能问题、业务匹配度。

---

## 四、需要哪些规范文档

按照驾驭工程方法论，一个完整的整合项目最终应包含以下规范文档体系：

### 已有文档（Layer 0-4 产物，无需重复创建）

| 文档 | 位置 | 作用 |
|---|---|---|
| LangExtract 能力边界评估 | `memory/project_langextract_capability_boundary.md` | 明确 LangExtract 的能力边界和不支持的功能 |
| MinerU 部署配置需求 | `memory/reference_mineru_deployment_config.md` | MinerU 三种部署方式的 API Key 配置 |
| MinerU API 规范文档 | `langextract/docs/MinerU-API-Specification.md` | 输入/输出格式、布局信息、MVP 必传参数 |
| MinerU MVP 测试配置指南 | `langextract/docs/MinerU_MVP测试配置指南.md_v1.0.md` | Pipeline 执行流程、参数规范、代码路径 |
| LangExtract Pipeline 规范 | `langextract/docs/LangExtract-Pipeline-Specification.md` | 输入/输出格式、DeepSeek 配置、关键参数 |
| BridgePipeline 规范 | `langextract/docs/bridge-pipeline-specification-v1.0.md` | MinerU->LangExtract 桥接管道完整规范 |
| Agentic KG-RAG 规范 | `langextract/docs/agentic-kg-rag-specification-v1.0.md` | LangGraph Agent 问答系统规范 |

### 需要新建的文档（Layer 5-6 产物）

| 文档 | 位置 | 作用 | 优先级 |
|---|---|---|---|
| **PRD（产品需求文档）** | `docs/PRD.md` | 定义产品功能、用户流程、页面清单 | 高 |
| **后端 API 架构规范** | `docs/backend-api-spec.md` | 定义所有 API 端点、数据模型、任务状态机、错误处理 | 高 |
| **前端系统设计规范** | `docs/frontend-design-spec.md` | 定义前端架构分层、UI 布局、组件树、数据流 | 高 |
| **项目根 CLAUDE.md** | `CLAUDE.md`（项目根目录） | 确立工程纪律：目录规范、环境隔离、.env 管理、规范文档索引 | 高 |

### 可选补充文档

| 文档 | 位置 | 作用 | 优先级 |
|---|---|---|---|
| 部署运维指南 | `docs/deployment-guide.md` | Docker Compose 配置、环境变量清单、健康检查 | 中 |
| 数据流详解 | `docs/data-flow.md` | 从 PDF 上传到最终问答的完整数据流图 | 低 |

---

## 五、关键风险提示

1. **不要跳过 Layer 5 直接写代码**。三份蓝图文档（PRD + 后端 API + 前端设计）是你施工的"施工图"。没有它们就开始写代码，后期必然返工。这是驾驭工程方法论最核心的纪律。

2. **后端服务独立 venv，不要混用**。`backend/` 需要自己独立的 `.venv`，不要直接复用 `langextract/.venv` 或 `integration/` 目录。可以把 `integration/` 中的核心逻辑作为内部库 import，但依赖管理必须独立。

3. **规范文档是唯一真相源**。当后端代码行为与 `backend-api-spec.md` 不一致时，必须修正其中之一。不允许"代码和文档各说各话"。

4. **MVP 优先**。第一个版本不需要完美。能用单页应用上传 PDF 并看到图谱 + 问一个问题得到答案，就是成功的 MVP。后续再迭代增强。

5. **环境隔离纪律**。项目最终会有 4 个独立的 Python 环境（langextract、mineru-mvp-test、integration、backend）。命名清晰、文档明确，避免开发者在错误的环境中执行命令。

---

## 六、总结

你现在需要立即开始 **Layer 5：产品/架构蓝图** 阶段。用三份规范文档（PRD、后端 API 规范、前端设计规范）把"RAG 问答系统"的产品形态和架构设计清楚，再进入 Layer 6（项目规范）和 Layer 7（代码施工）。

你的优势是底层能力（Layer 0-4）已经充分验证：MinerU 能把 PDF 转成结构化 Markdown，LangExtract 能从文本中抽取结构化实体，BridgePipeline 能把两者串联并生成知识图谱，Agentic KG-RAG 能基于图谱回答可溯源问题。现在需要做的是用一个产品化的壳把这些能力包装起来。
