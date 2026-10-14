# GraphRAG 论文 M3 最小方法合同

> 状态：M3 方法设计通过；图件保持 PLAN_READY，待渲染时确认  
> 代码基线：`46b202c3e400741fd569f024412c0745f224a538`  
> 证据状态：方法设计为 `AI_INFERENCE`，实现与效果为 `NOT_EXECUTED`  
> 工作名称：生产一致证据面核算框架（暂称 **PAESA-GraphRAG**，名称可在投稿前调整）  
> 补充口径：`paper-m3-evaluation-contract.md`；可审查变体清单：`paper-m3-variant-plan.yaml`。两者为 1.1 版设计补充，实验均未执行。

## 1. 方法身份与研究边界

PAESA-GraphRAG 不是新的检索模型，也不替换现有 GraphRAG 主链。它是在同一生产接口上运行的**变体控制、证据谱系、四阶段证据核算、claim/行为裁决和证据冻结方法**。

给定冻结文档集合 (D)、问题 (q_i)、最小充分证据集合 (G_i) 和目标行为
(b_i\in\{answer, refuse, correct\})，所有 baseline 和消融必须通过同一个
`POST /api/v1/rag/query` 执行。实验变体只允许改变显式声明的来源掩码、模块开关和预算向量；不得切换到旧接口、废弃原型或不同生成链。

本文能够检验的是：目标证据在生产链不同阶段如何保留、补入或丢失，以及这种变化与回答支持、拒答/纠错和成本之间的关系。本文不预设完整方案优于简单检索，也不把生产一致性本身写成性能贡献。

## 2. 方法框架图文字版

```text
冻结输入与身份
  文档/索引/GT/问题预处理/模型与 prompt/commit
                         │
                         ▼
M2 生产变体控制 ── enabled_sources + ablation_flags + budget vector
                         │
                         ▼
M3 多路径检索与稳定谱系
  Vector / KG / BM25 / conditional Table / optional Multi-Query
                         │
                         ▼
S1 path_hits ── 融合与允许的 rescue ──► S2 pre-rerank
                                              │
                                重排/去重/source cap/token budget
                                              │
                                              ▼
                                      S3 final-context
                                              │
                                   固定生成器与行为策略
                                              │
                                              ▼
                                      S4 answer claims
                                              │
                         ┌────────────────────┴───────────────────┐
                         ▼                                        ▼
              claim/citation 支持裁决                    answer/refuse/correct 裁决
                         └────────────────────┬───────────────────┘
                                              ▼
                     证据损耗 + 行为 + 成本 + paired comparison
                                              │
                                              ▼
                          独立变体目录与 frozen manifest

正交通道：release gate 只检查工程有效性与复现条件，不属于四阶段证据链。
```

## 3. 四阶段证据链与核算定义

### 3.1 四个证据状态

| 状态 | 定义 | 论文角色 |
|---|---|---|
| (E_i^{path}) | 各允许检索路径首次返回的稳定证据单元并集 | 早期可达性诊断 |
| (E_i^{pre}) | 融合与允许的 rescue 后、最终重排/选择前的候选集合 | 候选池诊断 |
| (E_i^{final}) | 实际送入生成器的有序 final-context | 检索 headline surface |
| (E_i^{claim}) | 被最终原子 claim 实际引用且经裁决为充分支持的规范证据单元并集；部分支持另列 | 严格回答支持面 |

`answer claims` 是第四阶段，`release gate` 是正交工程通道。旧正文把 release gate 算作第四层的写法被本合同取代。

### 3.2 证据保留、损失与补入

以下集合公式仅适用于已映射到相同规范证据粒度、且 gold 组合唯一的情形；存在等价出处或替代充分组合时，采用补充合同的事实组命中与充分组合完成率。对可回答或可纠错样本，在阶段 (s) 的目标证据召回为：

\[
R_i^s=\frac{|G_i\cap E_i^s|}{|G_i|}
\]

相邻阶段 (s\rightarrow t) 的目标证据损失与新增分别为：

\[
L_i^{s\rightarrow t}=\frac{|(G_i\cap E_i^s)\setminus E_i^t|}{|G_i|}
\]

\[
A_i^{s\rightarrow t}=\frac{|(G_i\cap E_i^t)\setminus E_i^s|}{|G_i|}
\]

必须同时报告损失与新增，因为 rescue 可能在后续阶段补入早期未命中的证据。`should_refuse=true` 且 (G_i=\varnothing) 的样本不进入检索 recall 分母，只进入回答行为评价。

### 3.3 claim 与引用边界

回答拆分为原子 claim，支持标签为：

- `fully_supported`
- `partially_supported`
- `unsupported`
- `contradicted`
- `not_applicable`

当前代码中的 `node_id_validity` 统一解释为 **citation-ID validity**：只验证引用标识是否存在、是否属于上下文。它不表示语义支持，也不能替代 claim support、citation precision/recall 或 hallucination evaluation。

## 4. 七个模块合同

本节 M1–M7 是方法内模块编号，与 SCI-Skills 阶段 M1–M7 不同；实施记录使用模块名称或 `MOD-01` 至 `MOD-07`，防止混淆。

| 模块 | 单一功能 | 输入 | 必须输出 | 无效或失败条件 |
|---|---|---|---|---|
| M1 证据注册 | 建立跨层稳定证据身份与原文边界 | 文档、解析结果、KG、索引版本 | `evidence_id`、文档/文本哈希、类型、source span、页码/bbox、构建版本、`locator_status` | 未知文档回退、合成 offset 或不可回源对象不得计入坐标级结果 |
| M2 生产变体控制 | 只改变声明的实验变量 | 问题、`variant_id`、冻结预处理、source mask、flags、预算 | requested/effective 配置、endpoint、commit、`metadata.mode` | legacy fallback、mask 泄漏、配置无法核对则整次运行无效 |
| M3 检索轨迹记录 | 保存 `path_hits` 与 `pre-rerank` 谱系 | 各检索器事件、证据目录 | 所有来源、路径内 rank/score、融合分数、query variant、rescue/丢弃原因 | 最后完成线程覆盖来源或同分排序不确定 |
| M4 final-context 治理 | 在固定预算内形成真实生成上下文 | pre-rerank、重排、去重、来源/token 预算 | 有序 final-context、累计 token、实际重排状态、跳过/截断原因 | 超预算、不可重放或 final 项无上游谱系 |
| M5 响应记录 | 生成并记录回答行为 | 问题、final-context、固定生成配置 | 原始回答、预测行为、引用、token、时延、重试 | 引用不属于 final-context，或变体间模型/prompt 漂移 |
| M6 claim 与行为裁决 | 判断语义支持及回答/拒答/纠错是否适当 | 回答、final-context、GT、标注协议 | claim 标签、引用映射、支持/矛盾证据、行为标签、仲裁状态 | 仅凭 ID 存在或拒答关键词自动判为正确 |
| M7 损耗核算与冻结 | 汇总四阶段、行为与成本并生成不可覆盖证据包 | M1–M6、变体合同、GT | 问题级/宏平均指标、paired delta/CI、raw run、manifest、完整 SHA-256 | 混用 commit、问题集、生成配置或历史结果 |

`locator_status` 至少分为 `verified`、`unverified`、`synthetic`。只有 `verified` 能支持页码、bbox 或字符坐标级主张。结构边和属性推断边可用于候选扩展，但不能自动充当事实 claim 的支持证据。

## 5. 最小数据结构

### 5.1 实验变体

```yaml
variant_id:
enabled_sources: [vector, kg, bm25, table, multi_query]
retrieval_mode: local | global
ablation_flags:
  disable_rescue: false
  disable_refusal_policy: false
  disable_answer_repair: false
  disable_citation_id_check: false
budget:
  raw_candidates_total:
  pre_rerank_cap: 7
  final_k: 5
  context_tokens: 4000
enable_cross_encoder:
```

`per_source_caps` 只表示预算，不能兼作来源开关。`disable_rescue` 必须同时约束 retrieval rescue 和 generator targeted rescue。

### 5.2 EvidenceRef

```yaml
evidence_id:
document_id:
document_sha256:
local_id:
kind:
source_paths: []
path_ranks: {}
path_scores: {}
rrf_score:
rerank_score:
page_idx:
bbox_norm:
char_start:
char_end:
text_sha256:
truncated: false
rescue_reasons: []
locator_status: verified | unverified | synthetic
```

重复候选必须合并 `source_paths/path_ranks/path_scores/rescue_reasons`；主来源使用固定 precedence，最终排序使用稳定 `evidence_id` 作为 tie-break。禁止 UUID fallback 和基于线程完成先后的 last-writer 语义。另需 `canonical_evidence_ids` 和 `visible_spans`，使异构检索对象及截断后的实际内容能够映射到相同的 gold 事实组。

### 5.3 ClaimRecord 与回答决策

```yaml
claim_id:
text:
answer_char_start:
answer_char_end:
claim_type:
requires_citation:
citation_evidence_ids: []
support_label: fully_supported | partially_supported | unsupported | contradicted | not_applicable
supporting_evidence_ids: []
contradicting_evidence_ids: []
action: keep | correct | remove
original_text:
corrected_text:
reason_code:
label_source: runtime | annotator | adjudication
verifier:
  kind:
  version:
  prompt_hash:
```

查询级另存：

```yaml
answer_decision:
  predicted: answer | refuse | correct
  gold:
  reason_code:
  evidence_ids: []
  policy_version:
```

runtime 自评与人工/独立裁决必须分栏，纯拒答样本不得强行生成 claim。

### 5.4 Frozen manifest 与成本账本

manifest 至少记录：commit 及 dirty 状态、完整命令、variant/config hash、GT/语料/索引/冻结 rewrite 的 SHA-256、生成/预处理/embedding/reranker 精确版本、prompt hashes、temperature、retry/timeout/budgets、QID、UTC 和输出哈希。

`cost_ledger` 分项记录 `coreference/query_preprocess/multi_query/embedding/recall/rerank/generation/index_build` 的 calls、cache hit、input/output tokens、latency 和 model。货币成本由冻结 price book 离线计算，索引一次性成本必须与单题在线成本分开。

## 6. 端到端操作流程

1. 冻结 commit、依赖锁、文档、GT、索引、模型、prompt 和预算合同。
2. 建立证据目录并核验 document hash、node/source 映射及 locator 状态。
3. 一次性生成并冻结问题预处理结果，所有变体重放同一结果。
4. 通过同一 `/api/v1/rag/query` 发送带 `variant_id` 的请求。
5. 正常检索、global 分支、retrieval rescue 和 generator rescue 共同服从 source mask/flags。
6. 保存逐来源 path hits，并按确定性规则合并完整来源谱系。
7. 保存融合/rescue 后的 pre-rerank，再执行受控重排、去重与预算选择。
8. 保存实际 final-context；生成器只能读取这一集合。
9. 记录回答、决策和引用；离线拆分原子 claim 并按统一协议裁决。
10. 计算证据损失/新增、final-context、claim、行为和成本指标。
11. 对同一问题执行成对比较并在 M5 决定区间估计/检验方式。
12. 每个变体输出独立、不可覆盖的目录和 frozen manifest。

任何 legacy fallback、来源掩码泄漏、未记录预算、生成配置漂移或谱系断裂都标记为 `invalid_run`，不得静默进入平均值。必须保留全部预定问题、运行失败及无效原因，报告共同有效样本覆盖比例；科学上的未命中与错误答案不能排除为无效运行。

## 7. baseline 与消融合同

主表最低包含：

1. BM25-only；
2. Vector-only；
3. Vector + BM25 + RRF，Cross-Encoder off；
4. Vector + BM25 + KG + conditional Table + RRF，Cross-Encoder off；
5. Full production adaptive：与第 4 行相同来源，启用自适应 Cross-Encoder 与预算保护。

共同固定 `K_final=5`、`context_tokens=4000`、`pre_rerank_cap=7`、同一生成模型与 prompt、temperature 0、输出上限、重试策略和冻结问题预处理。raw candidate 总预算必须在 M5 前锁定并对各路线公平分配。

上述五行只能测 KG/Table 的组合增量。执行清单采用 `paper-m3-variant-plan.yaml` 的七行 B01–B07，并加入仅新增 KG、仅新增 Table 的 hybrid 对照以分别归因。KG-only 独立检索器、Multi-Query、Global 和回答侧 flags 进入诊断表或专项消融。full-context/SELF-ROUTE 风格强基线在资源允许时加入，但不是 M4 最小原型的前置条件。

## 8. 待检验假设与证伪条件

| ID | 待检验主张（`AI_INFERENCE`） | 检验 | 证伪或降级条件 |
|---|---|---|---|
| H1 | path hits 会高估最终可用证据 | 成对比较 (R^{path}) 与 (R^{final}) 及损耗分布 | 差值接近零、不稳定或方向相反 |
| H2 | KG/conditional Table 的增量集中在特定复杂题型 | 比较基线 3 与 4 的总体和分层结果 | 目标题型无增益或成本不可接受 |
| H3 | citation-ID 合法率高于完整 claim 支持率 | 同回答上的 paired comparison 与人工裁决 | 无可靠差异或标注一致性不足 |
| H4 | 自适应 Cross-Encoder 存在质量—延迟权衡 | 比较基线 4 与 5并报告实际执行率 | 模块未执行、质量无变化或成本记录不全 |
| H5 | 关键词式拒答评价存在行为误判 | 与人工 answer/refuse/correct 混淆矩阵比较 | 两者高度一致且无系统误判 |

以上均不能提前写成结果。

## 9. 相对现有方法的改进点

| 方法族 | 本合同增加的可检验内容 | 明确不声称 |
|---|---|---|
| 平面检索 | 同接口、同 raw/final/context 预算的公平基线 | 不预设图检索更优 |
| GraphRAG / KG-RAG | 从路径候选到 claim 的证据状态及原文谱系 | 不提出新社区发现、图遍历或摘要算法 |
| 长文档检索 | 固定 final-context 预算并保留全文对照条件 | 不以中文/长文档场景本身声称新颖 |
| 引用与忠实性 | 分离 citation-ID validity 与 claim support | 不将引用存在写成语义忠实 |
| 拒答评测 | 三类行为裁决，替代关键词式成功判定 | 不声称拒答问题已解决 |
| 自适应检索 | 记录实际执行率、跳过原因和全链成本 | 不以配置开启推断模块贡献 |
| ARES/RAGChecker 类框架 | 增加生产 endpoint、有效配置和冻结资产一致性 | 不声称取代通用 RAG 评价框架 |

## 10. 仓库实施条件与精确落点

| 需求 | 可复用位置 | M4 最小变化 |
|---|---|---|
| source mask/flags | `backend/models.py:40-68`、`backend/config.py:78-98`、`backend/routes/rag_query.py:97-118` | 新增 allowlist、resolved config 和 metadata 回传 |
| mask 全链一致 | `backend/retrieval.py:465-536,2590-2683`、`backend/generator.py:1019-1147,1371-1383` | normal/global/retrieval rescue/generator rescue 共用 mask |
| 稳定融合 | `backend/retrieval.py:485-530,1790-1803` | 固定 source precedence、合并多来源谱系、稳定 tie-break |
| 跨文档 ID | `backend/kg_store.py:480-488`、`backend/retrieval.py:796,952-996`、`run_inference_helpers.py:4-10` | 使用真实 document ID + local ID；评测不剥文档前缀 |
| 四阶段 trace | `backend/retrieval.py:2648-2651,2690-2696,2840-2849`、`backend/generator.py:1418-1425,1593-1600`、`backend/routes/rag_query.py:379-386` | 从 ID 列表升级为结构化 `EvidenceRef`，加入 claims |
| span/bbox 保留 | `backend/doc_processor.py:32-45`、`backend/vector_store.py:258-289`、`backend/retrieval.py:1091-1131,1221-1235`、`backend/routes/rag_query.py:315-332` | 扩展投影白名单，禁止 SourceNode 丢 bbox/span |
| KG 原文定位 | `backend/schema.py:50-70`、`backend/kg_builder.py:328-340` | 将 document identity 和 char interval 保存到 KG node |
| claim/行为 trace | `backend/generator.py:624,643,699,919,1194,1215-1256,1385-1531` | 输出 decision/correction/citation trace；ID 检查不冒充 entailment |
| frozen runner | `iteration-2/eval-2-existing-components/rag_eval/run_inference.py:149-219,253-343` | 增加 variant config、独立目录、manifest、invalid-run 检查 |
| 全链成本 | `backend/generator.py:1542-1546`、`backend/retrieval.py:339-355,1738-1757`、`backend/conversation.py:376-445` | 记录预处理、多查询、指代、重排和生成；离线价格簿 |

无需发明新模型即可实施，但 M4 前必须承认六个风险：跨文档 ID 碰撞、span/bbox 投影丢失、异步 last-writer、generator rescue 绕过 mask、token 截断不记录新 span、rewrite/cache 漂移。

## 11. 方法章节结构

```text
3 方法
3.1 任务定义与研究边界
3.2 生产一致的实验执行合同
3.3 文档证据身份与谱系
3.4 多路径检索轨迹
3.5 final-context 治理
3.6 回答行为与 claim 证据映射
3.7 证据损耗与联合评价
3.8 基线、消融与统计协议
3.9 复现与证据冻结
```

正文写作仍在 M6；本结构现在只作为 M4/M5 的复现合同。

## 12. 资源与条件清单

### 已核实

- 生产主接口、多路检索、RRF、条件 Table、自适应 Cross-Encoder、预算与三层旧 trace 已存在。
- 现有 runner 已通过生产 TestClient 执行，适合扩展而非另起原型。
- 仓库已有 GT、标注协议、历史 raw runs、指标脚本和证据冻结规则。

### 待实现或待冻结

- 统一 source mask/ablation flags、稳定 provenance 和结构化四阶段 trace。
- claim/行为标注结构及至少一轮独立复核/仲裁安排。
- held-out 或跨文档切片及抽样规则。
- raw candidate 总预算、精确模型版本、硬件与价格簿。
- 新 frozen commit 下的统一 rerun。

### 禁止表述

“首次/首创/填补空白”“显著优于”“零幻觉”“可靠多跳推理”“中文长文档总体适用”“企业级生产就绪”“坐标级可追溯（定位未核验时）”“图谱边均为事实”“no-rerank（仅关闭 Cross-Encoder 时）”“五路默认全开”“降低成本（未统计全链时）”。

## 13. M3 正式评审

| 验收项 | 当前状态 | 依据 |
|---|---|---|
| 方案结构清楚 | 通过 | 四阶段链、七模块、12 步流程与无效运行规则完整；1.1 补充明确等价证据与分母 |
| 每个模块功能明确 | 通过 | 模块输入、输出和失败条件已定义；代码落点已复核 |
| 相对现有方法改进具体 | 通过 | 生产一致核算与谱系可检验；七变体支持 KG/Table 单模块归因 |
| 具备实施条件 | 通过 | 已映射现有代码复用点、最小改动和风险；实现与效果仍为 NOT_EXECUTED |
| 图位与拆图方案 | 计划完备；渲染确认待办 | 已提供全览加模块图及组合图选项；未制作图件，此项不阻塞方法设计验收 |

**M3 方法设计结论：PASS。** 本结论只验收方法设计。图件尚未渲染，作者选择和渲染批准均不推定为已取得，留到图件制作前确认；原型实现、真实依赖验证及实验效果由 M4/M5 独立验收。
