"""TEST_ONLY: evidence software contracts, not scientific evaluation data."""
from copy import deepcopy

import retrieval
from config import RetrievalConfig
from models import QueryOptions
import prompt_builder
import generator
import pytest
from types import SimpleNamespace


def candidate(doc="docA", text="test evidence", source="vector", cid="n0010"):
    return {"chunk_id": cid, "text": text, "source": source, "score": 1.0,
            "metadata": {"document_id": doc, "char_start": 0, "char_end": len(text)}}


def test_same_legacy_id_in_different_documents_is_not_merged():
    hits = retrieval.rrf_fusion([("vector", [candidate(), candidate("docB")])])
    assert len(hits) == 2
    assert len({h["evidence_id"] for h in hits}) == 2
    assert len({h["chunk_id"] for h in hits}) == 2


def test_multi_source_hits_merge_paths_and_scores_without_mutation():
    a, b = candidate(), candidate(source="bm25")
    original = deepcopy([a, b])
    hits = retrieval.rrf_fusion([("bm25", [b]), ("vector", [a])])
    assert len(hits) == 1
    assert hits[0]["source_paths"] == ["vector", "bm25"]
    assert {p["source"] for p in hits[0]["provenance"]} == {"vector", "bm25"}
    assert hits[0]["original_scores"] == {"vector": [1.0], "bm25": [1.0]}
    assert [a, b] == original


def test_same_location_content_conflict_is_retained():
    a, b = candidate(text="fact one"), candidate(text="fact two", source="bm25")
    hits = retrieval.rrf_fusion([("vector", [a]), ("bm25", [b])])
    assert len(hits) == 2
    assert all(h["identity_conflicts"] for h in hits)


def test_missing_id_and_async_path_order_are_stable():
    a, b = candidate(cid=""), candidate("docB", cid="")
    paths = [("vector", [a]), ("bm25", [b])]
    first = retrieval.rrf_fusion(paths)
    second = retrieval.rrf_fusion(list(reversed(paths)))
    assert first == second
    assert all(h["chunk_id"] and h["evidence_id"] for h in first)


def test_tied_rank_order_is_stable():
    a, b = candidate(cid="c002"), candidate("docB", cid="c001")
    assert retrieval.rrf_fusion([("vector", [a, b])]) == retrieval.rrf_fusion([("vector", [b, a])])


def test_projection_keeps_identity_and_real_location():
    fused = retrieval.rrf_fusion([("vector", [candidate()])])[0]
    projected = retrieval.project_candidate(fused)
    assert projected["evidence_id"] == fused["evidence_id"]
    assert projected["provenance"] == fused["provenance"]


def test_opt_in_pipeline_trace_and_no_shared_mutation(monkeypatch):
    monkeypatch.setattr(retrieval, "preprocess_query", lambda query, **kw: retrieval.PreprocessedQuery(query, query, "hybrid", []))
    monkeypatch.setattr(retrieval, "_bm25_recall", lambda *args: [candidate(source="bm25")])
    pipeline = retrieval.RetrievalPipeline(None, None, bm25_index=object())
    options = QueryOptions(include_evidence_trace=True)
    assert options.include_evidence_trace is True
    traced = pipeline.retrieve("TEST_ONLY query", retrieval_config=RetrievalConfig(
        enabled_sources=["bm25"], enable_cross_encoder=False, include_evidence_trace=True))
    trace = traced.pipeline["evidence_trace"]
    assert trace["retrieval_stages"]["path_hits"]["evidence"]
    assert trace["retrieval_stages"]["retrieval_final"]["evidence"][0]["evidence_id"]
    assert "evidence_trace" not in pipeline.retrieve("TEST_ONLY query", retrieval_config=RetrievalConfig(
        enabled_sources=["bm25"], enable_cross_encoder=False)).pipeline


def test_formatted_prompt_visible_spans_exclude_headers_and_cut_text():
    text = "人工智能 TEST_ONLY " * 60 + "HIDDEN_GOLD"
    fused = retrieval.rrf_fusion([("vector", [candidate(text=text, cid="c001")])])[0]
    item = retrieval.project_candidate(fused)
    chunk = retrieval.RetrievalChunk("c001", item["text"], 1, "vector", section_title="TITLE" * 20, metadata=item["metadata"])
    messages, meta = prompt_builder.build_prompt(retrieval.RetrievalResult([chunk], 1, {}, "hybrid", []), "query", 70,
                                                 return_metadata=True, include_evidence_trace=True)
    context = meta["evidence_context"]
    assert context["messages"] == messages
    assert len(context["context_text"]) <= 280
    record = context["visible_evidence"][0]
    start, end = record["context_span"]
    assert context["context_text"][start:end] == record["visible_text"]
    assert text.startswith(record["visible_text"])
    assert "HIDDEN_GOLD" not in record["visible_text"]
    assert record["original_span"] is None


def test_domain_hint_only_does_not_count_retrieval_as_visible():
    chunk = retrieval.RetrievalChunk("c001", "HIDDEN_GOLD", 1, "kg")
    result = retrieval.RetrievalResult([chunk], 1, {}, "hybrid", [], domain_hint="hint " * 100)
    _, meta = prompt_builder.build_prompt(result, "query", 20, return_metadata=True, include_evidence_trace=True)
    assert meta["evidence_context"]["visible_evidence"] == []
    assert "HIDDEN_GOLD" not in meta["evidence_context"]["context_text"]


def test_large_header_without_visible_body_is_not_evidence():
    chunk = retrieval.RetrievalChunk("c001", "HIDDEN_GOLD", 1, "kg", section_title="large header " * 100)
    _, meta = prompt_builder.build_prompt(retrieval.RetrievalResult([chunk], 1, {}, "hybrid", []), "query", 30,
                                         return_metadata=True, include_evidence_trace=True)
    assert meta["evidence_context"]["visible_evidence"] == []


@pytest.fixture
def isolated_lineage(monkeypatch, sandbox_tmp_path):
    from services import lineage_store
    monkeypatch.setattr(lineage_store, "_store", lineage_store.LineageStore(sandbox_tmp_path / "lineage"))


def test_deterministic_correction_has_decision_evidence_not_model_context(monkeypatch, isolated_lineage):
    config = RetrievalConfig(enabled_sources=["bm25"], enable_cross_encoder=False, include_evidence_trace=True)
    chunk = retrieval.RetrievalChunk("c001", "TEST_ONLY 加装储能后年产量从9023提升至10903吨。", 1, "bm25")
    pipeline = SimpleNamespace(config=config, retrieve=lambda *a, **kw: retrieval.RetrievalResult([chunk], 1, {}, "hybrid", []))
    monkeypatch.setattr(generator, "generate_answer", lambda **kw: pytest.fail("no model call expected"))
    answer = generator.RAGGenerator(pipeline, generator.GenerationConfig()).generate("储能使产量降低，对吗？")
    trace = answer["metadata"]["evidence_trace"]
    assert trace["generation_mode"] == "deterministic_correction"
    assert trace["model_call_attempted"] is False
    assert trace["raw_model_answer"] is None
    assert trace["serialized_model_context"] is None
    assert trace["decision_evidence"][0]["text"] == chunk.text
    assert trace["final_answer"] == answer["answer"]


@pytest.mark.parametrize("provider_error", [False, True])
def test_real_generation_boundary_keeps_raw_output_and_transforms(monkeypatch, isolated_lineage, provider_error):
    original = "  TEST_ONLY provider output without citation  \n"
    def respond(*args, **kwargs):
        if provider_error:
            return SimpleNamespace(status_code=500)
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                               json=lambda: {"choices": [{"message": {"content": original}, "finish_reason": "length"}], "usage": {}})
    monkeypatch.setattr("requests.post", respond)
    config = RetrievalConfig(enabled_sources=["bm25"], enable_cross_encoder=False, include_evidence_trace=True)
    chunk = retrieval.RetrievalChunk("c001", "TEST_ONLY software evidence", 1, "bm25")
    pipeline = SimpleNamespace(config=config, retrieve=lambda *a, **kw: retrieval.RetrievalResult([chunk], 1, {}, "hybrid", []))
    result = generator.RAGGenerator(pipeline, generator.GenerationConfig(base_url="https://invalid.example", api_key="", max_retries=0)).generate("TEST_ONLY explain")
    trace = result["metadata"]["evidence_trace"]
    assert trace["raw_model_answer"] == (None if provider_error else original)
    assert trace["serialized_model_context"]["messages"]
    assert trace["model_call_attempted"] is True
    assert trace["model_output_received"] is not provider_error
    assert trace["final_answer"] == result["answer"]
    stages = trace["answer_stages"]
    assert stages[0]["stage"] == ("generation_fallback" if provider_error else "provider_output")
    assert all(stage["output_answer"] is not None for stage in stages)
    if not provider_error:
        assert any(stage["stage"] == "length_notice" for stage in stages)
        assert any(stage["stage"] == "citation_notice" for stage in stages)
    assert [stage["stage"] for stage in stages][-3:] == ["repair", "complete", "supplement"]


def test_table_rows_without_source_id_have_stable_identity():
    table = SimpleNamespace(query=lambda **kw: [{"sheet_name": "TEST_ONLY", "column_value": "fact"}])
    query = retrieval.PreprocessedQuery("query", "query", "metric", [])
    first = retrieval.rrf_fusion([("table", retrieval._table_recall(query, table, RetrievalConfig()))])
    second = retrieval.rrf_fusion([("table", retrieval._table_recall(query, table, RetrievalConfig()))])
    assert first == second


def test_trim_ties_do_not_depend_on_input_order():
    a, b = candidate(cid="c002"), candidate("docB", cid="c001")
    assert retrieval.trim_results_by_source_budget([a, b], {"vector": 1}, 1) == retrieval.trim_results_by_source_budget([b, a], {"vector": 1}, 1)


def test_unknown_original_span_not_promoted_to_verified():
    fused = retrieval.rrf_fusion([("bm25", [candidate(source="bm25")])])[0]
    assert fused["provenance"][0]["declared_span"] == [0, 13]
    assert fused["provenance"][0]["original_span"] is None


def test_prompt_validated_span_maps_only_visible_prefix():
    item = candidate(text="TEST_ONLY " * 100, source="kg")
    item["metadata"]["span_verified"] = True
    fused = retrieval.rrf_fusion([("kg", [item])])[0]
    projected = retrieval.project_candidate(fused)
    chunk = retrieval.RetrievalChunk(projected["chunk_id"], projected["text"], 1, "kg", metadata=projected["metadata"])
    _, meta = prompt_builder.build_prompt(retrieval.RetrievalResult([chunk], 1, {}, "hybrid", []), "q", 50,
                                         return_metadata=True, include_evidence_trace=True)
    record = meta["evidence_context"]["visible_evidence"][0]
    assert record["original_span"] == [0, len(record["visible_text"])]


def test_rescue_merge_keeps_paths_in_chunk_metadata():
    first = retrieval.project_candidate(retrieval.rrf_fusion([("vector", [candidate()])])[0])
    rescue = retrieval.project_candidate(retrieval.rrf_fusion([("bm25", [candidate(source="bm25")])])[0])
    merged = retrieval._merge_priority_candidates([first], [rescue])[0]
    chunk = retrieval.filter_redundant([merged])[0]
    assert chunk.metadata["source_paths"] == ["vector", "bm25"]


def test_deterministic_refusal_has_no_model_trace(monkeypatch, isolated_lineage):
    config = RetrievalConfig(enabled_sources=["bm25"], include_evidence_trace=True)
    chunk = retrieval.RetrievalChunk("c001", "TEST_ONLY 使用 Python 计算。", 1, "bm25")
    pipeline = SimpleNamespace(config=config, retrieve=lambda *a, **kw: retrieval.RetrievalResult([chunk], 1, {}, "hybrid", []))
    monkeypatch.setattr(generator, "generate_answer", lambda **kw: pytest.fail("no provider call expected"))
    result = generator.RAGGenerator(pipeline, generator.GenerationConfig()).generate("论文用了 GPT-4 来辅助优化求解，对吗？")
    trace = result["metadata"]["evidence_trace"]
    assert trace["generation_mode"] == "deterministic_refusal"
    assert trace["serialized_model_context"] is trace["raw_model_answer"] is None
    assert trace["decision_evidence"][0]["chunk_id"] == "c001"


def test_cross_document_filter_preserves_distinct_ids_and_dropped_evidence(monkeypatch):
    monkeypatch.setattr(retrieval, "preprocess_query", lambda query, **kw: retrieval.PreprocessedQuery(query, query, "hybrid", []))
    monkeypatch.setattr(retrieval, "_bm25_recall", lambda *args: [candidate(source="bm25"), candidate("docB", source="bm25")])
    config = RetrievalConfig(enabled_sources=["bm25"], include_evidence_trace=True, enable_cross_encoder=False,
                             per_source_caps={"bm25": 3}, max_total_candidates=3)
    result = retrieval.RetrievalPipeline(None, None, bm25_index=object()).retrieve("TEST_ONLY", retrieval_config=config)
    stages = result.pipeline["evidence_trace"]["retrieval_stages"]
    assert len(stages["path_hits"]["evidence"]) == 2
    # Redundancy filtering may select one passage, but the other identity must not disappear from the audit.
    final_ids = {r["evidence_id"] for r in stages["retrieval_final"]["evidence"]}
    dropped_ids = {r["evidence_id"] for r in stages["retrieval_final"]["dropped"]}
    assert final_ids | dropped_ids == {r["evidence_id"] for r in stages["post_rerank"]["evidence"]}


def test_unverified_id_does_not_strip_document_prefix():
    a, b = candidate(doc=None, cid="docA:n0010"), candidate(doc=None, cid="docB:n0010")
    fused = retrieval.rrf_fusion([("kg", [a, b])])
    assert len(fused) == 2
    assert {r["original_id"] for r in fused} == {"docA:n0010", "docB:n0010"}


def test_vector_projection_does_not_create_false_content_conflict():
    text = "TEST_ONLY " * 200
    full = candidate(text=text)
    class Store:
        def search(self, **kwargs):
            item = deepcopy(full)
            cap = kwargs.get("text_char_limit")
            if cap is not None:
                item["text"] = item["text"][:cap]
            return [item]
    vector = retrieval._vector_recall([[1.0]], Store(), RetrievalConfig())
    bm25 = candidate(text=text, source="bm25")
    hits = retrieval.rrf_fusion([("vector", vector), ("bm25", [bm25])])
    assert len(hits) == 1
    assert hits[0]["identity_conflicts"] == []
    assert hits[0]["source_paths"] == ["vector", "bm25"]


def test_vector_internal_dedup_does_not_drop_other_document():
    class Store:
        def search(self, **kwargs):
            return [candidate(), candidate("docB")]
    assert len(retrieval._vector_recall([[1.0]], Store(), RetrievalConfig(vector_top_k=5))) == 2


def test_synthetic_retrieval_marker_is_not_raw_source_span():
    item = candidate(text="TEST_ONLY " * 100)
    item["metadata"]["span_verified"] = True
    projected = retrieval.project_candidate(retrieval.rrf_fusion([("vector", [item])])[0])
    chunks = retrieval.filter_redundant([projected], max_context_tokens=60)
    assert chunks[0].text.endswith("...")
    _, meta = prompt_builder.build_prompt(retrieval.RetrievalResult(chunks, 1, {}, "hybrid", []), "query",
                                         return_metadata=True, include_evidence_trace=True)
    record = meta["evidence_context"]["visible_evidence"][0]
    assert not record["visible_text"].endswith("...")
    assert record["original_span"] == [0, 240]


def test_projection_preserves_protection_flag():
    item = candidate()
    item["metadata"]["protected_evidence"] = True
    projected = retrieval.project_candidate(retrieval.rrf_fusion([("vector", [item])])[0])
    assert projected["metadata"]["protected_evidence"] is True


def test_priority_remerge_cannot_erase_actual_rerank_score():
    normal = retrieval.project_candidate(retrieval.rrf_fusion([("bm25", [candidate(source="bm25")])])[0])
    normal["rerank_score"] = 0.9
    rescue = deepcopy(normal)
    rescue.pop("rerank_score")
    rescue["score"] = 1.4
    merged = retrieval._merge_priority_candidates([normal], [rescue])[0]
    assert merged["rerank_score"] == 0.9
    assert merged["metadata"]["rerank_score"] == 0.9


def test_storage_rescue_reuses_normal_vector_identity():
    text = "TEST_ONLY 加装储能后年产量从9023提升至10903吨。" + "software passage " * 100
    full = candidate(text=text)
    class Store:
        def search(self, **kwargs):
            item = deepcopy(full)
            cap = kwargs.get("text_char_limit")
            if cap is not None:
                item["text"] = item["text"][:cap]
            return [item]
    store = Store()
    pipeline = SimpleNamespace(vector_store=store, embedding_client=SimpleNamespace(embed_query=lambda query: [1.0]),
                               config=RetrievalConfig(enabled_sources=["vector"]))
    normal = retrieval._vector_recall([[1.0]], store, pipeline.config)
    rescued = generator._targeted_storage_claim_rescue_chunks("储能降低产量，对吗？", pipeline)
    assert len(retrieval._merge_priority_candidates(normal, rescued)) == 1
    assert rescued[0]["evidence_id"] == normal[0]["evidence_id"]


def test_canonical_citation_is_verified_as_exact_identity():
    canonical = retrieval.rrf_fusion([("vector", [candidate(cid="")])])[0]["chunk_id"]
    answer = f"TEST_ONLY fact [{canonical}]"
    valid, invalid, cited = generator.verify_citations(answer, [{"chunk_id": canonical, "text": "fact"}])
    assert valid and not invalid and cited == [canonical]
    assert generator.validate_output_format(answer)["has_citations"]


@pytest.mark.parametrize("legacy_id", ["c00001", ""])
def test_unknown_canonical_citation_cannot_use_legacy_substring(legacy_id):
    unknown = "ev1_" + "c00001" + "0" * 58
    valid, invalid, cited = generator.verify_citations(
        f"TEST_ONLY [{unknown}]", [{"chunk_id": legacy_id, "text": "other evidence"}])
    assert not valid and invalid == [unknown] and cited == []
