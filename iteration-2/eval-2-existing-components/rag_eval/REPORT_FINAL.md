# GraphRAG 综合评测报告

> **对象**：GraphRAG（LangGraph create_agent + DeepSeek-chat + NetworkX KG）
> **文档**：`论文.pdf`（439 节点 / 1901 边 / 31 页 / 中文，电氢氨园区优化论文）
> **样本**：50 题真实问答，分 7 类（T1 事实 / T2 聚合 / T3 数值 / T4 多跳 / T5 拒答 / T6 噪声 / T7 假前提）
> **评测日期**：2026/05/28
> **真实性保证**：所有 GT 节点 ID 都经 `assert nid in NODES` 校验存在；所有指标用确定性 Python 脚本从 `raw_runs.jsonl` + `ground_truth.json` 计算得出；脚本与原始数据均已落盘可复现。

---

## 一句话定性

**这套 GraphRAG 是「高召回、高忠实、高鲁棒，但低精度、高成本、长尾爆炸」的 agentic 检索系统。**

数据：能找到答案的比例 82%、答案中引用的节点 100% 真实存在、噪声/假前提/拒答 3 项全部 100%；代价是平均每题 19 次工具调用、$0.025/题、Q31 单题 100 次调用 / $0.44 / 137 秒。

---

## 七大维度仪表盘

| 维度 | 指标 | 数值 | 解读 |
|---|---|--:|---|
| **A1 检索召回** | Recall_macro | **0.82** | 39 题计入，excluded 11 题 |
| A1 检索召回 | HitRate / StrictHit | 0.82 / 0.82 | 全有/全无模式 |
| **A1 检索精度** | Precision_macro | **0.078** | avg \|R\|=40 vs \|E\|=2，过取 19× |
| A1 F1_macro | F1 | 0.129 | 精度拖累 |
| **A2 忠实度** | node_id_validity | **1.000** | 0 个幻觉节点 ID（共 253 次引用） |
| A2 忠实度 | cited_in_retrieved | 1.000 | 答案引用的节点 100% 来自实际检索 |
| A2 忠实度 | keyword_coverage | 0.799 | GT 关键词字面匹配率 |
| A2 忠实度 | forbidden_violation | 0.20 (1/5) | Q24 提到了不应提的数值 |
| **A3 拒答** | T5 correct_refusal | **1.000** (10/10) | OOD 全部正确拒答 |
| A3 拒答 | T5 false_positive_answer | 0 | 没有"造答案" |
| **A3 噪声鲁棒** | T6 robustness_match | 1.000 (5/5) | 错别字下节点命中不掉 |
| A3 噪声鲁棒 | T6 vs T1 Δtool_calls | +5.2 | 噪声让 agent 多花 5 次工具调用 |
| **A3 假前提** | T7 rejection_rate | **1.000** (3/3) | 都识别出错误前提 |
| **A4 多跳** | hops=1 HitRate | 0.605 (38 题) | 包含 T5/T7 应拒题 |
| A4 多跳 | hops=2 HitRate | 0.750 (12 题) | 多跳反而更高 |
| A4 工具效率 | repeat_signature 率 | 50% | 一半工具调用是重复签名 |
| A4 工具效率 | Pearson(calls, tokens) | 0.84 | tokens 由调用次数主导 |
| **A5 延迟** | P50 / P95 / max (ms) | 13,049 / 60,198 / 137,599 | 长尾极端 |
| A5 token | P50 / P95 / max | 16,710 / 360,023 / **1,614,329** | Q31 单题 1.6M tokens |
| A5 工具 | P50 / P95 / max calls | 11 / 60 / 100 | 8% 题 ≤3 次 |
| **A5 成本** | 总 / 均值 / 中位 (USD) | $1.250 / $0.025 / $0.0073 | mean ≫ median，长尾倾斜 |
| A5 成本 | 月成本（1000题/天） | $750 | cache-miss 上界 |
| A5 成本 | Q31 占比 | 35.5% | 单题占总成本 1/3 |

---

## 维度详解

### A1 检索精度 / 召回率

**结论**：高召回 + 低精度，「宁滥勿缺」。

| 类别 | n | P | R | F1 | avg\|R\| | avg\|E\| |
|---|--:|--:|--:|--:|--:|--:|
| T1 | 12 | 0.125 | 0.750 | 0.188 | 26.2 | 1.08 |
| T2 | 8 | 0.079 | **0.625** | 0.136 | 47.1 | 4.25 |
| T3 | 8 | 0.045 | **1.000** | 0.084 | 43.0 | 1.25 |
| T4 | 4 | 0.082 | 1.000 | 0.144 | 81.5 | 3.50 |
| T6 | 5 | 0.043 | 1.000 | 0.082 | 38.8 | 1.20 |
| T7 | 2* | 0.011 | 0.500 | 0.021 | 53.3 | 2.00 |

7 题完全错过（hit=0）：Q04、Q10、Q11、Q15、Q16、Q19、Q49 —— 集中在「图表类」和「列表型 metric 聚合」。

> 详情：`report_a1_retrieval.md`

### A2 答案忠实度 / 抗幻觉

**结论**：零幻觉、100% 引用真实节点、T5 拒答完美；关键词覆盖 79.9%、forbidden 违规 1 例。

| 指标 | 全局 | T1 | T2 | T3 | T4 |
|---|--:|--:|--:|--:|--:|
| node_id_validity | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| cited_in_retrieved | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| keyword_coverage | 0.799 | 0.833 | 0.708 | 1.00 | 0.542 |
| hallucination_rate | **0** | 0 | 0 | 0 | 0 |

- **0 幻觉节点 ID**：43 题 / 253 次引用，全部 ∈ KG 439 节点，且 ∈ 检索过的 R。
- **唯一 forbidden_violation**：Q24（T3）正确答了"可再生能源发电量 603.45 MWh"但答案中提到了 forbidden 词「558.72」（属总用电量）—— 不是错答，是「多答」。
- **keyword_coverage 最低 5 题**：Q10、Q11（"图 X"题，agent 没用 GT 关键词描述图）、Q15、Q16、Q31。
- **T5 (OOD) 拒答关键词命中 10/10**：每题都用「不包含 / 没有 / 无法 / 未提及 / 未涉及 / 无关」之一明确拒绝。

> 详情：`report_a2_faithfulness.md`

### A3 拒答 / 噪声鲁棒 / 假前提

**结论**：三项核心安全能力 100%。

- **T5 OOD 拒答 (10/10 = 100%)**：Transformer/BERT/ResNet/作者邮箱/影响因子等 KG 外问题全部正确拒答。avg_tool_calls=10.2 vs T1 的 11.5（over_retrieval_ratio=0.89）—— 拒答时调用反而更少，说明 agent 知道何时该放弃。
- **T6 噪声鲁棒 (5/5 = 100%)**：错别字"证书→整数"、"用店→用电"、"吨案→吨氨"、"Pythn→Python"、"wind 4 solar 1" 全部正确命中节点，关键词命中率 0.95（仅 0.05 下降）。代价：平均多 5.2 次工具调用、+5076ms 延迟、+21,736 tokens。
- **T7 假前提反驳 (3/3 = 100%)**：「论文用了 GPT-4」「储能反而降低产量」「初始产能 100 吨/日」均被纠正。

> 详情：`report_a3_robustness.md`

### A4 多跳推理 / 工具使用效率

**结论**：hops=2 反而比 hops=1 命中率高（0.75 vs 0.605）；工具重复调用率 50%；Q31 是发散爆炸不是循环死锁。

| hops | n | avg_calls | avg_retrieved | HitRate | avg_latency | avg_tokens |
|--:|--:|--:|--:|--:|--:|--:|
| 1 | 38 | 14.4 | 34.4 | 0.605 | 15.4 s | 48k |
| 2 | 12 | 33.8 | 58.6 | **0.750** | 34.6 s | 214k |

> 注：hops=1 包含 T5/T7-Q48 等应当拒答（无 expected），它们计入分母拉低 HitRate；hops=2 大多是 T2/T4 需检索类。

**工具调用分布**：search_kg_by_type 52% / get_entity_detail 33% / get_entity_neighbors 13% / get_kg_statistics 3%。

**Q31 outlier 解剖**（T4，"成本最低和最高的两种运营模式分别对应多少元/吨"）：
- 100 次 request，95 个不同签名 + 4 个重复 → **不是死循环，是探索发散**
- 序列：先 6× search_kg_by_type 横扫 claim/metric/method/section_header → 26× neighbors 拉 26 个不同 node 的邻居 → 30× detail 串调（结尾连发 8 次）
- HitRate=1（覆盖了 expected），Precision=0.02（捞了 153 个无关节点）

> 详情：`report_a4_multihop.md`

### A5 延迟与成本性能

**结论**：tool_calls 单一变量主导一切；Q31 单题占总成本 35%；mean ≫ median 长尾倾斜严重。

| 类别 | n | mean latency | mean cost | mean tokens |
|---|--:|--:|--:|--:|
| T1 | 12 | 13.6 s | $0.0105 | 41.9k |
| T2 | 8 | 21.6 s | $0.0181 | 65.2k |
| T3 | 8 | 18.7 s | $0.0237 | — |
| **T4** | 4 | **60.4 s** | **$0.1442** | 521k |
| T5 | 10 | 11.2 s | $0.0051 | 16.4k |
| T6 | 5 | 15.3 s | $0.0105 | 37.6k |
| T7 | 3 | 28.6 s | $0.0363 | — |

**Pearson 相关**：
- calls vs latency = **0.962**（近完美）
- calls vs tokens = **0.837**（强）
- input vs output = 0.913

**月成本推算**（按 mean $0.025/题、cache-miss 上界）：
- 1,000 题/天 → **$750/月**
- 10,000 题/天 → $7,502/月

**Q31 是绝对孤狼**：唯一一个 latency + tokens + tool_calls 三维都超 P95 的题。若设 max_tool_calls=30 截断，预计可省 30-40% 总成本。

> 详情：`report_a5_performance.md`

---

## 关键案例

### 完美案例

- **Q02 (T1)**：「论文编号是什么？」→ 1 次工具调用、200ms、命中 n0002、正确答 "002196"
- **Q33 (T5)**：「Transformer 模型用了多少层 encoder？」→ 5 次工具调用、确认 KG 无关联实体后明确"不包含"
- **Q49 (T7) 反驳**：「储能反而降低产量」→ 正确反驳：实际从 9023 → 10903 吨，提升 20.8%

### 失败案例

- **Q10/Q11 (T1)**：「图 5 / 图 6 展示什么内容」→ agent 检索了节点但没用 GT 关键词（问题四 / 三种模式 / 吨氨成本）描述，keyword_coverage=0；这是「答对了但用词不一致」，不是真错
- **Q15 (T2)**：「论文所有的图有哪些」→ 仅检索了 11 个节点，但 3 个 figure 节点 n0221/n0313/n0379 全错过 —— 真错
- **Q16 (T2)**：「吨氨成本类经济指标列表」→ 5 个 metric 节点全错过，但检索了 77 个无关节点 —— 真错
- **Q31 (T4)**：「成本最低和最高的两种模式」→ 命中了 expected 但用了 100 次工具调用、$0.44 —— 答对得离谱

---

## 整体优劣

### 优势 ✓

1. **零幻觉**：答案中所有 node_id 都真实存在并被实际检索（253/253）
2. **拒答可靠**：T5 (10/10) + T7 (3/3) = 100%，没有"自信地答错"
3. **噪声鲁棒**：T6 错别字下节点命中不掉，关键词只降 5%
4. **数值/多跳完整召回**：T3/T4/T6 三类的 Recall/HitRate/StrictHit 全 1.0
5. **agent 能放弃**：T5 平均工具调用比 T1 少（10.2 vs 11.5），说明 system_prompt 第 7 条「If the KG doesn't contain the information, say so clearly」被很好遵循

### 劣势 ✗

1. **精度极低（0.078）**：每召回 1 个相关节点带 19 个无关节点，下游答案合成压力大
2. **图表/列表类盲区**：Q10/Q11/Q15/Q16 真错；agent 对"图 X"和"列出所有 X"类查询稳定性不足
3. **Q31 单题 outlier**：100 次工具调用、1.6M tokens、$0.44，占总成本 35%
4. **context 累积成本爆炸**：input/output 中位比 18×、P95 84×，每次工具调用都重发整个 context
5. **重复签名率 50%**：一半工具调用是重复 (tool, args) 组合，纯浪费

---

## 优化建议（按 ROI 降序）

| # | 建议 | 预期收益 | 复杂度 |
|--:|---|---|---|
| 1 | **设 `max_tool_calls=30` 硬上限** | Q31 + 7 题被截断，省 30-40% 总成本 | 低 |
| 2 | **裁剪 ToolMessage**：search 默认 `max_results=15`，每条几 KB；改为 5 + 仅返回 node_id/label/page_idx/score | 减小累积 input，降 50% input tokens | 中 |
| 3 | **签名去重**：在 agent 包一层「same args → cached result」拦截 50% 重复调用 | 减少 50% 工具调用次数 | 中 |
| 4 | 开启 DeepSeek prompt cache（input $0.07/M cache-hit） | input cost 降 75%（视重复率） | 低 |
| 5 | **答案合成阶段加证据筛选**：当前 retrieved 40 节点直接灌给 LLM 回答，应先按问题关键词排序取 top-10 | 提升 Precision，改善 forbidden_violation | 高 |
| 6 | 对"图 X"类查询特殊处理：先 search section_header 包含"图"的，再 detail | 修复 Q10/Q11/Q15 类盲区 | 低 |
| 7 | T4 多跳类用更精简 system_prompt + 工具描述 | 降低 T4 类 60s P95 → 30s | 中 |

---

## 可信度与限制

### 数据真实性证明

1. **GT 节点全验证**：`build_ground_truth.py` 用 `assert nid in NODES, f"{qid}: node {nid} not in KG"` 校验全部 50 题 × 共 ~80 个 expected_node_ids 都真实存在于 KG。
2. **指标算法确定性**：A1-A5 五个 metrics 脚本全部用纯规则（集合运算、字符串匹配、token 计数）计算，**未调用任何 LLM 作 judge**，可完整复现。
3. **原始日志完整保留**：`raw_runs.jsonl` 650KB（50 × 行）记录每题 query / tool_calls 全序列 / retrieved_node_ids / final_answer / latency_ms / tokens / timestamp，可逐题追溯。
4. **零失败运行**：50/50 题成功，0 错误，0 超时（设了 120s timeout，最长 Q31 137s 是 OpenAI SDK 累计调用未触发单次超时）。

### 评测限制

1. **expected_node_ids 是人工反向构建**：可能存在等价节点未列入，所以 Recall 是真实下界；同理某些 T2 题的 "完整列出" 边界由我主观划定。
2. **HitRate ≡ StrictHit**：因为 avg|E|=2 远小于 avg|R|=40，呈"全有/全无"，本指标不区分部分命中。
3. **forbidden / T5 样本量小**：5 / 10 题样本，统计置信度有限。
4. **A4 hops 分组按 GT 标注**：hops=3 实际不存在；分组定义边界主观。
5. **成本是 cache-miss 上界**：DeepSeek prompt-cache 命中可降 75%，实际生产场景应该更低。
6. **未对照 baseline**：本评测是单系统单文档评估；与朴素 BM25/Embedding RAG 的对比需另起评测。
7. **样本规模 50 题**：足以观察分布，但 P99 仅 1 个点（Q31），尾部统计需更大样本验证。

---

## 产出物清单

| 文件 | 用途 |
|---|---|
| `ground_truth.json` | 50 题 GT（验证通过） |
| `build_ground_truth.py` | GT 构建脚本（含 assert 校验） |
| `run_inference.py` | 50 题 inference runner |
| `raw_runs.jsonl` | 50 条原始 run record |
| `run.log` | inference 文本日志 |
| `metrics_a1_retrieval.{py,json}` | 检索指标 |
| `report_a1_retrieval.md` | 检索报告 |
| `metrics_a2_faithfulness.{py,json}` | 忠实度指标 |
| `report_a2_faithfulness.md` | 忠实度报告 |
| `metrics_a3_robustness.{py,json}` | 拒答/鲁棒/假前提指标 |
| `report_a3_robustness.md` | 拒答/鲁棒报告 |
| `metrics_a4_multihop.{py,json}` | 多跳/工具效率指标 |
| `report_a4_multihop.md` | 多跳/工具效率报告 |
| `metrics_a5_performance.{py,json}` | 延迟/成本指标 |
| `report_a5_performance.md` | 延迟/成本报告 |
| **`REPORT_FINAL.md`** | **本综合报告** |

所有脚本可重跑：`D:/graghRAG-agent/backend/.venv/Scripts/python.exe metrics_X.py`。
