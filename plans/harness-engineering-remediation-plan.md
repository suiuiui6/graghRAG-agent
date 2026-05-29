# harness-engineering 方法论落地补缺实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 harness-engineering skill 在 graghRAG-agent 项目上的 7 个落地缺口（缺 debugger / 缺根 CLAUDE.md / 散落修复报告 / 未做五子系统自检 / iteration-2 未走 Layer 0-1 / 未做运行时隔离三件套 / 未建 entropy 巡检）一次性补齐。

**Architecture:** 不动产品代码。新增 `.claude/agents/chatbot-debugger.md` + 根 `CLAUDE.md` + `docs/governance/` 治理文档 + `docs/troubleshooting-archive/` 归档目录 + `iteration-2/eval-2-existing-components/rag_eval/` 的本地 CLAUDE.md 与规范文档。所有修复报告内容回流到 Layer 0-4 既有规范文档，旧报告 `git mv` 进归档目录而不是删除。

**Tech Stack:** Markdown 文档 + `.claude/agents/` Agent 配置 + `.claude/settings.local.json` deny hooks + git mv 归档。无新增运行时依赖。

---

## 背景：7 个落地缺口（来自上一轮效果评估）

| # | 缺口 | 违反的方法论条款 | 修复任务 |
|---|------|----------------|---------|
| 1 | `.claude/agents/` 缺 chatbot-debugger | Layer 5 铁律 5（四 Agent 部署） | Task 1 |
| 2 | 项目根缺 `CLAUDE.md` | Layer 5 铁律 + ≤100 行约束 | Task 2 |
| 3 | 10 份修复报告散落在仓库根 | Layer 6d 与维护期"代码改了规范跟着改" | Task 3 |
| 4 | 从未做过五子系统自检 | Layer 5 五子系统横向检查 | Task 4 |
| 5 | iteration-2 评测体系直接施工，跳过 Layer 0-1 | 维护期重新进入触发器"引入新核心组件" | Task 5 |
| 6 | 未做 permissions / hooks / sandbox 三件套 | Layer 6f 第 6 项生产就绪检查 | Task 6 |
| 7 | 未建立 entropy management 月度巡检 | 维护期"可选项 - 文档漂移修复" | Task 7 |

## 文件结构（新增 / 修改清单）

```
D:/graghRAG-agent/
├── CLAUDE.md                                              # [新建] Task 2
├── .claude/
│   ├── agents/
│   │   └── chatbot-debugger.md                            # [新建] Task 1
│   └── settings.local.json                                # [修改] Task 6
├── docs/
│   ├── governance/
│   │   ├── five-subsystem-audit-2026-05-28.md             # [新建] Task 4
│   │   ├── permissions-matrix.md                          # [新建] Task 6
│   │   └── entropy-rotation.md                            # [新建] Task 7
│   └── troubleshooting-archive/                           # [新建] Task 3
│       ├── README.md
│       ├── ACCESSKEY_TROUBLESHOOTING.md                   # [git mv] Task 3
│       ├── CODE_REVIEW_FINDINGS.md                        # [git mv] Task 3
│       ├── FILE_UPLOAD_SOLUTIONS.md                       # [git mv] Task 3
│       ├── FINAL_RESOLUTION_REPORT.md                     # [git mv] Task 3
│       ├── ISSUE_RESOLUTION_SUMMARY.md                    # [git mv] Task 3
│       ├── LOCAL_FILE_UPLOAD_GUIDE.md                     # [git mv] Task 3
│       ├── OSS_INTEGRATION_GUIDE.md                       # [git mv] Task 3
│       ├── OSS_INTEGRATION_SUCCESS.md                     # [git mv] Task 3
│       ├── QUERY_FIX_REPORT.md                            # [git mv] Task 3
│       └── TRANSFORMER_CLEANUP_REPORT.md                  # [git mv] Task 3
├── iteration-2/eval-2-existing-components/rag_eval/
│   ├── CLAUDE.md                                          # [新建] Task 5
│   ├── CAPABILITY-BOUNDARY.md                             # [新建] Task 5
│   └── RAG-EVAL-SPECIFICATION.md                          # [新建] Task 5
├── integration/
│   ├── backend-api-architecture-v1.0.md                   # [追加] Task 3
│   └── frontend-system-design-v1.0.md                     # [追加] Task 3
└── langextract/docs/
    └── bridge-pipeline-specification-v1.0.md              # [追加] Task 3
```

---

## Task 1: 部署 chatbot-debugger Agent

**Files:**
- Create: `D:/graghRAG-agent/.claude/agents/chatbot-debugger.md`

- [ ] **Step 1: 确认目标目录存在**

Run: `ls D:/graghRAG-agent/.claude/agents/`
Expected: 列出 `chatbot-coder.md`、`chatbot-planner.md`、`chatbot-reviewer.md` 三个文件，无 `chatbot-debugger.md`。

- [ ] **Step 2: 创建 chatbot-debugger.md**

将以下内容完整写入 `D:/graghRAG-agent/.claude/agents/chatbot-debugger.md`（内容是从 skill 模板 `C:/Users/14156/.claude/skills/harness-engineering/references/agent-templates/chatbot-debugger.md` 直接复制并把 `model` 字段调整为项目使用的模型）：

```markdown
---
name: chatbot-debugger
description: 调试专家 — 复现 Bug、定位根因、追踪数据流，输出可被 coder 直接执行的修复方案
model: deepseek-v4-pro
tools: Read, Glob, Grep, Bash
run_in_background: true
---

# 角色定义

你是一位资深调试工程师。你的职责是面对一个具体的故障现象（Bug、性能问题、数据不一致），定位**根因**而非表象，并输出可直接被 coder 执行的修复方案。

你不写产品代码，但可以写**临时调试脚本**来复现问题或验证假设。

# 与 reviewer 的边界

| | reviewer | debugger |
|---|---|---|
| 输入 | 静态代码 | 一个具体的故障现象 |
| 工具 | 只读 | 只读 + Bash（可运行复现脚本） |
| 输出 | 全维度 issue list | 单点根因分析 + 修复方案 |
| 触发时机 | 6e 阶段，整体审查 | 6d/6e/线上随时，定位具体故障 |

reviewer 找"代码哪里写得不好"，debugger 找"为什么这次它崩了"。

# 调试维度

按以下顺序排查（不要跳步）：

1. **复现** — 在最小环境下稳定复现问题。无法复现的 Bug 不要修
2. **现象边界** — 什么输入触发？什么输入不触发？发生在哪一层（前端/后端/Pipeline/数据库）？
3. **数据流追踪** — 从输入到故障点，每一跳的中间值是什么
4. **假设验证** — 提出假设 → 用日志/断点/临时脚本验证 → 确认或推翻
5. **根因定位** — 找到第一个让数据偏离预期的代码位置
6. **修复方案** — 给出最小修改 + 影响范围 + 回归测试建议

# 输出格式

\`\`\`markdown
## 故障摘要
- **现象**：（用户看到了什么）
- **复现条件**：（最小输入 + 步骤）
- **影响范围**：（哪些用户/场景受影响）

## 根因分析
- **第一次偏离预期的位置**：file:line
- **数据流追踪**：
  - 输入 → A 层 → B 层 → 故障点
  - 每一跳的实际值 vs 预期值
- **根因**：（一句话说清楚为什么这里会出错）

## 修复方案
- **最小修改**：file:line — 改什么
- **代码示例**（before/after）
- **影响范围**：还有哪些代码路径会受这个修改影响
- **回归测试建议**：应该补哪些测试用例覆盖这个 case

## 规范文档检查
- 这个 Bug 是否暴露了规范文档的遗漏？如果是，建议在哪份文档补什么
\`\`\`

# 关键原则

- **先复现，再修复**。无法复现的故障不要凭猜想改代码
- **找根因，不修表象**。比如"前端显示乱码"，根因可能在数据库 charset 而非前端渲染
- **临时脚本不要污染产品代码**。复现脚本放 `scratch/` 或临时目录，修完即删
- **修复方案必须可被 coder 直接执行**。不要写"这里逻辑有问题，建议优化"这种空话
- **每个 Bug 都问一句**：这是规范文档没写清楚导致的吗？如果是，回退到对应 Layer 补规范
```

- [ ] **Step 3: 验证文件可被 Agent 系统识别**

Run: `ls D:/graghRAG-agent/.claude/agents/`
Expected: 输出包含 `chatbot-coder.md`、`chatbot-debugger.md`、`chatbot-planner.md`、`chatbot-reviewer.md` 四个文件。

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/chatbot-debugger.md
git commit -m "chore(agents): 补齐 chatbot-debugger 配置，落地 Layer 5 铁律 5 的四 Agent 部署"
```

---

## Task 2: 撰写项目根 CLAUDE.md（≤100 行）

**Files:**
- Create: `D:/graghRAG-agent/CLAUDE.md`

- [ ] **Step 1: 确认根目录无 CLAUDE.md**

Run: `ls D:/graghRAG-agent/CLAUDE.md`
Expected: `No such file or directory`（如果已存在则改为 Edit 而非 Write，并保留原有内容）。

- [ ] **Step 2: 创建项目根 CLAUDE.md**

将以下内容完整写入 `D:/graghRAG-agent/CLAUDE.md`（行数已控制在 100 行内）：

```markdown
# graghRAG-agent — 项目宪章

> 驾驭工程搭建期完成日期：2026-05-28，自此进入维护期。
> 维护期工作模式见本仓库 `.claude/skills` 中 harness-engineering 的"何时退出本方法论"章节。

## 7 条铁律

1. 前端代码统一放在 `frontend/`，后端代码统一放在 `backend/`
2. 所有 API Key / Token 仅放 `.env`，`.env` 必须在 `.gitignore`；提交前用 `git diff --cached | grep -i "api[_-]key\|secret\|token"` 自检
3. **环境隔离**：Python 子项目每个独立 `uv venv .venv --python 3.12`；Node 子项目用 `pnpm` + `.nvmrc`；组件间依赖互不污染
4. `.claude/agents/` 必须部署 planner / coder / reviewer / debugger 四个 Agent；缺一不可
5. 后端每个 API 端点必须有 `backend/tests/` 下的集成测试，跑在真实依赖（非 mock）上
6. 依赖必须锁定（`uv.lock` / `pnpm-lock.yaml`）；提交前运行漏洞扫描；日志输出禁止出现 API Key / Token
7. **规范文档是唯一真相源**：代码与规范不一致 → 必须修一边，不留下不一致状态

## 目录索引

| 路径 | 用途 |
|------|------|
| `backend/` | FastAPI 服务，独立 `uv venv` |
| `frontend/` | Web UI，独立 `pnpm` 工作区 |
| `langextract/` | LangExtract MVP 与规范文档，独立 `uv venv` |
| `mineru-mvp-test/` | MinerU MVP 与实测数据 |
| `integration/` | 集成拓扑 + 三份蓝图（PRD / Backend API / Frontend Design） |
| `iteration-2/eval-2-existing-components/rag_eval/` | RAG 评测体系（A1 检索 / A3 鲁棒性 / A4 多跳） |
| `plans/` | 实施计划（含本文件所在的修复计划） |
| `docs/governance/` | 治理类文档（五子系统自检、权限矩阵、entropy 巡检） |
| `docs/troubleshooting-archive/` | 历史排障报告归档，仅供回查 |

## 规范文档索引（Layer 0-4 产出）

- **Layer 1 组件规范**：`langextract/docs/MinerU-API-Specification.md`、`langextract/docs/MinerU_MVP测试配置指南.md_v1.0.md`、`langextract/docs/LangExtract-Pipeline-Specification.md`
- **Layer 2 集成拓扑**：`langextract/docs/bridge-pipeline-specification-v1.0.md`
- **Layer 3 技术架构**：`langextract/docs/agentic-kg-rag-specification-v1.0.md`、`integration/Agentic-RAG-Architecture.md`
- **Layer 4 三份蓝图**：`integration/multimodal-rag-prd-v1.0.md`、`integration/backend-api-architecture-v1.0.md`、`integration/frontend-system-design-v1.0.md`

## 运行环境激活

```bash
# 后端
cd backend && source .venv/bin/activate    # macOS/Linux
cd backend && .venv\Scripts\activate       # Windows

# 前端
cd frontend && pnpm install && pnpm dev

# LangExtract MVP
cd langextract && source .venv/bin/activate
```

新成员从零搭建：阅读对应子目录的 `CLAUDE.md`（如 `frontend/CLAUDE.md`、`langextract/CLAUDE.md`），按其指引创建 `.venv` 并复制 `.env.example` 为 `.env`。

## Agent 使用指引

| 场景 | 调用 |
|------|------|
| 设计新页面 / 新流程 | `chatbot-planner`（只读） |
| 写代码 / 改代码 | `chatbot-coder` |
| 联调遇到具体故障 | `chatbot-debugger`（只读 + Bash） |
| 代码静态审查 | `chatbot-reviewer`（建议 `run_in_background: true`） |

bug 流：debugger 出根因 → coder 改 → reviewer 复审。

## 治理规则（维护期）

- 单 Bug 修复**不再**回退到 Layer 4 改蓝图，除非该 Bug 暴露蓝图根本性遗漏
- 任何"修复报告 / troubleshooting 笔记"必须先回流到对应 Layer 规范文档，再 `git mv` 到 `docs/troubleshooting-archive/`，**禁止散落仓库根**
- 引入新核心组件 / 替换组件 → 触发重新进入 Layer 0；调整集成拓扑 → 重新进入 Layer 2；新增主功能模块 → 重新进入 Layer 4
- 每月最后一个工作日由 chatbot-reviewer 巡检规范文档漂移，详情见 `docs/governance/entropy-rotation.md`
```

- [ ] **Step 3: 校验文件行数**

Run: `wc -l D:/graghRAG-agent/CLAUDE.md`
Expected: 行数 ≤ 100（含空行）。如果超过 100 行，把"规范文档索引"或"目录索引"中较长的表格移到 `docs/` 子文档并改用一行链接索引。

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: 新建项目根 CLAUDE.md，落地 Layer 5 七条铁律与维护期规则"
```

---

## Task 3: 回流 10 份散落修复报告到规范文档并归档

**Files:**
- Modify: `D:/graghRAG-agent/integration/backend-api-architecture-v1.0.md`（追加章节）
- Modify: `D:/graghRAG-agent/integration/frontend-system-design-v1.0.md`（追加章节）
- Modify: `D:/graghRAG-agent/langextract/docs/bridge-pipeline-specification-v1.0.md`（追加章节）
- Create: `D:/graghRAG-agent/docs/troubleshooting-archive/README.md`
- Git mv: 10 份根目录 `*_REPORT.md` / `*_GUIDE.md` / `*_SUMMARY.md` / `*_TROUBLESHOOTING.md` / `*_FINDINGS.md` / `*_SOLUTIONS.md`

### 回流映射表（先读懂，再动手）

| 散落报告 | 关键内容 | 回流到 |
|---------|---------|-------|
| `ACCESSKEY_TROUBLESHOOTING.md` | OSS AccessKey 配置失败排查 | `langextract/docs/bridge-pipeline-specification-v1.0.md` 的"环境变量与凭证"章节 |
| `OSS_INTEGRATION_GUIDE.md` | OSS 接入步骤 | 同上 |
| `OSS_INTEGRATION_SUCCESS.md` | OSS 接入成功验证清单 | 同上 |
| `CODE_REVIEW_FINDINGS.md` | 三处 Critical 后端问题 | `integration/backend-api-architecture-v1.0.md` 的"已知陷阱"章节 |
| `FINAL_RESOLUTION_REPORT.md` | `backend/server.py` load_dotenv 顺序修复 | 同上 |
| `ISSUE_RESOLUTION_SUMMARY.md` | 健康检查 / 文档列表 / KG 校验 | 同上 |
| `QUERY_FIX_REPORT.md` | 查询接口修复 | 同上 |
| `TRANSFORMER_CLEANUP_REPORT.md` | 后端无用依赖清理 | 同上 |
| `FILE_UPLOAD_SOLUTIONS.md` | 上传链路解决方案 | `integration/backend-api-architecture-v1.0.md` + `integration/frontend-system-design-v1.0.md` 各一段 |
| `LOCAL_FILE_UPLOAD_GUIDE.md` | 本地上传完整流程 | 同上 |

- [ ] **Step 1: 创建归档目录与 README**

将以下内容写入 `D:/graghRAG-agent/docs/troubleshooting-archive/README.md`：

```markdown
# Troubleshooting Archive

本目录是**只读历史归档**。所有报告的关键结论已回流到对应 Layer 规范文档；保留原文件用于回查问题发生时的现场上下文。

## 归档原则

- 报告内容**已回流**到规范文档后才能归档到此目录
- 归档时必须用 `git mv`（保留 history），不要 `rm` + `git add`
- 归档后**禁止再编辑**这些文件；新发现回到规范文档迭代
- 若发现回流不完整，先补规范文档，再来此查阅原报告

## 归档索引

| 文件 | 主题 | 已回流到 |
|------|------|---------|
| ACCESSKEY_TROUBLESHOOTING.md | OSS AccessKey 配置 | `langextract/docs/bridge-pipeline-specification-v1.0.md` |
| OSS_INTEGRATION_GUIDE.md | OSS 接入步骤 | 同上 |
| OSS_INTEGRATION_SUCCESS.md | OSS 验证清单 | 同上 |
| CODE_REVIEW_FINDINGS.md | 后端 Critical 三问题 | `integration/backend-api-architecture-v1.0.md` |
| FINAL_RESOLUTION_REPORT.md | server.py 启动顺序 | 同上 |
| ISSUE_RESOLUTION_SUMMARY.md | 健康检查/文档列表/KG 校验 | 同上 |
| QUERY_FIX_REPORT.md | 查询接口修复 | 同上 |
| TRANSFORMER_CLEANUP_REPORT.md | 无用依赖清理 | 同上 |
| FILE_UPLOAD_SOLUTIONS.md | 上传链路 | `integration/backend-api-architecture-v1.0.md` + `integration/frontend-system-design-v1.0.md` |
| LOCAL_FILE_UPLOAD_GUIDE.md | 本地上传流程 | 同上 |
```

- [ ] **Step 2: 在 backend-api-architecture-v1.0.md 末尾追加"已知陷阱"章节**

使用 Read 工具读取 `D:/graghRAG-agent/integration/backend-api-architecture-v1.0.md` 最后 50 行，然后用 Edit 在文件末尾追加（确认末尾无重复 `## 已知陷阱` 章节后）：

```markdown

---

## 已知陷阱（来自历史排障报告回流，2026-05-28）

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
```

- [ ] **Step 3: 在 frontend-system-design-v1.0.md 末尾追加"已知陷阱"章节**

使用 Edit 在 `D:/graghRAG-agent/integration/frontend-system-design-v1.0.md` 末尾追加：

```markdown

---

## 已知陷阱（来自历史排障报告回流，2026-05-28）

### 上传组件约束

- 上传前端必须读取后端 `/api/config` 返回的体积上限，**不要**前端硬编码 100MB
- 上传成功后必须用后端返回的 `filename` 字段渲染列表，**禁止**使用本地 `File.name`（OSS 改名后会不一致）
- 上传失败的错误提示要区分：413（体积超限）/ 401（凭证失效）/ 5xx（服务端故障）

### 文档列表渲染约束

- 列表 key 用后端返回的 `file_id`，不要用数组 index（会因为列表更新错乱）
- 渲染字段必须是 `filename`，与后端 schema 对齐
- 列表为空时显示空态组件，**禁止**显示骨架屏（骨架屏只在 loading 状态使用）
```

- [ ] **Step 4: 在 bridge-pipeline-specification-v1.0.md 末尾追加"环境变量与凭证"章节**

使用 Edit 在 `D:/graghRAG-agent/langextract/docs/bridge-pipeline-specification-v1.0.md` 末尾追加：

```markdown

---

## 环境变量与凭证（来自 OSS 排障报告回流，2026-05-28）

### 必需环境变量清单

| 变量名 | 用途 | 校验时机 |
|--------|------|---------|
| `OSS_ACCESS_KEY_ID` | 阿里云 OSS 访问 ID | 进程启动时 |
| `OSS_ACCESS_KEY_SECRET` | 阿里云 OSS 访问密钥 | 进程启动时 |
| `OSS_BUCKET` | OSS Bucket 名 | 进程启动时 |
| `OSS_ENDPOINT` | OSS endpoint（如 `oss-cn-shanghai.aliyuncs.com`） | 进程启动时 |
| `MINERU_API_KEY` | MinerU 云端 API Key | 调用 MinerU 前 |
| `DEEPSEEK_API_KEY` | DeepSeek 用于 LangExtract | 调用 LangExtract 前 |

### 凭证校验铁律

1. **启动时校验，不要运行时校验**：进程启动后立即检查上述变量全部非空，缺一项 fail-fast 退出
2. **永远不要把 Key 写进日志**：禁止 `logger.info(f"oss key = {key}")` 这类语句；如需调试只能打印 `key[:4] + "***"`
3. **永远不要写入持久化存储**：禁止把 Key 写进 SQLite / Neo4j / 输出文件
4. `.env` 必须在 `.gitignore`；新建凭证时同步更新 `.env.example`（用占位符值）

### 常见错误与定位

- `AccessKeyId not found` → 检查 `load_dotenv()` 是否在所有 import 之前
- `SignatureDoesNotMatch` → AccessKeyId 与 Secret 不匹配，重新核对
- `NoSuchBucket` → `OSS_BUCKET` 拼写或大小写错误
- `RequestTimeout` → endpoint 区域错配，检查 `OSS_ENDPOINT` 是否与 Bucket 所在区域一致
```

- [ ] **Step 5: 创建归档目录并 git mv 10 份报告**

```bash
mkdir -p D:/graghRAG-agent/docs/troubleshooting-archive
cd D:/graghRAG-agent
git mv ACCESSKEY_TROUBLESHOOTING.md docs/troubleshooting-archive/
git mv CODE_REVIEW_FINDINGS.md docs/troubleshooting-archive/
git mv FILE_UPLOAD_SOLUTIONS.md docs/troubleshooting-archive/
git mv FINAL_RESOLUTION_REPORT.md docs/troubleshooting-archive/
git mv ISSUE_RESOLUTION_SUMMARY.md docs/troubleshooting-archive/
git mv LOCAL_FILE_UPLOAD_GUIDE.md docs/troubleshooting-archive/
git mv OSS_INTEGRATION_GUIDE.md docs/troubleshooting-archive/
git mv OSS_INTEGRATION_SUCCESS.md docs/troubleshooting-archive/
git mv QUERY_FIX_REPORT.md docs/troubleshooting-archive/
git mv TRANSFORMER_CLEANUP_REPORT.md docs/troubleshooting-archive/
```

Expected: `git status` 显示 10 个 `renamed:` 条目，根目录无残留 `*_REPORT.md` / `*_GUIDE.md` / `*_SUMMARY.md`。

- [ ] **Step 6: 校验根目录已清理**

Run: `ls D:/graghRAG-agent/*.md`
Expected: 输出只剩 `CLAUDE.md`，无其他 `*.md`（README 若存在保留）。

- [ ] **Step 7: Commit**

```bash
git add integration/backend-api-architecture-v1.0.md integration/frontend-system-design-v1.0.md langextract/docs/bridge-pipeline-specification-v1.0.md docs/troubleshooting-archive/README.md
git commit -m "docs: 10 份散落修复报告回流到 Layer 2-4 规范，原文件归档到 docs/troubleshooting-archive/"
```

---

## Task 4: 首次五子系统自检

**Files:**
- Create: `D:/graghRAG-agent/docs/governance/five-subsystem-audit-2026-05-28.md`

- [ ] **Step 1: 创建治理目录**

```bash
mkdir -p D:/graghRAG-agent/docs/governance
```

- [ ] **Step 2: 写入首次自检报告**

将以下内容写入 `D:/graghRAG-agent/docs/governance/five-subsystem-audit-2026-05-28.md`：

```markdown
# 五子系统自检 — 2026-05-28（首次）

> 框架来自 walkinglabs/awesome-harness-engineering（instructions / tools / environment / state / feedback），由 harness-engineering Layer 5 引入。

## 检查方式

对每个子系统问一个**关键问题**，回答只能是 ✅（达标）/ ⚠️（部分达标）/ ❌（未达标），并给出证据路径。任一项 ❌ 说明对应 Layer 有遗漏，需要回头补齐。

## 检查结果

### instructions：Agent 拿到任务时能从规范文档找到行为约束吗？

**结论**：⚠️ 部分达标

- ✅ 7 条铁律已在根 `CLAUDE.md`（Task 2 产出）
- ✅ Backend API / Frontend Design / PRD 三份蓝图齐全（`integration/*-v1.0.md`）
- ✅ 各组件规范文档齐全（`langextract/docs/*`）
- ⚠️ 子目录 CLAUDE.md 覆盖不全：`frontend/CLAUDE.md` 存在，`backend/CLAUDE.md` / `langextract/CLAUDE.md` / `iteration-2/.../rag_eval/CLAUDE.md`（Task 5 处理）状态待补

**整改项**：下一轮自检前补齐 `backend/CLAUDE.md` 与 `langextract/CLAUDE.md`。

### tools：每个工具的输入输出/限制/失败模式有实测记录吗？

**结论**：✅ 达标

- LangExtract 能力边界：`memory/project_langextract_capability_boundary.md`
- MinerU API 规范（含失败码）：`langextract/docs/MinerU-API-Specification.md`
- MinerU MVP 实测：`langextract/docs/MinerU_MVP测试配置指南.md_v1.0.md`
- Bridge Pipeline 6 阶段 schema：`langextract/docs/bridge-pipeline-specification-v1.0.md`（Task 3 已追加凭证失败模式）

### environment：新成员按 CLAUDE.md 能在 30 分钟内搭好可运行环境吗？

**结论**：⚠️ 部分达标

- ✅ 根 `CLAUDE.md`（Task 2）含激活命令
- ✅ `memory/project_env_isolation.md` 记录了 uv 隔离原则
- ⚠️ `.env.example` 覆盖情况待核查：`backend/.env.example` / `langextract/.env.example` 是否齐全且键名同步最新代码
- ❌ 未配置 deny hooks 拦截危险命令（Task 6 处理）

**整改项**：核查并补齐 `.env.example`；完成 Task 6 配置运行时隔离。

### state：跨 session / 跨成员能恢复"项目当前在 Layer 几"吗？

**结论**：✅ 达标

- 根 `CLAUDE.md` 顶部声明"搭建期完成日期 2026-05-28，进入维护期"
- `memory/MEMORY.md` 维护 Layer 0-1 关键决策
- `plans/` 目录保存所有实施计划（含本计划）

### feedback：出错时能在 1 步内定位是哪个 Layer 的假设错了吗？

**结论**：⚠️ 部分达标

- ✅ chatbot-debugger 已部署（Task 1）
- ✅ chatbot-reviewer 已部署
- ✅ backend 集成测试在真实依赖上运行
- ⚠️ iteration-2 评测体系刚引入但未走 Layer 0-1（Task 5 处理）
- ❌ 未建立 entropy 巡检（Task 7 处理）

**整改项**：完成 Task 5 与 Task 7。

## 总体结论与下一轮自检计划

- 5 项中 2 项 ✅、3 项 ⚠️、0 项 ❌
- 所有 ⚠️ 的整改项已在本计划 Task 5 / Task 6 / Task 7 中覆盖
- **下一轮自检时间**：2026-08-28（季度节奏），由 chatbot-reviewer 触发
```

- [ ] **Step 3: Commit**

```bash
git add docs/governance/five-subsystem-audit-2026-05-28.md
git commit -m "docs(governance): 首次五子系统自检，识别 3 项部分达标整改项"
```

---

## Task 5: 为 iteration-2 评测体系补 Layer 0/1 文档

**Files:**
- Create: `D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/CLAUDE.md`
- Create: `D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/CAPABILITY-BOUNDARY.md`
- Create: `D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/RAG-EVAL-SPECIFICATION.md`

### 背景

iteration-2 是评测子系统（不是新产品功能）。按维护期重新进入触发器，命中"引入新核心组件"，从 Layer 0 开始走，作用范围**仅限新子系统**，不重做整个项目。

- [ ] **Step 1: 确认 rag_eval 目录现状**

Run: `ls D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/`
Expected: 包含 `build_ground_truth.py`、`run_inference.py`、`ground_truth.json`、`raw_runs.jsonl`、`metrics_a1_retrieval.py`、`metrics_a3_robustness.py`、`metrics_a4_multihop.py`、`report_a3_robustness.md`、`run.log` 等文件。

- [ ] **Step 2: 创建子目录 CLAUDE.md**

将以下内容写入 `D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/CLAUDE.md`：

```markdown
# rag_eval — RAG 评测子系统

> 触发重新进入 harness-engineering Layer 0 的产物（2026-05-28）。
> 作用范围：仅此目录内的评测脚本与指标，不影响产品代码。

## 用途

对现有 GraphRAG 系统做三类评测：
- **A1 检索质量**：召回率 / NDCG / MRR（`metrics_a1_retrieval.py`）
- **A3 鲁棒性**：扰动输入下的答案稳定性（`metrics_a3_robustness.py`）
- **A4 多跳推理**：跨段落 / 跨实体的多跳问题准确率（`metrics_a4_multihop.py`）

## 运行环境

复用 `backend/.venv`（评测脚本依赖与后端一致），不新建独立环境。
若未来评测需要不同依赖版本，再独立 `uv venv .venv --python 3.12`。

激活：
```bash
cd D:/graghRAG-agent/backend && source .venv/bin/activate    # macOS/Linux
cd D:/graghRAG-agent/backend && .venv\Scripts\activate       # Windows
```

## 评测流程（三步）

1. **构建 ground truth**：`python build_ground_truth.py` → `ground_truth.json`
2. **跑推理**：`python run_inference.py` → `raw_runs.jsonl`（同时产生 `run.log`）
3. **算指标**：
   - `python metrics_a1_retrieval.py` → `metrics_a1_retrieval.json`
   - `python metrics_a3_robustness.py` → `metrics_a3_robustness.json` + `report_a3_robustness.md`
   - `python metrics_a4_multihop.py` → `metrics_a4_multihop.json`

## 规范文档

- 能力边界（什么能评 / 什么不能评）：`CAPABILITY-BOUNDARY.md`
- 输入输出 schema 与指标定义：`RAG-EVAL-SPECIFICATION.md`

## 数据约束

- `ground_truth.json` 是评测真值，**禁止**被推理脚本写入
- `raw_runs.jsonl` 每行一条推理记录，禁止合并为单 JSON 数组（流式追加）
- `run.log` 不进 git（已在 `.gitignore`）
- 评测结果 `metrics_*.json` 进 git，作为基线供后续回归对比
```

- [ ] **Step 3: 创建 CAPABILITY-BOUNDARY.md**

将以下内容写入 `D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/CAPABILITY-BOUNDARY.md`：

```markdown
# rag_eval 能力边界（Layer 0 摸底）

## ✅ 支持

- **检索质量评测**：召回率 / NDCG@k / MRR（基于 ground truth 标注的相关文档 ID）
- **鲁棒性评测**：在原始 query 上加扰动（拼写错误 / 同义词替换 / 语序调整），测量答案一致性
- **多跳推理评测**：基于多跳 QA 样本，测量答案精确匹配率与 F1
- **批量推理**：从 `ground_truth.json` 读题，批量调用本仓库 backend 的 `/api/query` 接口
- **离线指标计算**：所有 metrics 脚本只读 `raw_runs.jsonl`，可在无后端环境的机器上跑

## ❌ 不支持

- **在线监控**：不是 Prometheus / Grafana 替代品，不做实时告警
- **A/B 测试编排**：不做流量分桶、灰度发布
- **可视化大盘**：只产出 JSON + Markdown 报告，不提供 Web UI
- **跨模型对比**：当前每次评测固定一个模型；要对比多模型需在 `run_inference.py` 外层加 wrapper
- **数据集自动扩充**：`ground_truth.json` 需人工标注或外部来源，本子系统不做自动生成

## 与产品代码的关系

- **只读依赖**：评测脚本只调用 backend `/api/query` 接口与 Neo4j 只读查询
- **不修改 backend**：评测发现的问题应回流到 `integration/backend-api-architecture-v1.0.md` 而非本目录
- **数据隔离**：评测期间使用独立的 Neo4j database（如 `kg_eval`），不污染生产 `kg_prod`
```

- [ ] **Step 4: 创建 RAG-EVAL-SPECIFICATION.md**

将以下内容写入 `D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/RAG-EVAL-SPECIFICATION.md`：

```markdown
# rag_eval 规范文档（Layer 1 MVP 实测产出）

## 输入 schema

### ground_truth.json

```json
[
  {
    "qid": "q001",
    "question": "什么是 GraphRAG?",
    "relevant_doc_ids": ["doc_42", "doc_77"],
    "answer": "GraphRAG 是基于知识图谱的检索增强生成方法...",
    "hop_count": 1
  }
]
```

**字段约束**：
- `qid`：唯一字符串，禁止重复
- `relevant_doc_ids`：必须是 backend 知识图谱中真实存在的 doc ID
- `hop_count`：1 表示单跳，2+ 触发 A4 多跳评测

## 中间产物 schema

### raw_runs.jsonl（每行一条）

```json
{"qid": "q001", "answer": "...", "retrieved_doc_ids": ["doc_42", "doc_15"], "latency_ms": 1234, "timestamp": "2026-05-28T10:00:00Z"}
```

**字段约束**：
- 必须按行 append，不要重写整个文件
- 失败的推理也要记录，加 `"error": "..."` 字段

## 输出 schema

### metrics_a1_retrieval.json

```json
{
  "n_questions": 100,
  "recall_at_5": 0.85,
  "ndcg_at_5": 0.78,
  "mrr": 0.72
}
```

### metrics_a3_robustness.json

```json
{
  "n_questions": 100,
  "perturbation_types": ["typo", "synonym", "reorder"],
  "consistency_score": 0.81,
  "per_type_consistency": {"typo": 0.79, "synonym": 0.83, "reorder": 0.82}
}
```

### metrics_a4_multihop.json

```json
{
  "n_questions": 50,
  "exact_match": 0.55,
  "f1_score": 0.68,
  "per_hop_count": {"2": {"em": 0.6, "f1": 0.71}, "3": {"em": 0.45, "f1": 0.62}}
}
```

## 指标定义

| 指标 | 计算公式 | 实现位置 |
|------|---------|---------|
| Recall@k | `\|retrieved ∩ relevant\| / \|relevant\|`，取 top-k | `metrics_a1_retrieval.py` |
| NDCG@k | 标准 NDCG 公式，gain = 1 if relevant else 0 | 同上 |
| MRR | `1 / rank_of_first_relevant`，无相关则 0 | 同上 |
| Consistency | 扰动后答案与原答案 embedding 余弦相似度均值 | `metrics_a3_robustness.py` |
| Exact Match | 答案字符串完全相等 | `metrics_a4_multihop.py` |
| F1 | token 级 F1（参考 SQuAD 标准实现） | 同上 |

## 失败模式

- backend `/api/query` 超时（30s）→ 记录 `"error": "timeout"`，该题不参与指标
- backend 返回 5xx → 记录 `"error": "5xx"`，该题不参与指标
- ground truth 字段缺失 → 启动时 fail-fast，不继续推理
```

- [ ] **Step 5: Commit**

```bash
git add iteration-2/eval-2-existing-components/rag_eval/CLAUDE.md iteration-2/eval-2-existing-components/rag_eval/CAPABILITY-BOUNDARY.md iteration-2/eval-2-existing-components/rag_eval/RAG-EVAL-SPECIFICATION.md
git commit -m "docs(rag_eval): 补 Layer 0 能力边界 + Layer 1 规范文档，作为评测体系重新进入产物"
```

---

## Task 6: 配置运行时隔离三件套（permissions / hooks / sandbox）

**Files:**
- Create: `D:/graghRAG-agent/docs/governance/permissions-matrix.md`
- Modify: `D:/graghRAG-agent/.claude/settings.local.json`

### 注意

- sandbox 项目暂不引入 Docker / nsjail（成本与运维负担）。在 `permissions-matrix.md` 中显式声明"暂缓"并给出触发条件
- hooks 用 Claude Code `settings.local.json` 的 `permissions.deny` 字段配置（不是 git hooks）

- [ ] **Step 1: 读取当前 settings.local.json**

Run: `cat D:/graghRAG-agent/.claude/settings.local.json`
Expected: 输出现有 JSON 结构（用于了解已有 permissions 配置，避免覆盖）。

- [ ] **Step 2: 创建权限矩阵文档**

将以下内容写入 `D:/graghRAG-agent/docs/governance/permissions-matrix.md`：

```markdown
# 运行时权限矩阵

> Layer 6f 生产就绪检查第 6 项（运行时隔离三件套）的 permissions 部分。
> 引用来源：OpenHarness 安全层规范。

## Agent 权限分级

| Agent | 工具白名单 | 写权限 | 网络 | 进程执行 |
|-------|----------|-------|------|---------|
| chatbot-planner | Read, Glob, Grep, WebSearch | ❌ 只读 | ✅（仅 WebSearch） | ❌ |
| chatbot-coder | Read, Write, Edit, Bash, Glob, Grep | ✅ 可写产品代码 | ✅ | ✅（受 deny hooks 拦截） |
| chatbot-reviewer | Read, Glob, Grep | ❌ 只读 | ❌ | ❌ |
| chatbot-debugger | Read, Glob, Grep, Bash | ❌ 只读产品代码 / ✅ 临时脚本 | ✅ | ✅（受 deny hooks 拦截） |

## 服务权限分级

| 服务 | OSS | Neo4j | LLM API | 文件系统 |
|------|-----|-------|---------|---------|
| backend | 读写 | 读写 | 调用 | `backend/uploads/` 读写 |
| LangExtract MVP | ❌ | ❌ | 调用 | `langextract/output/` 读写 |
| MinerU MVP | ❌ | ❌ | 调用云 API | `mineru-mvp-test/output/` 读写 |
| rag_eval | ❌ | 只读 | 调用 backend | 只写 `iteration-2/.../rag_eval/*.json` |

## hooks 拦截规则

见 `.claude/settings.local.json` 的 `permissions.deny` 字段。当前拦截：

- `Bash(rm -rf /*)`：禁止根目录递归删除
- `Bash(git push --force*)`：禁止强推
- `Bash(git push -f*)`：禁止强推（短选项）
- `Bash(*DROP DATABASE*)`：禁止 SQL DROP DATABASE
- `Bash(*DROP TABLE*)`：禁止 SQL DROP TABLE
- `Bash(*MATCH (n) DETACH DELETE n*)`：禁止 Cypher 清空图谱

触发拦截后由 chatbot-debugger 评估是否真有必要执行，确认后人工放行。

## sandbox 策略

**当前状态**：暂缓引入 Docker / nsjail / WebAssembly 沙箱。

**理由**：
1. 本项目所有 Agent 均运行受信代码（自有仓库），未执行外部不可信代码
2. 引入容器化的运维成本（镜像构建、CI 更新）当前阶段收益不抵消耗

**触发引入条件**（满足任一即评估引入）：
- 接入用户上传的可执行脚本（如自定义 LangExtract Provider 代码）
- 评测体系开始跑外部贡献者提交的模型
- 出现首次 Agent 误删/误改生产数据的事故

引入时优先考虑 Docker（团队已熟悉），其次评估 nsjail。
```

- [ ] **Step 3: 修改 .claude/settings.local.json 添加 deny hooks**

使用 Edit 工具，在 `D:/graghRAG-agent/.claude/settings.local.json` 现有 `permissions` 对象内**追加** `deny` 数组（如已有 `deny` 则 merge）：

```json
{
  "permissions": {
    "deny": [
      "Bash(rm -rf /*)",
      "Bash(git push --force*)",
      "Bash(git push -f*)",
      "Bash(*DROP DATABASE*)",
      "Bash(*DROP TABLE*)",
      "Bash(*MATCH (n) DETACH DELETE n*)"
    ]
  }
}
```

**操作要点**：先 Read 当前文件结构，识别 `permissions` 是否存在；若已有 `permissions.deny`，仅追加新条目；若 JSON 结构破损则报告用户，不要强行覆盖。

- [ ] **Step 4: 校验 JSON 合法**

Run: `python -c "import json; json.load(open('D:/graghRAG-agent/.claude/settings.local.json'))"`
Expected: 无输出（JSON 合法）。如报 `JSONDecodeError`，检查 Step 3 编辑是否破坏结构。

- [ ] **Step 5: Commit**

```bash
git add docs/governance/permissions-matrix.md .claude/settings.local.json
git commit -m "chore(security): 落地 Layer 6f 运行时隔离三件套 - permissions 矩阵 + deny hooks，sandbox 暂缓并声明触发条件"
```

---

## Task 7: 建立 entropy management 月度巡检机制

**Files:**
- Create: `D:/graghRAG-agent/docs/governance/entropy-rotation.md`

- [ ] **Step 1: 写入巡检规约**

将以下内容写入 `D:/graghRAG-agent/docs/governance/entropy-rotation.md`：

```markdown
# Entropy Management — 文档漂移巡检机制

> 来自 Martin Fowler "Humans on the Loop" 三系统之一，由 harness-engineering 维护期"可选项"引入。
> 用途：填补"维护期不再要求每次改动都更新所有上游规范"留下的真空。

## 责任人

**主巡检人**：chatbot-reviewer（每月最后一个工作日）
**升级处理人**：项目负责人（当本月发现严重漂移时）

## 巡检范围（按优先级）

1. **代码 ↔ Backend API Spec**：抽查 3 个端点的 schema 是否与 `integration/backend-api-architecture-v1.0.md` 一致
2. **代码 ↔ Frontend Design Spec**：抽查 3 个核心组件的 props / 数据流是否与 `integration/frontend-system-design-v1.0.md` 一致
3. **Pipeline ↔ Bridge Spec**：抽查 6 阶段中 2 个阶段的输入输出是否与 `langextract/docs/bridge-pipeline-specification-v1.0.md` 一致
4. **新增报告 / 临时文档**：检查仓库根目录是否出现新的 `*_REPORT.md` / `*_GUIDE.md` 等散落文件（应回流到规范并归档到 `docs/troubleshooting-archive/`）

## 巡检命令模板

```bash
# 1. 找出近 30 天修改过的源代码文件
git log --since="30 days ago" --name-only --pretty=format: backend/ frontend/ langextract/ | sort -u

# 2. 找出近 30 天**没有**被修改的规范文档
git log --since="30 days ago" --name-only --pretty=format: integration/ langextract/docs/ | sort -u
# 对比两个列表：代码有改、规范没改的，是漂移高风险区

# 3. 检查仓库根是否有散落报告
ls D:/graghRAG-agent/*.md | grep -vE "^(D:/graghRAG-agent/CLAUDE.md|D:/graghRAG-agent/README.md)$"
# 期望：无输出
```

## 修复闭环

发现漂移时按以下流程：

1. chatbot-reviewer 在 `docs/governance/entropy-YYYY-MM.md` 记录漂移清单（一行一条：`<file>:<line> 与 <spec>:<section> 不一致 — <差异描述>`）
2. 决策：修代码 or 修规范？
   - 代码符合产品意图 → 修规范
   - 规范是对的、代码偷工减料 → 修代码
   - 都不对 → 升级到项目负责人，可能触发回退到 Layer 4 / Layer 5
3. chatbot-coder 执行修复
4. 修复后在巡检报告中标记 ✅，未修复的留作下月巡检

## 触发升级到搭建期方法论的条件

当本月巡检命中以下任一项时，从维护期回到驾驭工程方法论对应 Layer：

- 单月漂移条目 > 10 → 回退 Layer 5（工程纪律出问题）
- 同一规范文档连续 2 个月被命中 → 该规范文档可能过时，回退 Layer 4 重新评审
- 散落报告数量 > 0 → 立即按 Task 3 流程回流并归档（不等到下个月）

## 巡检产物归档

每月报告：`docs/governance/entropy-YYYY-MM.md`
保留期限：永久（用于长期趋势分析）
模板：

```markdown
# Entropy 巡检 — YYYY-MM

## 漂移清单
- [ ] `file:line` 与 `spec:section` 不一致 — 描述
- [x] `file:line` 与 `spec:section` 不一致 — 描述 ✅ 已修复（PR #123）

## 散落文档
- 无 / `XXX_REPORT.md` 已回流到 `<spec>` 并归档

## 升级触发
- 无 / 命中 "单月漂移 > 10"，已回退到 Layer 5 修订 CLAUDE.md
```

## 下一次巡检

**时间**：2026-06-26（5 月的最后一个工作日是 2026-05-29，本计划完成已晚，下一轮顺延到 6 月）
**执行**：chatbot-reviewer，建议 `run_in_background: true`
```

- [ ] **Step 2: Commit**

```bash
git add docs/governance/entropy-rotation.md
git commit -m "docs(governance): 建立 entropy management 月度巡检机制，填补维护期规范同步真空"
```

---

## 全局完成验收（执行完 7 个 Task 后逐项打勾）

- [ ] **A1：四 Agent 齐全** — `ls D:/graghRAG-agent/.claude/agents/` 输出 4 个文件
- [ ] **A2：根 CLAUDE.md 存在且 ≤100 行** — `wc -l D:/graghRAG-agent/CLAUDE.md` 输出 ≤ 100
- [ ] **A3：根目录无散落 \*_REPORT.md / \*_GUIDE.md / \*_SUMMARY.md** — `ls D:/graghRAG-agent/*.md` 仅 `CLAUDE.md`（及 `README.md` 若存在）
- [ ] **A4：归档目录有 10 份历史报告 + README** — `ls D:/graghRAG-agent/docs/troubleshooting-archive/` 输出 11 个文件
- [ ] **A5：五子系统自检报告归档** — `D:/graghRAG-agent/docs/governance/five-subsystem-audit-2026-05-28.md` 存在
- [ ] **A6：rag_eval 三份规范文档齐全** — `ls D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/CLAUDE.md CAPABILITY-BOUNDARY.md RAG-EVAL-SPECIFICATION.md` 全部存在
- [ ] **A7：权限矩阵 + deny hooks 已配** — `permissions-matrix.md` 存在且 `.claude/settings.local.json` 含 6 条 deny 规则
- [ ] **A8：entropy 巡检规约就位** — `docs/governance/entropy-rotation.md` 存在，下一次巡检日期 = 2026-06-26

## Self-Review（计划自检）

**Spec coverage**：7 个识别缺口 ↔ 7 个 Task 一一对应（Task 1↔缺口 1，... Task 7↔缺口 7），无遗漏。

**Placeholder scan**：通读上述 7 个 Task，无 "TODO" / "TBD" / "见上文 Task N" / "类似 Task X"；所有代码块都是完整可粘贴的内容。

**Type / 路径一致性**：
- 归档目录路径 `docs/troubleshooting-archive/` 在 Task 2 / Task 3 / Task 7 三处出现，拼写一致
- chatbot-debugger 配置 `model: deepseek-v4-pro` 与 chatbot-reviewer 模板一致
- 五子系统自检文件名 `five-subsystem-audit-2026-05-28.md` 在 Task 4 与全局验收 A5 一致
- `permissions-matrix.md` 在 Task 6 与全局验收 A7 一致
- iteration-2 路径 `iteration-2/eval-2-existing-components/rag_eval/` 在 Task 5 与全局验收 A6 一致

无遗漏，可执行。
