# graghRAG-agent — 项目宪章

> Harness Engineering 搭建期完成日期：2026-05-28，自此进入维护期。
> 默认维护流程为本文件定义的 Superpowers＋项目工作流；goal＋Harness 仅按用户明确选择启用。

## 7 条铁律

1. 前端代码统一放在 `frontend/`，后端代码统一放在 `backend/`
2. 所有 API Key / Token 仅放 `.env`，`.env` 必须在 `.gitignore`；提交前用 `git diff --cached | grep -i "api[_-]key\|secret\|token"` 自检
3. **环境隔离**：Python 子项目每个独立 `uv venv .venv --python 3.12`；Node 子项目用 `pnpm` + `.nvmrc`；组件间依赖互不污染
4. `.Codex/agents/` 必须部署 planner / coder / reviewer / debugger 四个 Agent；缺一不可
5. 后端每个 API 端点必须有 `backend/tests/` 下的集成测试，跑在真实依赖（非 mock）上
6. 依赖必须锁定（`uv.lock` / `pnpm-lock.yaml`）；提交前运行漏洞扫描；日志输出禁止出现 API Key / Token
7. **规范文档是唯一真相源**：代码与规范不一致 → 必须修一边，不留下不一致状态

## 启动与跨 Agent 接续

每次开始工作依次读取：本文件 → [memory/index.md](memory/index.md) → 相关日期记录 → 当前任务的需求、设计、契约及计划。检查 Git 分支、工作区与工具能力，保留其他任务未提交的修改。memory 记录进度与历史，不替代 docs 中的有效规范；发现冲突先核实并回流权威文档。

结束、切换工具或交接前更新 memory 索引与日期记录：已做事项、决策依据、相关文件、实际验证命令与结果、阻塞项、下一步。不得写入密钥、原始长聊天或把推测标为完成。

## 完整工作流与技能

默认使用下述工作流，不因任务跨层、规模较大或“继续做到完成”等表述自动启动 goal 或 Harness。只有用户明确调用或明确同意使用时才启用对应编排；显式 goal 流程可按其协议加载 Harness。默认流程不创建、更新或自动接续 goal 状态；既有状态保留历史，不能单凭状态文件推断新的授权。已明确选择且仍在进行的运行保留原授权。

保留 Harness 的关键检查：新/替换核心组件先核实能力与非能力边界；先在独立环境跑通最小真实输入输出再集成；假设失效只重开受影响设计并复验消费者；测试证据绑定最终代码快照。这些检查直接进入设计、评审与验证，不要求额外 Layer 分类或第二套状态机。

使用 Superpowers 技能辅助执行。下表使用技能短名称；支持命名空间的工具可使用 `superpowers:<名称>`。先发现并读取实际安装的技能；未安装时按同一文档协议执行并记录缺失，不能声称已调用。完整责任、模板及阶段出口见 [工作流规范](docs/governance/agent-workflow.md)。

| 阶段 | 对应技能 | 必须产出 |
|---|---|---|
| 启动、接续 | using-superpowers | 当前状态及输入规范定位 |
| 需求、总体方案、详细设计 | brainstorming | 验收标准、方案取舍、接口/数据流/异常及测试设计 |
| 独立设计评审 | requesting-code-review（适配设计检查表） | 需求覆盖、契约、风险、可测试性评审 |
| 修改设计、复核 | receiving-code-review（适配设计意见） | 逐项处理依据与复核结论 |
| 编码计划 | writing-plans | 任务依赖、文件归属、验证方法、完成标准 |
| 隔离、独立任务并行 | using-git-worktrees、dispatching-parallel-agents | 按需要隔离；明确所有权，禁止相互覆盖 |
| 按计划编码 | subagent-driven-development 或 executing-plans；test-driven-development | 实现、有效测试、任务状态及偏离理由 |
| 代码评审、修改 | requesting-code-review、receiving-code-review | 正确性、安全、契约及测试质量闭环 |
| 单元测试 | test-driven-development、verification-before-completion | 实际执行记录与有效断言 |
| 集成、功能测试 | verification-before-completion；UI 补充 webapp-testing | 真实依赖及验收场景证据 |
| 适应性测试 | verification-before-completion；失败用 systematic-debugging | 环境/配置、故障、异常输入、规模、兼容与恢复证据 |
| 故障定位、回归 | systematic-debugging、test-driven-development | 根因、复现、修复及回归 |
| 交付、归档 | verification-before-completion、finishing-a-development-branch | 提交门槛核验、规范回流、记忆更新及复用总结 |

设计评审使用上述评审技能的组织方式适配，非独立原生设计评审技能；webapp-testing 是补充技能。功能测试、适应性测试和归档不能仅凭调用技能判定完成，必须有对应产出与证据。

新功能先总体设计，再详细设计，独立评审后修改与复核，通过后制定计划并执行。用户确认设计与计划后持续推进；只在需要产品判断、授权或真实阻塞时暂停。普通 Bug 复用既有设计，走 debugger → coder → reviewer → 适用验证 → 交接的精简流程，不重新做整套架构设计。

设计者和评审者必须独立上下文，可配置不同模型（如 DeepSeek 设计、GLM 评审）。不可访问指定模型时记录未执行并生成交接包，不伪造外部评审。各任务明确文件所有权、输入版本、输出位置及验收标准；阻断问题关闭后才能进入下一阶段。

## Git 提交门槛：行与分支覆盖率分别 ≥90%

每次 Git 提交前，相关可执行子项目的**全量第一方生产代码行覆盖率 ≥90%，且分支覆盖率 ≥90%**，全部规定测试通过。跨子项目变更逐个达标，不能使用跨项目平均值、混合总分、仅变更行或仅已导入文件的覆盖率代替。按原始计数判断，不以四舍五入越过门槛。

相关子项目按变更影响与固定测试策略确定；纯文档或治理变更按项目测试策略所列全部第一方可执行子项目核验。尚未定义完整范围时视为证据不足，不允许将范围设为空来通过门槛。

- 覆盖范围固定且包含未导入的生产文件；依赖、虚拟环境、生成代码、构建输出及测试自身不作生产分母。范围调整须有理由及独立评审，禁止为达标排除业务代码。
- 保留最终待提交代码对应的命令、时间、代码快照标识、配置、退出码、两项原始计数及百分比、机器可读报告和日志。代码或覆盖配置变化须重新验证，旧报告及 Agent 自报不算证据。
- 禁止删弱断言、无理由跳过测试、增加忽略标记、缩小统计范围、修改报告、吞掉失败退出码、降低阈值或绕过检查。评审者同时检查测试的行为断言与异常分支，90% 不能替代测试质量和功能正确性。
- 缺少任一指标、无法执行、报告失效或未达标时禁止 git commit/push；更新 memory 记录阻塞，不得虚称完成。纯文档、memory、patterns 提交也不自动豁免。
- 当前 Windows 执行为 `audit-only-windows`，文档约束不能保证机械阻断。可信 CI、保护分支与禁止绕过策略需另行建设，未配置前不得声称已经启用。详见 [测试与覆盖率规范](docs/testing/README.md)。

工程投入优先补齐真实行为测试、全量双指标证据、真实依赖集成与安全扫描，再建设可信 CI 必需检查及保护分支。CI 必须分别检查两指标及统计范围，缺报告或失败不得放行；不能用增加编排状态或报告格式替代这些执行证据。实际 CI 门禁未验证前如实记录未启用。

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
| `docs/index.md` | 全部文档入口与现有有效规范导航 |
| `docs/requirements/`、`docs/design/`、`docs/contracts/` | 新需求、总体/详细设计及契约；历史权威文档保留原位 |
| `docs/plans/`、`docs/review/`、`docs/testing/`、`docs/archive/` | 新计划、评审、验证证据及被替代文档 |
| `memory/` | 索引及日期工作记录，用于跨 Agent、跨工具接续 |
| `patterns/` | 有适用条件、限制及来源证据的可复用范式 |

## 规范文档索引（Layer 0-4 产出）

- **Layer 1 组件规范**：`langextract/docs/MinerU-API-Specification.md`、`langextract/docs/MinerU_MVP测试配置指南.md_v1.0.md`、`langextract/docs/LangExtract-Pipeline-Specification.md`
- **Layer 2 集成拓扑**：`langextract/docs/bridge-pipeline-specification-v1.0.md`
- **Layer 3 技术架构**：`langextract/docs/agentic-kg-rag-specification-v1.0.md`、`integration/Agentic-RAG-Architecture.md`
- **Layer 4 三份蓝图**：`integration/multimodal-rag-prd-v1.0.md`、`integration/backend-api-architecture-v1.0.md`、`integration/frontend-system-design-v1.0.md`
- **企业级演进蓝图**：`integration/enterprise-evolution-blueprint-v1.0.md` — 协作闭环 / 数据资产 / 生态集成 + Engine-Vue 对接方案

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

新成员从零搭建：读取存在的子目录 `AGENTS.md`；不存在时继承根规则并读取对应依赖配置及有效规范。按子项目创建独立环境，并在存在 `.env.example` 时复制为 `.env`。

## 新项目初始化与复用

将本协议用于新项目时，先确认目标、范围和技术边界，再创建 docs/memory/patterns 及索引；先检查是否已在 Git 仓库内，仅在尚未初始化且目标目录明确时初始化 Git。写入项目自己的 AGENTS.md、环境/依赖约束和验收规则，然后按上述设计→评审→计划→实现流程推进。现有项目补齐缺失结构，不重建 Git、不覆盖用户文件。

项目专属架构和命令留在项目规则；通用范式提炼到 patterns，注明来源和限制。插件不可用时保留同等阶段产出和检查标准，避免把协作协议绑定到某个 AI 品牌。

## Agent 使用指引

| 场景 | 调用 |
|------|------|
| 设计新页面 / 新流程 | `chatbot-planner`（只读） |
| 写代码 / 改代码 | `chatbot-coder` |
| 联调遇到具体故障 | `chatbot-debugger`（只读 + Bash） |
| 代码静态审查 | `chatbot-reviewer`（建议 `run_in_background: true`） |

bug 流：debugger 出根因 → coder 改 → reviewer 复审。

## 治理规则（维护期）

- 单 Bug 修复只更新受影响规范，不重开整体蓝图，除非暴露蓝图根本性遗漏
- 任何"修复报告 / troubleshooting 笔记"必须先回流到对应 Layer 规范文档，再 `git mv` 到 `docs/troubleshooting-archive/`，**禁止散落仓库根**
- 引入新核心组件 → 核实能力边界及独立 MVP；调整集成拓扑 → 更新拓扑及受影响契约；新增主功能模块 → 更新需求、设计及开发计划。仅在用户明确选择 goal＋Harness 时映射到 Layer 0/2/4，不自动启动该编排。
- 每月最后一个工作日由 chatbot-reviewer 巡检规范文档漂移，详情见 `docs/governance/entropy-rotation.md`
