# 从两个独立服务到完整 RAG 问答系统 — 驾驭工程整合方案

> 适用场景：已有 MinerU 文档解析服务 + LangExtract 实体抽取服务，需整合为 RAG 问答系统
> 方法论：驾驭工程 8 层递进流程

---

## 一、当前状态诊断：你已经在哪里

根据驾驭工程方法论，你并非从零开始。MinerU 和 LangExtract 的能力边界评估（Layer 0）和 MVP 实测（Layer 1/2）已经完成，这意味着核心组件的输入输出契约已经明确。接下来的工作是 Layer 3 到 Layer 7：

| 层级 | 内容 | 你的状态 |
|------|------|---------|
| Layer 0 | 能力边界摸底 | 已完成 — 两组件能力边界清晰 |
| Layer 1 | MinerU MVP 实测 | 已完成 — MinerU API Spec 和 MVP 测试配置就绪 |
| Layer 2 | LangExtract MVP 实测 | 已完成 — LangExtract Pipeline 规范就绪 |
| **Layer 3** | 桥接管道 | **下一步从这里开始** |
| Layer 4 | 外部知识引入 | 待进行 |
| Layer 5 | 产品/架构蓝图 | 待进行 |
| Layer 6 | 项目开发规范确立 | 待进行 |
| Layer 7 | 前后端施工+联调 | 待进行 |

---

## 二、推荐目录结构

在进入 Layer 3 之前，先确立整个项目的目录结构。以下是驾驭工程推荐的完整目录布局：

```
D:\graghRAG-agent\                      ← 项目根目录
│
├── .claude/                            ← Claude Code 配置
│   ├── settings.json                   ← 项目级权限/配置
│   ├── agents/                         ← Layer 6 部署的三个 Agent
│   │   ├── chatbot-planner.md
│   │   ├── chatbot-coder.md
│   │   └── chatbot-reviewer.md
│   └── projects/
│       └── D--graghRAG-agent/
│           └── memory/                 ← 项目长期记忆（能力边界等）
│
├── mineru-mvp-test/                    ← [已有] MinerU 独立环境（Layer 1）
│   ├── .venv/                          ← uv 管理，Python 3.12
│   ├── .env                            ← MinerU API Key（不入 git）
│   ├── .env.example
│   ├── .gitignore
│   ├── CLAUDE.md
│   ├── sample.pdf                      ← 测试用 PDF
│   ├── run_mvp.py                      ← MVP 测试脚本
│   └── output/                         ← 实测输出（不入 git）
│
├── langextract/                        ← [已有] LangExtract 源码 + 独立环境（Layer 2）
│   ├── .venv/                          ← uv 管理，Python 3.12（与 mineru 隔离）
│   ├── .env                            ← LLM API Key（不入 git）
│   ├── .env.example
│   ├── .gitignore
│   ├── CLAUDE.md
│   ├── docs/                           ← 规范文档集中存放
│   │   ├── MinerU-API-Specification.md        ← Layer 1 产物
│   │   ├── MinerU_MVP测试配置指南.md_v1.0.md   ← Layer 1 产物
│   │   ├── LangExtract-Pipeline-Specification.md  ← Layer 2 产物
│   │   ├── bridge-pipeline-specification-v1.0.md  ← Layer 3 产物（待创建）
│   │   └── agentic-kg-rag-specification-v1.0.md   ← Layer 4 产物（待创建）
│   └── ...
│
├── integration/                        ← [核心整合目录] Layer 3~4 代码 + Layer 5 蓝图
│   ├── .env                            ← 合并 MinerU + LangExtract 所需的全部配置
│   ├── CLAUDE.md
│   ├── pipeline.py                     ← 主 Pipeline 编排器
│   ├── bridge.py                       ← 格式桥接（MinerU 输出 → LangExtract 输入）
│   ├── grounding.py                    ← 溯源解析（char 位置 → 页面/bbox）
│   ├── kg_builder.py                   ← 知识图谱构建（entity → node + edge）
│   ├── schema.py                       ← 各阶段数据类/类型定义
│   ├── config/
│   │   └── extraction_examples.yaml    ← Few-shot 抽取示例
│   ├── output/                         ← Pipeline 输出（不入 git）
│   │   └── kg/
│   │       ├── nodes.json
│   │       ├── edges.json
│   │       └── integrated_*.jsonl      ← 中间产物
│   │
│   │  ← Layer 5 蓝图文档（放在 integration/ 下，方便 Layer 7 施工时引用）
│   ├── multimodal-rag-prd-v1.0.md             ← PRD
│   ├── backend-api-architecture-v1.0.md        ← 后端 API 架构
│   ├── frontend-system-design-v1.0.md          ← 前端系统设计
│   └── Agentic-RAG-Architecture.md             ← 技术架构方案（Layer 4）
│
├── backend/                            ← [Layer 7 施工产物] 后端代码
│   ├── .venv/                          ← 独立 uv 环境
│   ├── .env                            ← 后端专属配置
│   ├── .env.example
│   ├── .gitignore
│   ├── CLAUDE.md
│   ├── server.py                       ← FastAPI 入口
│   ├── models.py                       ← 数据模型
│   ├── worker.py                       ← 异步任务处理
│   ├── oss_uploader.py                 ← 文件存储
│   ├── routes/                         ← API 路由分层
│   ├── config/                         ← 后端配置
│   ├── output/                         ← 后端运行时输出（不入 git）
│   └── uploads/                        ← 用户上传文件（不入 git）
│
├── frontend/                           ← [Layer 7 施工产物] 前端代码
│   ├── .gitignore
│   ├── CLAUDE.md
│   ├── package.json
│   ├── src/                            ← React/TypeScript 源码
│   │   ├── components/                 ← UI 组件
│   │   ├── pages/                      ← 页面
│   │   ├── hooks/                      ← 自定义 hooks
│   │   ├── services/                   ← API 调用层
│   │   └── types/                      ← TypeScript 类型
│   ├── public/                         ← 静态资源
│   └── dist/                           ← 构建产物（不入 git）
│
├── plans/                              ← 施工计划（可选的临时目录）
├── .gitignore                          ← 根级 gitignore
├── CLAUDE.md                           ← [Layer 6 产物] 项目级规范宪章
└── README.md                           ← 项目说明
```

**关键隔离原则**：
- `mineru-mvp-test/.venv` 和 `langextract/.venv` 和 `backend/.venv` 各自独立，依赖互不干扰
- 所有 `.env` 文件不入 git
- 规范文档统一放在 `langextract/docs/`（可访问性最好）或 `docs/`（项目根级），蓝图文档放在 `integration/`（与施工代码邻近）
- `integration/` 的 Python 代码**共用 `langextract/.venv`**（因为 BridgePipeline 需要 import LangExtract），MinerU 通过 HTTP API 调用，不需要引用其 venv

---

## 三、执行顺序（先做什么，后做什么）

严格按驾驭工程的 8 层递进顺序执行，不跳步。以下是针对你当前状态的详细计划：

### Layer 3 — 桥接管道（当前立即开始）

**目标**：让 MinerU 的输出能自动流转为 LangExtract 的输入，打通从 PDF 到结构化实体的完整链路。

**具体步骤**：

1. **在 `integration/` 下建立 Pipeline 骨架**（如果还没有）：
   - `schema.py` — 定义每个阶段的输入/输出数据类（IngestedDocument, Segment, ExtractionResult, KGNode, KGEdge）
   - `pipeline.py` — 编排 6 个 Stage 的执行顺序和错误处理
   - `bridge.py` — 实现格式转换：Markdown → 按 section 分段 → 纯文本列表
   - `grounding.py` — 实现位置溯源：LangExtract 的 `char_interval` → MinerU 的 `page_idx` + `bbox`
   - `kg_builder.py` — 实现实体到知识图谱的转换

2. **定义 Bridge Pipeline 的 6 个 Stage**：

   | Stage | 输入 | 输出 | 负责文件 |
   |-------|------|------|---------|
   | 1. PDF Ingestion | PDF 文件 | MinerU 解析结果 (JSON, Markdown, 图片) | pipeline.py (调用 MinerU API) |
   | 2. Content Extraction | MinerU 输出目录 | 纯文本 Markdown | bridge.py |
   | 3. Text Segmentation | 全文 Markdown | 按 section 分段的文本列表 | bridge.py |
   | 4. Entity Extraction | 分段文本列表 | 结构化实体列表 (JSONL) | pipeline.py (调用 LangExtract) |
   | 5. Position Mapping | 实体 char_interval + layout.json | 实体 → page_idx + bbox 映射 | grounding.py |
   | 6. KG Construction | 实体列表 + 映射 | nodes.json + edges.json | kg_builder.py |

3. **实现 `--cached` 模式**：允许跳过 Stage 1（MinerU 解析），直接使用已有的 MinerU 输出调试下游逻辑。这对迭代效率至关重要。

4. **端到端测试**：用一个 sample.pdf 跑通全部 6 个 Stage，验证从 PDF 到 nodes.json/edges.json 的完整链路。

5. **生成桥接管道规范文档**（`bridge-pipeline-specification-v1.0.md`）：
   - 必须显式引用 Layer 1 的 MinerU API Spec 和 Layer 2 的 LangExtract Pipeline Spec
   - 每个 Stage 的输入/输出 schema 必须有明确定义
   - 包含完整的 Position Mapping 算法说明（char_interval → page_idx + bbox）
   - 包含端到端实测数据的示例

**产出**：`bridge-pipeline-specification-v1.0.md` + Pipeline 代码 + 端到端测试通过

---

### Layer 4 — 外部知识引入

**目标**：为 RAG 问答系统引入必要的框架知识，设计完整技术架构。

**具体步骤**：

1. **安装所需 MCP 工具**（如 LangChain MCP — 如果后端计划用 LangChain 构建 Agentic RAG）
2. **连通性测试**：确认 MCP 工具可用
3. **设计 Agentic KG-RAG 架构**：
   - 文档上传 → MinerU 解析 → Bridge Pipeline → KG 存储
   - 用户提问 → 实体识别 → KG 检索 → 上下文增强 → LLM 回答
   - 答案溯源（每条答案关联 source node 和 PDF 页码）
4. **编写 MVP 验证脚本**：用硬编码的方式验证 RAG 问答的核心链路可行
5. **生成技术架构方案文档**（`Agentic-RAG-Architecture.md`）：
   - 架构选型要有依据（为什么选这个框架而不是另一个）
   - 严格参照 Layer 3 的 BridgePipeline 输出作为 RAG 的索引数据源

**产出**：`Agentic-RAG-Architecture.md` + MCP 连通性验证 + RAG MVP 脚本验证通过

---

### Layer 5 — 产品/架构蓝图（绝不能跳过）

**目标**：在写任何产品代码（backend/frontend）之前，把三份蓝图文档全部确定下来。

**这是整个流程中最容易被跳过的步骤，也是跳过后代价最大的步骤。**

**按以下顺序编写三份文档**（顺序不能乱 — 每份依赖上一份）：

#### 5a. 产品需求文档（PRD）— `multimodal-rag-prd-v1.0.md`

必须包含：
- **产品定义**：一句话说清楚这个系统是做什么的
- **用户流程**：从打开页面到完成问答的完整操作路径（可用流程图描述）
- **页面清单**：列出所有页面和模块，每个标注 P0/P1/P2 优先级
  - P0: 文档上传页、问答页、知识图谱可视化页
  - P1: 文档管理列表、历史问答记录
  - P2: 用户设置、批量上传
- **核心交互逻辑**：上传后如何触发解析 → 如何在图谱中浏览 → 如何提问
- **产品边界**：V1.0 包含什么、不包含什么

#### 5b. 后端 API 架构规范 — `backend-api-architecture-v1.0.md`

必须包含：
- **系统架构总览图**（服务拓扑：前端 → API Gateway → 任务队列 → Worker）
- **RESTful API 端点列表**（method + path + request body schema + response schema）
  - `POST /api/documents/upload` — 上传文档
  - `GET /api/documents/{id}/status` — 查询处理状态
  - `GET /api/documents` — 文档列表
  - `POST /api/query` — 问答接口
  - `GET /api/graph/{document_id}` — 获取知识图谱数据
- **数据模型定义**（Document, Task, Query, GraphData 的字段和类型）
- **异步任务状态机**（PENDING → PARSING → EXTRACTING → BUILDING_KG → READY → FAILED）
- **错误处理规范**（统一错误响应格式、错误码体系）
- **实施路线**（每个 API 的依赖关系和开发优先级）

#### 5c. 前端系统设计规范 — `frontend-system-design-v1.0.md`

必须包含：
- **前端架构分层**（Pages → Components → Hooks → Services → Types）
- **UI 布局风格**（颜色体系、字体、间距规范）
- **完整页面清单 + 组件树**（每个页面的组件拆解）
- **交互逻辑详述**（文件拖拽上传、图谱力导向图交互、问答流式输出）
- **数据流与状态管理方案**（全局状态 vs 页面状态、API 调用封装）
- **技术选型**（React/Vue, Tailwind/MUI, 状态管理库, 图谱可视化库如 D3.js/Cytoscape.js）
- **响应式适配方案**（桌面端优先还是移动端优先）

**产出**：三份蓝图文档（PRD + Backend API Spec + Frontend Design Spec），三份文档之间没有矛盾

**验证标准**：把三份文档分别给两个开发者看，他们对系统设计应达成一致理解。

---

### Layer 6 — 项目开发规范确立

**目标**：把工程纪律写入项目根目录的 `CLAUDE.md`，形成宪章级别的约束。

**必须包含的 5 条铁律**：

```markdown
1. 前端所有代码统一放在 frontend/ 目录
2. 后端所有代码统一放在 backend/ 目录
3. 后端敏感配置（API Key 等）统一在 .env 文件管理，.env 必须加入 .gitignore
4. 后端服务使用 uv 创建独立虚拟环境
5. 部署 chatbot-planner/coder/reviewer 三个 Agent 配置
```

**项目根目录 `CLAUDE.md` 应包含**：
- 项目概述（一句话 + 技术栈）
- 虚拟环境隔离规范（每个组件激活/验证/创建 venv 的具体命令）
- 项目文件结构图（参照上面第二节的目录结构）
- 环境约束规则（启动前激活哪个 venv、依赖变更流程）
- 规范文档索引（所有 Layer 0-5 产出的文档路径）
- 常用运行命令

**附加规范**（根据项目需要）：
- Git 分支策略（如 main → dev → feature/xxx）
- Commit message 格式（如 Conventional Commits）
- 每个子目录的 CLAUDE.md 也需同步更新

**同时部署 Agent 配置**：
在 `.claude/agents/` 下创建三个 Agent 配置文件（从本 skill 的 `references/agent-templates/` 复制模板后按项目调整）。

**产出**：项目根 `CLAUDE.md` + `.gitignore` + `.claude/agents/` 三个 Agent 配置

---

### Layer 7 — 前后端施工 + 联调闭环

**目标**：按照 Layer 5 的蓝图和 Layer 6 的规范，完成代码实现。

#### 7a. 前端施工

1. 调用 **chatbot-planner** agent，输入 PRD + Frontend Design Spec → 产出实现计划
2. 审查实现计划是否与蓝图一致
3. 调用 **chatbot-coder** agent，输入实现计划 → 生成代码到 `frontend/`
4. 验证前端可独立启动（先 mock 后端数据）

#### 7b. 后端施工

1. 调用 **chatbot-coder** agent，输入 Backend API Spec + 数据模型 → 生成代码到 `backend/`
2. 创建独立 `.venv`：`uv venv .venv --python 3.12`
3. 安装依赖并验证后端可独立启动

#### 7c. 联调

1. 启动后端服务 + 前端开发服务器
2. 从前端发起真实用户操作（上传 PDF → 等待解析 → 浏览图谱 → 提问）
3. 追踪完整数据流，记录每个 Bug
4. Bug 修复后检查是否需要更新规范文档

#### 7d. 审查

调用 **chatbot-reviewer** agent（建议后台运行），审查维度：
- 代码规范（命名、注释、复用）
- 逻辑漏洞（边界条件、空值、异步时序）
- 安全风险（注入、信息泄露、文件上传安全）
- 性能问题（大文件处理、图谱渲染性能）
- 业务匹配度（与蓝图定义的一致性）

**产出**：可运行的前后端系统 + 审查报告 + 联调通过

---

## 四、需要的规范文档清单（按产生顺序）

| 序号 | 文档名称 | 对应 Layer | 存放位置 | 状态 |
|------|---------|-----------|---------|------|
| 1 | 能力边界评估 Memory 条目 | Layer 0 | `.claude/projects/D--graghRAG-agent/memory/` | 已有 |
| 2 | MinerU 部署配置需求 | Layer 0 | `.claude/projects/D--graghRAG-agent/memory/` | 已有 |
| 3 | MinerU-API-Specification.md | Layer 1 | `langextract/docs/` | 已有 |
| 4 | MinerU_MVP测试配置指南.md_v1.0.md | Layer 1 | `langextract/docs/` | 已有 |
| 5 | LangExtract-Pipeline-Specification.md | Layer 2 | `langextract/docs/` | 已有 |
| 6 | bridge-pipeline-specification-v1.0.md | **Layer 3** | `langextract/docs/` | **待创建** |
| 7 | Agentic-RAG-Architecture.md | Layer 4 | `integration/` | 待创建 |
| 8 | multimodal-rag-prd-v1.0.md | Layer 5 | `integration/` | **待创建** |
| 9 | backend-api-architecture-v1.0.md | Layer 5 | `integration/` | **待创建** |
| 10 | frontend-system-design-v1.0.md | Layer 5 | `integration/` | **待创建** |
| 11 | 项目根 CLAUDE.md | Layer 6 | `D:\graghRAG-agent\` | **待创建** |
| 12 | Agent 配置文件 (x3) | Layer 6 | `.claude/agents/` | **待创建** |

---

## 五、关键原则提醒

### MVP 优先于完美
在 Layer 3 的 Bridge Pipeline 阶段，先用一个 sample.pdf 验证端到端链路，不要上来就追求支持所有 11 种文档格式。跑通的 50 行脚本比 500 行的完整实现更有价值。

### 规范文档是唯一真相源
当代码行为与规范文档不一致时，要么改代码、要么改文档，**不允许**两者同时"对"但互不一致。

### 环境隔离是纪律
MinerU 和 LangExtract 的 venv 各自独立，BridgePipeline（integration/）可以共用 LangExtract 的 venv（因为它需要 import LangExtract），但 MinerU 通过 HTTP API 调用，不需要引用其 venv。

### Layer 5 三份蓝图必须按顺序写
PRD 定义"要做什么"、Backend API Spec 定义"后端怎么支持"、Frontend Design Spec 定义"前端怎么呈现"。顺序错了会导致前后矛盾、反复返工。

### 每次迭代都沉淀
每一轮测试或修改后，问自己：是否有新的认知需要写入规范文档？没有的话，这轮迭代只产生了代码，没有产生知识。

---

## 六、总结：你现在应该做的第一件事

从 **Layer 3 桥接管道**开始。具体操作：

1. 在 `integration/schema.py` 中定义 IngestedDocument、Segment、ExtractionResult、KGNode、KGEdge 五个数据类
2. 在 `bridge.py` 中实现 MinerU Markdown 输出 → 按 section 分段 → 纯文本列表的转换
3. 在 `grounding.py` 中实现 LangExtract 的 char_interval → MinerU layout.json 的 page_idx + bbox 映射
4. 在 `kg_builder.py` 中实现实体列表 → nodes.json + edges.json 的转换
5. 在 `pipeline.py` 中编排完整 6 阶段流程，并实现 `--cached` 模式
6. 跑通第一个端到端测试
7. 将以上结论写入 `bridge-pipeline-specification-v1.0.md`

完成后，Layer 4~7 严格按上述顺序推进，不跳步。
