# rag_eval 规范文档（Layer 1 实测产出）

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
