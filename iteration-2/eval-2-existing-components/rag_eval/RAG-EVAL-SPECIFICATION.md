# rag_eval 规范文档（Layer 1 实测产出）

## M4-P1 生产来源控制合同（2026-10-07）

以下是当前生产 `/api/v1/rag/query`、`/rag/retrieve`、`/rag/summarize` 的来源控制增量规范，优先于历史示例 schema；不是已完成的七变体实验。

`options.enabled_sources` 可省略或为 null（兼容原默认行为）；显式列表只允许 `vector/kg/bm25/table/multi_query`，非空，重复项按上述固定顺序去重。未知值、字符串替代列表和空列表返回 422。`per_source_caps` 仍为 1–50 数量上限，不用 0 或漏填来禁用来源。

所有 normal/global/global-fallback/retrieval-rescue/generator-rescue 入口在调用前遵守请求级列表。Multi-Query 还须开关开启、vector 权限与依赖齐备。community 是 KG 子能力，不能独立加入列表；KG 禁用时不执行 global/community，并回到允许来源的 local。显式列表下 Table 普通召回与 rescue 均要求 metric intent；省略列表保留历史 rescue 条件。未启用 vector/Multi-Query 时，不做用于这些召回的 query embedding；没有 KG 权限时，不做候选的图谱补投影。输入文字带节点 ID 不授予 KG 查询权限。

显式列表不能进入主 pipeline 时返回 503，禁止 legacy fallback；未设置列表仍兼容旧回退。请求级配置与执行记录均不能写入共享 pipeline.config。

响应 metadata 的 `effective_config` 版本为 `1.0`，含 requested_sources（null 或规范列表）、allowed_sources、eligible_sources、flags、budget、query_mode、stages、attempted_sources/executed_sources/skipped_sources 及 cross_encoder。stages 按 normal、global、retrieval_rescue、generator_rescue 分开记录各入口 `status=executed/failed/skipped`、reason 与 candidate_count。零命中是 executed/count=0，不等于 skipped；failed 的计数未知为 null。skipped_sources 只列没有任何已执行/失败入口的来源，详细入口原因以 stages 为准。

cross_encoder 分开 requested、attempted、executed、skip_reason；timeout/unavailable 等回退不算成功重排。预算记录当前实现的 source top-k、pre-rerank cap、最终候选与 context 上限；生成响应另记 prompt_max_context_tokens，区分 retrieval 配置与 prompt 构造实参。Multi-Query 合法空变体记 skipped/query_variants_empty，变体请求或解析失败记 failed。当前 raw 候选总预算未锁，不能因有来源开关就声称七变体公平预算已经通过。

记录为执行合同元数据，不是稳定证据 ID、真正模型可见 context、claim 语义标注或完整成本账本；这些属于 M4-P2/P3。测试夹具仅为软件验证，论文结果必须另行冻结。

## 输入 schema

### ground_truth.json

```json
[
  {
    "qid": "q001",
    "question": "什么是 GraphRAG?",
    "relevant_doc_ids": ["doc_42", "doc_77"],
    "answer": "GraphRAG 是基于知识图谱的检索增强生成方法...",
    "hop_count": 1
  }
]
```

**字段约束**：
- `qid`：唯一字符串，禁止重复
- `relevant_doc_ids`：必须是 backend 知识图谱中真实存在的 doc ID
- `answer`：参考答案，用于 A2 忠实度与 A4 多跳评测
- `hop_count`：1 表示单跳，2+ 触发 A4 多跳评测

## 中间产物 schema

### raw_runs.jsonl（每行一条）

```json
{"qid": "q001", "answer": "...", "retrieved_doc_ids": ["doc_42", "doc_15"], "latency_ms": 1234, "timestamp": "2026-05-29T10:00:00Z"}
```

**字段约束**：
- 必须按行 append，不要重写整个文件
- 失败的推理也要记录，加 `"error": "..."` 字段，该条不参与指标计算

## 输出 schema

### metrics_a1_retrieval.json

```json
{
  "n_questions": 100,
  "recall_at_5": 0.85,
  "ndcg_at_5": 0.78,
  "mrr": 0.72
}
```

### metrics_a2_faithfulness.json

```json
{
  "n_questions": 100,
  "faithfulness_score": 0.83,
  "method": "llm-as-judge"
}
```

### metrics_a3_robustness.json

```json
{
  "n_questions": 100,
  "perturbation_types": ["typo", "synonym", "reorder"],
  "consistency_score": 0.81,
  "per_type_consistency": {"typo": 0.79, "synonym": 0.83, "reorder": 0.82}
}
```

### metrics_a4_multihop.json

```json
{
  "n_questions": 50,
  "exact_match": 0.55,
  "f1_score": 0.68,
  "per_hop_count": {"2": {"em": 0.6, "f1": 0.71}, "3": {"em": 0.45, "f1": 0.62}}
}
```

### metrics_a5_performance.json

```json
{
  "n_questions": 100,
  "latency_p50_ms": 820,
  "latency_p95_ms": 2100,
  "latency_p99_ms": 3400,
  "qps": 1.2
}
```

## 指标定义

| 指标 | 计算公式 | 实现位置 |
|------|---------|---------|
| Recall@k | `\|retrieved ∩ relevant\| / \|relevant\|`，取 top-k | `metrics_a1_retrieval.py` |
| NDCG@k | 标准 NDCG 公式，gain = 1 if relevant else 0 | 同上 |
| MRR | `1 / rank_of_first_relevant`，无相关则 0 | 同上 |
| Faithfulness | LLM 判断答案是否与检索段落事实一致，0-1 分 | `metrics_a2_faithfulness.py` |
| Consistency | 扰动后答案与原答案 embedding 余弦相似度均值 | `metrics_a3_robustness.py` |
| Exact Match | 答案字符串完全相等（去除标点后比较） | `metrics_a4_multihop.py` |
| F1 | token 级 F1（参考 SQuAD 标准实现） | 同上 |
| Latency pXX | 推理延迟分位数（ms） | `metrics_a5_performance.py` |
| QPS | 每秒完成的查询数 | 同上 |

## 失败模式

- backend `/api/query` 超时（30s）→ 记录 `"error": "timeout"`，该题不参与指标
- backend 返回 5xx → 记录 `"error": "5xx"`，该题不参与指标
- ground truth 字段缺失（如无 `qid`）→ 启动时 fail-fast，不继续推理
- `relevant_doc_ids` 中的 doc ID 不存在于图谱 → 警告并跳过该题，不 fail-fast
