# A4 多跳推理 & 工具使用分析报告

**一句话结论**：HitRate 1-hop=0.605/2-hop=0.75；平均工具调用次数随 hops 非递减；Q31 触发 100 次工具调用（95 个独立签名），工具调用次数与 tokens 的 Pearson 相关系数为 0.8373，强正相关。

> **数据范围说明**：ground_truth 中 `reasoning_hops` 实际只有 1 和 2 两档（虽然 schema 描述为 1/2/3）；T4 全部 4 题被标注为 hops=2，并无 hops=3 题目。

## A. 按 reasoning_hops 分组指标

| hops | 题数 | 平均 num_tool_calls | 平均 \|R\| | HitRate | StrictHit | 平均 latency_ms | 平均 total tokens |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 38 | 14.447 | 34.421 | 0.605 | 0.605 | 15438.8 | 48075.6 |
| 2 | 12 | 33.75 | 58.583 | 0.75 | 0.75 | 34554.0 | 214122.0 |

工具调用数随 hops 的序列：hops=1: 14.447, hops=2: 33.75。符合「hops 越多 → 调用次数越多」的预期。

## B. T4 多跳详细分析（Q29-Q32）

| qid | num_tool_calls | HitRate | P | R | expected | retrieved (前20) |
|---|---:|---:|---:|---:|---|---|
| Q29 | 67 | 1 | 0.04 | 1.0 | n0018, n0024, n0078, n0079 | n0013, n0014, n0015, n0016, n0017, n0018, n0019, n0020, n0021, n0022, n0023, n0024, n0025, n0026, n0027, n0028, n0029, n0030, n0032, n0033 |
| Q30 | 10 | 1 | 0.2 | 1.0 | n0032, n0037, n0038 | n0026, n0027, n0028, n0029, n0030, n0032, n0033, n0034, n0035, n0036, n0037, n0038, n0039, n0040, n0041 |
| Q31 | 100 | 1 | 0.02 | 1.0 | n0015, n0019, n0021 | n0002, n0003, n0005, n0006, n0007, n0008, n0009, n0011, n0012, n0013, n0014, n0015, n0016, n0017, n0018, n0019, n0020, n0021, n0022, n0023 |
| Q32 | 35 | 1 | 0.069 | 1.0 | n0020, n0024, n0029, n0030 | n0001, n0002, n0003, n0005, n0006, n0007, n0008, n0009, n0011, n0012, n0013, n0014, n0015, n0016, n0017, n0018, n0019, n0020, n0021, n0022 |

**Q29** query：解决问题二的核心建模方法及其与问题三方法的差异是什么？
  工具序列（共 67 次）：search_kg_by_type×3 → get_entity_detail×2 → search_kg_by_type×3 → get_entity_detail → get_entity_neighbors → get_entity_detail → get_entity_neighbors → search_kg_by_type×2 → get_entity_neighbors → search_kg_by_type → get_entity_detail → search_kg_by_type×3 → get_entity_neighbors → search_kg_by_type×2 → get_kg_statistics → search_kg_by_type×3 → get_entity_detail×8 → search_kg_by_type×6 → get_entity_detail×2 → search_kg_by_type×9 → get_entity_detail×3 → search_kg_by_type×2 → get_entity_neighbors → search_kg_by_type×8 → get_entity_detail

**Q30** query：离网带储能场景相比无储能场景，产量提升了多少？
  工具序列（共 10 次）：search_kg_by_type×6 → get_entity_neighbors → get_entity_detail×3

**Q31** query：成本最低和最高的两种运营模式分别对应多少元/吨？
  工具序列（共 100 次）：search_kg_by_type×6 → get_entity_neighbors×3 → search_kg_by_type → get_entity_detail×5 → search_kg_by_type×3 → get_entity_neighbors → get_entity_detail×3 → get_entity_neighbors×3 → get_entity_detail → get_entity_neighbors×2 → search_kg_by_type×4 → get_entity_neighbors → search_kg_by_type×2 → get_entity_neighbors → get_entity_detail×2 → search_kg_by_type×2 → get_entity_detail → get_entity_neighbors → search_kg_by_type×2 → get_entity_detail×2 → get_entity_neighbors×2 → search_kg_by_type×3 → get_entity_neighbors → search_kg_by_type×6 → get_entity_neighbors → get_entity_detail → search_kg_by_type×5 → get_entity_neighbors → search_kg_by_type → get_entity_detail → get_entity_neighbors → search_kg_by_type → get_entity_neighbors → get_entity_detail×2 → get_entity_neighbors → search_kg_by_type×2 → get_entity_neighbors → search_kg_by_type → get_entity_detail×4 → search_kg_by_type×2 → get_entity_neighbors → search_kg_by_type → get_entity_neighbors×2 → search_kg_by_type×2 → get_entity_neighbors×2 → get_entity_detail×8

**Q32** query：摘要中讨论的两种连续调节方式分别使绿电合规率达到了什么水平？
  工具序列（共 35 次）：search_kg_by_type×6 → get_entity_detail → get_entity_neighbors → search_kg_by_type×2 → get_kg_statistics → search_kg_by_type → get_entity_detail → get_entity_neighbors → search_kg_by_type×2 → get_entity_detail → get_entity_neighbors → search_kg_by_type×2 → get_entity_detail → get_entity_neighbors → get_entity_detail → get_entity_neighbors → get_entity_detail×5 → get_entity_neighbors → get_entity_detail×5

## C. Q31 outlier 解剖（100 次调用）

Q31 共发起 **100** 次工具调用，独立调用签名 95 个，重复签名 4 组。各工具调用次数：
  - `search_kg_by_type`: 44
  - `get_entity_neighbors`: 26
  - `get_entity_detail`: 30

`get_entity_neighbors` 命中节点数：26 个；`get_entity_detail` 命中节点数：30 个。

**Top 重复调用 pattern：**
  - `search_kg_by_type({"entity_type": "section_header", "keyword": "问题四", "max_results": 20})` × 3
  - `search_kg_by_type({"entity_type": "section_header", "keyword": "5.4", "max_results": 20})` × 2
  - `search_kg_by_type({"entity_type": "metric", "keyword": "离网", "max_results": 20})` × 2
  - `search_kg_by_type({"entity_type": "metric", "keyword": "3682", "max_results": 10})` × 2

> 100 次调用里只有 4 组完全重复的签名；其余 95 个签名都不同——agent 实际上是在「不断切换 keyword 或 node_id」形成宽 BFS：先 6 次 `search_kg_by_type` 横扫 claim/metric/method/section_header，再切到 `get_entity_neighbors`（26 个不同 node_id）和 `get_entity_detail`（30 个不同 node_id），最后陷入大量 `get_entity_detail` 串调。failure mode 不是「卡死循环」而是「探索发散」——找不到目标后越搜越宽。

前 8 个 request：['search_kg_by_type', 'search_kg_by_type', 'search_kg_by_type', 'search_kg_by_type', 'search_kg_by_type', 'search_kg_by_type', 'get_entity_neighbors', 'get_entity_neighbors']

后 8 个 request：['get_entity_detail', 'get_entity_detail', 'get_entity_detail', 'get_entity_detail', 'get_entity_detail', 'get_entity_detail', 'get_entity_detail', 'get_entity_detail']

## D. 工具使用效率

全题集合 agent-initiated 调用总数：**954**。

| 工具名 | 调用次数 | 占比 |
|---|---:|---:|
| `search_kg_by_type` | 499 | 0.5231 |
| `get_entity_detail` | 311 | 0.326 |
| `get_entity_neighbors` | 119 | 0.1247 |
| `get_kg_statistics` | 25 | 0.0262 |

重复调用率（相同 `(tool_name, args)` 出现 ≥2 次的占比）：**0.499**，共有 156 个签名被重复发起。

Pearson(num_tool_calls, total_tokens) = **0.8373**。

**高效率示范（命中且调用最少）：**
  - Q02 (T1) — 1 次调用，tokens=1595
  - Q01 (T1) — 2 次调用，tokens=2648
  - Q03 (T1) — 3 次调用，tokens=3857
  - Q25 (T3) — 4 次调用，tokens=4009
  - Q26 (T3) — 4 次调用，tokens=4507

**低效率反例（未命中且调用最多）：**
  - Q49 (T7) — 60 次调用，tokens=360023
  - Q19 (T2) — 29 次调用，tokens=58827
  - Q16 (T2) — 27 次调用，tokens=72983
  - Q10 (T1) — 14 次调用，tokens=26861
  - Q11 (T1) — 11 次调用，tokens=16084

## E. T2 类型聚合召回（Q13-Q20）

| qid | |E| | |R| | |E∩R| | recall |
|---|---:|---:|---:|---:|
| Q13 | 5 | 65 | 5 | 1.0 |
| Q14 | 5 | 19 | 5 | 1.0 |
| Q15 | 3 | 11 | 0 | 0.0 |
| Q16 | 5 | 77 | 0 | 0.0 |
| Q17 | 4 | 37 | 4 | 1.0 |
| Q18 | 4 | 77 | 4 | 1.0 |
| Q19 | 2 | 45 | 0 | 0.0 |
| Q20 | 6 | 46 | 6 | 1.0 |

recall mean = **0.625**，min = 0.0，max = 1.0，median = 1.0。

## F. 限制说明

- `reasoning_hops` 是 ground_truth 中的人工估计值，按题型先验给定，不是图上的最短路径。
- `retrieved_node_ids` 在 raw_runs 中已经过去重；本脚本进一步用 `set()` 处理，因此 |R| 与 HitRate/Precision/Recall 均按集合语义计算。
- 工具调用次数只统计 `phase=='request'` 一类，`phase=='result'` 是 runtime 返回的 ToolMessage，不计入 agent 主动调用。
- Pearson 相关系数在 50 题样本上由 Q31 outlier（100 次调用）强烈拉动；去掉 Q31 后系数会下降，但本报告不剔除 outlier，以反映真实分布。
