# harness-engineering 评测语义映射实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `harness-engineering` iteration-1 评测数据中的 Layer 0-6 语义，与 `docs/superpowers/skill-evaluation.md` 中的 Superpowers skill taxonomy 建立一份可追踪、可验证、不中断历史 benchmark 的映射说明。重点不是重写历史成绩，而是明确三类真相源：`evals.json` 定义断言、`benchmark.json` 记录结果、`docs/superpowers/skill-evaluation.md` 负责解释这些结果如何投影到 superpowers 体系。

**Architecture:** 只做文档与少量评测措辞修正，不改产品代码、不重跑 benchmark。先修正 iteration-1 中明显错位的层编号描述，再新增一份映射文档，最后在 README / superpowers 总览中建立跳转。所有映射都必须回指到现有评测原文，避免把 superpowers 变成新的主评判标准。

**Tech Stack:** Markdown、JSON、已有评测产物（`evals.json` / `benchmark.json` / `review.html`）、`rg` / `jq` / `git diff` 验证。

---

## 背景：当前不一致点

基于现有文件可确认以下事实：

- `harness-engineering/evals/evals.json` 仍把 BridgePipeline 写成 `Layer 3`、蓝图写成 `Layer 5`、项目规范写成 `Layer 6`，与当前方法论的 Layer 0-6 编号不一致。
- `harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json` 的实际结果已经按“已有组件从 Layer 2/4/5 继续推进”的语义给出 evidence，但断言文本保留了旧编号术语。
- `harness-engineering/evals/skill-evaluation/iteration-1/review.html` 只是渲染 `benchmark.json` 内容，本身没有独立的层级知识，因此不应单独修文案，而应通过上游数据和旁路说明文档解释。
- `docs/superpowers/skill-evaluation.md` 已经在做 skill 级别评测汇总，但还没有把 harness-engineering 的 Layer 0-6 方法论，映射到 superpowers 的“需求澄清 / 规范约束 / 任务编排 / 代码审查 / 验证闭环”等能力标签。

因此这次修复分三层处理：

1. 修正评测定义中的层号漂移。
2. 补一份“Layer → superpowers 能力映射”说明文档。
3. 在已有 README / superpowers 文档中加引用，让后续读者知道该去哪里理解这层映射，而不是重新解读 benchmark。

---

## 文件落点

```
D:/graghRAG-agent/
├── docs/
│   ├── skill-evaluation/
│   │   └── README.md                                 # [修改] 加入 mapping 文档索引
│   └── superpowers/
│       ├── skill-evaluation.md                       # [修改] 补 harness-engineering 映射摘要
│       └── harness-engineering-layer-mapping.md     # [新建] Layer 0-6 ↔ superpowers 对照表
├── harness-engineering/
│   └── evals/
│       ├── evals.json                               # [修改] 修正旧层编号表述
│       └── skill-evaluation/
│           └── iteration-1/
│               ├── benchmark.json                   # [可选修改] 仅在需要时同步断言文本，不改结果值
│               └── benchmark.md                     # [可选修改] 若有旧“7-layer”措辞则统一
└── plans/
    └── harness-engineering-remediation-plan.md      # [本文件]
```

---

## Task 1: 修正 iteration-1 评测定义中的层号漂移

**Why:** 当前 `evals.json` 的断言文本仍把集成拓扑 / 产品蓝图 / 项目规范分别写成 Layer 3 / 5 / 6。这会把历史 benchmark 的解释锚点固定在旧编号上，后续无论映射到 superpowers 还是对外说明都会持续歧义。

**Files:**
- Modify: `D:/graghRAG-agent/harness-engineering/evals/evals.json`

- [ ] **Step 1: 写失败检查，确认旧编号仍存在**

Run:

```bash
rg -n "Layer 3|Layer 5|Layer 6|BridgePipeline" D:/graghRAG-agent/harness-engineering/evals/evals.json
```

Expected before fix:

- Eval 2 `expected_output` 或 `expectations` 中能看到 `BridgePipeline（Layer 3）`
- 同段能看到 `产品蓝图阶段（Layer 5）`
- 同段能看到 `开发规范（Layer 6）`

- [ ] **Step 2: 只修正编号，不改断言意图**

按当前 methodology 统一为：

- BridgePipeline / 集成拓扑 → `Layer 2`
- PRD / Backend API / Frontend Design 蓝图 → `Layer 4`
- 项目目录结构 / 开发规范 / Agent 协作约束 → `Layer 5`
- 正式施工与验证闭环 → `Layer 6`

需要修改的典型句子包括：

```text
若桥接尚未完成则建议先建立BridgePipeline（Layer 3），若桥接已完成则确认状态并引导进入产品蓝图阶段（Layer 5）
```

改为：

```text
若桥接尚未完成则建议先建立BridgePipeline（Layer 2），若桥接已完成则确认状态并引导进入产品蓝图阶段（Layer 4）
```

以及：

```text
响应中建议在写产品代码之前生成PRD和后端API规范（Layer 5）
```

改为：

```text
响应中建议在写产品代码之前生成PRD和后端API规范（Layer 4）
```

以及：

```text
响应中建议确立项目目录结构和开发规范（Layer 6）：frontend/、backend/、.env管理、uv虚拟环境
```

改为：

```text
响应中建议确立项目目录结构和开发规范（Layer 5）：frontend/、backend/、.env管理、uv虚拟环境
```

- [ ] **Step 3: 验证旧编号只在允许位置保留**

Run:

```bash
rg -n "Layer 3|Layer 5|Layer 6" D:/graghRAG-agent/harness-engineering/evals/evals.json
```

Expected after fix:

- 不再出现把 BridgePipeline 说成 `Layer 3` 的语句
- 不再出现把蓝图阶段说成 `Layer 5` 的语句
- 不再出现把项目规范说成 `Layer 6` 的语句

- [ ] **Step 4: 校验 JSON**

Run:

```bash
jq empty D:/graghRAG-agent/harness-engineering/evals/evals.json
```

Expected: exit code 0 and no output.

---

## Task 2: 建立 Layer 0-6 到 superpowers 的显式映射文档

**Why:** `benchmark.json` 是历史结果，不适合承载新的解释框架；`skill-evaluation.md` 是总览页，不适合塞进大段层级定义。需要一份独立文档把 harness-engineering 的方法论步骤，映射为 superpowers 视角下的可复用能力标签。

**Files:**
- Create: `D:/graghRAG-agent/docs/superpowers/harness-engineering-layer-mapping.md`

- [ ] **Step 1: 先列出映射边界，不直接写结论**

文档开头必须说明三件事：

- `Layer 0-6` 是 harness-engineering 的过程模型，不是 superpowers 的官方分类。
- superpowers 映射是“解释层”，用于帮助读者把评测结果迁移到通用技能框架理解。
- benchmark 的通过/失败仍以 `harness-engineering/evals/evals.json` 与 `benchmark.json` 为准。

- [ ] **Step 2: 写核心映射表**

至少覆盖以下对照关系：

| Harness Layer | 核心动作 | 对应 superpowers 能力标签 | 证据来源 |
|---|---|---|---|
| Layer 0 | 能力边界摸底 / 先探索再选型 | requirements-clarification / exploratory-analysis | eval 1 expectations |
| Layer 1 | MVP 实测与组件规范 | evidence-driven-validation / spec-first-delivery | eval 1 expected_output |
| Layer 2 | 集成拓扑与 BridgePipeline | systems-integration-planning / interface-contracting | eval 2 expected_output |
| Layer 3 | 技术架构沉淀 | architecture-synthesis / dependency-boundary-design | methodology reference |
| Layer 4 | PRD + Backend API + Frontend Design | blueprint-authoring / implementation-contracts | eval 2, eval 3 |
| Layer 5 | 项目规范、目录结构、Agent 角色边界 | repo-governance / workflow-orchestration | eval 3 expectations |
| Layer 6 | coder/reviewer/debugger 执行与验证闭环 | execution-discipline / review-and-verification | benchmark + review flow |

注：具体标签命名应以 `docs/superpowers/skill-evaluation.md` 现有措辞为准，避免在新文档里创造新的 taxonomy 词汇。如果总览文档没有现成术语，就用自然语言短语，不要伪造“官方枚举”。

- [ ] **Step 3: 在文档尾部补“如何阅读 iteration-1 benchmark”**

必须明确：

- Eval 1 主要测 Layer 0/1/4/5 的起手顺序是否正确
- Eval 2 主要测“已有组件时从 Layer 2 继续推进”的能力
- Eval 3 主要测 Layer 5-6 的 agent 编排与执行约束

并加一句：剩余 fail 项“未完整提及三 Agent 协作流程”属于 Layer 5/6 交界，不应被误读为前序层能力失败。

---

## Task 3: 在 superpowers 总览和 skill-evaluation README 中挂出入口

**Why:** 如果只新增映射文档而不挂入口，后续维护者仍会继续直接解读 `benchmark.json` 或 `review.html`，导致重复劳动和再次漂移。

**Files:**
- Modify: `D:/graghRAG-agent/docs/superpowers/skill-evaluation.md`
- Modify: `D:/graghRAG-agent/docs/skill-evaluation/README.md`

- [ ] **Step 1: 在 `docs/superpowers/skill-evaluation.md` 增加 harness-engineering 小节**

补充内容应包含：

- 一句说明 harness-engineering 的核心贡献不是“会写代码”，而是“把项目启动与落地拆成 Layer 0-6 的验证链”。
- 一句链接到 `harness-engineering-layer-mapping.md`。
- 一句提示 iteration-1 benchmark 保持原始评测结果不变，映射文档只负责解释。

- [ ] **Step 2: 在 `docs/skill-evaluation/README.md` 增加 mapping 索引**

README 至少要说明：

- `harness-engineering/evals/skill-evaluation/iteration-1/` 是原始 benchmark 数据目录
- `docs/superpowers/harness-engineering-layer-mapping.md` 是语义映射入口
- 读 benchmark 时应先看断言定义，再看结果，再看 superpowers 映射解释

- [ ] **Step 3: 校验两个入口都能 grep 到 mapping 文档名**

Run:

```bash
rg -n "harness-engineering-layer-mapping" D:/graghRAG-agent/docs/superpowers/skill-evaluation.md D:/graghRAG-agent/docs/skill-evaluation/README.md
```

Expected: 两个文件都至少各出现一次映射文档引用。

---

## Task 4: 视需要同步 benchmark 文案，但不改成绩数据

**Why:** `benchmark.json` 中某些 expectation `text` 是从旧断言复制来的。如果 Task 1 修改了 `evals.json` 后，历史 benchmark 的展示文本仍显著使用旧编号，可以同步修正文案；但严禁改 `passed` / `failed` / `evidence` / `run_summary` 数值，以免伪造历史结果。

**Files:**
- Modify if needed: `D:/graghRAG-agent/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json`
- Modify if needed: `D:/graghRAG-agent/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md`

- [ ] **Step 1: 检查 benchmark 是否仍暴露旧层号**

Run:

```bash
rg -n "Layer 3|Layer 5|Layer 6|7-layer" D:/graghRAG-agent/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json D:/graghRAG-agent/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md
```

Expected before fix: 可能命中 `Layer 5`、`7-layer` 等旧措辞。

- [ ] **Step 2: 只改展示文字，不改历史结果字段**

允许修改：

- `expectations[].text`
- `notes[]` 中对层号的概括语
- `benchmark.md` 中对 methodology 的简介文字

禁止修改：

- `passed` / `failed` / `total`
- `evidence`
- `run_summary`
- 时间 / token / error 统计

- [ ] **Step 3: 校验 benchmark JSON 仍合法，且统计值未变化**

Run:

```bash
jq '.run_summary, [.runs[].result.pass_rate]' D:/graghRAG-agent/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.json
```

Expected: `run_summary` 数值与修改前保持一致，仅文本字段发生变化。

---

## Task 5: 最终验收

- [ ] **Step 1: 做一次全局 grep，确认旧映射歧义已收敛**

Run:

```bash
rg -n "BridgePipeline（Layer 3）|产品蓝图阶段（Layer 5）|开发规范（Layer 6）|following 7-layer methodology" D:/graghRAG-agent
```

Expected:

- `harness-engineering/evals/evals.json` 中不再出现这些旧表述
- 若仓库中仍有历史归档文档命中，需确认它们属于历史记录而不是当前解释入口

- [ ] **Step 2: 做一次变更范围审查**

Run:

```bash
git diff -- docs/superpowers docs/skill-evaluation harness-engineering/evals plans/harness-engineering-remediation-plan.md
```

Expected: 只包含本计划定义的文档 / JSON 变更，无产品代码改动。

- [ ] **Step 3: 记录最终结论**

验收完成后，实施结果必须能回答以下三个问题：

1. iteration-1 benchmark 的原始评分依据在哪里定义？
2. Layer 0-6 分别如何映射到 superpowers 语义？
3. 为什么这次没有重跑 benchmark，也没有修改历史分数？

如果还有一个问题答不上来，说明映射链条仍然不完整，不应结束任务。
