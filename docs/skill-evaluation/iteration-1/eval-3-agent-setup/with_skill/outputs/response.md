# 三大 Agent 配置与前后端开发工作流指南

## 一、当前状态确认

你的项目 `D:\graghRAG-agent` 中**已经存在**三个 Agent 的配置文件，位于：

```
D:\graghRAG-agent\.claude\agents\
├── chatbot-planner.md    (前端产品架构师)
├── chatbot-coder.md      (全栈开发工程师)
├── chatbot-reviewer.md   (代码审查专家)
```

这些文件是从驾驭工程 skill 的 `references/agent-templates/` 模板复制而来的默认配置，**基本可用**，但部分细节需要根据你的项目实际情况微调。

---

## 二、需要调整的配置项

### 2.1 chatbot-coder.md 需要修改 2 处

**问题 1 -- 颜色方案不匹配:**

当前 coder 配置中写的是：
```
- 样式规范: 暗色主题 #0b1120，强调色 #3b82f6，圆角按钮，Inter 字体
```

但你的 PRD v1.0 §5.2 定义的实际颜色是：
- 背景根色: `#0f172a` (Slate 900)
- Surface: `#1e293b`
- 强调色: `#38bdf8` (Sky 400)

需要将 coder 的样式规范改为：
```
- 样式规范: 暗色主题 #0f172a，强调色 #38bdf8，实体类型 10 色映射，Inter 字体，JetBrains Mono 代码字体
```

**问题 2 -- HTTP 库不匹配:**

当前 coder 配置写的是 `API 调用使用 fetch`，但你的前端系统设计规范 v1.0 §6.1 选型的是 `axios ^1.7`（带拦截器和进度回调）。需要改为：
```
- API 调用使用 axios，统一拦截器处理错误和进度
```

### 2.2 chatbot-planner.md 需要修改 1 处

当前 planner 的参考资源写的是：
```
- `docs/` 目录下的所有规范文档
```

但你的项目规范文档实际位于 `integration/` 目录下（因为项目是驾驭工程 Layer 5 在 integration 目录产出的蓝图文档）。需要改为：
```
- `integration/` 目录下的所有规范文档：
  - multimodal-rag-prd-v1.0.md — 产品需求文档
  - backend-api-architecture-v1.0.md — 后端 API 架构规范
  - frontend-system-design-v1.0.md — 前端系统设计规范
  - Agentic-RAG-Architecture.md — 技术架构方案
- `frontend/CLAUDE.md` — 前端项目的工程约束
- `backend/CLAUDE.md` — 后端项目的工程约束
```

### 2.3 chatbot-reviewer.md -- 无需修改

reviewer 的配置是通用的，不需要项目特定的调整。其审查清单（代码规范、逻辑漏洞、安全风险、性能问题、业务匹配度、TypeScript 类型安全）已经覆盖了你项目需要的所有维度。

### 2.4 其他关键配置说明

| 配置项 | 当前值 | 含义 |
|---|---|---|
| `model: deepseek-v4-pro` | deepseek-v4-pro | 你的对话模型，无需修改 |
| `permission_mode: plan` (planner) | plan | planner 只读不写，符合"只做规划"原则 |
| `permission_mode: acceptEdits` (coder) | acceptEdits | coder 可读写，执行代码生成 |
| `max_turns: 10` (planner) | 10 | planner 思考深度适中 |
| `max_turns: 20` (coder) | 20 | coder 有足够轮次完成复杂组件 |
| `run_in_background: true` (reviewer) | true | reviewer 在后台异步审查，不阻塞主流程 |

---

## 三、三大 Agent 的完整开发工作流

驾驭工程方法论（SKILL.md）定义了标准的 Agent 协作流程：

```
PRD + 规范文档
    │
    ▼
chatbot-planner ──► 实现计划
    │
    ▼
chatbot-coder ──► 代码实现
    │
    ▼
chatbot-reviewer ──► 审查报告
    │
    ▼
chatbot-coder ──► 修复代码（根据审查报告）
    │
    ▼
联调验证
```

---

## 四、前端开发实操指南

### 阶段 1: 用 planner 生成实现计划

在 Claude Code 对话中，使用 `Agent` 工具调用 chatbot-planner：

```
使用 chatbot-planner agent，基于以下三份规范文档，为前端生成完整的实现计划：

必读文档（按顺序阅读）：
1. D:\graghRAG-agent\integration\multimodal-rag-prd-v1.0.md
2. D:\graghRAG-agent\integration\backend-api-architecture-v1.0.md
3. D:\graghRAG-agent\integration\frontend-system-design-v1.0.md
4. D:\graghRAG-agent\frontend\CLAUDE.md

要求：
- 输出分 Phase 的实施计划（推荐按前端系统设计规范 §8 的 5 个 Phase 拆分）
- 每个 Phase 列出要创建的组件和文件路径
- 标注每个 Phase 的验收标准
```

Planner 会输出类似这样的结构（对应前端设计规范 §8）:

```
Phase 1: 项目脚手架 (0.5天)
  - Vite + React + TypeScript 初始化
  - Tailwind CSS 配置 + 暗色主题变量
  - 路由配置 / AppShell 布局 / API Client / Zustand

Phase 2: 上传 + 文档列表 (1.5天)
  - UploadZone / ConfigPanel / PipelineProgress / ResultCard
  - DocumentsPage / FilterBar / DocumentTable
  - useUploadStore + 轮询逻辑

Phase 3: KG 可视化 (1.5天)
  - GraphCanvas (vis.js) / FloatingPanel / Toolbar
  - LegendFilter / Node 选中交互
  - useKGStore

Phase 4: 问答页 (1.5天)
  - ChatHistory / QueryInput / AnswerBubble
  - AnswerDetail / SourcePreview
  - useQueryStore

Phase 5: 联调 + 打磨 (1天)
  - 端到端测试 / 错误状态覆盖 / 响应式
  - 键盘快捷键 / Loading/Empty/Error 三态
```

### 阶段 2: 用 coder 逐 Phase 实现

拿到 planner 的计划后，**一次只喂一个 Phase 给 coder**，不要一次性给全部计划。

调用示例：

```
使用 chatbot-coder agent，实现 Phase 1：项目脚手架。

参考规范:
- D:\graghRAG-agent\integration\frontend-system-design-v10.md (特别是 §2.3 主题变量、§6.1 技术栈、§6.3 目录结构)
- D:\graghRAG-agent\frontend\CLAUDE.md (工程约束)

Planner 的计划: [粘贴 planner 输出的 Phase 1 部分]

约束条件:
1. 所有前端代码放在 frontend/ 目录
2. 颜色使用 PRD §5.2 定义的值: bg-root=#0f172a, accent=#38bdf8
3. 使用 axios 而非 fetch
4. 所有用户可见文字使用中文
```

每完成一个 Phase，就调用下一个。如果遇到 Phase 之间互相依赖的情况（比如 Phase 4 的 QueryPage 需要 Phase 2 定义好的 API Client 和 Zustand store），coder 会基于已有文件继续开发。

### 阶段 3: 用 reviewer 审查代码

每个 Phase 完成后（或整个前端完成后），调用 reviewer：

```
使用 chatbot-reviewer agent，对 frontend/ 目录下 Phase 2 新增的代码进行全面审查。

规范文档参考:
- D:\graghRAG-agent\integration\multimodal-rag-prd-v1.0.md
- D:\graghRAG-agent\integration\frontend-system-design-v1.0.md

审查范围: frontend/src/pages/UploadPage.tsx, frontend/src/components/upload/*, frontend/src/stores/useUploadStore.ts
```

### 阶段 4: 根据审查报告修复

将 reviewer 输出的问题清单（特别是 Critical 和 High 级别的）作为 prompt 喂给 coder，要求逐条修复。

### 阶段 5: 启动前端验证

```bash
cd D:/graghRAG-agent/frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

验证前端可以独立启动（后端未就绪时，用 Zustand 的初始默认状态渲染 Loading/Empty 视图即可）。

---

## 五、后端开发实操指南

### 阶段 1: 用 planner 生成后端实现计划

```
使用 chatbot-planner agent，基于以下规范文档，为后端服务生成完整的实现计划：

必读文档：
1. D:\graghRAG-agent\integration\backend-api-architecture-v1.0.md
2. D:\graghRAG-agent\integration\Agentic-RAG-Architecture.md
3. D:\graghRAG-agent\backend\CLAUDE.md
4. D:\graghRAG-agent\integration\CLAUDE.md (BridgePipeline 的 CLAUDE.md，了解已有组件)

要求：
- 输出分 Phase 的实施计划（推荐按后端架构规范 §7 的 4 个 Phase 拆分）
- 标注每个 API 端点与其数据模型的对应关系
- 给出每个 Phase 的测试 curl 命令作为验收标准
```

### 阶段 2: 用 coder 逐 Phase 实现

```
使用 chatbot-coder agent，实现 Phase 1：FastAPI 骨架。

参考规范:
- D:\graghRAG-agent\integration\backend-api-architecture-v1.0.md (特别是 §3 接口规范、§4 数据模型、§6 错误处理)
- D:\graghRAG-agent\backend\CLAUDE.md (启动方式)

Planner 的计划: [粘贴 planner 输出的 Phase 1 部分]

约束条件:
1. 所有后端代码放在 backend/ 目录
2. 使用 uv 创建独立虚拟环境
3. 敏感配置（API Key）放在 .env 文件
4. .env 必须加入 .gitignore
5. 复用 integration/ 下已有的 pipeline.py / bridge.py / grounding.py / kg_builder.py / agentic_rag_mvp.py
```

### 阶段 3: 用 reviewer 审查后端代码

```
使用 chatbot-reviewer agent，对 backend/ 目录下 Phase 1 新增的代码进行全面审查。

规范文档参考:
- D:\graghRAG-agent\integration\backend-api-architecture-v1.0.md
- D:\graghRAG-agent\integration\Agentic-RAG-Architecture.md
```

### 阶段 4: 启动后端验证

```bash
source D:/graghRAG-agent/backend/.venv/Scripts/activate
cd D:/graghRAG-agent/backend
uvicorn server:app --host 0.0.0.0 --port 8000 --reload --limit-max-requests 0 --timeout-keep-alive 300
# Swagger UI: http://localhost:8000/docs
```

---

## 六、端到端联调流程

前后端各自开发和审查完毕后，进入联调阶段：

### 6.1 启动两个服务

**终端 1 -- 后端:**
```bash
source D:/graghRAG-agent/backend/.venv/Scripts/activate
cd D:/graghRAG-agent/backend
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

**终端 2 -- 前端:**
```bash
cd D:/graghRAG-agent/frontend
npm run dev
```

### 6.2 端到端测试清单

按用户旅程顺序验证：

| 步骤 | 操作 | 验证点 |
|---|---|---|
| 1 | 访问 `http://localhost:5173/upload` | UploadZone 正常渲染，Sidebar 导航可用 |
| 2 | 拖入/选择 sample.pdf | 格式校验通过，FilePreview 显示文件名和大小 |
| 3 | 配置参数，点击"开始解析" | POST /ingest 成功，PipelineProgress 开始动画 |
| 4 | 等待索引完成 | 5 阶段全部显示绿色 done，ResultCard 显示统计数字 |
| 5 | 点击"去问答" | 跳转 /query/:docId，5 条建议问题加载 |
| 6 | 输入问题，Enter 发送 | AnswerBubble 渲染，Markdown 表格正确，SourceChips 可点击 |
| 7 | 点击 SourceChip | 右侧 SourcePreview 打开，显示 node 详情和溯源信息 |
| 8 | 点击"去可视化" | 跳转 /graph/:docId，力导向图渲染，10 色 legend 正确 |
| 9 | 点击图中节点 | 节点放大高亮，FloatingPanel 显示详情 |
| 10 | 点击 Legend 某一类型 | 该类节点高亮，其余透明度降低 |

### 6.3 联调阶段的 Agent 使用

联调中发现 Bug 时：
1. **定位问题**：描述 bug 现象和复现步骤
2. **用 planner**：如果 bug 涉及跨组件逻辑变更，先让 planner 分析影响范围并给出修复方案
3. **用 coder**：根据修复方案修改代码
4. **用 reviewer**：修复后的代码重新审查

---

## 七、关键注意事项

### 7.1 规范文档是唯一真相源

驾驭工程的核心理念：**代码必须符合规范文档**。当实现与规范不一致时：
- 如果规范是对的：修改代码
- 如果规范需要更新：先更新规范文档，再修改代码

这意味着 reviewer 审查时，必须对照三份蓝图文档（PRD + Backend API Spec + Frontend Design Spec）逐项比对。

### 7.2 Planner-Coder-Reviewer 的正确调用顺序

**不要跳过 planner 直接让 coder 写代码。** 哪怕你觉得需求很清晰，也要让 planner 先输出实施计划。原因是：

- Planner 会通读所有规范文档，确保方案与全局设计一致
- Planner 的输出给 coder 提供了明确的"施工图纸"
- 跳过 planner 就像建筑工人没有图纸直接盖房

### 7.3 Coder 的 prompt 必须包含完整约束

每次调用 coder 时，prompt 必须包含：
1. 当前 Phase 的实施计划（planner 的输出）
2. 要参考的规范文档路径
3. 项目的工程约束（CLAUDE.md 中的规则）

缺少任何一项，coder 就可能"自由发挥"，产生与规范不一致的代码。

### 7.4 Reviewer 建议在后台运行

reviewer 配置了 `run_in_background: true`，所以审查不会阻塞你的主对话。你可以：
1. 在主对话中让 coder 完成代码
2. 同时发起 reviewer 在后台审查
3. 等 reviewer 完成后，查看审查报告
4. 根据报告发起新一轮修复

### 7.5 每完成一个 Phase 就审查

不要等到所有代码写完再一次性审查。**每完成一个 Phase 就审查一次**的好处：
- 问题发现早，修复成本低
- 不会出现"代码写了 2000 行才发现方向错了"
- 每个 Phase 的审查通过后，可以作为下一 Phase 的坚实基座

---

## 八、快速参考卡片

### Agent 调用速查

| Agent | 调用时机 | 给什么输入 | 期望输出 |
|---|---|---|---|
| **planner** | 每个 Phase 开始前 | 规范文档路径 + 需求描述 | 分步骤的实施方案 |
| **coder** | planner 输出计划后 | 实施计划 + 规范约束 | 可运行的代码文件 |
| **reviewer** | 每个 Phase 代码完成后 | 代码文件路径 + 对比规范 | 分级问题清单 + 修复建议 |

### 规范文档索引用

| 规范文档 | 路径 | 驱动范围 |
|---|---|---|
| PRD v1.0 | `integration/multimodal-rag-prd-v1.0.md` | 整体产品行为、UI 设计 |
| Backend API Spec v1.0 | `integration/backend-api-architecture-v1.0.md` | 后端 API、数据模型、状态机 |
| Frontend Design Spec v1.0 | `integration/frontend-system-design-v1.0.md` | 前端架构、组件树、数据流 |
| Agentic RAG Architecture | `integration/Agentic-RAG-Architecture.md` | 技术架构方案 |
| BridgePipeline CLAUDE.md | `integration/CLAUDE.md` | 已有组件使用方式 |
| Frontend CLAUDE.md | `frontend/CLAUDE.md` | 前端工程约束 |
| Backend CLAUDE.md | `backend/CLAUDE.md` | 后端工程约束 |

### 驾驭工程 Layer 7 施工阶段 -- 完整 SOP

```
1. 确认规范文档已就绪 (Layer 5) ✓ (你已完成)
2. 确认 CLAUDE.md 已写入 (Layer 6) ✓ (你已完成)
3. 调整 Agent 配置 (本文档 §二)         → 现在执行
4. Planner 生成前端实施计划             → 下一步
5. Coder 实现前端 Phase 1-5             → 按计划执行
6. Reviewer 审查前端代码                → 每 Phase 后执行
7. Planner 生成后端实施计划             → 与前端可并行
8. Coder 实现后端 Phase 1-4             → 按计划执行
9. Reviewer 审查后端代码                → 每 Phase 后执行
10. 前后端联调验证                      → 全部完成后
11. Reviewer 最终审查                   → 联调通过后
```

---

## 总结

你的项目处于驾驭工程方法论中 **Layer 6 已完成、Layer 7 即将启动**的阶段。三份蓝图文档（PRD、后端 API 规范、前端设计规范）已经完备，项目开发规范（CLAUDE.md）已经确立。Agent 配置文件已就位在 `.claude/agents/` 目录下，只需微调 3 处细节（coder 的颜色方案、HTTP 库、planner 的文档路径）即可投入施工。

前端推荐按 5 个 Phase 推进（脚手架 -> 上传/文档 -> 可视化 -> 问答 -> 联调），后端按 4 个 Phase 推进（骨架 -> 任务引擎 -> 集成测试 -> 生产加固），每个 Phase 都走 **planner -> coder -> reviewer -> 修复** 的闭环。前后端可以并行开发，最后在 Layer 7c 阶段联调。
