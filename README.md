# GraphRAG Agent — 多模态知识图谱 RAG 系统

基于 Harness Engineering 方法论构建的生产级 GraphRAG 系统，支持 PDF/DOCX/PPTX 多模态文档解析、知识图谱构建与智能问答。

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- Neo4j 5.x
- 阿里云 OSS（文档存储）
- DeepSeek API Key（LLM）
- MinerU API Key（文档解析）

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/suiuiui6/graghRAG-agent.git
cd graghRAG-agent
```

2. **后端环境**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入你的 API Keys
```

3. **前端环境**
```bash
cd frontend
npm install
cp .env.example .env
# 编辑 .env 配置后端 API 地址
```

4. **启动服务**
```bash
# 后端（终端 1）
cd backend && uvicorn server:app --reload

# 前端（终端 2）
cd frontend && npm run dev
```

访问 http://localhost:5173 开始使用。

---

## 使用 Harness Engineering Skill 开发

本项目采用 **Harness Engineering** 方法论（7 层渐进式工程框架）构建，确保从能力边界摸底到生产就绪的全流程质量。

### 什么是 Harness Engineering？

Harness Engineering 是一套 AI 辅助软件工程方法论，通过 7 个递进 Layer 管理项目复杂度：

- **Layer 0**：能力边界摸底（什么能做 / 什么不能做）
- **Layer 1**：组件规范（输入输出 schema / 失败模式）
- **Layer 2**：集成拓扑（组件间数据流与依赖）
- **Layer 3**：技术架构（核心算法与设计决策）
- **Layer 4**：三份蓝图（PRD / Backend API / Frontend Design）
- **Layer 5**：7 条铁律 + 四 Agent 协作（planner / coder / reviewer / debugger）
- **Layer 6**：生产就绪检查（6 个维度：测试 / 文档 / 安全 / 性能 / 可观测性 / 运行时隔离）

### 如何安装 Skill

1. **下载 skill 到本地**
```bash
# 克隆 skill 仓库（假设你已发布到 GitHub）
git clone https://github.com/suiuiui6/harness-engineering-skill.git \
  ~/.claude/skills/harness-engineering
```

2. **在 Claude Code 中激活**
```bash
# 打开 Claude Code，在项目根目录运行
claude code
```

3. **验证 skill 已加载**
```
你：/help
# 应该能看到 harness-engineering 出现在可用 skills 列表中
```

### Skill 核心命令

| 命令 | 用途 | 何时使用 |
|------|------|---------|
| `/harness-engineering start` | 启动新项目搭建期 | 从零开始新项目 |
| `/harness-engineering layer0` | 能力边界摸底 | 引入新核心组件 |
| `/harness-engineering layer4` | 生成三份蓝图 | 新增主功能模块 |
| `/harness-engineering audit` | 五子系统自检 | 每季度或重大变更后 |
| `/harness-engineering maintain` | 进入维护期 | 搭建期完成后 |

### 四 Agent 协作模式

本项目配置了 4 个专用 Agent（位于 `.claude/agents/`）：

```bash
# 1. 设计新功能
你：@chatbot-planner 设计一个文档批量上传功能

# 2. 实现代码
你：@chatbot-coder 根据 planner 的设计实现后端 API

# 3. 遇到 Bug
你：@chatbot-debugger 上传接口返回 500，帮我定位根因

# 4. 代码审查
你：@chatbot-reviewer 审查 backend/routes/upload.py 的安全性
```

**协作流程**：planner 设计 → coder 实现 → debugger 排障 → reviewer 复审

### 维护期工作模式

项目已于 2026-05-28 完成搭建期，进入维护期。维护期遵循以下规则：

#### 何时重新进入某个 Layer？

| 变更类型 | 重新进入 Layer | 示例 |
|---------|---------------|------|
| 引入新核心组件 | Layer 0（能力边界） | 新增向量数据库 / 新增 LLM 提供商 |
| 调整集成拓扑 | Layer 2（集成拓扑） | 改变组件间调用顺序 / 新增中间件 |
| 新增主功能模块 | Layer 4（三份蓝图） | 新增用户权限系统 / 新增导出功能 |
| 单 Bug 修复 | **不回退** | 修复某个端点的参数校验 |

#### 修复报告回流规则

任何 troubleshooting 笔记必须：
1. 先回流到对应 Layer 规范文档（如 `integration/backend-api-architecture-v1.0.md` 的"已知陷阱"章节）
2. 再 `git mv` 到 `docs/troubleshooting-archive/`
3. **禁止**散落在仓库根目录

#### Entropy 月度巡检

每月最后一个工作日，由 `chatbot-reviewer` 执行巡检（详见 `docs/governance/entropy-rotation.md`）：

```bash
# 手动触发巡检
你：@chatbot-reviewer 执行 entropy 月度巡检，按 docs/governance/entropy-rotation.md 的 4 个优先区域检查
```

巡检内容：
- 规范文档与代码一致性
- 环境变量同步
- 测试覆盖率漂移
- 归档文件回流检查

---

## 项目结构

```
graghRAG-agent/
├── backend/              # FastAPI 后端（独立 venv）
├── frontend/             # React 前端（独立 pnpm）
├── langextract/          # LangExtract MVP（独立 venv）
├── integration/          # 集成拓扑 + 三份蓝图
├── iteration-2/          # RAG 评测体系
├── docs/governance/      # 治理文档（五子系统自检 / 权限矩阵 / entropy 巡检）
├── plans/                # 实施计划
├── .claude/
│   ├── agents/           # 四 Agent 配置
│   └── settings.local.json  # 权限与 deny hooks
└── CLAUDE.md             # 项目宪章（7 条铁律）
```

## 规范文档索引

所有规范文档是**唯一真相源**，代码与规范不一致时必须修一边：

- **Layer 1 组件规范**：`langextract/docs/MinerU-API-Specification.md`
- **Layer 2 集成拓扑**：`langextract/docs/bridge-pipeline-specification-v1.0.md`
- **Layer 3 技术架构**：`integration/Agentic-RAG-Architecture.md`
- **Layer 4 三份蓝图**：
  - PRD：`integration/multimodal-rag-prd-v1.0.md`
  - Backend API：`integration/backend-api-architecture-v1.0.md`
  - Frontend Design：`integration/frontend-system-design-v1.0.md`

## 安全与权限

### Deny Hooks（全局拦截）

`.claude/settings.local.json` 配置了 6 条拦截规则，防止危险操作：

- `rm -rf /*` — 防止递归删除根目录
- `git push --force*` — 防止强制推送
- `DROP DATABASE` / `DROP TABLE` — 防止删除数据库
- `MATCH (n) DETACH DELETE n` — 防止清空 Neo4j 图谱

### Agent 权限矩阵

详见 `docs/governance/permissions-matrix.md`：

- **planner**：只读（Read / Glob / Grep / WebSearch）
- **coder**：读写（Read / Write / Edit / Bash）
- **reviewer**：只读（Read / Glob / Grep）
- **debugger**：只读 + 诊断命令（Read / Glob / Grep / Bash）

## 贡献指南

1. **新功能开发**：先调用 `@chatbot-planner` 设计，通过后再实现
2. **Bug 修复**：先调用 `@chatbot-debugger` 定位根因，输出修复方案后再改代码
3. **代码审查**：提交 PR 前必须通过 `@chatbot-reviewer` 审查
4. **测试要求**：后端每个 API 端点必须有集成测试（`backend/tests/`）

## Skill 效果评测

本项目使用 harness-engineering skill 构建，评测数据见 `docs/skill-evaluation/`：

### Iteration 1（首次评测）

| 场景 | 通过率 | 关键发现 |
|------|--------|---------|
| **eval-1-new-project**<br>新项目搭建 | ✅ 5/5 | 正确建议从 Layer 0 开始，避免直接选型 |
| **eval-2-existing-components**<br>现有组件集成 | ⚠️ 4/5 | 遗漏了 MVP 测试步骤 |
| **eval-3-agent-setup**<br>Agent 配置 | ✅ 5/5 | 正确部署四 Agent 协作模式 |

**总体通过率**：14/15（93.3%）

### Iteration 2（改进后评测）

| 场景 | 通过率 | 改进内容 |
|------|--------|---------|
| **eval-2-existing-components**<br>现有组件集成（重测） | ✅ 5/5 | 补齐了 Layer 0 能力边界摸底与 MVP 测试流程 |

**改进效果**：从 4/5 提升到 5/5，修复了 iteration-1 的遗漏项。

### 评测方法

每个场景包含：
- **prompt**：模拟真实用户需求
- **assertions**：5 项质量断言（如"是否建议从 Layer 0 开始"）
- **with_skill** vs **without_skill**：对比使用 skill 前后的响应质量

详细报告：
- [Iteration 1 完整报告](docs/skill-evaluation/iteration-1/review.html)
- [Iteration 1 基准数据](docs/skill-evaluation/iteration-1/benchmark.json)

### 关键指标

使用 harness-engineering skill 后：
- ✅ 100% 的场景建议从 Layer 0 开始（vs 不使用时 0%）
- ✅ 100% 的场景包含 MVP 测试建议（vs 不使用时 33%）
- ✅ 100% 的场景生成规范文档（vs 不使用时 67%）
- ✅ 0% 的场景跳过前置层次直接开工（vs 不使用时 67%）

---

## 常见问题

### Q: 如何添加新的 API 端点？

1. 在 `integration/backend-api-architecture-v1.0.md` 中补充端点规范
2. 在 `backend/routes/` 中实现
3. 在 `backend/tests/` 中添加集成测试
4. 运行 `pytest backend/tests/` 确保通过

### Q: 如何处理环境变量？

- 所有 API Key / Token 只放 `.env`
- `.env` 必须在 `.gitignore` 中
- 提交前运行：`git diff --cached | grep -i "api[_-]key\|secret\|token"`

### Q: 如何查看历史修复报告？

所有历史报告已归档到 `docs/troubleshooting-archive/`，索引见 `docs/troubleshooting-archive/README.md`。

## 许可证

MIT License

## 联系方式

- 项目主页：https://github.com/suiuiui6/graghRAG-agent
- Issue 跟踪：https://github.com/suiuiui6/graghRAG-agent/issues
- Harness Engineering Skill：https://github.com/suiuiui6/harness-engineering-skill
