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
- ⚠️ 子目录 CLAUDE.md 覆盖不全：`frontend/CLAUDE.md` 存在，`backend/CLAUDE.md` 状态待补

**整改项**：下一轮自检前补齐 `backend/CLAUDE.md`。

---

### tools：每个工具的输入输出/限制/失败模式有实测记录吗？

**结论**：✅ 达标

- LangExtract 能力边界：`.claude/projects/D--graghRAG-agent/memory/project_langextract_capability_boundary.md`
- MinerU API 规范（含失败码）：`langextract/docs/MinerU-API-Specification.md`
- MinerU MVP 实测：`langextract/docs/MinerU_MVP测试配置指南.md_v1.0.md`
- Bridge Pipeline 6 阶段 schema：`langextract/docs/bridge-pipeline-specification-v1.0.md`（Task 3 已追加凭证失败模式）

---

### environment：新成员按 CLAUDE.md 能在 30 分钟内搭好可运行环境吗？

**结论**：⚠️ 部分达标

- ✅ 根 `CLAUDE.md`（Task 2）含激活命令
- ✅ `.claude/projects/.../memory/project_env_isolation.md` 记录 uv 隔离原则
- ⚠️ `backend/.env.example` / `langextract/.env.example` 是否齐全且键名同步最新代码待核查
- ❌ 未配置 deny hooks 拦截危险命令（Task 6 处理）

**整改项**：核查并补齐 `.env.example`；完成 Task 6 配置运行时隔离。

---

### state：跨 session / 跨成员能恢复"项目当前在 Layer 几"吗？

**结论**：✅ 达标

- 根 `CLAUDE.md` 顶部声明"搭建期完成日期 2026-05-28，进入维护期"
- `.claude/projects/D--graghRAG-agent/memory/MEMORY.md` 维护 Layer 0-1 关键决策
- `plans/` 目录保存所有实施计划（含本计划 `harness-engineering-remediation-plan.md`）

---

### feedback：出错时能在 1 步内定位是哪个 Layer 的假设错了吗？

**结论**：⚠️ 部分达标

- ✅ chatbot-debugger 已部署（Task 1 产出）
- ✅ chatbot-reviewer 已部署
- ✅ backend 集成测试在真实依赖上运行（`backend/tests/`）
- ⚠️ iteration-2 评测体系刚引入但未走 Layer 0-1（Task 5 处理）
- ❌ 未建立 entropy 巡检（Task 7 处理）

**整改项**：完成 Task 5 与 Task 7。

---

## 总体结论与下一轮自检计划

| 子系统 | 结论 | 主要整改项 |
|--------|------|-----------|
| instructions | ⚠️ | 补 `backend/CLAUDE.md` |
| tools | ✅ | 无 |
| environment | ⚠️ | 核查 `.env.example`；完成 Task 6 |
| state | ✅ | 无 |
| feedback | ⚠️ | 完成 Task 5、Task 7 |

- 5 项中 2 项 ✅、3 项 ⚠️、0 项 ❌
- 所有 ⚠️ 的整改项已在本计划 Task 5 / Task 6 / Task 7 中覆盖
- **下一轮自检时间**：2026-08-28（季度节奏），由 chatbot-reviewer 触发
