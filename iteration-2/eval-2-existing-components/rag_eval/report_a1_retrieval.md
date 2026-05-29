# A1 - 检索精度 / 召回率 评测报告

> 评测对象：GraphRAG（LangGraph agent + DeepSeek-chat + NetworkX KG），50 题，7 类别
> 数据来源：`metrics_a1_retrieval.json`（脚本：`metrics_a1_retrieval.py`，原始：`raw_runs.jsonl` + `ground_truth.json`）
> 评测日期：2026/05/28

## 一句话结论

**Recall 0.82、Precision 0.078、F1 0.13** —— 系统呈现典型的「宁滥勿缺」模式：能找到正确答案节点（高召回），但把大量无关节点也拉了进来（低精度），平均每题检索 40 个节点而期望只有 2 个。

## 总体指标表（按 category macro 平均）

| 类别 | 题数 | 计入 | Precision | Recall | F1 | HitRate | StrictHit | MRR | avg\|R\| | avg\|E\| |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **Global** | 50 | 39 | **0.078** | **0.821** | **0.129** | **0.821** | **0.821** | 0.140 | 40.2 | 2.08 |
| T1 简单事实 | 12 | 12 | 0.125 | 0.750 | 0.188 | 0.750 | 0.750 | 0.223 | 26.2 | 1.08 |
| T2 类型聚合 | 8 | 8 | 0.079 | 0.625 | 0.136 | 0.625 | 0.625 | 0.086 | 47.1 | 4.25 |
| T3 数值精度 | 8 | 8 | 0.045 | **1.000** | 0.084 | 1.000 | 1.000 | 0.112 | 43.0 | 1.25 |
| T4 多跳推理 | 4 | 4 | 0.082 | **1.000** | 0.144 | 1.000 | 1.000 | 0.118 | 81.5 | 3.50 |
| T5 OOD 拒答 | 10 | 0 | — | — | — | — | — | — | 29.6 | — |
| T6 噪声鲁棒 | 5 | 5 | 0.043 | **1.000** | 0.082 | 1.000 | 1.000 | 0.118 | 38.8 | 1.20 |
| T7 假前提 | 3 | 2 | 0.011 | 0.500 | 0.021 | 0.500 | 0.500 | 0.071 | 53.3 | 2.00 |

> T5 全部 should_refuse、expected 为空，已排除（10 题在 A3 单独评测）。
> T7 Q48 应当拒答（expected 空）已排除；Q49/Q50 期望命中。

## 关键发现

1. **召回-精度严重失衡**：avg|R|=40.2 vs avg|E|=2.08，平均「覆盖率 19x」。Agent 偏爱多调用 `search_kg_by_type` + `get_entity_neighbors` 把大块邻居拉回来，导致 R∩E 占比极低。
2. **数值/多跳类 100% 召回**：T3 / T4 / T6 在 Recall/HitRate/StrictHit 上全部 1.0。说明 KG 结构 + agent 探索深度足以覆盖中文论文的数值实体。
3. **图表类与列表型聚合是盲区**：7 题完全 miss（hit=0），其中 4 题 (Q10/Q11/Q15/Q16) 与「图 X」「指标列表」相关；T2 的 HitRate 仅 0.625 是全局最弱类。
4. **HitRate ≡ StrictHit**：在 elig 题中要么完全命中要么完全错过，没有部分命中。说明 expected 集合较小（avg 2.08），加上 agent 检索量大（avg 40），一旦切中关键 keyword 就一并拉全 —— 是「全有/全无」模式，不是渐进式召回。
5. **T1 vs T6 噪声扰动**：T6 (错别字版) 相比 T1 (原版) Recall +0.25、Precision -0.082、F1 -0.106。系统对噪声鲁棒（召回更高），但代价是更滥的检索（精度更低）。

## Outlier 案例（最差 5 题）

| qid | 类别 | Query 摘要 | \|R\| | \|E\| | P | R | F1 | 问题诊断 |
|---|---|---|--:|--:|--:|--:|--:|---|
| Q16 | T2 | 摘要中"吨氨成本"类经济指标 | 77 | 5 | 0 | 0 | 0 | 5 个 metric 节点全错过；agent 拿了一堆 claim/section 节点 |
| Q49 | T7 | "储能装置反而降低园区产量"是否对 | 70 | 3 | 0 | 0 | 0 | 错误前提反驳类，agent 60 次工具调用都没命中 n0032/0037/0038 |
| Q10 | T1 | 图 5 展示了什么内容 (n0313) | 68 | 1 | 0 | 0 | 0 | "图 5" 这种 label 没被工具关键词搜索匹配到 |
| Q19 | T2 | 绿电指标合规率的具体数值 | 45 | 2 | 0 | 0 | 0 | 2 个 metric 节点漏检 |
| Q04 | T1 | 求解问题二的优化方法 | 44 | 2 | 0 | 0 | 0 | MILP 应该好找，但 agent 拉了一堆 claim 节点而漏掉 n0018/n0079 |

**最大 "过取" Top 3**（|R|/|E| 比值）：
- Q05 (T1) 91x 过取：1 个 expected 配 91 个 retrieved（虽然 R=1.0）
- Q27 (T3) 89x 过取
- Q31 (T4) 51x 过取，共检索 153 个节点 —— 这是 100 次工具调用的极端 outlier

## 计算公式与数据来源

对每题 $i$，令 $R_i$ = retrieved_node_ids 集合, $E_i$ = expected_node_ids 集合：

- $\text{Precision} = |R \cap E| / |R|$，$|R|=0$ 时为 0
- $\text{Recall} = |R \cap E| / |E|$，$|E|=0$ 时未定义（排除）
- $\text{F1} = 2PR/(P+R)$
- $\text{HitRate} = \mathbb{1}[|R \cap E| \geq 1]$
- $\text{StrictHit} = \mathbb{1}[E \subseteq R]$
- $\text{MRR} = 1/\text{rank}_1$，其中 rank_1 为第一个相关节点在 retrieved 列表中的位置

聚合方式：category 内 macro 平均；T5 全排除；T7 Q48 排除（与 T5 同质）。

数据：每题的 retrieved_node_ids 由 `run_inference.py` 用正则 `\bn\d{4}\b` 从所有 ToolMessage 的 content 中提取得到，并按出现顺序去重保序，保存到 `raw_runs.jsonl` 的 `retrieved_node_ids` 字段。

## 限制说明

1. **retrieved 是去重 set，MRR 意义有限**：retrieved_node_ids 虽然保序，但顺序来自「tool 结果拼接」，不反映学习到的相关性排序。MRR 数值仅作参考。
2. **HitRate ≡ StrictHit 的成因**：avg|E|=2 远小于 avg|R|=40，一旦 agent 找到入口节点就常把整族邻居拉回来，呈"全有全无"模式；该指标对部分召回不敏感。
3. **expected_node_ids 是人工反向构建的 GT**：可能存在等价节点（同义实体）未被列入 expected。本评测不补充等价集合，因此 Recall 是真实下界。
4. **T5 (10 题) 不计入检索指标**：因为 expected 为空，无法定义 P/R。这些题在 A3 报告中按「拒答能力」单独评测。
5. **Precision 数值偏低的根因**：本系统倾向"宁滥勿缺"的 agentic 检索策略（多次工具调用 + 邻居展开），不是召回失败。修复方向是答案合成阶段做证据筛选，而不是检索阶段。
