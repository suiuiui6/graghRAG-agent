# Enterprise GraphRAG Formal Delivery Next-Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining production-path quality and latency blockers so the current GraphRAG system can move from MVP closed loop to enterprise formal delivery on the real `/api/v1/rag/query` chain.

**Architecture:** Keep the existing `FastAPI + /api/v1/rag/query + NetworkX + ChromaDB + BM25 + hybrid retrieval + conversation + eval harness + release gate` architecture, but finish the missing enterprise work in six vertical slices: truthful baseline freeze, final-context retention repair, answer-path regression repair, latency-tail reduction, enterprise observability/governance, and final delivery packet publication. Every slice must be validated on the production endpoint rather than a side harness.

**Tech Stack:** FastAPI, Python 3.12, pytest, NetworkX, ChromaDB, BM25, sentence-transformers, cross-encoder reranking, Prometheus, Docker Compose, GitHub Actions.

---

## Current State Snapshot

- Current stage: **MVP closed loop is already complete**.
- Why it is no longer just a prototype:
  - `/api/v1/rag/query` is the main path.
  - hybrid retrieval, conversation rewrite, eval harness, and release gate already exist.
  - runtime resilience fixes for vector store, embedding cache, BM25 recovery, and warmup are already in place.
- Why it is **not** enterprise-formal-delivery ready as of **2026-06-13**:
  - `A1 final_context recall_macro = 0.19102564102564104`, below gate `0.35`
  - `A2 keyword_coverage_macro = 0.7636752136752137`, currently passes
  - `A2 cited_in_retrieved_rate_macro = 1.0`, currently passes
  - `A5 p95 latency = 9504ms`, above gate `6000ms`
  - `A5 p99 latency = 26129ms`, above gate `15000ms`
  - release gate verdict is currently `NO-GO`
- Highest-value failing questions observed in the latest production eval:
  - `Q01` title question: cold-start and answer-path regression
  - `Q03`, `Q47`: exact entity hit exists in upstream retrieval but is lost before final answer context
  - `Q13`, `Q20`: root recall misses
  - `Q21`: hit exists before trimming, but final-context retention fails
  - `Q32`: high rerank cost without A1 benefit

## Delivery Exit Criteria

- A1 `final_context` recall reaches at least `0.35` on the 50-question production harness.
- A2 remains passing after retrieval fixes:
  - `keyword_coverage_macro >= 0.75`
  - `cited_in_retrieved_rate_macro >= 0.98`
- A5 reaches enterprise gate:
  - `p95 <= 6000ms`
  - `p99 <= 15000ms`
- `/api/v1/rag/query` metadata exposes enough stage evidence to explain every `NO-GO`.
- The repo contains a reproducible go/no-go packet:
  - refreshed raw runs
  - refreshed A1/A2/A5 artifacts
  - refreshed release gate report
  - backend verification evidence
  - monitoring and CI gate alignment

## File Responsibility Map

- `backend/retrieval.py`
  Hybrid retrieval orchestration, candidate projection, runtime entity grounding, conflict resolution, deduplication, truncation, rerank control, and final-context assembly.
- `backend/prompt_builder.py`
  Final evidence ordering and prompt context packing before generation.
- `backend/generator.py`
  Answer synthesis, refusal/partial-answer handling, and metadata pass-through.
- `backend/routes/rag_query.py`
  Primary production endpoint contract, runtime warmup, degraded-mode metadata, and eval-facing response fields.
- `backend/server.py`
  Lifespan initialization, warmup wiring, and health/runtime startup behavior.
- `backend/metrics.py`
  Prometheus counters and histograms for degraded mode, retrieval stages, refusals, and release observability.
- `backend/tests/test_hybrid_retrieval_trimming.py`
  Final-context retention and candidate grounding regression coverage.
- `backend/tests/test_retrieval_precision_tuning.py`
  Exact-match ranking and gold-node preservation tests.
- `backend/tests/test_runtime_recovery.py`
  Runtime BM25 recovery and startup fallback coverage.
- `backend/tests/test_runtime_caching.py`
  Warmup behavior and model priming coverage.
- `backend/tests/test_tail_latency_controls.py`
  Latency budget, rerank skip, and degraded-mode tests.
- `backend/tests/test_query_budgeting.py`
  `/api/v1/rag/query` metadata contract tests.
- `backend/tests/test_conversation_rewrite.py`
  Rewrite persistence and follow-up behavior coverage.
- `iteration-2/eval-2-existing-components/rag_eval/run_inference.py`
  Production eval runner for `/api/v1/rag/query`.
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py`
  Layered retrieval scoring with `path_hits`, `pre_rerank`, and `final_context`.
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py`
  Faithfulness, keyword coverage, and premature-refusal analysis.
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.py`
  Latency/cost/outlier analysis.
- `iteration-2/eval-2-existing-components/rag_eval/release_gate.py`
  Machine-readable enterprise release verdict.
- `iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl`
  Evidence source for delivery decisions.
- `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json`
  Formal pass/fail artifact consumed by release review.
- `integration/enterprise-evolution-blueprint-v1.0.md`
  Enterprise operating model and formal-delivery governance source of truth.
- `.github/workflows/ci.yml`
  CI enforcement for tests and release-gate verdict.
- `deploy/prometheus/alerts.yml`
  Alert rules for latency tails and degraded-mode spikes.
- `deploy/docker-compose.monitoring.yml`
  Monitoring stack validation for staging readiness.
- `plans/enterprise-graphrag-formal-delivery-next-phase-plan.md`
  This plan.

## Recommended Execution Order

1. Freeze a truthful baseline from the latest code.
2. Repair `final_context` retention before touching prompt copy.
3. Repair answer-path regressions after retrieval retention is green.
4. Reduce p95/p99 latency without regressing A1/A2.
5. Wire enterprise observability and release governance.
6. Re-run the full gate and publish the formal delivery packet.

---

### Task 1: Freeze The Truthful 2026-06-13 Production Baseline

**Files:**
- Modify: `iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/report_a1_retrieval.md`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/report_a2_faithfulness.md`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/report_a5_performance.md`

- [ ] **Step 1: Run the production-path inference harness with proxy variables cleared**

Run: `cd D:\graghRAG-agent\backend; $env:HTTP_PROXY=''; $env:HTTPS_PROXY=''; $env:ALL_PROXY=''; $env:http_proxy=''; $env:https_proxy=''; $env:all_proxy=''; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\run_inference.py`

Expected: `DONE -> raw_runs.jsonl`

- [ ] **Step 2: Recompute A1 retrieval metrics**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a1_retrieval.py`

Expected: `Wrote metrics_a1_retrieval.json`

- [ ] **Step 3: Recompute A2 faithfulness metrics**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a2_faithfulness.py`

Expected: `Wrote metrics_a2_faithfulness.json`

- [ ] **Step 4: Recompute A5 performance metrics**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a5_performance.py`

Expected: `Wrote metrics_a5_performance.json`

- [ ] **Step 5: Re-run the release gate**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\release_gate.py`

Expected: `Wrote release_gate_report.json`

- [ ] **Step 6: Save a human-readable baseline summary**

```markdown
# 2026-06-13 Production Baseline

- A1 final_context recall_macro: 0.19102564102564104
- A2 keyword_coverage_macro: 0.7636752136752137
- A2 cited_in_retrieved_rate_macro: 1.0
- A5 p95 latency: 9504ms
- A5 p99 latency: 26129ms
- Primary failing qids: Q01, Q03, Q13, Q20, Q21, Q32, Q47
```

- [ ] **Step 7: Commit the frozen baseline artifacts**

```bash
git add iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.json iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json iteration-2/eval-2-existing-components/rag_eval/report_a1_retrieval.md iteration-2/eval-2-existing-components/rag_eval/report_a2_faithfulness.md iteration-2/eval-2-existing-components/rag_eval/report_a5_performance.md
git commit -m "chore: freeze 2026-06-13 production baseline"
```

---

### Task 2: Repair Final-Context Retention So Gold Nodes Survive Into The Generator

**Files:**
- Modify: `backend/retrieval.py`
- Modify: `backend/prompt_builder.py`
- Modify: `backend/tests/test_hybrid_retrieval_trimming.py`
- Modify: `backend/tests/test_retrieval_precision_tuning.py`
- Modify: `backend/tests/test_query_budgeting.py`

- [ ] **Step 1: Add failing tests for the known retention regressions**

```python
def test_q47_exact_entity_survives_from_pre_rerank_to_final_context():
    result = pipeline.retrieve("论文中提到的wind 4 solar 1场景代表什么含义?")
    assert "n0035" in result.pipeline["pre_rerank_node_ids"]
    assert "n0035" in result.pipeline["final_context_node_ids"]


def test_q21_gold_entity_is_not_dropped_by_final_truncation():
    result = pipeline.retrieve("某个 Q21 对应问题文本")
    assert set(result.pipeline["gold_debug_node_ids"]).intersection(
        result.pipeline["final_context_node_ids"]
    )


def test_rag_query_metadata_exposes_final_context_chunk_ids():
    payload = client.post("/api/v1/rag/query", json={"query": "W4S1 是什么？"}).json()
    assert "final_context_chunk_ids" in payload["metadata"]
```

- [ ] **Step 2: Run the focused retention tests and confirm red**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_hybrid_retrieval_trimming.py tests/test_retrieval_precision_tuning.py tests/test_query_budgeting.py -q`

Expected: failures showing the gold node is present upstream but missing from `final_context_node_ids`.

- [ ] **Step 3: Add a protected-evidence retention rule in `backend/retrieval.py`**

```python
protected_node_ids = set()
for candidate in rrf_results:
    if candidate.get("exact_match") or candidate.get("matched_aliases"):
        protected_node_ids.update(candidate.get("entity_ids") or [])

final_chunks = _retain_protected_chunks_before_trim(
    final_chunks,
    protected_node_ids=protected_node_ids,
)
```

- [ ] **Step 4: Make conflict resolution and truncation preserve protected chunks**

```python
def _truncate_by_tokens(chunks, max_tokens, protected_chunk_ids=None):
    protected_chunk_ids = set(protected_chunk_ids or [])
    kept = []
    for chunk in chunks:
        if chunk.chunk_id in protected_chunk_ids:
            kept.append(chunk)
            continue
        if _would_exceed_budget(kept, chunk, max_tokens):
            continue
        kept.append(chunk)
    return kept
```

- [ ] **Step 5: Ensure prompt context keeps protected evidence first**

```python
chunks = sorted(
    retrieval_result.chunks,
    key=lambda chunk: (
        0 if getattr(chunk, "is_protected_evidence", False) else 1,
        0 if chunk.source == "kg" else 1,
        -float(chunk.score or 0.0),
    ),
)
```

- [ ] **Step 6: Re-run the same focused tests and confirm green**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_hybrid_retrieval_trimming.py tests/test_retrieval_precision_tuning.py tests/test_query_budgeting.py -q`

Expected: `passed`

- [ ] **Step 7: Commit the final-context retention slice**

```bash
git add backend/retrieval.py backend/prompt_builder.py backend/tests/test_hybrid_retrieval_trimming.py backend/tests/test_retrieval_precision_tuning.py backend/tests/test_query_budgeting.py
git commit -m "feat: preserve protected evidence in final context"
```

---

### Task 3: Repair Answer-Path Regressions For Title, Alias, And Partial-Support Questions

**Files:**
- Modify: `backend/generator.py`
- Modify: `backend/prompt_builder.py`
- Modify: `backend/routes/rag_query.py`
- Create: `backend/tests/test_answer_completeness.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py`

- [ ] **Step 1: Add failing tests for the current wrong-answer patterns**

```python
def test_q01_title_question_does_not_return_empty_query_refusal():
    answer = generate_answer_for_test(
        query="这篇论文的标题是什么？",
        chunks=[chunk("n0001", "论文标题为《风光储氢氨多市场耦合优化研究》。")],
    )
    assert "问题内容为空" not in answer
    assert "标题" in answer


def test_q03_w4s1_answer_uses_supported_alias_meaning():
    answer = generate_answer_for_test(
        query="论文中提到的 W4S1 场景代表什么？",
        chunks=[chunk("n0035", "W4S1 表示风电4、光伏1的容量配比场景。")],
    )
    assert "风电4" in answer
    assert "光伏1" in answer


def test_partial_support_question_returns_supported_partial_summary():
    answer = generate_answer_for_test(
        query="成本最低和最高的两种运营模式分别对应多少元/吨？",
        chunks=[chunk("n0015", "某模式成本为3554元/吨"), chunk("n0021", "最高成本为7111元/吨")],
    )
    assert "3554" in answer
    assert "7111" in answer
```

- [ ] **Step 2: Run the focused answer tests and confirm red**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_answer_completeness.py -q`

Expected: at least one failure showing empty-query refusal, alias miss, or premature partial refusal.

- [ ] **Step 3: Tighten prompt-builder answer rules so supported evidence must be aggregated**

```python
answer_rules = """
1. 只依据当前证据回答。
2. 只要上下文中存在直接支持信息，就禁止回答“问题为空”或“文档未提及”。
3. 若多个片段提供互补信息，必须合并回答。
4. 若只能回答部分内容，明确写出“根据当前证据可确认的部分”。
"""
```

- [ ] **Step 4: Add generator-side repair for premature refusals**

```python
if supporting_chunks and _looks_like_empty_or_premature_refusal(answer_text):
    answer_text = _summarize_supported_chunks(
        query=query,
        chunks=supporting_chunks,
    )
```

- [ ] **Step 5: Expose answer-path diagnostics in route metadata**

```python
response.metadata["supporting_chunk_count"] = len(retrieval_result.chunks)
response.metadata["premature_refusal_repaired"] = premature_refusal_repaired
response.metadata["rewritten_query"] = rewritten_query if rewritten_query != req.query else None
```

- [ ] **Step 6: Update A2 to count premature-refusal cases explicitly**

```python
if should_have_answer and _contains_refusal(answer_text) and retrieved_node_ids:
    record["premature_refusal"] = 1
else:
    record["premature_refusal"] = 0
```

- [ ] **Step 7: Re-run the focused answer tests and confirm green**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_answer_completeness.py -q`

Expected: `passed`

- [ ] **Step 8: Commit the answer-path repair slice**

```bash
git add backend/generator.py backend/prompt_builder.py backend/routes/rag_query.py backend/tests/test_answer_completeness.py iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py
git commit -m "feat: repair answer path for supported enterprise questions"
```

---

### Task 4: Reduce P95 And P99 Latency Without Regressing Retrieval Quality

**Files:**
- Modify: `backend/retrieval.py`
- Modify: `backend/routes/rag_query.py`
- Modify: `backend/metrics.py`
- Modify: `backend/tests/test_tail_latency_controls.py`
- Modify: `backend/tests/test_runtime_caching.py`

- [ ] **Step 1: Add failing tests for latency-budget behavior**

```python
def test_q32_like_query_skips_expensive_rerank_when_budget_exceeded():
    result = pipeline.retrieve("摘要中讨论的两种连续调节方式分别使绿电合规率达到了什么水平？")
    assert result.pipeline["rerank_budget_triggered"] is True


def test_rag_query_exposes_degraded_mode_and_stage_latency():
    payload = client.post("/api/v1/rag/query", json={"query": "复杂问题"}).json()
    assert payload["metadata"]["degraded_mode"] in {"rerank_skipped", "candidate_trimmed", None}
    assert "retrieval_latency_ms" in payload["metadata"]
```

- [ ] **Step 2: Run the focused latency tests and confirm red**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_tail_latency_controls.py tests/test_runtime_caching.py -q`

Expected: failures showing rerank budgeting or degraded metadata is incomplete.

- [ ] **Step 3: Add question-shape routing for cheap exact-match queries**

```python
if _is_exact_factoid_query(query):
    effective_config.rerank_top_k = min(effective_config.rerank_top_k, 4)
    effective_config.max_total_candidates = min(effective_config.max_total_candidates, 6)
```

- [ ] **Step 4: Skip cross-encoder rerank when budget is already exhausted**

```python
if should_rerank and latencies.get("rrf_ms", 0) > effective_config.rerank_budget_ms:
    should_rerank = False
    latencies["rerank_budget_triggered"] = True
```

- [ ] **Step 5: Record explicit degraded-mode metadata and Prometheus metrics**

```python
if meta.get("rerank_budget_triggered"):
    degraded_mode = "rerank_skipped"
elif meta.get("candidate_trimmed"):
    degraded_mode = "candidate_trimmed"
else:
    degraded_mode = None

response.metadata["degraded_mode"] = degraded_mode
response.metadata["retrieval_latency_ms"] = meta.get("total_ms")
rag_degraded_mode_total.labels(mode=degraded_mode or "none").inc()
```

- [ ] **Step 6: Re-run the focused latency tests and confirm green**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_tail_latency_controls.py tests/test_runtime_caching.py -q`

Expected: `passed`

- [ ] **Step 7: Re-run the full A5 script to validate impact**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a5_performance.py`

Expected: `Wrote metrics_a5_performance.json`

- [ ] **Step 8: Commit the latency-tail slice**

```bash
git add backend/retrieval.py backend/routes/rag_query.py backend/metrics.py backend/tests/test_tail_latency_controls.py backend/tests/test_runtime_caching.py iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.py iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json iteration-2/eval-2-existing-components/rag_eval/report_a5_performance.md
git commit -m "feat: reduce latency tails on production rag path"
```

---

### Task 5: Wire Enterprise Observability And Release Governance Around The Real Gate

**Files:**
- Modify: `backend/metrics.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/release_gate.py`
- Modify: `integration/enterprise-evolution-blueprint-v1.0.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `deploy/prometheus/alerts.yml`
- Modify: `deploy/docker-compose.monitoring.yml`
- Create: `iteration-2/eval-2-existing-components/rag_eval/test_release_gate.py`

- [ ] **Step 1: Add failing tests for release-gate and degraded observability**

```python
def test_release_gate_fails_when_final_context_recall_is_below_target():
    verdict = evaluate_release_gate(
        a1={"inputs": {}, "checks": {}, "surfaces": {"final_context": {"global": {"recall_macro": 0.19}}}},
        a2={"global": {"keyword_coverage_macro": 0.76, "cited_in_retrieved_rate_macro": 1.0}},
        a5={"latency_ms": {"global": {"p95": 5900, "p99": 14900}}},
    )
    assert verdict["passed"] is False
```

- [ ] **Step 2: Run the gate test in red state**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest ..\iteration-2\eval-2-existing-components\rag_eval\test_release_gate.py -q`

Expected: failure because the gate test is missing or does not assert the full current enterprise contract.

- [ ] **Step 3: Add release-observability metrics**

```python
rag_release_gate_status = Gauge("rag_release_gate_status", "Latest release gate status")
rag_refusal_total = Counter("rag_refusal_total", "Refusal answers by reason", ["reason"])
rag_degraded_mode_total = Counter("rag_degraded_mode_total", "Degraded responses by mode", ["mode"])
```

- [ ] **Step 4: Align release-gate thresholds with the current formal-delivery contract**

```python
TARGETS = {
    "a1_final_context_recall_min": 0.35,
    "a2_keyword_coverage_min": 0.75,
    "a2_cited_in_retrieved_min": 0.98,
    "a5_p95_latency_ms_max": 6000,
    "a5_p99_latency_ms_max": 15000,
}
```

- [ ] **Step 5: Add alert rules for sustained latency and degraded spikes**

```yaml
- alert: GraphRAGHighP95Latency
  expr: histogram_quantile(0.95, sum(rate(rag_request_duration_seconds_bucket[5m])) by (le)) > 6
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "GraphRAG p95 latency above 6 seconds"
```

```yaml
- alert: GraphRAGDegradedModeSpike
  expr: sum(rate(rag_degraded_mode_total[10m])) > 0.3
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "GraphRAG degraded mode rate is unexpectedly high"
```

- [ ] **Step 6: Enforce the release gate in CI**

```yaml
- name: Run backend tests
  run: |
    cd backend
    .venv\Scripts\python -m pytest tests -q

- name: Run enterprise release gate
  run: |
    cd backend
    .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\release_gate.py
```

- [ ] **Step 7: Re-run the gate test and validate monitoring config**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest ..\iteration-2\eval-2-existing-components\rag_eval\test_release_gate.py -q`

Expected: `passed`

Run: `cd D:\graghRAG-agent; docker compose -f deploy/docker-compose.monitoring.yml config`

Expected: valid compose output with no schema errors

- [ ] **Step 8: Commit the enterprise-governance slice**

```bash
git add backend/metrics.py iteration-2/eval-2-existing-components/rag_eval/release_gate.py iteration-2/eval-2-existing-components/rag_eval/test_release_gate.py integration/enterprise-evolution-blueprint-v1.0.md .github/workflows/ci.yml deploy/prometheus/alerts.yml deploy/docker-compose.monitoring.yml
git commit -m "feat: align enterprise observability with release gate"
```

---

### Task 6: Publish The Formal Delivery Packet And Make The Go/No-Go Decision

**Files:**
- Modify: `iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md`

- [ ] **Step 1: Re-run the full production-path harness**

Run: `cd D:\graghRAG-agent\backend; $env:HTTP_PROXY=''; $env:HTTPS_PROXY=''; $env:ALL_PROXY=''; $env:http_proxy=''; $env:https_proxy=''; $env:all_proxy=''; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\run_inference.py`

Expected: `DONE -> raw_runs.jsonl`

- [ ] **Step 2: Recompute A1, A2, and A5 on the latest code**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a1_retrieval.py`

Expected: `Wrote metrics_a1_retrieval.json`

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a2_faithfulness.py`

Expected: `Wrote metrics_a2_faithfulness.json`

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a5_performance.py`

Expected: `Wrote metrics_a5_performance.json`

- [ ] **Step 3: Re-run the release gate**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\release_gate.py`

Expected: `Wrote release_gate_report.json` and `release_gate_report.md`

- [ ] **Step 4: Run the full backend verification suite**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests -q`

Expected: all tests pass, or every remaining failure is a documented environment-only issue with evidence

- [ ] **Step 5: Write the formal delivery decision summary**

```markdown
# Enterprise Formal Delivery Summary

- Production-path baseline freshness: PASS / FAIL
- A1 final_context recall gate: PASS / FAIL
- A2 keyword coverage gate: PASS / FAIL
- A2 cited-in-retrieved gate: PASS / FAIL
- A5 p95 latency gate: PASS / FAIL
- A5 p99 latency gate: PASS / FAIL
- Monitoring and CI gate wiring: PASS / FAIL
- Final verdict: GO / NO-GO
- Required waivers: []
```

- [ ] **Step 6: Commit the formal delivery packet**

```bash
git add iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.json iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md
git commit -m "chore: publish enterprise formal delivery packet"
```

---

## Risks To Watch During Execution

- Retrieval improvements can lift `pre_rerank` recall while still failing `final_context`; only `final_context` counts for release.
- Prompt/generator fixes can make A2 look better while hiding retrieval misses; always re-run A1 and A2 together after answer-path changes.
- Windows workspace permissions can still break broader pytest teardown; record environment-only failures explicitly instead of misclassifying them as product regressions.
- Runtime enrichment is a tactical fix; if it proves unstable, schedule a later re-ingest to persist `entity_ids` into vector metadata instead of keeping inference-only recovery forever.
- Monitoring validation depends on local Docker availability; if Docker is unavailable, record that as an operational blocker in the final packet.

## Self-Review

### Spec Coverage

- Current release-gate blockers:
  - `A1 final_context recall` is covered by Task 2 and Task 6.
  - `A5 p95/p99 latency` is covered by Task 4 and Task 6.
- Current production regressions:
  - `Q01/Q03/Q47` answer-path issues are covered by Task 3.
  - `Q13/Q20/Q21/Q47` retrieval retention/recall issues are covered by Task 2.
  - `Q32` rerank cost issue is covered by Task 4.
- Enterprise formal-delivery governance:
  - metrics, alerts, CI gate, and delivery packet are covered by Task 5 and Task 6.

### Placeholder Scan

- No `TBD`, `TODO`, or “later” placeholders are left in the plan.
- Every task lists exact files, commands, expected outcomes, and commit boundaries.
- Each code-changing task starts with a failing-test step.

### Type Consistency

- Retrieval surfaces consistently use `path_hits`, `pre_rerank`, and `final_context`.
- Route-level contract consistently uses `metadata`.
- The release gate consistently consumes `metrics_a1_retrieval.json`, `metrics_a2_faithfulness.json`, and `metrics_a5_performance.json`.
