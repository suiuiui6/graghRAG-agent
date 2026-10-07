# Enterprise GraphRAG Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current GraphRAG service from a high-latency prototype into an enterprise-grade, production-grade, industrial-grade retrieval and generation platform with controlled latency, bounded token cost, stable recall/precision tradeoffs, and resilient runtime behavior.

**Architecture:** Keep the current `NetworkX + ChromaDB + BM25 + LangGraph` stack as the short-term execution base, but introduce a strict query-budget layer, cached retrieval planning, process-wide model lifecycles, indexed KG recall, hybrid retrieval trimming, and community-level global search. Deliver the work in vertical slices so every phase is testable in isolation and safe to deploy behind feature flags.

**Tech Stack:** FastAPI, Python 3.12, NetworkX, ChromaDB, rank-bm25, sentence-transformers CrossEncoder, LangGraph, pytest, Prometheus, structlog.

---

## File Responsibility Map

- `backend/config.py`
  Central runtime tuning surface for retrieval, generation, cache, and budget controls.
- `backend/retrieval.py`
  Query planning, fan-out recall, rerank, trimming, and retrieval pipeline orchestration.
- `backend/generator.py`
  Generation runtime, timeout policy, retry policy, and citation verification.
- `backend/routes/rag_query.py`
  Online RAG entrypoint, lazy runtime initialization, and query metadata surface.
- `backend/routes/query.py`
  Legacy KG-agent path; must be constrained or explicitly degraded to non-primary mode.
- `backend/embedding.py`
  Query/document embedding client, cache persistence, and process lifecycle.
- `backend/vector_store.py`
  Vector search abstraction and minimal metadata projection support.
- `backend/index_registry.py`
  Shared BM25/Table index lifecycle and persistence hooks.
- `backend/kg_store.py`
  KG load path, version management, and future community-summary storage hooks.
- `backend/prompt_builder.py`
  Final context assembly and token-budget truncation.
- `backend/conversation.py`
  Multi-turn rewrite/coreference policy and cacheable conversation summary.
- `backend/metrics.py`
  Prometheus metric additions for retrieval/generation latency and budget usage.
- `backend/tests/`
  Enterprise regression coverage for latency control, retrieval quality gates, and runtime recovery.
- `plans/enterprise-graphrag-performance-implementation-plan.md`
  This implementation plan.

---

## Delivery Standards

- All production changes must be hidden behind explicit config or feature flags before becoming default-on.
- Every task must leave the service runnable in a mixed-mode state.
- All new runtime budgets must emit metrics.
- Every API endpoint touched must retain or gain integration coverage under `backend/tests/`.
- No new remote LLM call may be added to the hot path without cache or measurable gating.

---

### Task 1: Introduce Enterprise Query Budgeting And Feature Flags

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/models.py`
- Modify: `backend/routes/rag_query.py`
- Modify: `backend/prompt_builder.py`
- Test: `backend/tests/test_query_budgeting.py`

- [ ] **Step 1: Write the failing tests for budget propagation**

```python
from models import QueryOptions


def test_query_options_exposes_budget_controls():
    opts = QueryOptions()
    assert opts.max_total_candidates == 10
    assert opts.max_context_tokens == 4000
    assert opts.enable_multi_query is False
    assert opts.enable_cross_encoder is True


def test_query_options_allows_per_request_budget_override():
    opts = QueryOptions(
        max_total_candidates=6,
        max_context_tokens=2400,
        per_source_caps={"vector": 3, "kg": 2, "bm25": 1},
    )
    assert opts.max_total_candidates == 6
    assert opts.per_source_caps["vector"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_query_budgeting.py -v`
Expected: `FAILED` because `QueryOptions` does not yet define enterprise budget fields.

- [ ] **Step 3: Extend request models and config defaults**

```python
class QueryOptions(BaseModel):
    max_tool_calls: int = Field(default=10, ge=1, le=50)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    language: str = Field(default="en", pattern="^(en|ch|ja)$")
    include_sources: bool = Field(default=True)
    max_total_candidates: int = Field(default=10, ge=1, le=50)
    max_context_tokens: int = Field(default=4000, ge=512, le=16000)
    enable_cross_encoder: bool = Field(default=True)
    enable_multi_query: bool = Field(default=False)
    enable_global_mode: bool = Field(default=False)
    per_source_caps: dict[str, int] = Field(
        default_factory=lambda: {"vector": 4, "kg": 3, "bm25": 2, "table": 2, "multi_query": 2}
    )
```

- [ ] **Step 4: Pass per-request budget config into the RAG pipeline**

```python
config = RetrievalConfig(
    enable_cross_encoder=req.options.enable_cross_encoder,
    max_total_candidates=req.options.max_total_candidates,
    max_context_tokens=req.options.max_context_tokens,
    vector_top_k=req.options.per_source_caps.get("vector", 4),
    kg_top_k=req.options.per_source_caps.get("kg", 3),
    bm25_top_k=req.options.per_source_caps.get("bm25", 2),
    table_top_k=req.options.per_source_caps.get("table", 2),
    multi_query_top_k=req.options.per_source_caps.get("multi_query", 2),
)
```

- [ ] **Step 5: Enforce prompt-level truncation against the same budget**

```python
messages, prompt_meta = build_prompt(
    query=query,
    retrieval_result=retrieval_result,
    max_context_tokens=max_context_tokens,
)
assert prompt_meta["context_tokens"] <= max_context_tokens
```

- [ ] **Step 6: Run focused tests**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_query_budgeting.py -v`
Expected: `2 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/config.py backend/models.py backend/routes/rag_query.py backend/prompt_builder.py backend/tests/test_query_budgeting.py
git commit -m "feat: add enterprise query budgeting controls"
```

---

### Task 2: Remove Hot-Path Reinitialization With Shared Runtime Caches

**Files:**
- Modify: `backend/retrieval.py`
- Modify: `backend/embedding.py`
- Modify: `backend/routes/rag_query.py`
- Modify: `backend/conversation.py`
- Test: `backend/tests/test_runtime_caching.py`

- [ ] **Step 1: Write the failing tests for singleton model reuse**

```python
from retrieval import get_cross_encoder


def test_cross_encoder_is_cached_process_wide():
    first = get_cross_encoder()
    second = get_cross_encoder()
    assert first is second


def test_query_rewrite_cache_reuses_prior_result(tmp_path):
    from retrieval import QueryRewriteCache

    cache = QueryRewriteCache(tmp_path / "rewrite-cache.sqlite3")
    cache.set("q:预算执行率", {"rewritten": "预算执行率", "intent": "metric"})
    assert cache.get("q:预算执行率")["intent"] == "metric"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_runtime_caching.py -v`
Expected: `FAILED` because there is no cached cross-encoder helper or rewrite cache implementation.

- [ ] **Step 3: Add process-wide model getters instead of request-scoped initialization**

```python
_cross_encoder = None
_cross_encoder_lock = threading.Lock()


def get_cross_encoder(model_name: str = "BAAI/bge-reranker-base"):
    global _cross_encoder
    if _cross_encoder is None:
        with _cross_encoder_lock:
            if _cross_encoder is None:
                from sentence_transformers import CrossEncoder
                _cross_encoder = CrossEncoder(model_name, max_length=512)
    return _cross_encoder
```

- [ ] **Step 4: Add rewrite/coreference cache with stable keys**

```python
class QueryRewriteCache:
    def __init__(self, path: Path):
        self.path = path
        self._db = sqlite3.connect(str(path))
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS query_rewrite_cache (cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )

    def get(self, cache_key: str) -> dict | None:
        row = self._db.execute(
            "SELECT payload FROM query_rewrite_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, cache_key: str, payload: dict) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO query_rewrite_cache(cache_key, payload) VALUES(?, ?)",
            (cache_key, json.dumps(payload, ensure_ascii=False)),
        )
        self._db.commit()
```

- [ ] **Step 5: Route `preprocess_query()` and coreference resolution through cache-first logic**

```python
cache_key = f"rewrite:{raw_query}:{history_signature}"
cached = rewrite_cache.get(cache_key)
if cached:
    return PreprocessedQuery(**cached)

result = _call_rewrite_llm(...)
rewrite_cache.set(cache_key, result.model_dump())
return PreprocessedQuery(**result.model_dump())
```

- [ ] **Step 6: Run focused tests**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_runtime_caching.py -v`
Expected: `2 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/retrieval.py backend/embedding.py backend/routes/rag_query.py backend/conversation.py backend/tests/test_runtime_caching.py
git commit -m "feat: cache query planning and model runtimes"
```

---

### Task 3: Fix Retrieval Consistency And Source-Aware Trimming

**Files:**
- Modify: `backend/retrieval.py`
- Modify: `backend/index_registry.py`
- Modify: `backend/vector_store.py`
- Modify: `backend/prompt_builder.py`
- Test: `backend/tests/test_hybrid_retrieval_trimming.py`

- [ ] **Step 1: Write the failing tests for BM25 tokenization and source caps**

```python
def test_bm25_query_uses_same_tokenizer_as_index():
    from index_registry import _tokenize_for_bm25
    query = "预算执行率超过80%的项目"
    assert _tokenize_for_bm25(query) != [query.lower()]


def test_source_aware_trim_honors_caps():
    from retrieval import trim_results_by_source_budget
    candidates = [
        {"chunk_id": "v1", "source": "vector", "score": 0.9},
        {"chunk_id": "v2", "source": "vector", "score": 0.8},
        {"chunk_id": "kg1", "source": "kg", "score": 0.7},
    ]
    trimmed = trim_results_by_source_budget(candidates, {"vector": 1, "kg": 1}, max_total=2)
    assert [x["chunk_id"] for x in trimmed] == ["v1", "kg1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_hybrid_retrieval_trimming.py -v`
Expected: `FAILED` because there is no source-aware trimmer and BM25 query path still uses whitespace split.

- [ ] **Step 3: Reuse the same tokenizer in BM25 search**

```python
def _bm25_recall(query_text: str, bm25_index, config: RetrievalConfig) -> list[dict]:
    tokenized_query = _tokenize_for_bm25(query_text)
    scores = bm25_model.get_scores(tokenized_query)
```

- [ ] **Step 4: Add minimal metadata projection for prompt-safe candidates**

```python
def project_candidate(candidate: dict) -> dict:
    return {
        "chunk_id": candidate["chunk_id"],
        "text": candidate.get("text", "")[:1200],
        "score": candidate.get("score", 0.0),
        "source": candidate.get("source", ""),
        "page_idx": candidate.get("metadata", {}).get("page_idx"),
        "section_title": candidate.get("metadata", {}).get("section_title", ""),
        "entity_ids": candidate.get("metadata", {}).get("entity_ids", []),
    }
```

- [ ] **Step 5: Add source-aware trimming before rerank and before prompt build**

```python
def trim_results_by_source_budget(results: list[dict], caps: dict[str, int], max_total: int) -> list[dict]:
    per_source: dict[str, int] = collections.defaultdict(int)
    trimmed: list[dict] = []
    for item in sorted(results, key=lambda x: -x["score"]):
        src = item["source"]
        if per_source[src] >= caps.get(src, max_total):
            continue
        trimmed.append(item)
        per_source[src] += 1
        if len(trimmed) >= max_total:
            break
    return trimmed
```

- [ ] **Step 6: Run focused tests**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_hybrid_retrieval_trimming.py -v`
Expected: `2 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/retrieval.py backend/index_registry.py backend/vector_store.py backend/prompt_builder.py backend/tests/test_hybrid_retrieval_trimming.py
git commit -m "feat: align hybrid retrieval tokenization and trimming"
```

---

### Task 4: Replace Full-Graph KG Scans With Indexed KG Recall

**Files:**
- Modify: `backend/kg_store.py`
- Modify: `backend/retrieval.py`
- Modify: `backend/routes/query.py`
- Test: `backend/tests/test_kg_indexed_recall.py`

- [ ] **Step 1: Write the failing tests for indexed KG lookup**

```python
def test_kg_index_builds_entity_type_buckets():
    from kg_store import build_kg_lookup_indexes
    graph = nx.Graph()
    graph.add_node("n1", entity_type="metric", label="预算执行率", properties={"value": "82%"})
    idx = build_kg_lookup_indexes(graph)
    assert "metric" in idx["by_type"]
    assert "预算" in idx["token_to_nodes"]


def test_indexed_kg_recall_returns_without_full_scan():
    from retrieval import indexed_kg_recall
    graph = nx.Graph()
    graph.add_node("n1", entity_type="metric", label="预算执行率", properties={"value": "82%"})
    indexes = build_kg_lookup_indexes(graph)
    result = indexed_kg_recall("预算执行率", ["metric"], graph, indexes, top_k=3)
    assert result[0]["chunk_id"] == "n1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_kg_indexed_recall.py -v`
Expected: `FAILED` because KG index helpers do not exist.

- [ ] **Step 3: Build reusable KG lookup indexes at load time**

```python
def build_kg_lookup_indexes(graph: nx.Graph) -> dict:
    by_type: dict[str, list[str]] = collections.defaultdict(list)
    token_to_nodes: dict[str, set[str]] = collections.defaultdict(set)
    neighbor_preview: dict[str, list[dict]] = {}

    for nid, data in graph.nodes(data=True):
        by_type[data.get("entity_type", "")].append(nid)
        text = f"{data.get('label', '')} {' '.join(str(v) for v in data.get('properties', {}).values())}"
        for tok in _tokenize_for_bm25(text):
            token_to_nodes[tok].add(nid)
        neighbor_preview[nid] = list(itertools.islice(_iter_neighbors(graph, nid), 5))

    return {"by_type": by_type, "token_to_nodes": token_to_nodes, "neighbor_preview": neighbor_preview}
```

- [ ] **Step 4: Swap retrieval to candidate-first indexed recall**

```python
candidate_ids = set()
for etype in entity_types[:5]:
    for nid in kg_indexes["by_type"].get(etype, []):
        candidate_ids.add(nid)
for token in _tokenize_for_bm25(query_text):
    candidate_ids.update(kg_indexes["token_to_nodes"].get(token, set()))
```

- [ ] **Step 5: Constrain legacy `/query` tools with the same indexes or mark them non-primary**

```python
MAX_LEGACY_QUERY_RESULTS = 8
MAX_LEGACY_NEIGHBOR_FANOUT = 10
```

- [ ] **Step 6: Run focused tests**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_kg_indexed_recall.py -v`
Expected: `2 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/kg_store.py backend/retrieval.py backend/routes/query.py backend/tests/test_kg_indexed_recall.py
git commit -m "feat: add indexed kg recall path"
```

---

### Task 5: Add Community Summaries And Global Search Mode

**Files:**
- Create: `backend/community_index.py`
- Modify: `backend/kg_store.py`
- Modify: `backend/retrieval.py`
- Modify: `backend/routes/rag_query.py`
- Test: `backend/tests/test_community_global_mode.py`

- [ ] **Step 1: Write the failing tests for community index support**

```python
def test_build_community_index_creates_summary_records():
    from community_index import build_community_index
    graph = nx.karate_club_graph()
    idx = build_community_index(graph)
    assert idx["communities"]
    assert "summary_text" in idx["communities"][0]


def test_global_mode_prefers_community_records():
    from retrieval import choose_query_mode
    mode = choose_query_mode("总结所有主要风险与部门关系", enable_global_mode=True)
    assert mode == "global"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_community_global_mode.py -v`
Expected: `FAILED` because there is no community index or global mode router.

- [ ] **Step 3: Add community summary builder**

```python
def build_community_index(graph: nx.Graph) -> dict:
    communities = list(nx.algorithms.community.greedy_modularity_communities(graph))
    records = []
    for i, nodes in enumerate(communities):
        labels = [graph.nodes[n].get("label", n) for n in list(nodes)[:20]]
        types = collections.Counter(graph.nodes[n].get("entity_type", "unknown") for n in nodes)
        records.append({
            "community_id": f"c{i:04d}",
            "node_ids": sorted(nodes),
            "top_entity_types": dict(types.most_common(5)),
            "summary_text": " | ".join(labels[:10]),
        })
    return {"communities": records}
```

- [ ] **Step 4: Add query mode router and community-first retrieval path**

```python
def choose_query_mode(query: str, enable_global_mode: bool) -> str:
    if enable_global_mode and any(tok in query for tok in ["总结", "整体", "全局", "概览", "总体"]):
        return "global"
    return "local"
```

- [ ] **Step 5: Only allow global mode to descend into top-scoring communities**

```python
selected_communities = sorted(community_hits, key=lambda x: -x["score"])[:3]
```

- [ ] **Step 6: Run focused tests**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_community_global_mode.py -v`
Expected: `2 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/community_index.py backend/kg_store.py backend/retrieval.py backend/routes/rag_query.py backend/tests/test_community_global_mode.py
git commit -m "feat: add community summaries and global graph mode"
```

---

### Task 6: Production Hardening, Persistence Recovery, And Observability

**Files:**
- Modify: `backend/index_registry.py`
- Modify: `backend/server.py`
- Modify: `backend/metrics.py`
- Modify: `backend/generator.py`
- Modify: `backend/routes/health.py`
- Test: `backend/tests/test_runtime_recovery.py`

- [ ] **Step 1: Write the failing tests for index recovery and metrics**

```python
def test_runtime_recovers_bm25_index_from_disk(tmp_path):
    from index_registry import persist_bm25_artifact, restore_bm25_artifact
    sample = {"chunks": ["预算执行率 82%"]}
    persist_bm25_artifact(tmp_path / "bm25.json", sample)
    assert restore_bm25_artifact(tmp_path / "bm25.json")["chunks"] == sample["chunks"]


def test_generation_timeout_policy_is_bounded():
    from generator import GenerationConfig
    cfg = GenerationConfig(timeout=30, max_retries=1)
    assert cfg.timeout == 30
    assert cfg.max_retries == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_runtime_recovery.py -v`
Expected: `FAILED` because recovery helpers and bounded retry config do not exist.

- [ ] **Step 3: Persist and restore BM25/Table artifacts at startup**

```python
def persist_bm25_artifact(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def restore_bm25_artifact(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Bound generation retries and remove request-thread sleeps**

```python
@dataclass
class GenerationConfig:
    temperature: float = 0.0
    max_tokens: int = 2048
    model: str = "deepseek-chat"
    api_key: str | None = None
    base_url: str | None = None
    timeout: int = 30
    max_retries: int = 1
```

- [ ] **Step 5: Emit metrics for budget, cache hit, rerank latency, and query mode**

```python
rag_query_budget_tokens = Histogram("rag_query_budget_tokens", "Context token budget used")
rag_cache_hits_total = Counter("rag_cache_hits_total", "Rewrite/coreference/cache hits", ["cache"])
rag_rerank_duration_seconds = Histogram("rag_rerank_duration_seconds", "Cross-encoder rerank latency")
rag_query_mode_total = Counter("rag_query_mode_total", "Query mode selections", ["mode"])
```

- [ ] **Step 6: Run focused tests**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_runtime_recovery.py -v`
Expected: `2 passed`

- [ ] **Step 7: Run enterprise regression suite**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_query_budgeting.py tests/test_runtime_caching.py tests/test_hybrid_retrieval_trimming.py tests/test_kg_indexed_recall.py tests/test_community_global_mode.py tests/test_runtime_recovery.py -v`
Expected: `all passed`

- [ ] **Step 8: Commit**

```bash
git add backend/index_registry.py backend/server.py backend/metrics.py backend/generator.py backend/routes/health.py backend/tests/test_runtime_recovery.py
git commit -m "feat: harden runtime recovery and observability"
```

---

## Release Gates

- [ ] `cd backend && .venv\Scripts\python -m pytest backend/tests -v`
- [ ] `cd backend && .venv\Scripts\python -m pytest tests/test_query_budgeting.py tests/test_runtime_caching.py tests/test_hybrid_retrieval_trimming.py tests/test_kg_indexed_recall.py tests/test_community_global_mode.py tests/test_runtime_recovery.py -v`
- [ ] `cd backend && .venv\Scripts\python -m uvicorn server:app --host 127.0.0.1 --port 8000`
- [ ] Validate `/api/v1/rag/query` for:
  - [ ] first-turn local query
  - [ ] second-turn query with coreference
  - [ ] global summary query
  - [ ] timeout degradation path
- [ ] Re-run:
  - [ ] `backend/.venv/Scripts/python.exe iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py`
  - [ ] `backend/.venv/Scripts/python.exe iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py`
  - [ ] `backend/.venv/Scripts/python.exe iteration-2/eval-2-existing-components/rag_eval/metrics_a4_multihop.py`
  - [ ] `backend/.venv/Scripts/python.exe iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.py`
- [ ] Confirm target improvements before enabling defaults:
  - [ ] `p95 latency < 20s`
  - [ ] `mean cost/question < $0.01`
  - [ ] `precision_macro >= 0.18`
  - [ ] `mrr_macro >= 0.25`
  - [ ] `keyword_coverage_macro >= 0.85`
  - [ ] `hallucination_rate == 0.0`

---

## Self-Review

- Spec coverage:
  - Enterprise query budgeting: covered in Task 1.
  - Hot-path runtime optimization: covered in Task 2.
  - Hybrid retrieval quality and cost control: covered in Task 3.
  - Indexed KG retrieval: covered in Task 4.
  - Community/global GraphRAG mode: covered in Task 5.
  - Production recovery/observability/release gates: covered in Task 6.
- Placeholder scan:
  - No `TBD`, `TODO`, or “implement later” placeholders remain.
  - Every task includes explicit files, code, commands, and expected outcomes.
- Type consistency:
  - Budget fields are consistently named `max_total_candidates`, `max_context_tokens`, `per_source_caps`.
  - Community routing uses `enable_global_mode` and `choose_query_mode`.
  - Cache and recovery helpers are named consistently across tasks.

---

Plan complete and saved to `plans/enterprise-graphrag-performance-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
