# Enterprise GraphRAG Enterprise-Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current GraphRAG MVP into an enterprise-deliverable system with production-aligned retrieval measurement, materially better retrieval quality, stable multi-turn behavior, bounded latency tails, and explicit release gates for pilot-to-production promotion.

**Architecture:** Keep the current `FastAPI + NetworkX + ChromaDB + BM25 + hybrid retrieval + /api/v1/rag/query` primary path, but tighten the system in five areas: layered retrieval observability, retrieval precision/recall tuning, conversation rewrite reliability, latency-tail controls, and enterprise release governance. Deliver the work in vertical slices so every slice is measurable against A1/A2/A5 before the next one begins.

**Tech Stack:** FastAPI, Python 3.12, pytest, NetworkX, ChromaDB, BM25, sentence-transformers, LangGraph, Prometheus, structlog.

---

## File Responsibility Map

- `backend/retrieval.py`
  Retrieval-path accounting, pre/post-rerank evidence, source-budget trimming, and query-mode runtime.
- `backend/generator.py`
  Retrieval metadata pass-through into `/api/v1/rag/query` generation outputs.
- `backend/routes/rag_query.py`
  Main enterprise query endpoint contract, metadata exposure, and release-gate response surface.
- `backend/conversation.py`
  Multi-turn history policy, rewrite persistence, rewrite diagnostics, and fallback behavior.
- `backend/routes/conversation.py`
  Conversation inspection endpoints used to validate multi-turn rewrite correctness.
- `backend/metrics.py`
  Prometheus metrics for retrieval stages, rewrite hit/miss, source budgets, and latency-tail diagnostics.
- `backend/server.py`
  Runtime initialization, observability wiring, and health/reporting integration.
- `backend/tests/test_query_budgeting.py`
  Main endpoint contract tests for retrieval metadata and evaluation compatibility.
- `backend/tests/test_conversation_rewrite.py`
  Multi-turn rewrite correctness and fallback behavior coverage.
- `backend/tests/test_retrieval_stage_metrics.py`
  Tests for layered retrieval metadata and path-hit accounting.
- `backend/tests/test_tail_latency_controls.py`
  Tests for rerank budgets, long-tail protection, and degraded-mode behavior.
- `iteration-2/eval-2-existing-components/rag_eval/run_inference.py`
  Main eval harness targeting `/api/v1/rag/query`.
- `iteration-2/eval-2-existing-components/rag_eval/run_inference_helpers.py`
  Shared eval extraction helpers for retrieved ids, answer ids, and token usage normalization.
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py`
  Retrieval scoring logic; must evolve from single-surface A1 into layered retrieval A1.
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py`
  Generation-faithfulness scoring over production-path raw runs.
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.py`
  Latency/cost/activity reporting for the production GraphRAG path.
- `iteration-2/eval-2-existing-components/rag_eval/report_*.md`
  Regenerated metric reports used in release review.
- `integration/enterprise-evolution-blueprint-v1.0.md`
  Enterprise target architecture reference; update if any release gate or operating model changes materially.
- `plans/enterprise-graphrag-enterprise-delivery-plan.md`
  This plan.

---

## Delivery Standards

- All quality improvements must be measured on the primary `/api/v1/rag/query` path, not legacy `/query`.
- Every retrieval-quality change must preserve or improve A2 faithfulness; no retrieval tuning that raises hallucination risk.
- Long-tail latency controls must degrade gracefully; no new 500-paths for budget exhaustion.
- Multi-turn rewrite must be observable; silent rewrite failure is not acceptable for enterprise release.
- Every task must include TDD red-green evidence and focused tests before full-suite verification.
- The final release gate is not “tests pass”; it is “tests pass + A1/A2/A5 targets are met or explicitly waived with evidence.”

---

### Task 1: Split A1 Into Layered Retrieval Measurements

**Files:**
- Modify: `backend/retrieval.py`
- Modify: `backend/generator.py`
- Modify: `backend/routes/rag_query.py`
- Modify: `backend/tests/test_query_budgeting.py`
- Create: `backend/tests/test_retrieval_stage_metrics.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/run_inference.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/run_inference_helpers.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py`

- [ ] **Step 1: Write the failing endpoint metadata tests**

```python
def test_rag_query_response_exposes_layered_retrieval_ids(monkeypatch):
    response = asyncio.run(
        rag_query_module.rag_query(
            QueryRequest(query="W4S1 是什么？", options=QueryOptions(include_sources=True))
        )
    )

    assert "retrieval_node_ids" in response.metadata
    assert "path_hit_node_ids" in response.metadata
    assert "pre_rerank_node_ids" in response.metadata
    assert "final_context_node_ids" in response.metadata
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_query_budgeting.py tests/test_retrieval_stage_metrics.py -v`

Expected: `FAILED` because layered retrieval keys are not fully exposed yet.

- [ ] **Step 3: Add layered retrieval evidence in `backend/retrieval.py`**

```python
latencies["path_hit_node_ids"] = _path_hit_node_ids(all_paths)
latencies["pre_rerank_node_ids"] = _retrieval_node_ids(rrf_results)
latencies["pre_rerank_chunk_ids"] = [item["chunk_id"] for item in rrf_results if item.get("chunk_id")]

final_chunks = final_chunks[:effective_config.max_total_candidates]
latencies["final_context_node_ids"] = _ordered_unique_node_ids(
    [node_id for chunk in final_chunks for node_id in chunk.entity_ids]
)
latencies["final_context_chunk_ids"] = [chunk.chunk_id for chunk in final_chunks]
```

- [ ] **Step 4: Pass the new retrieval evidence through generator and route metadata**

```python
"metadata": {
    "retrieval_node_ids": retrieval_result.pipeline.get("retrieval_node_ids", []),
    "pre_rerank_node_ids": retrieval_result.pipeline.get("pre_rerank_node_ids", []),
    "final_context_node_ids": retrieval_result.pipeline.get("final_context_node_ids", []),
    "path_hit_node_ids": retrieval_result.pipeline.get("path_hit_node_ids", {}),
}
```

- [ ] **Step 5: Update eval helpers to prefer explicit retrieval-stage ids**

```python
explicit_ids = runtime_metadata.get("pre_rerank_node_ids") or runtime_metadata.get("retrieval_node_ids") or []
if explicit_ids:
    return _ordered_unique([nid for nid in explicit_ids if nid])
```

- [ ] **Step 6: Extend A1 to emit layered metrics instead of a single aggregate**

```python
surfaces = {
    "path_hits": run.get("runtime_metadata", {}).get("path_hit_node_ids_flat", []),
    "pre_rerank": run.get("runtime_metadata", {}).get("pre_rerank_node_ids", []),
    "final_context": run.get("runtime_metadata", {}).get("final_context_node_ids", []),
}
```

- [ ] **Step 7: Run focused verification**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_query_budgeting.py tests/test_retrieval_stage_metrics.py -v`

Expected: `PASS`

- [ ] **Step 8: Commit**

```bash
git add backend/retrieval.py backend/generator.py backend/routes/rag_query.py backend/tests/test_query_budgeting.py backend/tests/test_retrieval_stage_metrics.py iteration-2/eval-2-existing-components/rag_eval/run_inference.py iteration-2/eval-2-existing-components/rag_eval/run_inference_helpers.py iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py
git commit -m "feat: add layered retrieval evidence for production eval"
```

---

### Task 2: Raise Retrieval Precision Without Collapsing Recall

**Files:**
- Modify: `backend/retrieval.py`
- Modify: `backend/domain_dict.py`
- Modify: `backend/prompt_builder.py`
- Create: `backend/tests/test_retrieval_precision_tuning.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py`

- [ ] **Step 1: Write the failing retrieval-precision tests**

```python
def test_pre_rerank_results_respect_source_caps_before_context_assembly():
    result = pipeline.retrieve("W4S1 是什么？", retrieval_config=config)
    assert len(result.pipeline["pre_rerank_chunk_ids"]) <= 8
    assert len(result.pipeline["final_context_chunk_ids"]) <= config.max_total_candidates


def test_exact_entity_match_is_ranked_ahead_of_generic_reference_chunks():
    result = pipeline.retrieve("W4S1 是什么？", retrieval_config=config)
    assert result.pipeline["pre_rerank_node_ids"][0] == "n0035"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_retrieval_precision_tuning.py -v`

Expected: `FAILED` because the current ranking still allows generic reference chunks to dominate.

- [ ] **Step 3: Add source-aware penalties and exact-match boosts in `backend/retrieval.py`**

```python
if exact_keyword_match and source == "kg":
    candidate["score"] += 0.20
if source == "vector" and not candidate.get("entity_ids"):
    candidate["score"] -= 0.05
if source == "reference":
    candidate["score"] -= 0.10
```

- [ ] **Step 4: Add domain-term expansion only when it narrows ambiguity**

```python
if len(domain_terms) <= 3 and any(term in raw_query for term in domain_terms):
    expanded_terms = domain_terms
else:
    expanded_terms = []
```

- [ ] **Step 5: Tighten prompt-builder context ordering to preserve top evidence first**

```python
chunks = sorted(
    retrieval_result.chunks,
    key=lambda chunk: (
        0 if chunk.source == "kg" and chunk.entity_ids else 1,
        -chunk.score,
    ),
)
```

- [ ] **Step 6: Re-run the focused tests**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_retrieval_precision_tuning.py -v`

Expected: `PASS`

- [ ] **Step 7: Commit**

```bash
git add backend/retrieval.py backend/domain_dict.py backend/prompt_builder.py backend/tests/test_retrieval_precision_tuning.py iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py
git commit -m "feat: tune retrieval ranking for enterprise precision"
```

---

### Task 3: Make Multi-Turn Rewrite Enterprise-Reliable

**Files:**
- Modify: `backend/conversation.py`
- Modify: `backend/routes/rag_query.py`
- Modify: `backend/routes/conversation.py`
- Create: `backend/tests/test_conversation_rewrite.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/run_inference.py`

- [ ] **Step 1: Write the failing multi-turn rewrite tests**

```python
def test_followup_question_persists_rewritten_query():
    first = client.post("/api/v1/rag/query", json={"query": "W4S1 是什么？", "session_id": "s1"})
    second = client.post("/api/v1/rag/query", json={"query": "它对应的弃电量是多少？", "session_id": "s1"})

    assert second.json()["metadata"]["rewritten_query"] is not None
    assert "W4S1" in second.json()["metadata"]["rewritten_query"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_conversation_rewrite.py -v`

Expected: `FAILED` because rewrite metadata is still absent or unstable on follow-up turns.

- [ ] **Step 3: Add a deterministic history-selection rule in `backend/conversation.py`**

```python
history = [
    turn for turn in conversation.turns[-3:]
    if turn.user_query and turn.answer_text
]
```

- [ ] **Step 4: Persist rewrite diagnostics in conversation turns**

```python
conv_mgr.append_turn(
    conv_id,
    req.query,
    gen_result["answer"],
    rewritten=rewritten_query if rewritten_query != req.query else None,
    rewrite_reason="coreference_resolution" if rewritten_query != req.query else None,
    sources=conv_sources,
)
```

- [ ] **Step 5: Expose rewrite diagnostics via `/api/v1/conversations`**

```python
{
    "session_id": conv.session_id,
    "turns": [
        {
            "user_query": turn.user_query,
            "rewritten_query": turn.rewritten_query,
            "rewrite_reason": turn.rewrite_reason,
        }
        for turn in conv.turns
    ],
}
```

- [ ] **Step 6: Re-run the focused tests**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_conversation_rewrite.py -v`

Expected: `PASS`

- [ ] **Step 7: Commit**

```bash
git add backend/conversation.py backend/routes/rag_query.py backend/routes/conversation.py backend/tests/test_conversation_rewrite.py iteration-2/eval-2-existing-components/rag_eval/run_inference.py
git commit -m "feat: stabilize enterprise multi-turn query rewriting"
```

---

### Task 4: Eliminate P99 Latency Spikes And Add Safe Degraded Modes

**Files:**
- Modify: `backend/retrieval.py`
- Modify: `backend/generator.py`
- Modify: `backend/routes/rag_query.py`
- Modify: `backend/metrics.py`
- Create: `backend/tests/test_tail_latency_controls.py`

- [ ] **Step 1: Write the failing tail-latency guard tests**

```python
def test_query_degrades_before_cross_encoder_runs_over_budget(monkeypatch):
    result = pipeline.retrieve("复杂问题", retrieval_config=config)
    assert result.pipeline["rerank_budget_triggered"] is True


def test_rag_query_marks_degraded_mode_in_metadata(monkeypatch):
    response = asyncio.run(rag_query_module.rag_query(req))
    assert response.metadata["degraded_mode"] in {"rerank_skipped", "candidate_trimmed", None}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_tail_latency_controls.py -v`

Expected: `FAILED` because the endpoint does not yet expose explicit degraded-mode metadata.

- [ ] **Step 3: Add rerank budget and candidate budget guards**

```python
rerank_budget_ms = effective_config.rerank_budget_ms
if should_rerank and latencies["rrf_ms"] > rerank_budget_ms:
    should_rerank = False
    latencies["rerank_budget_triggered"] = True
```

- [ ] **Step 4: Mark degraded modes explicitly in route metadata**

```python
degraded_mode = None
if meta.get("rerank_budget_triggered"):
    degraded_mode = "rerank_skipped"
elif meta.get("final_chunks", 0) < meta.get("total_candidates", 0):
    degraded_mode = "candidate_trimmed"
```

- [ ] **Step 5: Emit Prometheus counters/histograms**

```python
rag_degraded_mode_total.labels(mode=degraded_mode or "none").inc()
rag_retrieval_stage_duration_seconds.labels(stage="rerank").observe(meta.get("rerank_latency_ms", 0) / 1000)
```

- [ ] **Step 6: Re-run focused tests**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_tail_latency_controls.py -v`

Expected: `PASS`

- [ ] **Step 7: Commit**

```bash
git add backend/retrieval.py backend/generator.py backend/routes/rag_query.py backend/metrics.py backend/tests/test_tail_latency_controls.py
git commit -m "feat: bound enterprise latency tails with degraded modes"
```

---

### Task 5: Define Enterprise Release Gates In Code And Reports

**Files:**
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.py`
- Create: `iteration-2/eval-2-existing-components/rag_eval/release_gate.py`
- Create: `iteration-2/eval-2-existing-components/rag_eval/test_release_gate.py`
- Modify: `integration/enterprise-evolution-blueprint-v1.0.md`

- [ ] **Step 1: Write the failing release-gate tests**

```python
def test_release_gate_fails_when_p95_latency_exceeds_target():
    verdict = evaluate_release_gate(
        a1={"global": {"recall": 0.30}},
        a2={"global": {"keyword_coverage_macro": 0.80}},
        a5={"latency_ms": {"global": {"p95": 6500}}},
    )
    assert verdict["passed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv\Scripts\python -m pytest ..\iteration-2\eval-2-existing-components\rag_eval\test_release_gate.py -v`

Expected: `FAILED` because `release_gate.py` does not exist yet.

- [ ] **Step 3: Implement explicit enterprise targets**

```python
TARGETS = {
    "a1_final_context_recall_min": 0.35,
    "a2_keyword_coverage_min": 0.75,
    "a2_cited_in_retrieved_min": 0.98,
    "a5_p95_latency_ms_max": 6000,
    "a5_p99_latency_ms_max": 15000,
}
```

- [ ] **Step 4: Evaluate the current reports into a pass/fail verdict**

```python
return {
    "passed": all(check["passed"] for check in checks),
    "checks": checks,
    "waivers_required": [check for check in checks if not check["passed"]],
}
```

- [ ] **Step 5: Document the gate in the enterprise blueprint**

```markdown
正式交付前必须满足：
- A1 final-context recall >= 0.35
- A2 keyword coverage >= 0.75
- A2 cited-in-retrieved >= 0.98
- A5 p95 <= 6000ms
- A5 p99 <= 15000ms
```

- [ ] **Step 6: Re-run focused tests**

Run: `cd backend && .venv\Scripts\python -m pytest ..\iteration-2\eval-2-existing-components\rag_eval\test_release_gate.py -v`

Expected: `PASS`

- [ ] **Step 7: Commit**

```bash
git add iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.py iteration-2/eval-2-existing-components/rag_eval/release_gate.py iteration-2/eval-2-existing-components/rag_eval/test_release_gate.py integration/enterprise-evolution-blueprint-v1.0.md
git commit -m "feat: add enterprise release gate evaluation"
```

---

### Task 6: Run Full Enterprise Validation And Produce The Go/No-Go Packet

**Files:**
- Modify: `iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/report_a2_faithfulness.md`
- Create: `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json`
- Create: `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md`

- [ ] **Step 1: Run the production-path eval harness**

Run: `cd backend && .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\run_inference.py`

Expected: `DONE -> raw_runs.jsonl`

- [ ] **Step 2: Recompute A1, A2, and A5**

Run: `cd backend && .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a1_retrieval.py`

Expected: `Wrote metrics_a1_retrieval.json`

Run: `cd backend && .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a2_faithfulness.py`

Expected: `Wrote metrics_a2_faithfulness.json`

Run: `cd backend && .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a5_performance.py`

Expected: `Wrote metrics_a5_performance.json`

- [ ] **Step 3: Run the enterprise release gate**

Run: `cd backend && .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\release_gate.py`

Expected: `Wrote release_gate_report.json` and a markdown summary with `passed=true` or `passed=false`.

- [ ] **Step 4: Run the full backend test suite**

Run: `cd backend && .venv\Scripts\python -m pytest tests -q`

Expected: `all tests passed`

- [ ] **Step 5: Write the go/no-go summary**

```markdown
# Enterprise Release Gate Summary

- Retrieval measurement surface: PASS
- Multi-turn rewrite stability: PASS/FAIL
- Tail latency target: PASS/FAIL
- Final enterprise verdict: GO / NO-GO
- Required waivers: [...]
```

- [ ] **Step 6: Commit**

```bash
git add iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.json iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json iteration-2/eval-2-existing-components/rag_eval/report_a2_faithfulness.md iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md
git commit -m "chore: publish enterprise release validation packet"
```

---

## Self-Review

### Spec Coverage

- 企业级正式交付所缺的检索测量分层：由 Task 1 覆盖。
- 检索噪声高、A1 精确率低：由 Task 2 覆盖。
- 多轮改写不稳定：由 Task 3 覆盖。
- 长尾时延与 degraded mode：由 Task 4 覆盖。
- 缺少明确交付门槛：由 Task 5 覆盖。
- 最终企业交付验证包：由 Task 6 覆盖。

### Placeholder Scan

- 未使用 `TBD` / `TODO` / “后续再做” 之类占位符。
- 每个任务都给了明确文件、测试、命令、预期结果。
- 所有行为变更都先有失败测试步骤。

### Type Consistency

- 统一使用 `retrieval_node_ids / pre_rerank_node_ids / final_context_node_ids / path_hit_node_ids`。
- endpoint 统一使用 `metadata` 作为评测契约承载面。
- release gate 统一消费 `metrics_a1_retrieval.json / metrics_a2_faithfulness.json / metrics_a5_performance.json`。

