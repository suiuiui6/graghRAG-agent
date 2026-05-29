# graghRAG-agent — 项目宪章

> 驾驭工程搭建期完成日期：2026-05-28，自此进入维护期。
> 维护期工作模式见 yujia-engineering skill 的"何时退出本方法论"章节。

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
| `plans/` | 实施计划 |
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

新成员从零搭建：阅读对应子目录的 `CLAUDE.md`，按其指引创建 `.venv` 并复制 `.env.example` 为 `.env`。

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
- 引入新核心组件 → 触发重新进入 Layer 0；调整集成拓扑 → Layer 2；新增主功能模块 → Layer 4
- 每月最后一个工作日由 chatbot-reviewer 巡检规范文档漂移，详情见 `docs/governance/entropy-rotation.md`
