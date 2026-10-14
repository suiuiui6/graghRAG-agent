# rag_eval 规范文档（Layer 1 实测产出）

## 2026-10-13 当前软件验收口径（覆盖旧设计冲突）

本目录当前指标脚本使用`expected_node_ids`、`retrieved_node_ids`和`answer_node_ids`等节点身份；旧设计的`relevant_doc_ids`不能当作已实现输入。A1为精确节点集合召回/排名指标；A2按KG节点有效性、引用是否属于已检索集合、关键词及拒答规则计算；A3拒答/误导前提为硬编码关键词规则，噪声对照使用显式题目映射；A4验证节点覆盖/路径相关代理。当前实现不调用LLM judge，也不计算embedding语义一致性；这些规则结果不能冒称语义忠实度、完整多跳推理或人工质量裁决。原设计中的LLM judge/embedding consistency属于待建设方案。

本轮74项离线软件测试使用临时合成JSON/CSV、确定性数学输入及HTTP边界替代，覆盖全部12个第一方生产文件（含CLI/build_ground_truth）；独立锁环境安装23项公开依赖。测试覆盖不代表重新运行历史研究、验收真实模型供应商或确认Gold质量；原Gold、历史结果与实验冻结不改。双覆盖/锁扫描证据见`docs/testing/2026-10-13-rag-eval-readiness.md`。本节仅修正文档对当前实现的描述，不回写历史科学结果。

## M4-P2 证据身份、上下文与答案链合同（2026-10-07）

生产接口使用 strict boolean `options.include_evidence_trace=true` 才返回 `metadata.evidence_trace`（默认关闭）；主链不可用返回503，不走 legacy fallback。完整字段/身份/隐私合同见 `integration/backend-api-architecture-v1.0.md` 的4.3.0a。软件验收见 `docs/superpowers/plans/paper-m4-p2-verification.md`。

规范身份 evidence-v1 / ev1_ SHA256 保留文档命名空间，基于投影前全文；跨文档同旧 ID 不合并，无 namespace/span 标记 unknown/null。同位置内容冲突保留，不覆盖；固定来源优先及身份二级键使同分选择稳定。多路命中合并 source_paths/provenance/raw scores；RRF/rerank 合并采用最大观测值并保留所有 score_observations。legacy 引用标签是兼容别名，不用于跨文档比较；canonical 引用只能精确验证，不代表语义支持。

可观测面为 path_hits/rescue_hits/fusion_and_rescue/pre_rerank/post_rerank/retrieval_final，后者只是检索输出。评价 final-context 必须使用 serialized_model_context.visible_evidence 及实际 messages/context 哈希，不能使用响应 sources 或检索末尾 chunks 代替。位置为 Unicode codepoint 半开区间；生成头部、domain hint、省略号不属于源证据；verified original_span 缺失时不计为已验证原文映射。KG 序列化不等于原文，跨 gold 的精确到达性仍须单独核验。

确定性拒答/纠错 context/raw 为 null，记录自己的 decision_evidence；生成失败 fallback 不能冒充 raw_model_answer。model_call_attempted 与 model_output_received 分开，尝试调用的 context 不保证模型实际消费。provider 原答、strip/提示、repair/complete/supplement、api_response_limit 逐阶段保留，final_answer 对齐 API 返回值。model-context support 与 decision-evidence support 必须分别裁决；P2 不自动标注 claim support。

测试数据为 TEST_ONLY，真实本地 Chroma/BM25 与 FastAPI/SQLite 验证不等于 embedding/CE/生成模型完整集成。网络边界替代响应只验证答案链软件逻辑。M4 仍部分通过，M2 新颖性复核状态不改变；七变体冻结、预算一致性、盲评导出和成本账本待 P3，不产生新的论文结果。

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
