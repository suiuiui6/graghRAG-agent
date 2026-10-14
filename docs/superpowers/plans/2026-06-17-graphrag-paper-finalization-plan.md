# GraphRAG 论文终稿化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 GraphRAG 中文论文 v2 初稿推进为可投稿终稿包，最低目标为北大核心及同类较强中文期刊，冲刺目标为 SCI 四区系统/应用型论文。

**Architecture:** 以“中文复杂长文档问答的可追溯 GraphRAG 系统设计与评测”为论文身份，先冻结证据，再补外部文献、基线、消融、置信区间和轻量迁移，最后按证据优先顺序重写正文。终稿的所有 headline 数字只能来自同一 frozen commit、同一 artifact bundle、同一 metric contract 和可追溯 manifest。

**Tech Stack:** Markdown manuscript, Python evaluation scripts, FastAPI in-process TestClient, `rag_eval` metrics, Git artifact governance, CrossRef/arXiv/Semantic Scholar/OpenAlex/CNKI manual literature workflow, reference-manager export.

---

## 1. 当前状态

### 1.1 已有稿件与治理材料

| 角色 | 文件 | 终稿用途 |
|---|---|---|
| 当前最佳中文初稿 | `docs/superpowers/plans/2026-06-15-graphrag-paper-draft-v2-core-journal.md` | 终稿重写底稿 |
| 既有论文路线图 | `docs/superpowers/plans/2026-06-15-graphrag-paper-plan.md` | 实验与投稿路线基础 |
| 计划预审意见 | `docs/superpowers/plans/2026-06-15-graphrag-paper-plan-review.md` | 证据治理风险清单 |
| 证据冻结说明 | `docs/superpowers/plans/paper-evidence-freeze-note.md` | 终稿数字准入规则 |
| 指标契约 | `docs/superpowers/plans/paper-metric-contract.md` | 主结果面与诊断面边界 |
| 标注协议 | `docs/superpowers/plans/paper-annotation-protocol.md` | GT、拒答、假前提、hop 标注边界 |
| 历史综合评测 | `iteration-2/eval-2-existing-components/rag_eval/REPORT_FINAL.md` | historical evidence，只能解释系统行为和风险 |
| 工程门禁报告 | `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md` | gated engineering surface，只能做复现/工程支撑 |

### 1.2 当前最关键判断

- 当前 v2 已经是合格论文初稿，但不是投稿终稿。
- 现在的瓶颈不是语言，而是证据链还没封死。
- `REPORT_FINAL.md` 中的 2026-05-28 数字属于 historical evidence。
- `release_gate_report.md` 中的 GO、p95/p99、pytest 通过属于工程门禁证据，不是学术主结论。
- 终稿摘要、引言和主结果表只能使用下一次统一冻结后的 current frozen evidence。
- `final-context` 是默认 headline retrieval surface。
- `path_hits` 和 `pre-rerank` 只能进入诊断、消融、失败分析或附录。
- 外部文献可以补，但必须经检索、核验、引用台账和支撑等级审查后进入正文。

## 2. 终稿身份与路线

### 2.1 一句话论证

在中文复杂长文档问答任务中，本文检验一个围绕知识图谱证据、多路径检索、预算约束控制和引用校验生成组织的 GraphRAG 系统，说明其在证据可追溯、回答行为可靠、拒答/纠错可控方面具有应用价值，同时揭示该价值受检索精度、长尾成本、标注边界和外部有效性约束。

### 2.2 三条贡献边界

1. 可审计系统链路：把知识图谱证据、多路径检索、预算约束控制、引用校验生成、拒答和假前提纠错组织为同一问答流程。
2. 证据治理评测协议：区分 `final-context` 主结果面、`path_hits/pre-rerank` 诊断面、answer-support 支撑面和工程门禁面。
3. 经验发现与边界：在冻结评测中报告可靠性、可追溯性和质量-成本权衡，保留低精度、图表/列表盲区、长尾成本和外部有效性限制。

### 2.3 非目标

- 不写成“首个 GraphRAG”。
- 不写成“SOTA 算法论文”。
- 不写成“全面优于现有方法”。
- 不写成“已生产级落地的企业平台”。
- 不写成“通用低成本实时问答框架”。

### 2.4 路线 A: 北大核心/强普刊最低闭环

**适用条件:** 冻结主结果、基础 baseline、关键消融和案例分析完成，但跨文档迁移或国际化文献竞争强度不足。

**重点:** 中文场景价值、系统完整性、评测可复现、证据可追溯、失败分析、应用边界。

**最低可投稿包:**

- current frozen evidence bundle。
- `final-context` 主结果表。
- 2-3 个预算匹配 baseline。
- 3-4 个关键消融。
- T5/T6/T7 样本量和置信区间。
- 图表/列表/多跳失败分析。
- 外部文献支撑的相关工作。
- 清楚的局限性与应用边界。

### 2.5 路线 B: SCI 四区冲刺闭环

**适用条件:** 路线 A 全部完成，并额外完成更强对照、消融、轻量跨文档迁移和英文相关工作支撑。

**重点:** 证据治理、实验闭环、可复现评测、与国际 RAG/GraphRAG 文献的差异化、质量-成本 Pareto 分析。

**升级门槛:**

- 至少 4 类 budget-matched baselines。
- 关键模块消融覆盖系统主张。
- 小样本鲁棒性结果附 Wilson 或 exact binomial interval，baseline/ablation 差异附 paired bootstrap、permutation test 或明确说明为何不做显著性检验。
- 至少 2 个结构不同中文文档，或总量不少于 30-50 个问题的迁移切片；若只能完成 1 篇 10-20 题，SCI 四区路线必须降级为探索性外推。
- 相关工作覆盖 long-document RAG、GraphRAG/KG-RAG、grounded generation/refusal、RAG evaluation/cost。
- 英文标题、摘要和 contribution wording 通过外部文献支撑和 reviewer-style 自审。
- 完成 target journal matrix、novelty positioning matrix、annotation reliability audit、LLM stability protocol、human evaluation protocol、Data/Code Availability、Threats to Validity。

## 3. 终稿准入红线

### 3.1 数字准入红线

- 摘要数字只能来自 `accepted_for_manuscript` 的 current frozen evidence。
- 引言末段只能预告 current frozen evidence 支持的结果。
- 主结果表只放 `final-context` headline retrieval metrics。
- `path_hits` 和 `pre-rerank` 不进摘要、引言和主结果 headline。
- historical evidence 可以用于“前期观察”“风险发现”“失败模式来源”，必须显式标注。
- release gate 可以用于“工程执行面可控”“复现检查”，不能写成核心贡献。

### 3.2 语言红线

- 禁用“首次”“首个”“最先进”“SOTA”“显著领先”“革命性”“全面优于”“生产级落地”“通用框架”。
- 缺 baseline 时不能写“优于现有方法”。
- 缺消融时不能把效果归因到某个模块。
- 缺迁移时不能写“适用于中文长文档问答总体”。
- T5/T6/T7 小样本结论必须写样本量。
- 每个强结论必须能回溯到证据表。

### 3.3 外部文献红线

- 不使用未核验论文作为支撑。
- 不使用“标题相似”论文支撑具体主张。
- 不引用模型生成的虚构文献。
- 不把综述文献当作实验主张的一手证据。
- 中文核心路线可以补 CNKI/万方人工检索，但必须记录检索日期、题名、来源和人工核验结果。
- SCI 四区路线优先使用 CrossRef、arXiv、Semantic Scholar、publisher page，可把 CNKI/万方作为中文任务背景补充。

## 4. 文件产物地图

### 4.1 本计划将驱动的新产物

| 产物 | 建议路径 | 责任 |
|---|---|---|
| 冻结证据 manifest | `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/manifest.md` | 记录 commit、命令、sha256、模型和预算配置 |
| 统一指标台账 | `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/metrics_ledger.md` | 每个数字对应 evidence class 与 manuscript use |
| 文献台账 | `docs/superpowers/plans/paper-literature-ledger.md` | 每条引用对应主张、支撑等级、核验状态 |
| 目标期刊矩阵 | `docs/superpowers/plans/paper-target-journal-matrix.md` | 候选期刊栏目、篇幅、图表、引用格式、系统论文友好度 |
| 创新定位矩阵 | `docs/superpowers/plans/paper-novelty-positioning-matrix.md` | 说明已有 RAG/GraphRAG/KG-RAG 通常报告什么、本文多报告什么、本文不声称什么 |
| 统计分析计划 | `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/statistical_analysis.md` | paired delta、bootstrap/permutation、effect size、重复运行策略 |
| 标注可靠性记录 | `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/annotation_reliability.md` | 双人标注、抽样复核、一致性或 adjudication log |
| LLM 稳定性协议 | `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/llm_stability_protocol.md` | 模型版本、temperature、prompt、缓存、重复运行、失败重试 |
| 人工评价协议 | `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/human_evaluation_protocol.md` | answer correctness、citation usefulness、refusal appropriateness 的盲评方案 |
| 数据与代码可用性声明 | `docs/superpowers/plans/paper-data-code-availability.md` | 数据、代码、artifact、license、受限发布和替代材料 |
| 图表包说明 | `docs/superpowers/plans/paper-figure-table-package.md` | 图表清单、数据来源、caption 要点 |
| Threats to Validity | `docs/superpowers/plans/paper-threats-to-validity.md` | internal、external、construct、conclusion validity |
| 终稿正文 | `docs/superpowers/plans/2026-06-17-graphrag-paper-final-manuscript.md` | 中文终稿 |
| SCI 四区英文转写稿 | `docs/superpowers/plans/2026-06-17-graphrag-paper-sci-q4-draft.md` | 冲刺路线可选 |
| 投稿包自检表 | `docs/superpowers/plans/2026-06-17-graphrag-paper-submission-checklist.md` | 投稿前 gate |

### 4.2 不能被覆盖的原始证据

- `ground_truth.json`
- `raw_runs.jsonl`
- `metrics_a1_retrieval.json`
- `metrics_a2_faithfulness.json`
- `metrics_a3_robustness.json`
- `metrics_a4_multihop.json`
- `metrics_a5_performance.json`
- `report_a1_retrieval.md`
- `report_a2_faithfulness.md`
- `report_a3_robustness.md`
- `report_a4_multihop.md`
- `report_a5_performance.md`
- `REPORT_FINAL.md`
- `release_gate_report.md`
- `run.log`

操作规则: 终稿冻结时复制到独立 `paper_freeze_YYYYMMDD/` 目录，不直接引用 working files。

## 5. Phase 0: 锁定论文控制台

**目标:** 在补实验和写终稿前，先锁论文的术语、主张、证据面和投稿路线。

**Files:**

- Read: `docs/superpowers/plans/2026-06-15-graphrag-paper-draft-v2-core-journal.md`
- Read: `docs/superpowers/plans/paper-metric-contract.md`
- Read: `docs/superpowers/plans/paper-evidence-freeze-note.md`
- Create: `docs/superpowers/plans/paper-final-terminology-ledger.md`

**Steps:**

- [ ] Step 0.1: 抽取终稿术语表，至少包括 `GraphRAG`、知识图谱证据、多路径检索、预算约束控制、引用校验生成、`final-context`、`path_hits`、`pre-rerank`、answer-support、historical evidence、current frozen evidence、release gate。
- [ ] Step 0.2: 锁定中文术语和英文括注，例如首次使用写“生成前最终证据集合（final-context）”，后文统一用“final-context 主结果面”。
- [ ] Step 0.3: 写入三条终稿贡献，禁止把“使用 KG/RAG”本身写成贡献。
- [ ] Step 0.4: 写入 route decision table，明确“北大核心最低闭环”和“SCI 四区升级门槛”。
- [ ] Step 0.5: 标记所有当前 v2 中需要等冻结结果后才能保留的句子。

**Acceptance gate:**

- 术语表完成后，终稿正文不得再出现同义漂移。
- 一句话论证可以映射到结果、方法、讨论和摘要。
- 贡献句中没有“首次”“SOTA”“全面优于”。

## 6. Phase 1: 证据冻结与规范对齐

**目标:** 让终稿中的每个数字都能追溯到同一冻结证据包。

**Files:**

- Read: `iteration-2/eval-2-existing-components/rag_eval/run_inference.py`
- Read: `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py`
- Read: `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py`
- Read: `iteration-2/eval-2-existing-components/rag_eval/metrics_a3_robustness.py`
- Read: `iteration-2/eval-2-existing-components/rag_eval/metrics_a4_multihop.py`
- Read: `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.py`
- Read: `iteration-2/eval-2-existing-components/rag_eval/release_gate.py`
- Modify if needed: `iteration-2/eval-2-existing-components/rag_eval/RAG-EVAL-SPECIFICATION.md`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/manifest.md`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/metrics_ledger.md`

**Steps:**

- [ ] Step 1.1: 记录当前 `git rev-parse HEAD`，并记录工作区 dirty 状态。若存在未提交实验改动，先决定是否以当前 working tree 生成 freeze bundle，或先提交/打 tag 后再冻结。
- [ ] Step 1.2: 建立独立冻结目录，目录名采用 `paper_freeze_YYYYMMDD`，不复用 `rag_eval` 根目录下会被覆盖的 working files。
- [ ] Step 1.3: 复制 `ground_truth.json`、`raw_runs.jsonl`、`metrics_*.json`、`report_*.md`、`REPORT_FINAL.md`、`release_gate_report.*`、`run.log` 到冻结目录，并记录源文件路径。
- [ ] Step 1.4: 对冻结目录中的每个 artifact 计算 sha256，写入 manifest。
- [ ] Step 1.5: 将每个 artifact 标记为 `historical_only`、`diagnostic_only`、`engineering_support`、`accepted_for_manuscript` 或 `pending_rerun`。
- [ ] Step 1.6: 对照 `RAG-EVAL-SPECIFICATION.md` 与实际脚本，修正规范漂移，特别是 document-level metric、LLM-as-judge、EM/F1、QPS 等旧口径。
- [ ] Step 1.7: 重新生成统一 50 题评测，命令以 `run_inference.py --out-path ... --log-path ... --gt-path ...` 的实际接口为准。
- [ ] Step 1.8: 在同一冻结目录下重跑 A1-A5 指标和 release gate，确保输入 raw runs 一致。
- [ ] Step 1.9: 写 `metrics_ledger.md`，每一行包括 metric、value、surface、source_class、artifact_id、sha256、allowed manuscript location、interpretation boundary。
- [ ] Step 1.10: 将 `final-context` 标记为 retrieval headline surface，将 `path_hits` 和 `pre-rerank` 标记为 diagnostic surface。

**Acceptance gate:**

- `metrics_ledger.md` 中没有来源不明数字。
- 摘要候选数字均来自 `accepted_for_manuscript`。
- `REPORT_FINAL.md` 的历史数字没有被列为 current headline。
- release gate 的 GO、pytest 通过、conversation rewrite 通过没有被列为学术主贡献。

**No-go condition:**

- 如果冻结重跑失败且无法定位原因，终稿只能保留“投稿导向初稿”状态，不进入投稿终稿。
- 如果规范与脚本存在无法安全判断的冲突，先修规范或脚本，不继续写结果。

## 7. Phase 2: 外部文献补强

**目标:** 让引言、相关工作和讨论具备投稿需要的外部学术定位，同时避免虚构引用和错引。

**Files:**

- Create: `docs/superpowers/plans/paper-literature-ledger.md`
- Optional create: `docs/superpowers/plans/paper-references.bib`
- Optional create: `docs/superpowers/plans/paper-references.ris`
- Modify later: `docs/superpowers/plans/2026-06-17-graphrag-paper-final-manuscript.md`

**Literature blocks:**

| Block | 用途 | 最低中文核心要求 | SCI 四区要求 |
|---|---|---|---|
| 中文长文档问答与复杂文档理解 | 支撑任务意义 | 3-5 篇中英文文献 | 5-8 篇，含长文档/复杂文档 QA |
| RAG 与长上下文检索 | 支撑方法背景 | 3-5 篇 | 6-10 篇，含 recent RAG evaluation |
| GraphRAG/KG-RAG | 区分常规路线与本系统 | 3-5 篇 | 6-10 篇，覆盖 KG-enhanced retrieval |
| grounded generation 与引用可追溯 | 支撑 hallucination/refusal 讨论 | 2-4 篇 | 5-8 篇，含 citation/faithfulness |
| RAG evaluation、robustness、cost | 支撑质量-成本论点 | 2-4 篇 | 5-8 篇，含 latency/token/cost |
| 中文核心本土语境 | 支撑中文应用意义 | CNKI/万方人工补 5-10 篇 | 可作为中文场景补充 |

**Steps:**

- [ ] Step 2.1: 将 v2 初稿拆成可引用主张片段，每个片段只表达一个背景或相关工作主张。
- [ ] Step 2.2: 为每个片段写英文检索 query，中文核心文献另写中文检索 query。
- [ ] Step 2.3: 优先检索 CrossRef、arXiv、Semantic Scholar/OpenAlex；中文核心路线手动检索 CNKI/万方。
- [ ] Step 2.4: 每条候选文献记录 title、authors、year、venue、DOI/URL、abstract checked、publisher page checked、support grade。
- [ ] Step 2.5: 支撑等级使用 `strong support`、`partial support`、`background support`、`contradictory/limiting`、`metadata-only candidate`。
- [ ] Step 2.6: 删除所有 `metadata-only candidate`，除非后续完成摘要或全文核验。
- [ ] Step 2.7: 建立 `paper-literature-ledger.md`，用表格映射“正文主张 -> 支撑文献 -> 支撑等级 -> 插入位置”。
- [ ] Step 2.8: 导出 BibTeX 或 RIS，保留 DOI 和访问日期。
- [ ] Step 2.9: 重写相关工作，不按年份罗列，按技术问题分组。
- [ ] Step 2.10: 引言中只引用任务背景和 gap，不堆砌过多方法细节。

**Acceptance gate:**

- 每个相关工作段落至少有 2 条核验过的 citation support。
- 每条关键外部主张均能在 `paper-literature-ledger.md` 找到支撑。
- 没有引用未核验文献。
- 没有用外部文献替代本项目实验证据。

**SCI 四区 upgrade gate:**

- 相关工作能明确说明本项目不同于常规 GraphRAG 的地方是“证据面分层治理、引用校验生成、拒答/假前提纠错、质量-成本联合评测”，而不是单纯“用了知识图谱”。

## 7A. Phase 2A: 目标期刊矩阵与创新定位矩阵

**目标:** 把“北大核心/SCI 四区”从笼统目标变成可执行投稿路径，并把“不同于常规 GraphRAG”的差异写成国际审稿人能理解的 gap。

**Files:**

- Create: `docs/superpowers/plans/paper-target-journal-matrix.md`
- Create: `docs/superpowers/plans/paper-novelty-positioning-matrix.md`
- Modify later: `docs/superpowers/plans/2026-06-17-graphrag-paper-final-manuscript.md`
- Modify later: `docs/superpowers/plans/2026-06-17-graphrag-paper-sci-q4-draft.md`

**Target journal matrix fields:**

| Field | Required content |
|---|---|
| candidate journal | 期刊中文名/英文名、ISSN 或官方页面 |
| route | 北大核心/强普刊/SCI 四区 |
| article type | 系统设计、应用研究、技术方法、实验评测、案例研究等 |
| section fit | 是否接受 AI 系统、信息检索、知识工程、软件系统或应用评测论文 |
| manuscript constraints | 字数、摘要格式、图表数量、参考文献格式、补充材料规则 |
| evidence expectation | 是否偏工程应用、算法评测、实证研究或行业场景 |
| risk | 不适配原因，例如过强算法要求、过窄行业栏目、不接收系统论文 |
| action | 选择、备选、暂缓或排除 |

**Novelty positioning matrix fields:**

| Prior-work block | Usually reports | This paper additionally reports | This paper does not claim |
|---|---|---|---|
| Long-document RAG | 检索/生成效果、长上下文处理 | 中文复杂长文档中的证据面治理、拒答/纠错、质量-成本边界 | 不声称通用长文档 SOTA |
| GraphRAG/KG-RAG | KG 增强检索、结构化证据 | `final-context` 主结果面、诊断面分层、引用校验生成 | 不声称 KG 构建算法原创 |
| Grounded generation | faithfulness、citation、hallucination | 引用节点真实性、引用是否来自已检索证据、拒答/假前提行为 | 不声称完全消除幻觉 |
| RAG evaluation/cost | 准确率、召回率、延迟或成本 | 质量-成本 Pareto、长尾成本失败桶、预算约束边界 | 不声称低成本实时部署 |

**Steps:**

- [ ] Step 2A.1: 先列 6-10 个中文核心/强普刊候选和 4-6 个 SCI 四区候选，不填无法核验的投稿事实。
- [ ] Step 2A.2: 对每个候选期刊查官方投稿指南或数据库页面，记录检索日期和页面来源；如果信息可能随时间变化，在矩阵中标记“需投稿前复核”。
- [ ] Step 2A.3: 根据栏目、篇幅、图表数、参考文献格式和系统论文友好度给每个候选打 `primary`、`backup`、`watch`、`exclude`。
- [ ] Step 2A.4: 建立 novelty positioning matrix，逐块写清“已有文献通常报告什么、本文多报告什么、本文不声称什么”。
- [ ] Step 2A.5: 用 novelty matrix 重写引言末段和相关工作结尾，避免把贡献写成“使用 GraphRAG”。
- [ ] Step 2A.6: 若目标 SCI 期刊偏算法评测而非系统应用，先补实验，不用语言包装硬投。

**Acceptance gate:**

- 至少有 2 个中文核心/强普刊 primary/backup 目标。
- 至少有 1 个 SCI 四区 primary 或 backup 目标，且栏目允许系统/应用/评测类论文。
- 相关工作最后一段能用 4 句话以内说明 international gap。
- 标题、摘要和贡献句不再依赖“常规 GraphRAG 复述”。

## 8. Phase 3: Baseline Ladder

**目标:** 回答“为什么需要完整 GraphRAG 系统，而不是更简单 RAG”。

**Files:**

- Inspect: `backend/retrieval.py`
- Inspect: `backend/generator.py`
- Inspect/Create: `iteration-2/eval-2-existing-components/rag_eval/baselines/`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/baseline_results.md`

**Baseline set:**

| Baseline | 最低路线 | SCI 四区路线 | 必须匹配的预算 |
|---|---|---|---|
| BM25-only | 必做 | 必做 | candidate 数、final context size、generation setting |
| Vector-only | 必做 | 必做 | candidate 数、context token 上限、generation setting |
| Vector + BM25 | 必做 | 必做 | fusion budget、rerank budget、context 上限 |
| KG-only | 推荐 | 必做 | node budget、neighbor expansion budget |
| Non-agentic fixed pipeline | 推荐 | 必做 | tool/call budget、context 上限、prompt setting |
| Full GraphRAG | 必做 | 必做 | 与 baseline 同预算或明确报告额外预算 |

**Steps:**

- [ ] Step 3.1: 先定义 budget-matched protocol，写明 retrieval budget、context budget、generation model、prompt、temperature、stop rule。
- [ ] Step 3.2: 明确每个 baseline 是否使用同一 `ground_truth.json` 和同一 `final-context` 评测 surface。
- [ ] Step 3.3: 对每个 baseline 输出 raw runs，不覆盖 full GraphRAG 的 raw runs。
- [ ] Step 3.4: 对每个 baseline 计算 A1 final-context、A2 answer-support、A5 performance。
- [ ] Step 3.5: 在主表中同时报告 quality、grounding、latency、tokens、cost。
- [ ] Step 3.6: 若某 baseline 无法实现，写入 `[需要补证据：某 baseline 尚未完成，不能声称全面优于该类方法。]`。

**Acceptance gate:**

- 所有 baseline 共享同一问题集和同一指标契约。
- baseline 表不只报准确性，也报 latency/tokens/cost。
- 没有把“预算更多”包装成“方法更好”。

**北大核心 minimum:**

- BM25-only、Vector-only、Full GraphRAG 三者完成。

**SCI 四区 minimum:**

- BM25-only、Vector-only、Vector+BM25、KG-only、Non-agentic fixed pipeline、Full GraphRAG 完成。

## 9. Phase 4: Ablation 与预算扫描

**目标:** 回答“哪些模块真的贡献了效果，哪些只是工程复杂度”。

**Files:**

- Inspect: `backend/retrieval.py`
- Inspect: `backend/generator.py`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/ablation_results.md`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/pareto_scan.md`

**Required ablations:**

| Ablation | 对应主张 | 结果位置 |
|---|---|---|
| remove KG rescue / KG path | 知识图谱证据是否必要 | Ablation table |
| remove rerank/final-context selection | final-context 选择是否改善可用证据 | Ablation table |
| remove budget guard / max tool calls | 预算控制是否约束长尾成本 | Ablation table + Pareto |
| remove redundancy/source budget filtering | 冗余抑制是否改善 precision/cost | Ablation table |
| remove citation verification | 引用校验是否改善 answer-support | Ablation table |
| disable false-premise/refusal policy if separable | 拒答/纠错策略是否必要 | Robustness table |

**Budget scan axes:**

- `max_tool_calls`
- final context top-k
- rerank candidate count
- rerank max chars
- search result count per path
- neighbor expansion limit

**Steps:**

- [ ] Step 4.1: 为每个 ablation 写清楚“只关掉什么，不改变什么”。
- [ ] Step 4.2: 每个 ablation 生成独立 raw runs 和独立 metrics。
- [ ] Step 4.3: 每个 ablation 报告相对 Full GraphRAG 的 delta。
- [ ] Step 4.4: Budget scan 输出质量-延迟-token-成本 Pareto。
- [ ] Step 4.5: Q31 这类长尾问题单独报告，但不让单题替代全局结论。
- [ ] Step 4.6: 如果无法完成某项消融，正文只保留设计动机，不写效果归因。

**Acceptance gate:**

- 每条模块贡献至少有一个 ablation 或诊断指标钩子。
- 如果消融结果不支持预期，讨论中必须保留，不删除。
- 不能把 `REPORT_FINAL.md` 中的优化建议写成已验证结论。

## 9A. Phase 4A: 统计分析与 LLM 稳定性 Gate

**目标:** 让 baseline 和 ablation 不只“报数”，而能经受“50 题差异是否稳定、LLM 随机性是否可控”的审稿质疑。

**Files:**

- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/statistical_analysis.md`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/paired_delta_table.csv`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/llm_stability_protocol.md`
- Optional create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/repeated_runs/`

**Statistical analysis requirements:**

| Analysis | Applies to | Minimum route | SCI 四区 route |
|---|---|---|---|
| per-question paired delta | Full vs baseline, Full vs ablation | 必做 | 必做 |
| paired bootstrap CI | final-context recall, answer-support, latency/cost | 推荐 | 必做 |
| permutation test or paired sign test | Full vs strongest baseline | 可选 | 推荐，若不做需说明原因 |
| effect size | quality delta、latency delta、cost delta | 推荐 | 必做 |
| multiple-comparison note | 多 baseline、多 ablation | 可选 | 必做说明，不必过度统计化 |
| repeated-run variance | LLM generation and retrieval behavior | 推荐 | 必做或明确固定 deterministic setting |

**LLM stability fields:**

- model provider and model identifier。
- model version or API date if available。
- temperature、top_p、max tokens、system prompt、retrieval prompt。
- cache policy and whether prompt cache was used。
- retry rule、timeout rule、failed-run inclusion rule。
- repeated-run count for a sampled subset or full set。
- random seed if the stack supports it; if not supported, write “not supported by provider/API”。
- exact prompt artifacts or prompt hashes in the freeze bundle。

**Steps:**

- [ ] Step 4A.1: 为每个 baseline 和 ablation 生成 per-question paired table，行粒度为 `qid`，列包括 full metric、comparison metric、delta、category、surface。
- [ ] Step 4A.2: 对主指标计算 paired bootstrap CI，抽样单位为 question，不把单题内部指标当作独立样本。
- [ ] Step 4A.3: 对 strongest baseline 与 Full GraphRAG 的主指标差异运行 permutation test、paired sign test 或解释为何样本/分布不适合显著性检验。
- [ ] Step 4A.4: 对质量、延迟、token、成本分别报告 effect size 或 median paired delta，不只报告均值差。
- [ ] Step 4A.5: 选择代表性子集做 repeated runs；最低包含成功案例、失败桶、拒答、假前提和长尾成本题。
- [ ] Step 4A.6: 若 repeated runs 与单次 frozen result 不一致，终稿使用“主冻结结果 + 稳定性分析”双层写法，不选择性报告最好一次。
- [ ] Step 4A.7: 将统计检验限制写入 Discussion，避免把小样本 p 值包装成强证明。

**Acceptance gate:**

- 主 baseline 表和 ablation 表旁边有 paired delta 或 CI。
- SCI 四区版不能只报告单次均值。
- LLM 稳定性协议能复现模型、prompt、temperature、缓存和重试规则。
- 若统计检验缺失，正文必须写 `[需要补证据：baseline/ablation 差异尚未完成 paired statistical analysis。]`。

## 10. Phase 5: 鲁棒性、置信区间与失败桶

**目标:** 把小样本正面信号写得可信，而不是写得过强。

**Files:**

- Read: `iteration-2/eval-2-existing-components/rag_eval/metrics_a3_robustness.json`
- Read: `iteration-2/eval-2-existing-components/rag_eval/metrics_a4_multihop.json`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/robustness_ci.md`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/failure_buckets.md`

**Failure buckets:**

| Bucket | Known cases | 论文用途 |
|---|---|---|
| 图表描述词面失配 | Q10/Q11 | 区分 lexical proxy 与 semantic adequacy |
| 列表聚合真错 | Q15/Q16 | 暴露图表/metric 节点盲区 |
| 极值/比较问题 | Q31 | 展示答对但成本异常 |
| 拒答小样本 | T5, n=10 | 写样本量和 CI |
| 噪声鲁棒小样本 | T6, n=5 | 写样本量和 CI |
| 假前提小样本 | T7, n=3 | 写样本量和 CI |

**Steps:**

- [ ] Step 5.1: 对 T5、T6、T7 计算 Wilson interval 或 exact binomial interval。
- [ ] Step 5.2: 若不扩样，正文写“小样本条件下观察到稳定信号”，不写“充分证明强鲁棒性”。
- [ ] Step 5.3: 对 Q10/Q11/Q15/Q16/Q31 逐题记录 query、expected evidence、retrieved evidence、final answer、failure type、repair implication。
- [ ] Step 5.4: 选择 2 个成功案例和 3 个失败案例进入正文，更多案例进附录。
- [ ] Step 5.5: 对 `keyword_coverage` 明确写成词面代理指标，不等同语义正确性。
- [ ] Step 5.6: 对拒答/假前提纠错区分 plain refusal 与 correction-style false premise。

**Acceptance gate:**

- 所有小样本比例后面都有 `n=`。
- 鲁棒性结论有 CI 或明确说明未补 CI。
- 失败分析不被写成“个别异常”，而是映射到系统边界。

## 10A. Phase 5A: 标注可靠性与人工评价 Gate

**目标:** 降低审稿人对 `ground_truth.json` 人工构造、关键词代理指标和 answer quality 的质疑。

**Files:**

- Read: `docs/superpowers/plans/paper-annotation-protocol.md`
- Read: `iteration-2/eval-2-existing-components/rag_eval/ground_truth.json`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/annotation_reliability.md`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/adjudication_log.md`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/human_evaluation_protocol.md`
- Create: `iteration-2/eval-2-existing-components/rag_eval/paper_freeze_YYYYMMDD/human_evaluation_results.md`

**Annotation reliability design:**

| Item | Minimum route | SCI 四区 route |
|---|---|---|
| second review | 高歧义题抽样复核 | 全部或分层抽样复核 |
| agreement target | 报告一致/不一致数量和 adjudication | 报告 Cohen's kappa、Krippendorff's alpha、percent agreement 或解释为何字段不适合 |
| adjudication log | 记录图表、列表、假前提、hop 分歧 | 记录全部分歧、裁决依据和最终字段 |
| GT boundary note | 写入方法/附录 | 写入方法，并把风险纳入 Threats to Validity |

**Human evaluation dimensions:**

- answer correctness: 回答是否由文档证据支持。
- citation usefulness: 引用是否帮助定位证据，而不只是形式上给 node id。
- refusal appropriateness: 该拒答时是否拒答，不该拒答时是否过度拒答。
- correction appropriateness: 假前提是否被明确纠正。
- readability: 中文回答是否清楚、不过度堆砌节点。

**Human evaluation protocol:**

- 盲评材料隐藏系统名称和实验条件。
- 至少比较 Full GraphRAG 与 strongest baseline；若 baseline 未完成，则只做人类质量审计，不写比较结论。
- 每题至少 2 名评审或 1 名评审加抽样复核。
- 使用 3 级或 5 级量表，并保留自由文本错误原因。
- 评价样本必须覆盖成功案例、失败桶、拒答、噪声和假前提。

**Steps:**

- [ ] Step 5A.1: 从 50 题中按题型分层抽样，优先包括 Q10/Q11/Q15/Q16/Q31 和所有 T5/T7。
- [ ] Step 5A.2: 组织第二标注者或独立复核者检查 `expected_node_ids`、`expected_keywords`、`should_refuse`、`false_premise`、`reasoning_hops`。
- [ ] Step 5A.3: 对不一致项写入 `adjudication_log.md`，记录原标注、复核意见、最终裁决和理由。
- [ ] Step 5A.4: 计算一致性指标；如果样本量或字段类型不适合 kappa，报告 percent agreement 和分歧类型。
- [ ] Step 5A.5: 建立 human evaluation rubric，先小样本 pilot，确认评审能理解 answer correctness、citation usefulness、refusal appropriateness。
- [ ] Step 5A.6: 完成人工盲评，输出总表、题型分表和典型分歧说明。
- [ ] Step 5A.7: 如果人工评价与规则指标冲突，讨论中优先解释冲突，不删除不利结果。

**Acceptance gate:**

- `ground_truth.json` 的人工边界有复核或 adjudication 证据。
- human evaluation 不替代规则指标，只补充 answer quality 和 citation usefulness。
- 若没有人评，北大核心版可保留为未来工作，SCI 四区版必须降级或明确增加该实验。

## 11. Phase 6: 轻量跨文档迁移

**目标:** 缓解单文档、单任务集导致的外部有效性不足。

**Files:**

- Create: `iteration-2/eval-2-existing-components/rag_eval/transfer_slice/`
- Create: `iteration-2/eval-2-existing-components/rag_eval/transfer_slice/ground_truth_transfer.json`
- Create: `iteration-2/eval-2-existing-components/rag_eval/transfer_slice/transfer_report.md`

**Scope:**

- 北大核心最低路线选择 1 篇结构不同的中文长文档，人工构造 10-20 个问题。
- SCI 四区路线优先选择 2 篇结构不同的中文长文档，或至少形成 30-50 个迁移问题。
- 题型至少覆盖事实、图表/列表、数值、多跳、拒答、假前提中的 4 类。
- 使用同一 metric contract，若无法完全复用则写出差异。

**Steps:**

- [ ] Step 6.1: 选择第二文档，记录文档页数、节点数、边数、领域。
- [ ] Step 6.2: 按 `paper-annotation-protocol.md` 构造 transfer GT。
- [ ] Step 6.3: 重跑 Full GraphRAG，输出 raw runs 和 metrics。
- [ ] Step 6.4: 对 SCI 四区路线追加第二迁移文档或扩展到 30-50 题，除非目标期刊矩阵显示该期刊明确接受小规模系统案例研究。
- [ ] Step 6.5: 不强行追求大样本结论，只写“轻量迁移切片”或“扩展迁移切片”。
- [ ] Step 6.6: 如果迁移结果较弱，讨论中写明系统可能依赖文档结构和 KG 构建质量。

**Acceptance gate:**

- SCI 四区路线至少完成 2 篇文档或 30-50 题迁移切片；只完成 1 篇 10-20 题时，外部有效性只能写成探索性。
- 北大核心路线若不完成 transfer slice，必须在讨论中写 `[需要补证据：跨文档迁移尚未完成，外部有效性有限。]`。

## 12. Phase 7: 图表包

**目标:** 让读者不用钻代码也能看懂系统、证据面和边界。

**Files:**

- Create: `docs/superpowers/plans/paper-figure-table-package.md`
- Optional create: `docs/superpowers/figures/`

**Required figures and tables:**

| 编号 | 类型 | 内容 | 数据来源 |
|---|---|---|---|
| Figure 1 | 系统总览图 | 文档解析、KG、检索、final-context、生成、拒答/纠错 | 方法设计 |
| Figure 2 | 证据面流图 | `path_hits` -> `pre-rerank` -> `final-context` -> answer-support | metric contract |
| Figure 2A | 审稿人友好版证据链图 | 问题进入系统后，证据如何被找到、筛掉、引用，并在证据不足或前提错误时拒答/纠错 | metric contract + 方法设计 |
| Table 1 | 主结果表 | frozen `final-context` headline metrics + answer-support | metrics ledger |
| Table 2 | Baseline 表 | budget-matched comparison | baseline results |
| Table 3 | Ablation 表 | 模块移除与 delta | ablation results |
| Figure 3 | Pareto 图 | quality vs latency/tokens/cost | pareto scan |
| Table 4 | 失败桶表 | Q10/Q11/Q15/Q16/Q31 | failure buckets |
| Figure 4 | 案例图 | 一个成功可追溯案例、一个拒答/纠错案例、一个失败案例 | raw runs |

**Steps:**

- [ ] Step 7.1: 每个图表先写一句 message，不先画图。
- [ ] Step 7.2: 每个图表都绑定 `metrics_ledger.md` 或 case artifact。
- [ ] Step 7.3: Figure 2A 使用读者语言，不把 `path_hits`、`pre-rerank`、answer-support 作为主标签；这些术语放在图注或方法细节中解释。
- [ ] Step 7.4: 表格列名标注 metric direction，例如 `Recall ↑`、`Latency ↓`。
- [ ] Step 7.5: caption 只写设置和读图方式，不把讨论塞进 caption。
- [ ] Step 7.6: 失败案例表必须保留“错因”和“不能推出什么”。

**Acceptance gate:**

- 主文每张图表都服务一个主张。
- 没有图表引用 historical evidence 作为 current headline。
- 图表足以降低 `final-context/path_hits/pre-rerank` 的读者负担。
- SCI 四区英文稿主文优先使用 Figure 2A 解释证据链，Figure 2 可放方法细节或附录。

## 13. Phase 8: 终稿正文重写

**目标:** 以冻结证据为中心，把 v2 改成投稿终稿，而不是继续堆项目材料。

**Target file:**

- Create: `docs/superpowers/plans/2026-06-17-graphrag-paper-final-manuscript.md`

**Writing order:**

1. 实验与结果
2. 方法/系统设计
3. 讨论
4. 引言
5. 相关工作
6. 结论
7. 标题
8. 摘要

### 13.1 实验与结果

**Required structure:**

- 评测设置与 evidence governance。
- frozen 主结果面: `final-context`。
- answer-support 支撑面: citation/grounding。
- budget-matched baseline。
- ablation。
- 鲁棒性与拒答/纠错，必须写样本量和 CI。
- 质量-成本 Pareto。
- 案例与失败分析。

**Stop condition:**

- 若 baseline 或 ablation 未完成，实验章节保留 `[需要补证据：...]`，不写成终稿主张。

### 13.2 方法/系统设计

**Per-module pattern:**

- 设计动机: 解决什么中文长文档 QA 失败模式。
- 模块机制: 做了什么，读者如何复现。
- 证据钩子: 对应哪个指标、消融或案例。
- 作用边界: 在什么情况下可能失败。

**Modules:**

- KG evidence organization。
- Query preprocessing。
- Multi-path retrieval。
- Rerank and final-context selection。
- Redundancy/source-budget filtering。
- Budget-constrained control。
- Citation-verified generation。
- Refusal and false-premise correction。
- Evidence governance layer。

### 13.3 讨论

**Required claims:**

- 系统证明了什么: 可追溯系统链路和行为可靠性信号。
- 系统没有证明什么: SOTA、充分外部有效性、全面成本治理。
- 为什么高召回可能伴随低精度和长尾成本。
- 图表/列表问题为什么是中文长文档 QA 的独立难点。
- 标注边界和词面指标如何影响结果解释。
- 北大核心应用价值和 SCI 四区外推边界分别是什么。

### 13.4 引言

**Required arc:**

- 中文复杂长文档 QA 的现实需求。
- 单纯 answer-only RAG 的可靠性、可追溯、拒答/纠错和成本报告不足。
- GraphRAG/KG-RAG 提供启发，但系统级证据面和质量-成本治理仍需展开。
- 本文定位为系统设计与评测，不是算法 SOTA。
- 贡献句只使用冻结证据能支持的表述。

### 13.5 相关工作

**Required blocks:**

- Long-document QA and RAG。
- GraphRAG and KG-enhanced retrieval。
- Grounded generation, citation, hallucination control, refusal。
- RAG evaluation, robustness, and cost。
- Chinese long-document/application context。

**Rule:**

- 每段最后一句必须落回本文差异，不做文献流水账。

### 13.6 标题与摘要

**Title gate:**

- 如果 frozen traces 不能证明强 agentic 决策，不用 `Agentic` 领头。
- 最稳标题仍优先为“面向中文复杂长文档问答的可追溯 GraphRAG 系统设计与评测”。

**Abstract gate:**

- 摘要最后写。
- 摘要数字只来自 `accepted_for_manuscript`。
- 摘要必须同时写正面结果和边界。
- 摘要不出现 historical + gated 混合叙述。

**Acceptance gate:**

- 每个章节末尾建立 claim-evidence-boundary 表。
- 没有一个强句子找不到证据。
- 所有 `[需要补证据：...]` 要么补齐，要么保留并降级为“未来工作/局限”。

## 14. Phase 9: 投稿版本分叉

**目标:** 基于同一证据包，形成中文核心版和 SCI 四区版两套可投包装。

### 14.1 中文核心/强普刊版

**Title style:**

- 面向中文复杂长文档问答的可追溯 GraphRAG 系统设计与评测。
- 融合知识图谱与多路径检索的中文长文档可追溯问答系统及实验分析。

**Emphasis:**

- 中文场景现实意义。
- 系统架构完整。
- 评测协议清楚。
- 案例与失败分析具体。
- 应用价值与局限并存。

**De-emphasis:**

- 国际 SOTA 对打。
- 强 novelty 包装。
- 大规模跨领域泛化。

### 14.2 SCI 四区版

**Title style:**

- Citation-Verified GraphRAG for Chinese Complex Long-Document Question Answering: System Design and Evidence-Governed Evaluation。
- A Knowledge-Graph-Enhanced and Citation-Verified RAG System for Chinese Long-Document Question Answering。

**Emphasis:**

- Evidence-governed evaluation。
- Budget-matched baselines。
- Ablations。
- Robustness CI。
- Transfer slice。
- Quality-cost Pareto。
- Claim-to-metric traceability。

**De-emphasis:**

- 本土期刊语境。
- 未充分证明的 enterprise deployment。
- 过强 agentic branding。

**SCI 四区 no-go:**

- 没有 baseline。
- 没有 ablation。
- 没有 paired statistical analysis 或 CI/effect size 说明。
- 没有外部文献矩阵。
- 没有 target journal matrix。
- 没有 novelty positioning matrix。
- 没有 LLM stability protocol。
- 没有 annotation reliability audit。
- 没有 human evaluation 或明确降级。
- 没有数据/代码可用性声明。
- 没有 Threats to Validity。
- 没有迁移切片或明确 deferment。

## 15. Phase 10: 终稿自审与模拟审稿

**目标:** 投稿前先像审稿人一样拆稿，优先修会被拒稿的问题。

**Files:**

- Create: `docs/superpowers/plans/2026-06-17-graphrag-paper-submission-checklist.md`
- Optional create: `docs/superpowers/plans/2026-06-17-graphrag-paper-mock-review.md`
- Create: `docs/superpowers/plans/paper-threats-to-validity.md`
- Create: `docs/superpowers/plans/paper-data-code-availability.md`

**Self-review checklist:**

- [ ] 每个摘要数字都能指向 frozen artifact。
- [ ] 每个贡献都有实验、案例或评测协议支撑。
- [ ] baseline 是 budget-matched。
- [ ] ablation 覆盖所有模块主张。
- [ ] T5/T6/T7 写了样本量和 CI。
- [ ] transfer slice 或外部有效性限制已写明。
- [ ] historical evidence 与 current frozen evidence 没有混写。
- [ ] release gate 没有被包装成学术核心贡献。
- [ ] 外部文献均已核验，不存在 metadata-only citation。
- [ ] 相关工作不是文献列表，而是差异化论证。
- [ ] 图表与正文数字一致。
- [ ] 局限性没有藏在最后一句。
- [ ] 标题没有强于证据。
- [ ] 摘要没有掩盖低精度、失败模式和长尾成本。
- [ ] Data Availability 与 Code Availability 已说明 artifact、raw runs、GT、脚本、license 和不可公开项。
- [ ] Threats to Validity 已按 internal、external、construct、conclusion validity 分组。

**Mock reviewer prompts:**

- Reviewer 1: 技术闭环和实验设计是否足够。
- Reviewer 2: 创新点是否区别于常规 GraphRAG。
- Reviewer 3: 中文核心读者是否能读懂任务价值和系统图。
- Reviewer 4: SCI 四区读者是否认可 evidence governance 和 reproducibility。

**Acceptance gate:**

- 每个 reviewer major concern 都有对应修改或明确 rebuttal。
- 如果 reviewer concern 指向缺失实验，不能只靠文字润色解决。

## 15A. Phase 10A: 数据/代码可用性与 Threats to Validity

**目标:** 让投稿包不仅“结果可读”，还具备可复查、可复现、可共享或可解释限制的合规层。

**Files:**

- Create: `docs/superpowers/plans/paper-data-code-availability.md`
- Create: `docs/superpowers/plans/paper-threats-to-validity.md`
- Read: `docs/superpowers/plans/paper-evidence-freeze-note.md`
- Read: `iteration-2/eval-2-existing-components/rag_eval/`

**Data/Code Availability inventory:**

| Asset | Availability decision |
|---|---|
| `ground_truth.json` | 判断是否可公开；如含版权文档派生内容，说明限制和可替代字段 |
| `raw_runs.jsonl` | 判断是否可公开；检查是否含 API 响应、敏感日志或受限文档片段 |
| `metrics_*.json` | 优先公开或作为 supplementary artifacts |
| metric scripts | 优先公开，记录运行环境和依赖 |
| backend retrieval/generation code | 判断是否开源；若不能全量开源，提供最小复现实验脚本 |
| source document / PDF | 判断版权和授权；不能公开时提供文档统计、schema、匿名化样例或 synthetic sample |
| prompts and model configs | 优先公开 prompt hash、版本、temperature、budget；如 prompt 受限，说明原因 |
| frozen manifest | 必须公开或随稿提供，至少公开 checksum 和命令链 |

**Threats to Validity structure:**

| Validity type | Must discuss |
|---|---|
| Internal validity | 实现错误、评测脚本漂移、LLM 随机性、缓存/重试影响 |
| External validity | 单文档或少量迁移文档、中文技术文档范围、KG 构建质量依赖 |
| Construct validity | `expected_node_ids`、`keyword_coverage`、`final-context` 是否充分代表任务质量 |
| Conclusion validity | 50 题样本量、paired test 限制、多重比较、小样本拒答/假前提桶 |

**Steps:**

- [ ] Step 10A.1: 逐项盘点支撑论文主表、图表、案例和统计分析的所有数据与代码 artifact。
- [ ] Step 10A.2: 对每个 artifact 判定 `public repository`、`within supplement`、`restricted`、`available on justified request` 或 `not shareable`。
- [ ] Step 10A.3: 对不能公开的 artifact 写明限制原因，例如版权、第三方模型输出、商业实现、敏感日志或 API key 风险。
- [ ] Step 10A.4: 为可公开 artifact 准备 README 字段：用途、生成命令、输入、输出、sha256、license、复现步骤。
- [ ] Step 10A.5: 草拟中文核心版“数据与代码可用性说明”和 SCI 四区英文版 `Data Availability` / `Code Availability`。
- [ ] Step 10A.6: 写 `paper-threats-to-validity.md`，每个 validity type 至少列 2 个具体风险和 1 个缓解动作。
- [ ] Step 10A.7: 将 Threats to Validity 压缩进正文讨论，详细表格放附录或 supplementary。

**Acceptance gate:**

- 没有用“可向作者索取”替代具体访问路线。
- 每个主结果数字背后的数据和脚本都有可用性决定。
- SCI 四区版有独立的 Data Availability、Code Availability 和 Threats to Validity。
- 如果 artifact 不能公开，提供可审计替代材料，而不是只写“受限”。

## 16. 六周执行排期

### Week 1: 2026-06-17 to 2026-06-23

**Objective:** 证据冻结、术语锁定、规范对齐。

- [ ] 建立终稿术语表。
- [ ] 建立 freeze bundle 目录。
- [ ] 记录 commit、dirty 状态、命令、环境。
- [ ] 复制 artifact 并计算 sha256。
- [ ] 重跑或确认统一 50 题评测。
- [ ] 对齐 `RAG-EVAL-SPECIFICATION.md`。
- [ ] 生成 `metrics_ledger.md`。
- [ ] 固化 LLM model、prompt、temperature、缓存和重试规则。

**Exit criteria:** 没有来源不明的可投稿数字。

### Week 2: 2026-06-24 to 2026-06-30

**Objective:** 外部文献与 baseline。

- [ ] 建立 `paper-literature-ledger.md`。
- [ ] 建立 `paper-target-journal-matrix.md`。
- [ ] 建立 `paper-novelty-positioning-matrix.md`。
- [ ] 完成 5 个相关工作 block 的初筛文献。
- [ ] 完成 citation support 分级。
- [ ] 定义 budget-matched baseline protocol。
- [ ] 跑 BM25-only、Vector-only、Full GraphRAG。

**Exit criteria:** 相关工作有可核验引用，主 baseline 表有初版，至少锁定中文核心 primary/backup 和 SCI 四区候选路径。

### Week 3: 2026-07-01 to 2026-07-07

**Objective:** 消融、预算扫描和 CI。

- [ ] 跑 KG path、rerank、budget、citation verification 等关键消融。
- [ ] 跑质量-成本 Pareto scan。
- [ ] 建立 per-question paired delta table。
- [ ] 完成 baseline/ablation 的 paired bootstrap 或 permutation/sign test 计划。
- [ ] 计算 T5/T6/T7 CI。
- [ ] 固化 Q10/Q11/Q15/Q16/Q31 失败桶。

**Exit criteria:** ablation table、Pareto figure、robustness CI note、statistical analysis note 完成。

### Week 4: 2026-07-08 to 2026-07-14

**Objective:** 迁移、人评与图表包。

- [ ] 选择第二中文长文档。
- [ ] SCI 四区路线评估是否追加第二迁移文档或扩展到 30-50 题。
- [ ] 构建 10-20 题 transfer GT。
- [ ] 跑 transfer slice。
- [ ] 完成 annotation reliability audit。
- [ ] 完成 human evaluation pilot 或正式盲评。
- [ ] 完成 Figure 1-4 和 Table 1-4 的草图/表格。

**Exit criteria:** SCI 四区外推短板被缓解，中文核心版至少有明确局限写法。

### Week 5: 2026-07-15 to 2026-07-21

**Objective:** 按证据优先顺序重写终稿。

- [ ] 写实验与结果。
- [ ] 写方法/系统设计。
- [ ] 写讨论。
- [ ] 写引言。
- [ ] 写相关工作。
- [ ] 写结论。
- [ ] 写标题和摘要。

**Exit criteria:** 中文终稿 v1 完成，所有 `[需要补证据：...]` 已归类。

### Week 6: 2026-07-22 to 2026-07-28

**Objective:** 投稿包硬化。

- [ ] 完成中文核心版标题/摘要/关键词。
- [ ] 完成 SCI 四区英文标题/摘要/贡献句。
- [ ] 完成 Data Availability / Code Availability。
- [ ] 完成 Threats to Validity。
- [ ] 完成模拟审稿。
- [ ] 完成 submission checklist。
- [ ] 检查引用格式和图表编号。
- [ ] 最终确认所有数字都来自 metrics ledger。

**Exit criteria:** 可选择中文核心投稿包或 SCI 四区投稿包。

## 17. 立即行动清单

按优先级执行:

1. 建立 `paper-final-terminology-ledger.md`。
2. 建立 `paper_freeze_YYYYMMDD/` 冻结目录和 manifest。
3. 生成 `metrics_ledger.md`，锁定 current frozen evidence。
4. 修正或确认 `RAG-EVAL-SPECIFICATION.md` 与脚本一致。
5. 建立 `paper-literature-ledger.md`。
6. 完成外部文献检索 query 设计。
7. 建立 `paper-target-journal-matrix.md`。
8. 建立 `paper-novelty-positioning-matrix.md`。
9. 定义 budget-matched baseline protocol。
10. 运行最低 baseline ladder。
11. 运行关键 ablations。
12. 建立 `statistical_analysis.md` 和 per-question paired delta table。
13. 固化 LLM stability protocol。
14. 计算鲁棒性 CI。
15. 执行 annotation reliability audit。
16. 设计并运行 human evaluation。
17. 固化失败桶和案例。
18. 生成图表包说明，包括 Figure 2A 审稿人友好版证据链图。
19. 完成 Data/Code Availability 和 Threats to Validity。
20. 按结果优先顺序写终稿。

## 18. 降级策略

### 18.1 如果 baseline 不足

正文只能写“单系统诊断与案例评测”，不能写“优于现有方法”。投稿路线降级为北大核心/强普刊优先。

### 18.2 如果 ablation 不足

方法章只能写设计动机和系统机制，不能把性能改善归因到具体模块。

### 18.3 如果 transfer slice 不足

讨论中必须写“当前证据主要来自单篇中文长文档，外部有效性尚未充分建立”。

### 18.4 如果外部文献不足

引言和相关工作不得使用宽泛断言，先以中文核心路线推进，SCI 四区暂缓。

### 18.5 如果 final-context 主结果不理想

保留结果，不改写成漂亮叙事。可以将论文转为“系统边界与证据治理评测”路线，但不能隐藏失败。

## 19. 完成标准

终稿完成必须同时满足:

- 有一个 frozen artifact bundle。
- 有一个 metrics ledger。
- 有一个 literature ledger。
- 有一个 target journal matrix。
- 有一个 novelty positioning matrix。
- 有主结果表、baseline 表、ablation 表、失败桶表。
- baseline/ablation 有 paired delta、CI、effect size 或明确统计限制说明。
- 有 LLM stability protocol。
- 有 annotation reliability 或 adjudication 记录。
- 有 human evaluation 结果或 SCI 四区路线降级说明。
- 有系统总览图、证据面流图、Pareto 图、案例图。
- 有审稿人友好版证据链图。
- 有 Data Availability / Code Availability。
- 有 Threats to Validity。
- 摘要只使用 current frozen evidence。
- 讨论明确说明证明了什么、没有证明什么。
- 所有外部引用均已核验。
- 所有强主张均有证据或明确降级。

如果以上任一项缺失，稿件可以继续作为“投稿导向初稿”，但不应标为“终稿”。
