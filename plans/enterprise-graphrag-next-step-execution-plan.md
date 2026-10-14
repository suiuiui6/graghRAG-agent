# GraphRAG Next-Step Enterprise Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining production-path evaluation, retrieval-quality, latency-governance, and release-readiness gaps so the current GraphRAG system can move from MVP closed loop to enterprise formal delivery.

**Architecture:** Keep the current `FastAPI + /api/v1/rag/query + hybrid retrieval + conversation + eval harness` primary path and harden it in six vertical slices: layered retrieval evidence, layered A1 scoring, retrieval precision and source budgeting, multi-turn reliability, enterprise release gates, and deployable go/no-go validation. Each slice must land with TDD evidence, focused regression coverage, and measurable A1/A2/A5 outputs on the production endpoint rather than a side-path harness.

**Tech Stack:** FastAPI, Python 3.12, pytest, unittest, NetworkX, ChromaDB, BM25, sentence-transformers, Prometheus, GitHub Actions.

---

## Current Delivery Judgment

- Current state: the system has already completed the **minimum MVP closed loop**.
- Evidence: there is a working primary endpoint at `/api/v1/rag/query`, hybrid retrieval exists, conversation exists, enterprise support modules already exist, and the eval harness already targets the production endpoint.
- Blocking gap: it is **not yet enterprise-formal-delivery ready** because the release decision is still weak in four places:
  1. retrieval-stage evidence is not yet fully surfaced and scored layer-by-layer,
  2. A1 precision/ordering is not yet governed by a production-path contract,
  3. multi-turn rewrite and degraded-mode behavior are not yet enforced by release gates,
  4. the repo lacks an automated `GO / NO-GO` packet that combines tests + A1/A2/A5 + deployment verification.

## Delivery Exit Criteria

- `/api/v1/rag/query` exposes stable retrieval-stage metadata used directly by the eval pipeline.
- A1 outputs `path_hits`, `pre_rerank`, and `final_context` metrics separately, with report text matching the JSON contract.
- Retrieval precision tuning improves final-context precision without degrading A2 faithfulness.
- Multi-turn follow-up queries persist rewrite diagnostics and keep answer citations traceable.
- Release gate script returns machine-readable `passed=true|false`, is enforced in CI, and produces a markdown decision packet.
- Staging deployment can be brought up, smoke-tested, and judged with a single documented command sequence.

## File Responsibility Map

- `backend/retrieval.py`
  Production retrieval pipeline, candidate merge, stage-level evidence, source budgets, degraded-mode signals.
- `backend/generator.py`
  Pass-through of retrieval evidence and generation diagnostics into route-level metadata.
- `backend/routes/rag_query.py`
  Public production endpoint contract for retrieval metadata, rewrite metadata, degraded mode, and response observability.
- `backend/conversation.py`
  Conversation persistence, rewrite tracking, and follow-up query behavior.
- `backend/routes/conversation.py`
  Inspection/export surface for conversation debugging and enterprise auditability.
- `backend/metrics.py`
  Prometheus counters and histograms for retrieval stages, degraded modes, rewrite hits, and release observability.
- `backend/tests/test_query_budgeting.py`
  Endpoint metadata contract tests for `/api/v1/rag/query`.
- `backend/tests/test_retrieval_stage_metrics.py`
  Retrieval helper tests for stage-id extraction and ordered uniqueness.
- `backend/tests/test_hybrid_retrieval_trimming.py`
  Source-budget and trimming behavior for hybrid retrieval.
- `backend/tests/test_conversation_rewrite.py`
  New multi-turn rewrite contract tests for follow-up behavior and diagnostics.
- `backend/tests/test_tail_latency_controls.py`
  New degraded-mode and latency-budget contract tests.
- `iteration-2/eval-2-existing-components/rag_eval/run_inference.py`
  Production-path eval runner; must keep calling `/api/v1/rag/query`.
- `iteration-2/eval-2-existing-components/rag_eval/run_inference_helpers.py`
  Extraction of retrieval ids, citations, answer evidence, and latency metadata.
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py`
  Layered retrieval metrics and report generation.
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py`
  Answer grounding and citation-faithfulness checks against production runs.
- `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.py`
  Latency, cost, and degraded-mode reporting.
- `iteration-2/eval-2-existing-components/rag_eval/report_a1_retrieval.md`
  Human-readable retrieval report for release review.
- `iteration-2/eval-2-existing-components/rag_eval/report_a2_faithfulness.md`
  Human-readable generation-faithfulness report for release review.
- `iteration-2/eval-2-existing-components/rag_eval/report_a5_performance.md`
  Human-readable performance report for release review.
- `iteration-2/eval-2-existing-components/rag_eval/release_gate.py`
  New enterprise delivery gate evaluator.
- `iteration-2/eval-2-existing-components/rag_eval/test_release_gate.py`
  New unit tests for release verdict logic.
- `.github/workflows/ci.yml`
  CI enforcement for backend tests, eval scripts, and release-gate verdict.
- `deploy/docker-compose.monitoring.yml`
  Monitoring bring-up for staging validation.
- `deploy/prometheus/alerts.yml`
  Alert rules for latency and degraded-mode conditions.
- `integration/enterprise-evolution-blueprint-v1.0.md`
  Enterprise delivery target and release governance source of truth.
- `plans/enterprise-graphrag-enterprise-delivery-plan.md`
  Existing plan that remains the broad blueprint.
- `plans/enterprise-graphrag-next-step-execution-plan.md`
  This near-term execution plan for formal delivery readiness.

## Recommended Execution Style

- Execute this plan in order.
- Do not start Task 3 before Task 1 and Task 2 are green, because A1 precision work needs the layered evidence contract.
- Do not start Task 6 before Task 5 is green, because the release packet must consume the gated reports, not ad-hoc screenshots.
- Commit after each task. Keep commits small and reviewable.

---

### Task 1: Finish Layered Retrieval Evidence On The Production Endpoint

**Files:**
- Modify: `backend/retrieval.py`
- Modify: `backend/generator.py`
- Modify: `backend/routes/rag_query.py`
- Modify: `backend/tests/test_query_budgeting.py`
- Modify: `backend/tests/test_retrieval_stage_metrics.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/run_inference_helpers.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/test_run_inference_helpers.py`

- [ ] **Step 1: Add the failing endpoint-contract assertions**

```python
def test_rag_query_response_exposes_layered_retrieval_ids(monkeypatch):
    response = asyncio.run(
        rag_query_module.rag_query(
            QueryRequest(query="W4S1 是什么？", options=QueryOptions(include_sources=True))
        )
    )

    assert response.metadata["path_hit_node_ids"] == {"kg": ["n1"], "vector": ["n2"]}
    assert response.metadata["pre_rerank_node_ids"] == ["n1", "n2", "n3"]
    assert response.metadata["final_context_node_ids"] == ["n1", "n2"]
    assert response.metadata["pre_rerank_chunk_ids"] == ["c1", "c2", "c3"]
    assert response.metadata["final_context_chunk_ids"] == ["c1", "c2"]
```

- [ ] **Step 2: Add the failing helper-preference assertion**

```python
def test_extract_retrieved_node_ids_prefers_pre_rerank_surface_over_broader_retrieval_surface():
    run = {
        "runtime_metadata": {
            "retrieval_node_ids": ["n100", "n101", "n102"],
            "pre_rerank_node_ids": ["n100", "n101"],
        }
    }

    assert extract_retrieved_node_ids(run) == ["n100", "n101"]
```

- [ ] **Step 3: Run focused tests and confirm the red state**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_query_budgeting.py tests/test_retrieval_stage_metrics.py -q`

Expected: one or more failures mentioning missing layered metadata keys.

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m unittest ..\iteration-2\eval-2-existing-components\rag_eval\test_run_inference_helpers.py`

Expected: failure showing `retrieval_node_ids` is still preferred over `pre_rerank_node_ids`.

- [ ] **Step 4: Implement stage-level id capture in `backend/retrieval.py`**

```python
latencies["path_hit_node_ids"] = _path_hit_node_ids(all_paths)
latencies["retrieval_node_ids"] = _retrieval_node_ids(rrf_results)
latencies["retrieval_chunk_ids"] = [item.get("chunk_id") for item in rrf_results if item.get("chunk_id")]
latencies["pre_rerank_node_ids"] = _retrieval_node_ids(rrf_results)
latencies["pre_rerank_chunk_ids"] = [item.get("chunk_id") for item in rrf_results if item.get("chunk_id")]

final_chunks = final_chunks[: effective_config.max_total_candidates]
latencies["final_context_node_ids"] = _ordered_unique_node_ids(
    node_id
    for chunk in final_chunks
    for node_id in getattr(chunk, "entity_ids", []) or []
)
latencies["final_context_chunk_ids"] = [
    chunk.chunk_id for chunk in final_chunks if getattr(chunk, "chunk_id", None)
]
```

- [ ] **Step 5: Pass the new fields through generator and route metadata**

```python
metadata = {
    "path_hit_node_ids": retrieval_result.pipeline.get("path_hit_node_ids", {}),
    "retrieval_node_ids": retrieval_result.pipeline.get("retrieval_node_ids", []),
    "retrieval_chunk_ids": retrieval_result.pipeline.get("retrieval_chunk_ids", []),
    "pre_rerank_node_ids": retrieval_result.pipeline.get("pre_rerank_node_ids", []),
    "pre_rerank_chunk_ids": retrieval_result.pipeline.get("pre_rerank_chunk_ids", []),
    "final_context_node_ids": retrieval_result.pipeline.get("final_context_node_ids", []),
    "final_context_chunk_ids": retrieval_result.pipeline.get("final_context_chunk_ids", []),
}
```

- [ ] **Step 6: Update helper preference order for explicit retrieval ids**

```python
explicit_ids = (
    runtime_metadata.get("pre_rerank_node_ids")
    or runtime_metadata.get("retrieval_node_ids")
    or []
)
if explicit_ids:
    return _ordered_unique([node_id for node_id in explicit_ids if node_id])
```

- [ ] **Step 7: Re-run the same focused tests and confirm green**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_query_budgeting.py tests/test_retrieval_stage_metrics.py -q`

Expected: `passed`.

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m unittest ..\iteration-2\eval-2-existing-components\rag_eval\test_run_inference_helpers.py`

Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add backend/retrieval.py backend/generator.py backend/routes/rag_query.py backend/tests/test_query_budgeting.py backend/tests/test_retrieval_stage_metrics.py iteration-2/eval-2-existing-components/rag_eval/run_inference_helpers.py iteration-2/eval-2-existing-components/rag_eval/test_run_inference_helpers.py
git commit -m "feat: expose layered retrieval evidence on rag query"
```

---

### Task 2: Rewrite A1 As Layered Retrieval Measurement Instead Of A Single Surface

**Files:**
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/run_inference.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/report_a1_retrieval.md`

- [ ] **Step 1: Add the failing layered-A1 test or assertion block**

```python
def test_layered_a1_outputs_three_surfaces():
    result = compute_metrics(
        [{
            "qid": "q1",
            "runtime_metadata": {
                "path_hit_node_ids": {"kg": ["n1"], "vector": ["n2"]},
                "pre_rerank_node_ids": ["n1", "n2"],
                "final_context_node_ids": ["n1"],
            },
            "gold_node_ids": ["n1", "n3"],
        }]
    )

    assert set(result["surfaces"].keys()) == {"path_hits", "pre_rerank", "final_context"}
```

- [ ] **Step 2: Run the A1 script or test in red state**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a1_retrieval.py`

Expected: output still reflects a single retrieval surface or misses one of the three surfaces.

- [ ] **Step 3: Flatten path-hit ids and compute three independent surfaces**

```python
surfaces = {
    "path_hits": _ordered_unique(
        node_id
        for ids in (runtime_metadata.get("path_hit_node_ids") or {}).values()
        for node_id in ids
    ),
    "pre_rerank": runtime_metadata.get("pre_rerank_node_ids", []),
    "final_context": runtime_metadata.get("final_context_node_ids", []),
}
```

- [ ] **Step 4: Emit per-surface recall, precision, and MRR**

```python
surface_scores[name] = {
    "recall_at_k": recall_at_k(surface_ids, gold_ids),
    "precision_at_k": precision_at_k(surface_ids, gold_ids),
    "mrr": mean_reciprocal_rank(surface_ids, gold_ids),
}
```

- [ ] **Step 5: Make the markdown report mirror the JSON schema**

```markdown
## Surface: final_context

- Recall@K: 0.42
- Precision@K: 0.37
- MRR: 0.51
```

- [ ] **Step 6: Regenerate raw runs and A1 outputs**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\run_inference.py`

Expected: `raw_runs.jsonl` updated from `/api/v1/rag/query`.

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a1_retrieval.py`

Expected: `metrics_a1_retrieval.json` and `report_a1_retrieval.md` rewritten with three surfaces.

- [ ] **Step 7: Commit**

```bash
git add iteration-2/eval-2-existing-components/rag_eval/run_inference.py iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.json iteration-2/eval-2-existing-components/rag_eval/report_a1_retrieval.md iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl
git commit -m "feat: score layered retrieval on production rag path"
```

---

### Task 3: Raise Retrieval Precision Without Sacrificing Recall Or Faithfulness

**Files:**
- Modify: `backend/retrieval.py`
- Modify: `backend/prompt_builder.py`
- Modify: `backend/tests/test_hybrid_retrieval_trimming.py`
- Create: `backend/tests/test_retrieval_precision_tuning.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py`

- [ ] **Step 1: Add the failing retrieval-precision tests**

```python
def test_exact_entity_match_stays_ahead_of_generic_reference_chunks():
    result = pipeline.retrieve("W4S1 是什么？", retrieval_config=config)
    assert result.pipeline["final_context_node_ids"][0] == "n0035"


def test_final_context_chunk_count_respects_enterprise_budget():
    result = pipeline.retrieve("W4S1 是什么？", retrieval_config=config)
    assert len(result.pipeline["final_context_chunk_ids"]) <= config.max_total_candidates
```

- [ ] **Step 2: Run the precision-focused tests and confirm red**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_hybrid_retrieval_trimming.py tests/test_retrieval_precision_tuning.py -q`

Expected: failures showing generic chunks or over-wide context still win.

- [ ] **Step 3: Add exact-match boosts and weak-evidence penalties**

```python
if candidate.get("source") == "kg" and candidate.get("exact_match"):
    candidate["score"] += 0.20
if candidate.get("source") == "vector" and not candidate.get("entity_ids"):
    candidate["score"] -= 0.05
if candidate.get("source") == "reference":
    candidate["score"] -= 0.10
```

- [ ] **Step 4: Enforce source budgets before final context assembly**

```python
rrf_results = _trim_by_source_budget(
    rrf_results,
    {
        "kg": effective_config.max_kg_candidates,
        "vector": effective_config.max_vector_candidates,
        "bm25": effective_config.max_bm25_candidates,
    },
)
```

- [ ] **Step 5: Preserve top evidence ordering in prompt context**

```python
ordered_chunks = sorted(
    retrieval_result.chunks,
    key=lambda chunk: (
        0 if chunk.source == "kg" and chunk.entity_ids else 1,
        -float(chunk.score or 0.0),
    ),
)
```

- [ ] **Step 6: Re-run retrieval tests and then regenerate A2**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_hybrid_retrieval_trimming.py tests/test_retrieval_precision_tuning.py -q`

Expected: `passed`.

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a2_faithfulness.py`

Expected: updated faithfulness report with no regression beyond the allowed threshold.

- [ ] **Step 7: Commit**

```bash
git add backend/retrieval.py backend/prompt_builder.py backend/tests/test_hybrid_retrieval_trimming.py backend/tests/test_retrieval_precision_tuning.py iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json iteration-2/eval-2-existing-components/rag_eval/report_a2_faithfulness.md
git commit -m "feat: tune retrieval precision for enterprise context quality"
```

---

### Task 4: Make Multi-Turn Query Rewriting Observable And Release-Safe

**Files:**
- Modify: `backend/conversation.py`
- Modify: `backend/routes/rag_query.py`
- Modify: `backend/routes/conversation.py`
- Create: `backend/tests/test_conversation_rewrite.py`

- [ ] **Step 1: Add the failing follow-up rewrite contract test**

```python
def test_followup_question_persists_rewritten_query_and_reason():
    first = client.post("/api/v1/rag/query", json={"query": "W4S1 是什么？", "session_id": "s1"})
    second = client.post("/api/v1/rag/query", json={"query": "它的弃电量是多少？", "session_id": "s1"})

    payload = second.json()
    assert payload["metadata"]["rewritten_query"] is not None
    assert "W4S1" in payload["metadata"]["rewritten_query"]
    assert payload["metadata"]["rewrite_reason"] == "coreference_resolution"
```

- [ ] **Step 2: Add the failing conversation-inspection test**

```python
def test_conversation_detail_exposes_rewrite_diagnostics():
    detail = client.get("/api/v1/conversations/s1").json()
    assert "rewritten_query" in detail["turns"][1]
    assert "rewrite_reason" in detail["turns"][1]
```

- [ ] **Step 3: Run the rewrite tests in red state**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_conversation_rewrite.py -q`

Expected: failures showing missing metadata or missing persisted diagnostics.

- [ ] **Step 4: Persist deterministic rewrite metadata in `backend/conversation.py`**

```python
turn = ConversationTurn(
    user_query=req.query,
    rewritten_query=rewritten_query if rewritten_query != req.query else None,
    rewrite_reason="coreference_resolution" if rewritten_query != req.query else None,
    answer_text=gen_result["answer"],
    sources=conv_sources,
)
```

- [ ] **Step 5: Expose rewrite diagnostics on both query and conversation routes**

```python
response.metadata["rewritten_query"] = rewritten_query if rewritten_query != req.query else None
response.metadata["rewrite_reason"] = (
    "coreference_resolution" if rewritten_query != req.query else None
)
```

- [ ] **Step 6: Re-run the rewrite tests and confirm green**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_conversation_rewrite.py -q`

Expected: `passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/conversation.py backend/routes/rag_query.py backend/routes/conversation.py backend/tests/test_conversation_rewrite.py
git commit -m "feat: persist and expose rewrite diagnostics for follow-up queries"
```

---

### Task 5: Add Enterprise Release Gates For Quality, Latency, And Degraded Mode

**Files:**
- Modify: `backend/metrics.py`
- Modify: `backend/routes/rag_query.py`
- Create: `backend/tests/test_tail_latency_controls.py`
- Create: `iteration-2/eval-2-existing-components/rag_eval/release_gate.py`
- Create: `iteration-2/eval-2-existing-components/rag_eval/test_release_gate.py`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.py`
- Modify: `integration/enterprise-evolution-blueprint-v1.0.md`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add the failing degraded-mode tests**

```python
def test_rag_query_marks_degraded_mode_in_metadata():
    response = client.post("/api/v1/rag/query", json={"query": "复杂问题"})
    assert response.json()["metadata"]["degraded_mode"] in {"rerank_skipped", "candidate_trimmed", None}
```

```python
def test_release_gate_fails_when_p95_latency_exceeds_target():
    verdict = evaluate_release_gate(
        a1={"surfaces": {"final_context": {"recall_at_k": 0.36, "precision_at_k": 0.31, "mrr": 0.48}}},
        a2={"global": {"keyword_coverage_macro": 0.78, "cited_in_retrieved_ratio": 0.99}},
        a5={"latency_ms": {"global": {"p95": 6501, "p99": 14900}}},
    )
    assert verdict["passed"] is False
```

- [ ] **Step 2: Run the new tests in red state**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_tail_latency_controls.py ..\iteration-2\eval-2-existing-components\rag_eval\test_release_gate.py -q`

Expected: failures because degraded-mode metadata and release-gate logic do not yet exist.

- [ ] **Step 3: Emit degraded-mode metadata and metrics**

```python
degraded_mode = None
if meta.get("rerank_budget_triggered"):
    degraded_mode = "rerank_skipped"
elif len(meta.get("final_context_chunk_ids", [])) < len(meta.get("pre_rerank_chunk_ids", [])):
    degraded_mode = "candidate_trimmed"

response.metadata["degraded_mode"] = degraded_mode
rag_degraded_mode_total.labels(mode=degraded_mode or "none").inc()
```

- [ ] **Step 4: Implement release-gate thresholds in `release_gate.py`**

```python
TARGETS = {
    "a1_final_context_recall_min": 0.35,
    "a1_final_context_precision_min": 0.30,
    "a2_keyword_coverage_min": 0.75,
    "a2_cited_in_retrieved_min": 0.98,
    "a5_p95_latency_ms_max": 6000,
    "a5_p99_latency_ms_max": 15000,
}
```

- [ ] **Step 5: Wire release-gate evaluation into CI**

```yaml
- name: Run release gate
  run: |
    cd backend
    .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\release_gate.py
```

- [ ] **Step 6: Re-run focused tests and regenerate A5**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests/test_tail_latency_controls.py ..\iteration-2\eval-2-existing-components\rag_eval\test_release_gate.py -q`

Expected: `passed`.

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a5_performance.py`

Expected: refreshed performance report with degraded-mode visibility.

- [ ] **Step 7: Commit**

```bash
git add backend/metrics.py backend/routes/rag_query.py backend/tests/test_tail_latency_controls.py iteration-2/eval-2-existing-components/rag_eval/release_gate.py iteration-2/eval-2-existing-components/rag_eval/test_release_gate.py iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.py iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json iteration-2/eval-2-existing-components/rag_eval/report_a5_performance.md integration/enterprise-evolution-blueprint-v1.0.md .github/workflows/ci.yml
git commit -m "feat: add enterprise release gates and degraded-mode controls"
```

---

### Task 6: Produce The Formal Delivery Packet And Staging Go/No-Go Verdict

**Files:**
- Modify: `iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json`
- Modify: `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json`
- Create: `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json`
- Create: `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md`
- Modify: `deploy/prometheus/alerts.yml`
- Modify: `deploy/docker-compose.monitoring.yml`

- [ ] **Step 1: Run the full production-path inference harness**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\run_inference.py`

Expected: `raw_runs.jsonl` regenerated using `/api/v1/rag/query`.

- [ ] **Step 2: Recompute A1, A2, and A5**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a1_retrieval.py`

Expected: `metrics_a1_retrieval.json` and `report_a1_retrieval.md` updated.

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a2_faithfulness.py`

Expected: `metrics_a2_faithfulness.json` and `report_a2_faithfulness.md` updated.

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\metrics_a5_performance.py`

Expected: `metrics_a5_performance.json` and `report_a5_performance.md` updated.

- [ ] **Step 3: Run the release-gate decision script**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python ..\iteration-2\eval-2-existing-components\rag_eval\release_gate.py`

Expected: `release_gate_report.json` and `release_gate_report.md` written with `passed=true` or `passed=false`.

- [ ] **Step 4: Run the full backend suite**

Run: `cd D:\graghRAG-agent\backend; .venv\Scripts\python -m pytest tests -q`

Expected: all backend tests pass.

- [ ] **Step 5: Bring up monitoring and verify alert wiring**

Run: `cd D:\graghRAG-agent; docker compose -f deploy/docker-compose.monitoring.yml config`

Expected: valid compose output with Prometheus and Grafana services resolved.

Run: `cd D:\graghRAG-agent; docker compose -f deploy/docker-compose.monitoring.yml up -d`

Expected: monitoring stack starts without config errors.

- [ ] **Step 6: Write the final go/no-go summary**

```markdown
# Enterprise Formal Delivery Summary

- Production endpoint parity: PASS
- Layered retrieval measurement: PASS
- Retrieval precision target: PASS / FAIL
- Multi-turn rewrite observability: PASS / FAIL
- Latency and degraded-mode gate: PASS / FAIL
- Final verdict: GO / NO-GO
- Blocking waivers: []
```

- [ ] **Step 7: Commit**

```bash
git add iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.json iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md deploy/prometheus/alerts.yml deploy/docker-compose.monitoring.yml
git commit -m "chore: publish enterprise formal delivery decision packet"
```

---

## Recommended Release Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6

## Risks To Watch During Execution

- The retrieval metadata contract may drift again if `/api/v1/rag/query` and eval helpers evolve independently.
- Precision tuning can look better on A1 while silently hurting A2 unless the reports are regenerated every time.
- Rewrite persistence can create privacy or storage bloat if conversation cleanup policy is ignored.
- CI release-gate enforcement can become flaky if it depends on stale `raw_runs.jsonl` rather than explicitly regenerated artifacts.
- Monitoring stack verification depends on local Docker availability; if Docker is unavailable, record that as an operational blocker rather than silently skipping it.

## Self-Review

### Spec Coverage

- 生产链路评测对齐：Task 1, Task 2, Task 6 覆盖。
- 检索层量化指标召回率/精确率/MRR：Task 2, Task 3, Task 5 覆盖。
- 生成层相关性/准确性/全面性依托 A2/A5 与 rewrite diagnostics：Task 3, Task 4, Task 5 覆盖。
- 企业正式交付所需的可观测性、门禁、交付包：Task 5, Task 6 覆盖。

### Placeholder Scan

- No `TBD`, `TODO`, or “后续补充”.
- Every task lists exact files, commands, expected outcomes, and commit boundaries.
- The plan stays on the current repo’s real paths and does not invent a second architecture.

### Type Consistency

- Retrieval surfaces consistently use `path_hit_node_ids`, `pre_rerank_node_ids`, and `final_context_node_ids`.
- Route-level contract consistently uses `metadata`.
- Release gates consistently consume `metrics_a1_retrieval.json`, `metrics_a2_faithfulness.json`, and `metrics_a5_performance.json`.
