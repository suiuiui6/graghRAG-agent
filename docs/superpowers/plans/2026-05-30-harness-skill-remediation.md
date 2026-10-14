# Harness Engineering Skill 误导性表述整改方案

> **目标**：清理 `harness-engineering` skill 中会误导模型或读者的三类信息源：方法论文档中的默认技术栈暗示、Agent 模板中的硬编码实现偏好、README/benchmark 中带主观解释的评测宣称。

## 背景判断

当前问题不是单点笔误，而是三条内容链条互相放大：

1. `references/methodology.md` 在 Layer 5 把 Python/Node.js 写成“当前默认范围”，容易让模型把方法论误解成特定技术栈模板，而不是跨栈约束框架。
2. `references/agent-templates/chatbot-coder.md` 直接预设 React/FastAPI/Tailwind/Pydantic，会把通用 coder 模板扭成特定项目脚手架提示词。
3. `README.md` 与 `evals/skill-evaluation/iteration-1/benchmark.md` 使用“排除评测设计问题后的实际通过率”“with-skill would be ~93%”这类解释性语言，把评测结论从“记录结果”扩大成了“替结果做辩护”。

这三类表述叠加后，会让外部读者和模型都形成错误预期：

- 误以为该 skill 官方推荐 React + FastAPI 作为默认工程栈。
- 误以为评测结果允许按主观判断重算。
- 误以为方法论强绑定某个示例项目，而不是强调“先实测、后纳入规范”。

## 整改原则

1. **去默认技术栈化**：保留“按宿主项目技术栈落地”的要求，删除会被读成推荐栈的硬编码示例。
2. **去评测辩护化**：保留原始 benchmark 结果和已知限制，但不再把“修正后分数”写成正式宣传结论。
3. **去项目绑定化**：示例项目可以存在，但必须明确是案例，而不是方法论默认实现。
4. **最小改动**：仅修改误导性表述，不重写整套方法论，不改动 benchmark 原始数据文件。

## 影响范围

### A. 方法论正文

- `D:/graghRAG-agent/harness-engineering/references/methodology.md`
- 重点位置：Layer 5 技术栈映射表、默认范围声明、依赖扫描与隔离环境描述。

### B. Agent 模板

- `D:/graghRAG-agent/harness-engineering/references/agent-templates/chatbot-coder.md`
- 如检索后发现 planner/reviewer/debugger 也引用具体前后端栈，一并纳入同轮整改。

### C. 对外说明与评测基线文案

- `D:/graghRAG-agent/harness-engineering/README.md`
- `D:/graghRAG-agent/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md`

## 实施步骤

### 任务 1：修正方法论文档中的“默认技术栈”误导

**目标**：把 Layer 5 从“默认 Python + Node.js”改成“按项目技术栈建立映射表，仓库仅提供示例格式”。

**文件**：

- `D:/graghRAG-agent/harness-engineering/references/methodology.md`

**计划改动**：

1. 重写 `### 技术栈映射表` 前后的说明文字。
2. 将“当前默认范围为 Python + Node.js”改为“下表仅示例映射格式，实际条目必须由项目团队按已选技术栈补齐”。
3. 保留 Python / Node 行作为示例时，必须显式标注“示例”，避免被读成推荐默认值。
4. 检查 Layer 5、Layer 6 中所有“按技术栈映射表执行”的表述，确保语义变为“按项目自定义映射表执行”，而不是“按本文内置映射表执行”。

**验收检查**：

```bash
rg -n "当前默认范围为 Python \+ Node\.js|FastAPI|React 18|Tailwind CSS|Pydantic" D:/graghRAG-agent/harness-engineering/references/methodology.md
```

通过标准：

- 不再出现“当前默认范围为 Python + Node.js”。
- 若保留语言行，仅作为“示例映射格式”存在，不出现框架级默认推荐。

### 任务 2：把 coder Agent 模板改成宿主项目感知，而不是框架预设

**目标**：让 `chatbot-coder` 模板先遵循项目既有技术栈与规范，再决定实现方式。

**文件**：

- `D:/graghRAG-agent/harness-engineering/references/agent-templates/chatbot-coder.md`

**计划改动**：

1. 改写角色定义，删除“你同时掌握前端 React/后端 FastAPI”的默认身份设定，替换为“根据项目实际技术栈完成实现”。
2. 改写工作原则中的类型系统、CSS、API 规范描述，去掉 Pydantic、Tailwind、RESTful `/api/v1/` 这类具体框架/风格绑定。
3. 删除或重写“项目技术栈”整段，改成使用说明：执行前先读取项目现有 stack、目录结构、测试方式和 design system。
4. 检查是否需要在模板中新增一条硬约束：若规划方案与仓库现状冲突，先指出冲突，不凭空套用示例技术栈。

**验收检查**：

```bash
rg -n "React 18|Tailwind CSS|FastAPI|Pydantic|/api/v1/|fetch" D:/graghRAG-agent/harness-engineering/references/agent-templates/chatbot-coder.md
```

通过标准：

- 不再残留任何被读作“默认实现栈”的硬编码框架词。
- 模板明确要求优先遵循宿主项目实际约束。

### 任务 3：收敛 README 中的评测宣传措辞

**目标**：README 只陈述可追溯事实，不把“人工解释后的更高分数”作为对外结论。

**文件**：

- `D:/graghRAG-agent/harness-engineering/README.md`

**计划改动**：

1. 重写“评测效果”表格或脚注，使其与 benchmark 原始结果保持一致。
2. 删除 `93%*` 和 `*排除评测设计问题后的实际通过率` 这类主观修正分数。
3. 如果需要保留“评测存在设计局限”，改为中性表述，并把说明落到 benchmark 细节页，而不是 README 主结论区。
4. 检查示例项目段落，确保 `graghRAG-agent` 被表述为“实践案例”，而不是推荐宿主架构。

**验收检查**：

```bash
rg -n "93%\*|排除评测设计问题后的实际通过率|实际通过率" D:/graghRAG-agent/harness-engineering/README.md
```

通过标准：

- README 不再出现重算后的通过率。
- README 中的分数、措辞与 benchmark 摘要可直接对应。

### 任务 4：收敛 benchmark 摘要中的解释性辩护文案

**目标**：保留已知评测缺陷说明，但不把“would be ~93%”写成事实性主结论。

**文件**：

- `D:/graghRAG-agent/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md`

**计划改动**：

1. 保留 Eval2 / Eval3 的局限性说明，因为它们属于评测背景信息。
2. 删除 `with-skill would be ~93% vs without-skill ~73%` 这种反事实重算语句。
3. 将“following 7-layer methodology explicitly”改写为更中性的观察，例如“responses emphasized the documented Layer 0-6 process more strongly”。
4. 确保 benchmark.md 仍然忠实呈现原始表格数据，不修改任何分数。

**验收检查**：

```bash
rg -n "would be ~93%|93%|7-layer methodology explicitly" D:/graghRAG-agent/harness-engineering/evals/skill-evaluation/iteration-1/benchmark.md
```

通过标准：

- 不再出现反事实重算分数。
- 观察性备注不再伪装成正式结论。

## 执行顺序

建议按以下顺序落地，减少反复改文案：

1. 先改 `methodology.md`，建立“按宿主项目技术栈落地”的统一口径。
2. 再改 `chatbot-coder.md`，让 Agent 模板遵循新的统一口径。
3. 然后改 `benchmark.md` 与 `README.md`，把对外叙述收敛到可追溯事实。
4. 最后跑一次全文 grep，确认误导性词汇没有从别处漏出。

## 全量回归检查

```bash
rg -n "当前默认范围为 Python \+ Node\.js|React 18|Tailwind CSS|FastAPI|Pydantic|93%\*|排除评测设计问题后的实际通过率|would be ~93%" D:/graghRAG-agent/harness-engineering
```

**预期**：

- 方法论、Agent 模板、README、benchmark 主文档中不再出现上述误导性表述。
- 若仍有命中，只能出现在历史评测产物、样例输出或明确标注为历史记录的归档文件中；不能留在当前对外主文档里。

## 风险与边界

1. 不修改 `evals/skill-evaluation/.../grading.json`、历史 `outputs/response.md` 等评测产物，因为它们属于历史记录，不应被“洗稿”。
2. 不追求把所有语言示例全部删空；关键是把“示例”与“默认推荐”区分清楚。
3. 若 README 当前分数直接引用 iteration-1，而 benchmark 后续还有 iteration-2/3，后续可以再单独规划“评测基线版本化”整改；这不属于本轮最小修复范围。

## 完成定义

满足以下条件即可视为本轮整改完成：

- 方法论文档不再把 Python/Node.js 写成默认适用范围。
- coder Agent 模板不再内置 React/FastAPI/Tailwind/Pydantic 等实现偏好。
- README 与 benchmark 摘要不再使用重算后的通过率作为宣传结论。
- 全量 grep 仅在历史评测样本或归档记录中命中旧表述，主文档全部清理完成。
