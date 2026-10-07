# A5 - 延迟与成本 性能评测报告

> 评测对象：GraphRAG `/api/v1/rag/query`，50 题
> 数据来源：`metrics_a5_performance.json`（原始：`D:\graghRAG-agent\iteration-2\eval-2-existing-components\rag_eval\raw_runs.jsonl`）
> 评测日期：2026-07-04

## 一句话结论

**P95=3274ms、P99=4891ms、平均成本=$0.0003/题**。 当前 tail latency 已落在企业 gate 内，三维共同超阈值的极端题目：无。

## 全局开销快照

| 指标 | 数值 |
|---|--:|
| 总 latency | 83730 ms |
| 总 input tokens | 50808 |
| 总 output tokens | 2755 |
| 总 tokens | 53563 |
| 总 activity/tool calls | 201 |
| 总成本 | $0.0167 |
| 平均每题成本 | $0.0003 |

## 延迟分布（ms）

| 统计 | mean | median | P50 | P75 | P90 | P95 | P99 | max |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| latency_ms | 1674.6 | 1606.5 | 1590 | 2303 | 2951 | 3274 | 4891 | 4891 |

## Token 与调用分布

| 指标 | mean | median | P95 | max |
|---|--:|--:|--:|--:|
| total_tokens | 1071 | 1188 | 2088 | 2183 |
| activity/tool calls | 4.0 | 4.0 | 5 | 5 |

## 成本投影

| 场景 | 日成本 | 月成本 |
|---|--:|--:|
| 1,000 题/天 | $0.33 | $10.05 |

## 相关性与极端值

- Pearson(calls, latency) = 0.331
- Pearson(calls, tokens) = 0.492
- P95 三维共同超阈值题目：无
