# A1 - Layered Retrieval Evaluation Report

Production path: `POST /api/v1/rag/query`

This report scores retrieval at three distinct surfaces:
- `path_hits`: all node ids hit by recall paths before fusion and rerank
- `pre_rerank`: fused ordered candidates before final context trimming
- `final_context`: node ids that actually entered the generation context

## Surface: path_hits

- Questions: 50 total, 39 with expected ids
- Surface data coverage: 50 / 50
- Recall@K: 0.4598
- Precision@K: 0.0783
- F1: 0.1241
- HitRate: 0.5128
- StrictHit: 0.4103
- MRR: 0.4267
- Avg |R|: 9.78

| Category | Questions | Eligible | Precision | Recall | F1 | HitRate | StrictHit | MRR | Avg |R| |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| T1 | 12 | 12 | 0.0521 | 0.5000 | 0.0936 | 0.5000 | 0.5000 | 0.4286 | 10.67 |
| T2 | 8 | 8 | 0.1396 | 0.2833 | 0.1814 | 0.5000 | 0.1250 | 0.3958 | 9.62 |
| T3 | 8 | 8 | 0.0729 | 0.6250 | 0.1291 | 0.6250 | 0.6250 | 0.5208 | 8.75 |
| T4 | 4 | 4 | 0.0500 | 0.1667 | 0.0769 | 0.2500 | 0.0000 | 0.2500 | 8.75 |
| T5 | 10 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | 10.40 |
| T6 | 5 | 5 | 0.0722 | 0.6000 | 0.1279 | 0.6000 | 0.6000 | 0.4333 | 10.20 |
| T7 | 3 | 2 | 0.0833 | 0.5000 | 0.1429 | 0.5000 | 0.5000 | 0.5000 | 8.00 |

## Surface: pre_rerank

- Questions: 50 total, 39 with expected ids
- Surface data coverage: 50 / 50
- Recall@K: 0.7521
- Precision@K: 0.0435
- F1: 0.0804
- HitRate: 0.8462
- StrictHit: 0.6410
- MRR: 0.3923
- Avg |R|: 29.92

| Category | Questions | Eligible | Precision | Recall | F1 | HitRate | StrictHit | MRR | Avg |R| |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| T1 | 12 | 12 | 0.0359 | 0.9167 | 0.0689 | 0.9167 | 0.9167 | 0.3992 | 28.67 |
| T2 | 8 | 8 | 0.0621 | 0.5521 | 0.1104 | 0.8750 | 0.2500 | 0.3310 | 33.12 |
| T3 | 8 | 8 | 0.0299 | 0.8125 | 0.0576 | 0.8750 | 0.7500 | 0.5437 | 29.25 |
| T4 | 4 | 4 | 0.0774 | 0.6042 | 0.1368 | 0.7500 | 0.2500 | 0.3021 | 27.75 |
| T5 | 10 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | 32.00 |
| T6 | 5 | 5 | 0.0356 | 0.8000 | 0.0677 | 0.8000 | 0.8000 | 0.2605 | 28.40 |
| T7 | 3 | 2 | 0.0208 | 0.5000 | 0.0400 | 0.5000 | 0.5000 | 0.5000 | 26.67 |

## Surface: final_context

- Questions: 50 total, 39 with expected ids
- Surface data coverage: 50 / 50
- Recall@K: 0.7393
- Precision@K: 0.0493
- F1: 0.0905
- HitRate: 0.8462
- StrictHit: 0.6154
- MRR: 0.4027
- Avg |R|: 25.24

| Category | Questions | Eligible | Precision | Recall | F1 | HitRate | StrictHit | MRR | Avg |R| |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| T1 | 12 | 12 | 0.0423 | 0.9167 | 0.0806 | 0.9167 | 0.9167 | 0.4261 | 24.67 |
| T2 | 8 | 8 | 0.0664 | 0.4896 | 0.1160 | 0.8750 | 0.1250 | 0.3310 | 28.50 |
| T3 | 8 | 8 | 0.0384 | 0.8125 | 0.0730 | 0.8750 | 0.7500 | 0.5542 | 23.12 |
| T4 | 4 | 4 | 0.0788 | 0.6042 | 0.1389 | 0.7500 | 0.2500 | 0.3021 | 27.00 |
| T5 | 10 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | 25.70 |
| T6 | 5 | 5 | 0.0419 | 0.8000 | 0.0792 | 0.8000 | 0.8000 | 0.2605 | 24.60 |
| T7 | 3 | 2 | 0.0263 | 0.5000 | 0.0500 | 0.5000 | 0.5000 | 0.5000 | 21.67 |

## Interpretation

- `path_hits` shows raw recall breadth before ranking pressure.
- `pre_rerank` shows whether fusion and source budgeting preserve relevant ids near the top.
- `final_context` is the enterprise-critical surface because it is the evidence actually exposed to generation.

---

# Plan C — Keyword-Level Precision (Text Relevance)

This section evaluates retrieval precision using **keyword overlap** instead of exact node-id match.
A retrieved node is counted as relevant if its KG label or properties contain any `expected_keyword` from ground truth.

| Surface | Questions | With Keywords | Keyword Precision |
|---|---:|---:|---:|
| path_hits | 50 | 39 | 0.0507
| pre_rerank | 50 | 39 | 0.0670
| final_context | 50 | 39 | 0.0667

## Keyword Precision by Category — path_hits

Global keyword_precision: 0.0507

| Category | Questions | Keyword Precision |
|---|---:|---:|
| T1 | 12 | 0.0972 |
| T2 | 8 | 0.0804 |
| T3 | 8 | 0.0000 |
| T4 | 4 | 0.0417 |
| T6 | 5 | 0.0000 |
| T7 | 2 | 0.0000 |

## Keyword Precision by Category — pre_rerank

Global keyword_precision: 0.0670

| Category | Questions | Keyword Precision |
|---|---:|---:|
| T1 | 12 | 0.1056 |
| T2 | 8 | 0.0582 |
| T3 | 8 | 0.0180 |
| T4 | 4 | 0.1082 |
| T6 | 5 | 0.0356 |
| T7 | 2 | 0.0625 |

## Keyword Precision by Category — final_context

Global keyword_precision: 0.0667

| Category | Questions | Keyword Precision |
|---|---:|---:|
| T1 | 12 | 0.1145 |
| T2 | 8 | 0.0560 |
| T3 | 8 | 0.0125 |
| T4 | 4 | 0.1118 |
| T6 | 5 | 0.0357 |
| T7 | 2 | 0.0263 |
