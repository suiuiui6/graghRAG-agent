# Agent 工作流规范实施计划

> For agentic workers: 使用 executing-plans 按任务执行；独立 reviewer 复核最终文档。仅修改本计划列出的文档，不创建 Git 提交。

**Goal:** 落地已确认的 Agent 协作设计与双覆盖率提交门槛。

**Architecture:** AGENTS.md 为公共入口，治理文档承载详细流程，docs 索引关联现有规范，memory 记录接续状态，patterns 提供经验证的复用协议。

**Tech Stack:** Markdown、Git 只读检查、PowerShell 文档检查；无产品代码变更。

设计：[已确认设计](../design/2026-10-12-agent-workflow-design.md)。用户于 2026-10-12 确认。

## 执行任务

- [x] 1. 更新 `AGENTS.md`：保留七条铁律和 Layer 规则，增加启动、技能映射、双 90% 门槛及目录导航。
- [x] 2. 创建 `docs/governance/agent-workflow.md`、`docs/testing/README.md`：写清工作流、角色、证据与提交限制。
- [x] 3. 创建 `docs/index.md` 和 requirements/design/contracts/plans/review/archive 下的 README：索引历史规范，定义新文档归属与模板。
- [x] 4. 创建 `memory/index.md`、`memory/2026-10-12.md` 和 `patterns/index.md`、`patterns/file-based-agent-handoff.md`：如实记录本次任务，不推断其他任务已完成。
- [x] 5. 独立 reviewer 检查范围、矛盾、链接与门槛，记录到 `docs/review/2026-10-12-agent-workflow.md`，修复阻断意见。
- [x] 6. 核验新增文档相对链接、Markdown 空白、技能名称、旧规则保留和 Git 差异；更新记忆及计划状态，交付未提交文件。

## 验证及完成标准

文档检查包含：本任务新增文件及 AGENTS.md 所有 Markdown 本地链接存在；本任务文件无尾部空格、占位词；双指标分别 ≥90% 且未达到时禁止提交的规则可从 AGENTS.md 找到；新旧文档入口不重复建立权威规范；独立评审有真实结果。以实际检查输出记录证据。

不修改其他正在进行的产品工作，不运行具有外部副作用的产品集成测试，不伪造覆盖率。当前未具备双指标达标证据，因此不执行 git add/commit/push；文档结构检查通过不等同于覆盖率通过。
