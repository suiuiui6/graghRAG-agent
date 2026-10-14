from tests.request_helpers import admin_request
"""M4-P1 contract tests. Synthetic fixtures are software tests, not paper results."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import networkx as nx
import pytest
from pydantic import ValidationError

import generator
import retrieval
import routes.rag_query as route
from config import RetrievalConfig
from models import QueryOptions, QueryRequest


@pytest.mark.parametrize("value", [[], ["unknown"], "bm25"])
def test_query_options_reject_invalid_source_lists(value):
    with pytest.raises(ValidationError):
        QueryOptions(enabled_sources=value)


def test_request_sources_are_canonical_and_config_is_request_scoped():
    options = QueryOptions(enabled_sources=["bm25", "vector", "bm25"])
    config = route._build_retrieval_config(options)
    assert options.enabled_sources == ["vector", "bm25"]
    assert config.enabled_sources == ("vector", "bm25")
    assert QueryOptions().enabled_sources is None
    assert RetrievalConfig().enabled_sources is None
    assert config.per_source_caps["kg"] == 2  # cap is not the allowlist


@pytest.fixture
def offline_preprocess(monkeypatch):
    monkeypatch.setattr(
        retrieval, "preprocess_query",
        lambda query, **kwargs: retrieval.PreprocessedQuery(query, query, "metric", [], []),
    )


@pytest.fixture
def isolated_lineage(monkeypatch, sandbox_tmp_path):
    from services import lineage_store
    monkeypatch.setattr(lineage_store, "_store", lineage_store.LineageStore(sandbox_tmp_path / "lineage"))


def _candidate(source):
    return {"chunk_id": source + "_1", "text": "test evidence " + source,
            "score": 0.9, "source": source, "metadata": {}}


@pytest.mark.parametrize("enabled", [("bm25",), ("vector",), ("vector", "bm25")])
def test_normal_recall_does_not_call_disabled_sources(monkeypatch, enabled):
    called = []
    for source, name in (("vector", "_vector_recall"), ("kg", "_kg_recall"),
                         ("bm25", "_bm25_recall"), ("table", "_table_recall"),
                         ("multi_query", "_multi_query_recall_wrapper")):
        def recall(*args, _source=source, **kwargs):
            called.append(_source)
            return [_candidate(_source)]
        monkeypatch.setattr(retrieval, name, recall)
    config = RetrievalConfig()
    config.enabled_sources = enabled  # fails on old runtime even before constructor exists
    result = retrieval.multi_path_recall(
        retrieval.PreprocessedQuery("raw", "rewritten", "metric", []), [[1.0]],
        object(), config, kg_graph=object(), bm25_index=object(), table_index=object(),
        embedding_client=object(),
    )
    assert set(called) == set(enabled)
    assert {source for source, hits in result} == set(enabled)


def test_multi_query_requires_vector_permission(monkeypatch):
    called = []
    monkeypatch.setattr(retrieval, "_vector_recall", lambda *a: [])
    monkeypatch.setattr(retrieval, "_multi_query_recall_wrapper", lambda *a: called.append(True) or [])
    config = RetrievalConfig(enable_multi_query=True)
    config.enabled_sources = ("multi_query",)
    retrieval.multi_path_recall(
        retrieval.PreprocessedQuery("raw", "new", "metric", []), [[1.0]], object(),
        config, embedding_client=object(),
    )
    assert called == []


def test_bm25_pipeline_never_embeds_or_rescues_other_sources(monkeypatch, offline_preprocess):
    def forbidden(*args, **kwargs):
        pytest.fail("disabled evidence path was called")
    monkeypatch.setattr(retrieval, "_embed_queries_with_fallback", forbidden)
    monkeypatch.setattr(retrieval, "global_community_recall", forbidden)
    monkeypatch.setattr(retrieval, "_priority_kg_rescue_candidates", forbidden)
    monkeypatch.setattr(retrieval, "_scenario_metric_table_rescue_candidates", forbidden)
    monkeypatch.setattr(retrieval, "_bm25_recall", lambda *a: [_candidate("bm25")])
    monkeypatch.setattr(retrieval, "_scenario_metric_text_rescue_candidates", lambda *a: [])
    pipeline = retrieval.RetrievalPipeline(object(), object(), kg_graph=nx.Graph(),
                                           bm25_index=object(), table_index=object())
    config = RetrievalConfig(enable_global_mode=True, enable_cross_encoder=False)
    config.enabled_sources = ("bm25",)
    result = pipeline.retrieve("整体总结", retrieval_config=config)
    assert [chunk.source for chunk in result.chunks] == ["bm25"]
    trace = result.pipeline["effective_config"]
    assert trace["allowed_sources"] == ["bm25"]
    assert trace["executed_sources"] == ["bm25"]
    assert trace["stages"]["normal"]["kg"]["reason"] == "source_disabled"
    assert trace["stages"]["global"]["community"]["reason"] == "source_disabled"
    assert trace["cross_encoder"]["executed"] is False


def test_global_empty_result_falls_back_with_same_mask(monkeypatch, offline_preprocess):
    called = []
    monkeypatch.setattr(retrieval, "global_community_recall", lambda **kw: {
        "community_hits": [], "descendant_hits": [], "selected_communities": []})
    monkeypatch.setattr(retrieval, "_embed_queries_with_fallback", lambda *a: pytest.fail("unexpected embedding"))
    monkeypatch.setattr(retrieval, "_kg_recall", lambda *a: called.append("kg") or [])
    monkeypatch.setattr(retrieval, "_bm25_recall", lambda *a: pytest.fail("disabled bm25"))
    config = RetrievalConfig(enable_global_mode=True, enable_cross_encoder=False)
    config.enabled_sources = ("kg",)
    result = retrieval.RetrievalPipeline(None, None, kg_graph=nx.Graph(), bm25_index=object()).retrieve(
        "整体总结", retrieval_config=config)
    assert called == ["kg"]
    assert result.pipeline["effective_config"]["executed_sources"] == ["kg"]


def test_generator_does_not_call_disabled_supplement_paths(monkeypatch, isolated_lineage):
    config = RetrievalConfig(enable_cross_encoder=False)
    config.enabled_sources = ("bm25",)
    result = retrieval.RetrievalResult(
        [retrieval.RetrievalChunk("b1", "ordinary software test evidence", 1.0, "bm25")],
        1, {}, "hybrid", [],
    )
    pipeline = SimpleNamespace(config=RetrievalConfig(), retrieve=lambda *a, **kw: result,
                               kg_graph=nx.Graph(), vector_store=object(), embedding_client=object())
    def forbidden(*args, **kwargs):
        pytest.fail("disabled generator supplement called")
    monkeypatch.setattr(generator, "_supplement_context_with_retrieved_kg_chunks", forbidden)
    monkeypatch.setattr(generator, "_targeted_storage_claim_rescue_chunks", forbidden)
    monkeypatch.setattr(generator, "generate_answer", lambda **kw: generator.GenerationResult("test [b1]"))
    answer = generator.RAGGenerator(pipeline, generator.GenerationConfig()).generate(
        "储能使产量降低，对吗？", retrieval_config=config)
    assert answer["metadata"]["effective_config"]["allowed_sources"] == ["bm25"]
    assert answer["metadata"]["effective_config"]["budget"]["prompt_max_context_tokens"] == 12000
    assert answer["metadata"]["effective_config"]["stages"]["generator_rescue"]["vector"]["status"] == "skipped"


def test_explicit_mask_rejects_legacy_fallback_before_conversation(monkeypatch):
    monkeypatch.setattr(route, "_init_rag_pipeline", lambda: False)
    monkeypatch.setattr("conversation.get_conversation_manager", lambda: pytest.fail("conversation should not start"))
    response = None
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as caught:
        response = asyncio.run(route.rag_query(QueryRequest(query="test", options=QueryOptions(enabled_sources=["bm25"])), request=admin_request()))
    assert caught.value.status_code == 503
    assert response is None


def test_simultaneous_configs_do_not_mutate_shared_pipeline(monkeypatch, offline_preprocess):
    monkeypatch.setattr(retrieval, "_embed_queries_with_fallback", lambda *a: ([], None))
    monkeypatch.setattr(retrieval, "_kg_recall", lambda *a: [_candidate("kg")])
    monkeypatch.setattr(retrieval, "_bm25_recall", lambda *a: [_candidate("bm25")])
    shared = RetrievalConfig(enable_cross_encoder=False)
    pipeline = retrieval.RetrievalPipeline(None, None, config=shared, kg_graph=nx.Graph(), bm25_index=object())
    configs = [RetrievalConfig(enable_cross_encoder=False), RetrievalConfig(enable_cross_encoder=False)]
    configs[0].enabled_sources = ("bm25",)
    configs[1].enabled_sources = ("kg",)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda cfg: pipeline.retrieve("test", retrieval_config=cfg), configs))
    assert pipeline.config is shared
    assert getattr(shared, "enabled_sources", None) is None
    assert [r.pipeline["effective_config"]["allowed_sources"] for r in results] == [["bm25"], ["kg"]]


def test_direct_config_rejects_unknown_or_empty_mask():
    for value in ([], ["unknown"], "bm25"):
        with pytest.raises(ValueError):
            RetrievalConfig(enabled_sources=value)


def test_generator_non_storage_query_is_not_reported_as_vector_rescue(monkeypatch, isolated_lineage):
    config = RetrievalConfig(enabled_sources=["vector"], enable_cross_encoder=False)
    result = retrieval.RetrievalResult([], 0, {}, "hybrid", [])
    pipeline = SimpleNamespace(config=config, retrieve=lambda *a, **kw: result,
                               vector_store=object(), embedding_client=object(), kg_graph=None)
    monkeypatch.setattr(generator, "generate_answer", lambda **kw: generator.GenerationResult("no answer"))
    answer = generator.RAGGenerator(pipeline, generator.GenerationConfig()).generate("ordinary query")
    entry = answer["metadata"]["effective_config"]["stages"]["generator_rescue"]["vector"]
    assert entry["status"] == "skipped"
    assert entry["reason"] == "query_condition"


def test_kg_supplement_helper_enforces_pipeline_config_when_no_override():
    graph = nx.Graph()
    graph.add_node("n0010", label="forbidden fact")
    config = RetrievalConfig(enabled_sources=["bm25"])
    assert generator._supplement_context_with_retrieved_kg_chunks([], ["n0010"], graph, retrieval_config=config) == []


def test_table_rescue_is_conditional_for_explicit_mask(monkeypatch, offline_preprocess):
    monkeypatch.setattr(retrieval, "preprocess_query", lambda query, **kw: retrieval.PreprocessedQuery(query, query, "hybrid", []))
    def forbidden(*a, **kw):
        pytest.fail("non-metric Table path must not execute")
    monkeypatch.setattr(retrieval, "_table_recall", forbidden)
    monkeypatch.setattr(retrieval, "_scenario_metric_table_rescue_candidates", forbidden)
    result = retrieval.RetrievalPipeline(None, None, table_index=object()).retrieve(
        "ordinary query", retrieval_config=RetrievalConfig(enabled_sources=["table"], enable_cross_encoder=False))
    assert result.chunks == []
    assert result.pipeline["effective_config"]["stages"]["retrieval_rescue"]["table"]["reason"] == "intent_condition"


def test_normal_zero_hits_and_failed_path_are_distinct(monkeypatch, offline_preprocess):
    monkeypatch.setattr(retrieval, "_bm25_recall", lambda *a: [])
    def failed(*a):
        raise RuntimeError("software fixture failure")
    monkeypatch.setattr(retrieval, "_kg_recall", failed)
    result = retrieval.RetrievalPipeline(None, None, kg_graph=nx.Graph(), bm25_index=object()).retrieve(
        "ordinary query", retrieval_config=RetrievalConfig(enabled_sources=["kg", "bm25"], enable_cross_encoder=False))
    stage = result.pipeline["effective_config"]["stages"]["normal"]
    assert stage["bm25"]["status"] == "executed" and stage["bm25"]["candidate_count"] == 0
    assert stage["kg"]["status"] == "failed" and stage["kg"]["candidate_count"] is None


def test_untriggered_retrieval_rescues_are_skipped(monkeypatch, offline_preprocess):
    monkeypatch.setattr(retrieval, "multi_path_recall", lambda **kw: [])
    result = retrieval.RetrievalPipeline(None, None, kg_graph=nx.Graph(), bm25_index=object()).retrieve(
        "ordinary query", retrieval_config=RetrievalConfig(enabled_sources=["kg", "bm25"], enable_cross_encoder=False))
    for source in ("kg", "bm25"):
        entry = result.pipeline["effective_config"]["stages"]["retrieval_rescue"][source]
        assert entry["status"] == "skipped"
        assert entry["reason"] == "query_condition"


def test_table_rescue_failure_is_not_zero_hits(monkeypatch, offline_preprocess):
    monkeypatch.setattr(retrieval, "preprocess_query", lambda query, **kw: retrieval.PreprocessedQuery(query, query, "metric", []))
    monkeypatch.setattr(retrieval, "multi_path_recall", lambda **kw: [])
    class BrokenTable:
        def query(self, **kw):
            raise RuntimeError("software fixture failure")
    result = retrieval.RetrievalPipeline(None, None, table_index=BrokenTable()).retrieve(
        "W1S1 annual ammonia production", retrieval_config=RetrievalConfig(enabled_sources=["table"], enable_cross_encoder=False))
    entry = result.pipeline["effective_config"]["stages"]["retrieval_rescue"]["table"]
    assert entry["status"] == "failed"
    assert entry["candidate_count"] is None


def test_vector_rescue_embedding_failure_is_not_zero_hits(monkeypatch, isolated_lineage):
    class BrokenEmbedding:
        def embed_query(self, query):
            raise TypeError("software fixture failure")
    config = RetrievalConfig(enabled_sources=["vector"], enable_cross_encoder=False)
    pipeline = SimpleNamespace(config=config, retrieve=lambda *a, **kw: retrieval.RetrievalResult([], 0, {}, "hybrid", []),
                               vector_store=object(), embedding_client=BrokenEmbedding(), kg_graph=None)
    monkeypatch.setattr(generator, "generate_answer", lambda **kw: generator.GenerationResult("no answer"))
    answer = generator.RAGGenerator(pipeline, generator.GenerationConfig()).generate("储能使产量降低，对吗？")
    entry = answer["metadata"]["effective_config"]["stages"]["generator_rescue"]["vector"]
    assert entry["status"] == "failed"
    assert entry["candidate_count"] is None


@pytest.mark.parametrize("source", ["kg", "bm25", "table"])
def test_triggered_retrieval_rescue_records_execution(monkeypatch, offline_preprocess, source):
    monkeypatch.setattr(retrieval, "multi_path_recall", lambda **kw: [])
    names = {"kg": "_priority_kg_rescue_candidates", "bm25": "_scenario_metric_text_rescue_candidates",
             "table": "_scenario_metric_table_rescue_candidates"}
    called = []
    for label, name in names.items():
        def rescue(*args, _label=label):
            assert _label == source, "disabled rescue must not be called"
            called.append(_label)
            return [_candidate(_label)]
        monkeypatch.setattr(retrieval, name, rescue)
    result = retrieval.RetrievalPipeline(None, None, kg_graph=nx.Graph(), bm25_index=object(), table_index=object()).retrieve(
        "W1S1 annual ammonia production", retrieval_config=RetrievalConfig(enabled_sources=[source], enable_cross_encoder=False))
    assert called == [source]
    entry = result.pipeline["effective_config"]["stages"]["retrieval_rescue"][source]
    assert entry["status"] == "executed" and entry["candidate_count"] == 1


def test_normal_table_internal_failure_is_recorded(monkeypatch):
    from source_control import build_effective_config
    class BrokenTable:
        def query(self, **kw):
            raise RuntimeError("software fixture failure")
    config = RetrievalConfig(enabled_sources=["table"])
    trace = build_effective_config(config)
    retrieval.multi_path_recall(retrieval.PreprocessedQuery("raw", "new", "metric", []), [], None,
                                config, table_index=BrokenTable(), execution_trace=trace)
    assert trace["stages"]["normal"]["table"]["status"] == "failed"
    assert trace["stages"]["normal"]["table"]["candidate_count"] is None


@pytest.mark.parametrize("outcome", ["request_error", "bad_json", "wrong_type", "empty"])
def test_multi_query_internal_outcomes_are_recorded(monkeypatch, outcome):
    from source_control import build_effective_config
    def respond(*a, **kw):
        if outcome == "request_error":
            raise RuntimeError("software fixture failure before any network")
        content = {"bad_json": "[invalid]", "wrong_type": "[1]", "empty": "[]"}[outcome]
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"choices": [{"message": {"content": content}}]})
    monkeypatch.setattr("requests.post", respond)
    monkeypatch.setenv("LANGEXTRACT_API_KEY", "")
    class Embedding:
        def embed_query(self, text):
            pytest.fail("failed/empty variants must not cause embedding")
    config = RetrievalConfig(enabled_sources=["vector", "multi_query"], enable_multi_query=True)
    trace = build_effective_config(config)
    retrieval.multi_path_recall(retrieval.PreprocessedQuery("raw", "new", "hybrid", []), [], object(),
                                config, embedding_client=Embedding(), execution_trace=trace)
    entry = trace["stages"]["normal"]["multi_query"]
    assert entry["status"] == ("skipped" if outcome == "empty" else "failed")
    assert entry["candidate_count"] == (0 if outcome == "empty" else None)
