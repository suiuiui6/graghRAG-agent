# GraphRAG 论文计划评审与增强建议

> 评审日期：2026-06-15
> 评审对象：`docs/superpowers/plans/2026-06-15-graphrag-paper-plan.md`
> 评审性质：投稿前内部预审备忘录
> 评审上下文：本次审阅时工作区 `HEAD` 位于 `727c009`

---

## 1. 文档目的

本备忘录用于固化对当前 GraphRAG 论文计划的内部预审意见，重点回答三个问题：

1. 当前论文计划的大方向是否成立
2. 哪些问题会在投稿或预审阶段最先削弱说服力
3. 现有计划还需要补哪些“证据治理”和“实验治理”动作，才能更稳地支撑 SCI Q4 / 北大核心目标

本文不是论文正文草稿，也不是 rebuttal 文档，而是对当前计划和证据面的审稿人视角增强建议。

---

## 2. 审阅范围

本次评审基于以下本地材料：

- `docs/superpowers/plans/2026-06-15-graphrag-paper-plan.md`
- `iteration-2/eval-2-existing-components/rag_eval/REPORT_FINAL.md`
- `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md`
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py`
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.py`
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json`
- `iteration-2/eval-2-existing-components/rag_eval/RAG-EVAL-SPECIFICATION.md`
- `iteration-2/eval-2-existing-components/rag_eval/release_gate.py`
- `iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl`

边界说明：

- 本次没有对外部期刊目录、最新分区表或具体投稿指南做外部检索。
- 本次没有审阅完整论文草稿，只审阅计划和当前仓库证据面。
- 本次不判断最终录用概率，只判断“当前计划离可辩护投稿包还有哪些差距”。

---

## 3. 核心结论

### 3.1 大方向是对的

当前计划最正确的判断有三点：

1. 主线应锁定为“中文复杂长文档 QA 的系统/评测论文”，而不是算法突破论文。
2. “可靠性、可溯源、拒答鲁棒性、质量-成本权衡”是目前最能成立的论证主轴。
3. 第一优先级确实不是继续堆功能，而是先把 2026-05-28 的综合评测与 2026-06-14 / 2026-06-15 的 release gate 证据面统一。

### 3.2 当前最大风险不是功能不够，而是证据链不稳

计划已经识别到“评测面不一致”问题，但实际问题比计划中写得更严重：

1. 不是只有“不同日期”这么简单，而是“不同统计面、不同叙事口径、且当前产物可被原地覆盖”。
2. `REPORT_FINAL.md` 与 `release_gate_report.md` 之间已经存在足以触发审稿人复现怀疑的明显差异。
3. 当前 `RAG-EVAL-SPECIFICATION.md` 与真实脚本实现也存在规范漂移。

如果不先做证据冻结与规范对齐，后续任何 baseline、ablation、figure 都会建立在不稳定地基上。

---

## 4. 当前计划已经做对的部分

### 4.1 论文定位正确

`2026-06-15-graphrag-paper-plan.md` 把论文定义为：

- 中文长文档 QA
- GraphRAG / KG-RAG 系统论文
- 以 groundedness、refusal、robustness、cost trade-off 为主

这个定位明显优于以下几种高风险定位：

- “首个/最先进 GraphRAG 算法”
- “通用企业级 AI 平台”
- “低成本实时万能问答框架”

### 4.2 计划顺序总体正确

计划把以下事项放在前面是合理的：

- 先统一评测面
- 再做 baseline
- 再做 ablation
- 然后写 Results/Experiments

这符合证据优先的系统论文写法。

### 4.3 风险意识是到位的

计划已经意识到以下风险：

- 新颖性容易被看作工程拼装
- 指标面可能不一致
- 缺少强 baseline
- 长尾成本很难看
- 稿件可能写成项目文档

这说明计划的主问题不是“方向错了”，而是“还需要更严格的证据治理层”。

---

## 5. 当前最需要补强的点

### 5.1 增加一个早于 P0-1 的新阶段：P0-0 证据冻结与产物治理

现有计划的 `P0-1 Unified evaluation rerun on one frozen commit` 还不够。

建议新增：

### P0-0 Evidence Freeze and Artifact Governance

目标：

- 先冻结 paper evidence 的身份，再重跑评测
- 避免 `raw_runs.jsonl`、`metrics_*.json`、`report_*.md` 被后续 rerun 原地覆盖

最低要求：

1. 选定 paper experiment commit
2. 为该 commit 建立独立 artifact 目录
3. 生成 manifest，至少记录：
   - commit hash
   - `ground_truth.json` sha256
   - `raw_runs.jsonl` sha256
   - `metrics_a1/a2/a5` sha256
   - 评测命令
   - Python 环境与模型配置
   - 生成时间
4. 历史 `REPORT_FINAL` 明确标记为 historical snapshot，而不是默认当前主证据
5. 后续文稿只引用冻结目录中的产物，不直接引用会被覆盖的 working files

这一项建议进入所有实验之前，优先级高于 baseline 和 ablation。

### 5.2 必须修复规范漂移

当前 `iteration-2/eval-2-existing-components/rag_eval/RAG-EVAL-SPECIFICATION.md` 与真实实现并不一致，至少存在以下差异：

1. 规范仍以 `relevant_doc_ids` / `retrieved_doc_ids` 为主，而真实脚本已经基于 node-id surface。
2. 规范写的是 faithfulness 使用 LLM-as-judge，但当前 `A2` 实际是规则式验证和关键词覆盖。
3. 规范写的是 `A4` 用 EM/F1，而当前主证据更偏向 retrieval surface、多跳/工具效率、grounding。
4. 规范写了 `QPS`，但当前主报告重点是 latency/token/cost，不是吞吐测试。

按项目宪章，“规范文档是唯一真相源”。因此：

- 要么更新规范，使其对齐当前实现
- 要么按规范改回实现

不能继续允许“主评测规范”和“实际出稿证据”并行漂移。

### 5.3 必须定义一个论文主指标面

当前计划提出要统一：

- `path_hits`
- `pre-rerank`
- `final-context`
- answer grounding / citation

这个方向是对的，但还缺少一句最重要的话：

**哪一个 surface 才是论文主张所依赖的 headline metric。**

建议明确：

1. `final_context` 作为主论文指标面
2. `path_hits` 和 `pre-rerank` 作为诊断面
3. grounding / citation 作为 answer-side 佐证面

否则审稿人很容易问：

- 你们到底是在证明 recall 好，还是证明真正送进生成器的 evidence 好？
- 高 recall 是 raw recall，还是 final usable recall？

### 5.4 需要补一层 GT / 标注治理

当前 `REPORT_FINAL.md` 已明确承认：

- `expected_node_ids` 是人工反向构建
- 某些聚合题边界主观
- T5/T6/T7 样本量偏小

这类限制可以接受，但必须制度化说明。

建议新增一个短小但关键的 annotation protocol 文档或附录，说明：

1. `expected_node_ids` 如何确定
2. `expected_keywords` 如何确定
3. refusal / false-premise 标注规则是什么
4. hop count 如何标注
5. 遇到等价节点、等价表达、列表边界时如何处理

如果能做到，再加一个小型 spot-check 或二次复核，会显著提升可信度。

### 5.5 T5 / T6 / T7 的“100%”表述需要配置信区间

当前计划将 refusal / robustness / false-premise 视为亮点，这没有问题。
但从审稿人视角，以下说法仍偏脆弱：

- 10/10 refusal
- 5/5 noise robustness
- 3/3 false-premise correction

建议：

1. 对这些比例补充 Wilson interval 或 exact binomial interval
2. 在主文中保留百分比，但在表格或脚注中给出样本量
3. 若时间允许，优先扩增 T7 和 T6，而不是只润色文稿

### 5.6 baseline 必须 budget-matched

当前计划的 baseline ladder 是正确的，但还需要补一句硬约束：

**所有 baseline 必须在相同或可比的 retrieval budget / context budget / generation setting 下运行。**

否则很容易被质疑：

- full system 之所以更好，是因为它看了更多东西
- 不是 architecture 更好，而是 token 花得更多

建议在 baseline 表旁边强制汇报：

- recall / grounding
- latency
- input tokens
- total tokens
- cost

也就是让“质量-成本”成为每个 baseline 的共同评估轴。

### 5.7 外部有效性不应完全推迟到 P2

当前计划把“第二文档 / 第二基准”放在 `P2 optional`。
从执行成本上这可以理解，但从说服力上看，建议至少上调到 `P1`。

更稳妥的折中方案：

- 不一定完整做第二大 benchmark
- 但至少做一个轻量的 cross-document transfer slice
- 比如换一个结构不同的文档，人工构造 10 到 20 个问题

这会比增加一个 local/global benchmark 更能缓解“单论文过拟合”质疑。

### 5.8 “Agentic” 这个词要加一个标题门禁

根据当前 `raw_runs.jsonl`、`metrics_a5_performance.py` 和 `release_gate_report.md` 的表现，可以合理怀疑：

- 2026-06-14 surface 更像一个受预算严格约束的 retrieval pipeline
- 不再等同于 2026-05-28 报告中那种强工具链、多轮探索型 agent 行为

因此在论文标题里继续使用 `Agentic GraphRAG` 之前，建议加一个判定条件：

1. frozen commit 是否仍保留多路径策略控制、budget-aware rerank、refusal/generation policy 等 agentic decision logic
2. 如果系统已明显收敛为 bounded pipeline，应考虑改成更保守的标题，如：
   - hybrid retrieval RAG
   - grounded KG-enhanced RAG
   - citation-verified GraphRAG pipeline

这不是要否定现有贡献，而是避免标题强于证据。

---

## 6. 对现有论文计划的建议增强

### 6.1 对第 3 节“Repository Facts” 的增强建议

建议在计划第 3 节后补一小段：

- 当前证据分为 historical evidence 和 current gated evidence
- 两者不能混作同一张主结果表
- 后续 paper figures/tables 只允许引用 frozen artifact bundle

### 6.2 对第 8 节实验计划的增强建议

建议将现有 `8.1 P0` 改为：

1. `P0-0 Evidence freeze and spec alignment`
2. `P0-1 Unified evaluation rerun on one frozen commit`
3. `P0-2 Baseline ladder (budget-matched)`
4. `P0-3 Key ablation package`
5. `P0-4 Failure-bucket challenge set`

其中 `P0-0` 明确包含：

- artifact bundle
- manifest
- 规范对齐
- metric contract table

### 6.3 对第 10 节六周排期的增强建议

建议 Week 1 改成：

- Freeze experiment commit
- Create frozen artifact directory and manifest
- Align `RAG-EVAL-SPECIFICATION.md` with actual scripts
- Write annotation / metric contract note
- Re-run 50-question evaluation on frozen commit
- Re-run release gate on the same commit
- Produce unified metrics ledger
- Record exact commands and output paths

这样 Week 1 的 exit criteria 应该从“one reproducibility note”升级为：

- one frozen commit
- one immutable artifact bundle
- one aligned evaluation spec
- one unified metrics ledger

### 6.4 对第 13 节 Reviewer Risk Register 的增强建议

建议新增两个风险：

#### Risk 6: specification drift undermines credibility

Mitigation:

- align live evaluation spec with actual scripts before drafting
- cite only frozen artifact outputs

#### Risk 7: benchmark credibility is weakened by subjective GT boundaries

Mitigation:

- document annotation protocol
- report confidence intervals
- add a light external transfer slice if feasible

### 6.5 对第 15 节 Immediate Action List 的增强建议

建议将当前“next ten actions”前两项之前插入：

- [ ] Create `P0-0` evidence freeze package
- [ ] Decide the manuscript headline metric surface
- [ ] Align evaluation specification with implemented metrics

---

## 7. 建议新增的最小文档包

如果目标是让论文计划更像真实投稿准备，而不是工程记录，建议至少再新增三份轻文档：

### 7.1 `paper-evidence-freeze-note.md`

内容：

- frozen commit
- artifact paths
- sha256
- commands
- environment
- model / budget settings

### 7.2 `paper-metric-contract.md`

内容：

- 主指标面是什么
- 诊断面是什么
- 哪些数字能进摘要 / 引言
- 哪些数字只能做分析或 appendix

### 7.3 `paper-annotation-protocol.md`

内容：

- GT 构建原则
- keyword / refusal / hop 标注原则
- 歧义题处理规则
- 样本量限制说明

这三份文档很短也没关系，但它们会显著降低评审时的“你们到底按什么口径算”质疑。

---

## 8. 立即行动优先级

### 最高优先级

1. 冻结 paper experiment commit
2. 建立不可变 artifact bundle
3. 统一 `REPORT_FINAL` 风格指标与 `release_gate` 风格指标到同一 commit
4. 修复 `RAG-EVAL-SPECIFICATION.md` 与实现不一致的问题
5. 明确论文 headline metric surface

### 第二优先级

1. 做 budget-matched baseline ladder
2. 做 key ablations
3. 写 annotation protocol
4. 给 T5/T6/T7 补置信区间

### 第三优先级

1. 轻量第二文档外推验证
2. failure bucket 固化
3. figure/table manuscript packaging

---

## 9. 写稿阶段的表述红线

在证据冻结之前，建议避免以下表述：

1. 避免把 2026-05-28 的长尾 latency/cost 结论直接写成当前系统稳定结论。
2. 避免把 release gate 的 smoke-level multi-turn rewrite 结果写成主论文实验证据。
3. 避免在未定义 metric contract 前混用 `path_hits`、`pre-rerank`、`final_context` 数字。
4. 避免把 `100% refusal / robustness` 写成无条件强结论而不附样本量说明。
5. 避免在 frozen commit 尚未确认前，把系统标题定死为 `Agentic GraphRAG`。

---

## 10. 最终判断

当前论文计划不是方向错误，而是还缺少一个“证据资产治理层”。

如果按现状直接往下写稿，最先出问题的不会是 related work，也不会是图做得不够漂亮，而是：

- 同一论文里数字是否来自同一系统版本
- 指标定义是否稳定
- 原始产物是否可追溯
- 规范与实现是否一致

因此，最值得立刻补的不是更多功能，而是：

**P0-0：证据冻结、规范对齐、指标契约、标注治理。**

只要这一层补上，现有计划就能从“方向合理的内部路线图”升级成“更接近真实投稿工程的可执行计划”。

---

## 11. 一句话执行建议

先把“同一 commit、同一评测口径、同一 artifact bundle”做实，再去追 baseline、ablation 和文稿表达；否则后面写得越快，返工越大。
