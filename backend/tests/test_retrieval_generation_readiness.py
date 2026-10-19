"""Offline behavioral regressions for retrieval and answer generation boundaries."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import networkx as nx
import pytest
import requests
from rank_bm25 import BM25Okapi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generator as g
import retrieval as r
from config import RetrievalConfig


class Response:
    def __init__(self, content="答案", status=200, payload=None, finish="stop"):
        self.status_code = status
        self.payload = payload if payload is not None else {
            "choices": [{"message": {"content": content}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 3, "total_tokens": 12},
        }

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self.payload


@pytest.fixture(autouse=True)
def offline_provider(monkeypatch, tmp_path):
    """Never touch provider credentials, rewrite output, or production lineage."""
    monkeypatch.setattr(r, "_rewrite_cache", r.QueryRewriteCache(tmp_path / "rewrites.sqlite"))
    monkeypatch.setattr(r, "_cross_encoder_cache", {})
    monkeypatch.setattr(requests, "post", lambda *a, **kw: (_ for _ in ()).throw(requests.ConnectionError("offline")))
    monkeypatch.setenv("LANGEXTRACT_API_KEY", "offline-test-placeholder")
    monkeypatch.setenv("LANGEXTRACT_BASE_URL", "https://offline.invalid")
    monkeypatch.setenv("LANGEXTRACT_MODEL_ID", "deepseek-flash")


def cfg(**kw):
    return g.GenerationConfig(api_key="offline", base_url="https://offline.invalid", **kw)


def chunk(text, cid="c00001", **kw):
    return {"chunk_id": cid, "text": text, "score": 1.0, "source": "vector", **kw}


@pytest.mark.parametrize("failure", [requests.Timeout, requests.ConnectionError, requests.RequestException, 429, 503])
@pytest.mark.parametrize("retries", [0, 1])
def test_provider_retries_are_bounded_and_recover(monkeypatch, failure, retries):
    calls, sleeps = [], []
    def post(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            if isinstance(failure, int):
                return Response(status=failure)
            raise failure("unavailable")
        return Response("恢复 [c00001]")
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(g.time, "sleep", sleeps.append)
    result = g.generate_answer([{"role": "user", "content": "问题"}], cfg(max_retries=retries), [chunk("证据")])
    assert len(calls) == retries + 1
    assert all(call["timeout"] == 30 and call["json"]["max_tokens"] == 2048 for call in calls)
    assert result.model_call_attempted
    if retries:
        assert result.answer_text == "恢复 [c00001]"
        assert result.cited_sources == ["c00001"] and result.model_output_received
    else:
        assert result.finish_reason == "error" and not result.model_output_received
        assert "检索结果摘要" in result.answer_text and "证据" in result.answer_text
    assert sleeps == ([2.0 if failure == 429 else 1.0] if retries and isinstance(failure, int) else [])


@pytest.mark.parametrize("payload", [{"choices": []}, {"choices": [{"message": {"content": None}}]}, {"choices": [{"message": {"content": 9}}]}])
def test_invalid_provider_response_returns_structured_evidence(monkeypatch, payload):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: Response(payload=payload))
    result = g.generate_answer([], cfg(), [chunk("可追溯证据")])
    assert result.finish_reason == "error" and "可追溯证据" in result.answer_text
    assert not result.model_output_received


@pytest.mark.parametrize("answer,finish,notice", [(" 无来源 ", "length", "长度限制"), ("无来源", "stop", "未包含引用"), ("文档未提及", "stop", None), ("Not mentioned", "stop", None), ("错误 [c99999]", "stop", "未在检索结果中找到")])
def test_answer_notices_preserve_raw_output(monkeypatch, answer, finish, notice):
    captured = []
    def post(*a, **kw):
        captured.append(kw)
        return Response(answer, finish=finish)
    monkeypatch.setattr(requests, "post", post)
    result = g.generate_answer([], cfg(model="deepseek-v4-pro"), [chunk("证据")])
    assert result.raw_model_answer == answer and result.finish_reason == finish
    assert result.token_usage["total_tokens"] == 12
    assert captured[0]["json"]["thinking"] == {"type": "disabled"}
    assert "extra_body" not in captured[0]["json"]
    if notice:
        assert notice in result.answer_text
    else:
        assert "未包含引用" not in result.answer_text


def test_fallback_summary_groups_deduplicates_and_truncates():
    long_text = "甲" * 150 + "。" + "乙" * 200
    contexts = [chunk(long_text, section_title="节", label="实体"), chunk(long_text), chunk("", source="table"), chunk("丙" * 350, source="kg", label="实体")]
    text = g._build_structured_fallback_summary(contexts)
    assert text.count("甲" * 150) == 1 and "乙" * 200 not in text
    assert "**节**" in text and "暂无相关内容" in text and "丙" * 280 + "…" in text
    assert text.count("- 实体") == 1
    assert g._build_structured_fallback_summary([]) == "系统繁忙，请稍后重试。"
    assert g._extract_query_from_messages([{"role": "assistant", "content": "x"}]) == ""


@pytest.mark.parametrize("raw,rewrite,reject", [("中文 W4S1", "another term", True), ("中文 W4S1", "W4S1", False), ("wind 4 solar 1", "project report", True), ("问题", "", True), ("问题", "问题细化", False)])
def test_rewrite_rejects_loss_of_original_anchors(raw, rewrite, reject):
    assert r._should_reject_rewrite(raw, rewrite) is reject


@pytest.mark.parametrize("cached,entity_types", [(True, "invalid"), (False, "invalid"), (True, ["metric"]), (False, ["metric"])])
def test_preprocessing_cache_and_provider_normalize_entity_types(monkeypatch, cached, entity_types):
    payload = {"rewritten": "查询预算", "intent": "metric", "entity_types": entity_types, "table_conditions": ["budget > 5"]}
    calls = []
    def post(*a, **kw):
        calls.append(kw)
        return Response("```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```")
    monkeypatch.setattr(requests, "post", post)
    history = [{"role": "user", "content": "之前的问题"}]
    if cached:
        key = r._build_rewrite_cache_key("query_preprocess", "预算", "deepseek-flash", "https://offline.invalid", history)
        r._rewrite_cache.set(key, payload)
    result = r.preprocess_query("预算", chat_history=history)
    assert result.rewritten == "查询预算" and result.table_conditions == ["budget > 5"]
    assert result.entity_types == (entity_types if isinstance(entity_types, list) else [])
    assert len(calls) == (0 if cached else 1)
    if calls:
        assert "之前的问题" in calls[0]["json"]["messages"][0]["content"]
        assert r.preprocess_query("预算", chat_history=history) == result
        assert len(calls) == 1


def test_preprocess_cache_read_write_failure_is_tolerated(monkeypatch):
    class BrokenCache:
        def get(self, key):
            raise OSError("read")
        def set(self, key, value):
            raise OSError("write")
    monkeypatch.setattr(r, "_rewrite_cache", BrokenCache())
    monkeypatch.setattr(requests, "post", lambda *a, **kw: Response('{"rewritten":"enterprise project report","entity_types":["metric"]}'))
    result = r.preprocess_query("Python 标题 W4S1 图")
    assert result.rewritten == result.original
    assert {"method", "paper_metadata", "reference", "dataset"} <= set(result.entity_types)


def test_cache_explicit_path_and_lazy_default(monkeypatch, tmp_path):
    monkeypatch.setattr(r, "_rewrite_cache", None)
    monkeypatch.setattr(r, "REWRITE_CACHE_PATH", tmp_path / "lazy.sqlite")
    first = r.get_query_rewrite_cache()
    assert r.get_query_rewrite_cache() is first
    other = r.get_query_rewrite_cache(tmp_path / "other.sqlite")
    other.set("key", {"中文": 1})
    assert other.get("key") == {"中文": 1} and first.get("key") is None


def test_embeddings_original_variant_and_failure():
    class Embeddings:
        def embed_queries(self, texts):
            assert texts == ["重写", "原始"]
            return [[1.0], [2.0]]
    assert r.embed_queries(r.PreprocessedQuery("原始", "重写", "hybrid", []), Embeddings(), True) == [[1.0], [2.0]]
    assert r._embed_queries_with_fallback(r.PreprocessedQuery("a", "a", "hybrid", []), None) == ([], "embedding_client_unavailable")
    class Broken:
        def embed_queries(self, texts):
            raise ValueError("invalid embedding")
    assert r._embed_queries_with_fallback(r.PreprocessedQuery("a", "a", "hybrid", []), Broken()) == ([], "invalid embedding")


@pytest.mark.parametrize("error", [ImportError, ValueError, r.CrossEncoderUnavailableError])
def test_cross_encoder_predict_error_preserves_coarse_order(monkeypatch, error):
    class Encoder:
        def predict(self, pairs):
            raise error("offline")
    monkeypatch.setitem(r._cross_encoder_cache, "test", Encoder())
    items = [chunk("one", "c00002"), chunk("two", "c00001")]
    result, reason = r.cross_encoder_rerank("q", items, 1, "test")
    assert result == items[:1]
    assert reason == ("cross_encoder_import_error" if error is ImportError else "cross_encoder_unavailable")


def test_cross_encoder_success_limits_text_and_breaks_score_ties(monkeypatch):
    class Encoder:
        def predict(self, pairs):
            assert len(pairs[0][1]) == 512
            return [0.7, 0.7]
    model = Encoder()
    monkeypatch.setitem(r._cross_encoder_cache, "test", model)
    assert r.get_cross_encoder("test") is model
    result, reason = r.cross_encoder_rerank("q", [chunk("x" * 900, "c00002"), chunk("y", "c00001")], 2, "test")
    assert reason is None and len(result) == 2
    assert [r.stable_key(c) for c in result] == sorted(r.stable_key(c) for c in result)
    assert all(c["rerank_score"] == 0.7 for c in result)
    monkeypatch.setitem(r._cross_encoder_cache, "missing", r._CROSS_ENCODER_UNAVAILABLE)
    with pytest.raises(r.CrossEncoderUnavailableError):
        r.get_cross_encoder("missing")
    assert r._budgeted_cross_encoder_rerank("q", result, 1, 0) == (result[:1], True, "timeout")


@pytest.mark.parametrize("protected_first,protected_second,first_score,second_score,winner", [(False, True, 3, 1, "c00002"), (True, False, 1, 3, "c00001"), (False, False, 1, 3, "c00002"), (False, False, 3, 1, "c00001")])
def test_near_duplicate_filter_prioritizes_protected_evidence(protected_first, protected_second, first_score, second_score, winner):
    items = [r.RetrievalChunk("c00001", "identical evidence alpha", first_score, "vector", metadata={"protected_evidence": protected_first}), r.RetrievalChunk("c00002", "identical evidence alpha", second_score, "kg", metadata={"protected_evidence": protected_second}), r.RetrievalChunk("c00003", "", 0, "kg")]
    result = r._dedup_by_jaccard(items)
    assert [c.chunk_id for c in result] == [winner, "c00003"]


def test_bm25_real_model_handles_unwrapped_and_missing_chunks():
    corpus = [["alpha"], ["beta"], ["gamma"]]
    model = BM25Okapi(corpus)
    result = r._bm25_recall("alpha", model, RetrievalConfig())
    assert len(result) == 1 and result[0]["chunk_id"] == "bm25_0" and result[0]["text"] == ""
    assert r._bm25_recall("alpha", object(), RetrievalConfig()) == []
    chunks = [SimpleNamespace(text="alpha"), SimpleNamespace(text="beta"), SimpleNamespace(text="gamma")]
    assert r._bm25_recall("alpha", (model, chunks), RetrievalConfig())[0]["chunk_id"] == "bm25_0"


@pytest.mark.parametrize("query", ["W4S1 是什么", "标题", "预算", "没有命中"])
def test_indexed_kg_fallback_searches_real_graph_across_wrong_types(query):
    graph = nx.DiGraph()
    graph.add_node("n0001", entity_type="dataset", label="W4S1 wind 4 solar 1", properties={"name": "W4S1", "description": "场景"})
    graph.add_node("n0002", entity_type="paper_metadata", label="论文标题", properties={"title": "标题", "id": "XYZ"})
    graph.add_node("n0003", entity_type="metric", label="预算", properties={"name": "预算", "value": "10"})
    result = r.indexed_kg_recall(r.PreprocessedQuery(query, query, "hybrid", ["wrong_type"]), graph, RetrievalConfig(kg_top_k=5))
    if query == "没有命中":
        assert result == []
    else:
        assert result and all(c["source"] == "kg" for c in result)
        assert query.split()[0] in result[0]["text"]


@pytest.mark.parametrize("text,expected", [('not json', ''), ('{"entity":broken}', ''), ('{"entity": [1]}', ''), ('{"entity":{"label":"x","properties":[]}}', 'x'), ('{"entity":{"properties":{"name":"a","value":"b"}}}', 'a；b')])
def test_raw_kg_summary_validates_structure(text, expected):
    assert g._summarize_raw_kg_json(text) == expected


@pytest.mark.parametrize("text,expected", [("2010 2020 2030 2010", "2010 / 2020 / 2030"), ("Figure 1 Figure 2 Figure 1", "Figure 1 / Figure 2"), ("nothing", "")])
def test_structured_inventory_summary_deduplicates(text, expected):
    assert g._summarize_structured_inventory_snippet(text) == expected


def test_inventory_repairs_only_supported_distinct_figures():
    contexts = [chunk(""), chunk("irrelevant"), chunk("Figure 1 风电"), chunk("Figure 1 风电"), chunk("Figure 2 光伏", "c00002")]
    answer = g._repair_inventory_answer_text("列出所有图", contexts)
    assert answer.count("- Figure 1") == 1 and "Figure 2 光伏 [c00002]" in answer
    assert "irrelevant" not in answer
    assert g._repair_inventory_answer_text("列出所有图", [chunk("Figure 1 风电")]) == ""


def test_entity_supplement_uses_tools_and_section_titles_without_numbers():
    contexts = [chunk("Python 3.10 Pandas CBC 12345", section_title="方法"), chunk("Pandas", "c00002", section_title="方法")]
    entities = g._extract_key_entities_from_chunks(contexts)
    assert entities == ["Python 3.10", "Pandas", "CBC", "方法"]
    assert "12345" not in g._supplement_key_entities("答案", contexts, "q")
    assert g._supplement_key_entities("Python 3.10 Pandas CBC 方法", contexts, "q") == "Python 3.10 Pandas CBC 方法"
    assert g._supplement_key_entities("答案", [], "q") == "答案"


def test_kg_supplement_retains_only_retrieved_ids_and_respects_disabled_scope():
    graph = nx.DiGraph()
    graph.add_node("n0001", label="允许", properties={"value": "10"}, document_id="doc")
    graph.add_node("n0002", label="未检索", properties={})
    result = g._supplement_context_with_retrieved_kg_chunks([], ["bad", "n9999", "n0001", "n0001"], graph)
    assert len(result) == 1 and result[0]["chunk_id"] == "n0001"
    assert result[0]["metadata"]["document_id"] == "doc" and not result[0]["metadata"]["span_verified"]
    assert "未检索" not in result[0]["text"]
    assert g._supplement_context_with_retrieved_kg_chunks([], ["n0001"], graph, RetrievalConfig(enabled_sources=["vector"])) == []


@pytest.mark.parametrize("query,tool", [("visualization library", "Matplotlib"), ("pandas role", "Pandas"), ("python implementation", "Python 3.10")])
def test_completion_emits_readable_supported_chinese_answer(query, tool):
    answer = g._complete_answer_text("未完整回答", query, [chunk(tool)])
    assert tool in answer and "[c00001]" in answer
    assert "???" not in answer
    assert any("\u4e00" <= c <= "\u9fff" for c in answer)


def test_method_inventory_extracts_actual_tool_names():
    assert g._summarize_structured_inventory_snippet("MILP Pandas Python Pandas") == "MILP / Pandas / Python"


@pytest.mark.parametrize("with_value,without_value,expected", [("12", "10", True), ("8", "10", False), ("bad", "10", False)])
def test_storage_refutation_compares_actual_metrics(with_value, without_value, expected):
    contexts = [chunk(json.dumps({"entity": {"properties": {"name": "annual ammonia production with storage", "value": with_value}}}), "n0001"), chunk(json.dumps({"entity": {"properties": {"name": "annual ammonia production without storage", "value": without_value}}}), "n0002")]
    answer = g._deterministic_storage_claim_refutation("储能使产量降低对吗", contexts)
    if expected:
        assert "12吨" in answer and "10吨" in answer and "[n0001] [n0002]" in answer
    else:
        assert answer is None


def test_citations_canonical_exactness_legacy_alias_and_formats():
    eid = "ev1_" + "a" * 64
    missing = "ev1_" + "b" * 64
    result = g.verify_citations(f"[c00001] [n0001] [{eid}] [{missing}]", [chunk('{"node_id":"n0001"}', "prefix_c00001", evidence_id=eid)])
    assert result == (False, [missing], ["c00001", eid, "n0001"])
    assert g.validate_output_format('| a | b |\n|---|---|\n```json\n{}\n``` [n0001]') == {"has_table": True, "has_json": True, "has_citations": True}


@pytest.mark.parametrize("mode", ["rows", "export", "query", "export_failure"])
def test_scenario_metric_table_rescue_ignores_unrelated_and_malformed_rows(mode):
    rows = [None, {"column_name": "unrelated", "column_value": "1", "context": []}, {"column_name": "弃电量", "column_value": "30", "context": {"scenario": "W4S2"}}, {"column_name": "unknown", "column_value": "2", "context": {"scenario": "W4S1"}}, {"column_name": "弃电量", "column_value": "173.7", "context": {"scenario": "W4S1"}, "sheet_name": "data", "row_number": 2}]
    class Table:
        def export_rows(self):
            if mode == "export_failure":
                raise OSError("export unavailable")
            return rows if mode == "export" else []
        def query(self, conditions, top_k):
            assert conditions is None and top_k >= 5
            return rows
    table = Table()
    if mode == "rows":
        table.rows = rows
    query = r.PreprocessedQuery("W4S1 弃电量", "W4S1 弃电量", "metric", [])
    result = r._scenario_metric_table_rescue_candidates(query, table, RetrievalConfig())
    assert len(result) == 1 and "173.7" in result[0]["text"]
    assert result[0]["metadata"]["protected_evidence"]
    assert r._candidate_matches_metric_query(query.rewritten, result[0])
    assert r._scenario_metric_table_rescue_candidates(query, table, RetrievalConfig(enabled_sources=["kg"])) == []
    assert r._scenario_metric_table_rescue_candidates(r.PreprocessedQuery("q", "q", "hybrid", []), table, RetrievalConfig(enabled_sources=["table"])) == []


def test_scenario_metric_text_rescue_needs_alias_metric_and_valid_chunk():
    chunks = [SimpleNamespace(chunk_id="", text="W4S1 弃电量"), SimpleNamespace(chunk_id="empty", text=""), SimpleNamespace(chunk_id="wrong", text="W4S2 弃电量"), SimpleNamespace(chunk_id="no_metric", text="W4S1 other"), SimpleNamespace(chunk_id="c00001", text="W4S1 弃电量173.7", metadata=SimpleNamespace(source_file="manual"))]
    query = r.PreprocessedQuery("W4S1 弃电量", "W4S1 弃电量", "metric", [])
    result = r._scenario_metric_text_rescue_candidates(query, (None, chunks), RetrievalConfig())
    assert len(result) == 1 and result[0]["chunk_id"] == "c00001"
    assert result[0]["metadata"]["rescue_reason"] == "scenario_metric_text"
    assert r._scenario_metric_text_rescue_candidates(query, None, RetrievalConfig()) == []
    assert r._scenario_metric_text_rescue_candidates(query, (None, chunks), RetrievalConfig(enabled_sources=["kg"])) == []


def test_global_community_recall_filters_missing_duplicate_and_wrong_type_nodes():
    graph = nx.DiGraph()
    graph.add_node("n0001", label="alpha budget", entity_type="metric", properties={})
    graph.add_node("n0002", label="alpha", entity_type="person_role", properties={})
    graph.add_node("n0003", label="unrelated", entity_type="metric", properties={})
    records = [{"community_id": "comm1", "summary_text": "alpha budget", "node_ids": ["missing", "n0002", "n0003", "n0001", "n0001"], "top_entity_types": {"metric": 2}, "size": 5}]
    result = r.global_community_recall(r.PreprocessedQuery("alpha", "alpha", "metric", ["metric"]), graph, RetrievalConfig(kg_top_k=1), {"communities": records})
    assert len(result["descendant_hits"]) == 1 and result["descendant_hits"][0]["chunk_id"] == "n0001"
    assert result["descendant_hits"][0]["metadata"]["community_id"] == "comm1"
    assert r.global_community_recall(r.PreprocessedQuery("z", "z", "hybrid", []), graph, RetrievalConfig(), {"communities": []})["community_hits"] == []
    fallback = r.global_community_recall(r.PreprocessedQuery("zzzz", "zzzz", "hybrid", []), graph, RetrievalConfig(), {"communities": records})
    assert fallback["community_hits"][0]["score"] == 0.1 and fallback["descendant_hits"] == []


@pytest.mark.parametrize("query,text", [("改进方向", "改进方向包含优化"), ("多市场改进方向", "改进方向加入碳交易耦合"), ("方法是什么", "MILP"), ("哪个库", "Pandas")])
def test_direct_lookup_rescue_accepts_supported_tool_and_method(query, text):
    assert r._candidate_matches_direct_lookup_query(query, chunk(text))
    assert not r._candidate_matches_direct_lookup_query(query, chunk("unrelated"))


@pytest.mark.parametrize("query,text,expected", [("问题二问题三差异", "问题二MILP 问题三LP", True), ("建模方法对比", "MILP LP", True), ("方法对比", "MILP", True), ("问题二问题三差异", "无信息", False), ("问题二方法", "问题二MILP", True), ("支撑价值提升了多少", "支撑价值10元/吨", True), ("产量提升了多少", "产量10903 9023", True), ("降低对吗", "并未证明", True)])
def test_comparison_and_claim_rescue_require_evidence(query, text, expected):
    function = r._has_comparison_rescue if r._is_comparison_query(query) else r._has_claim_verification_rescue
    assert function(query, [chunk(text)]) is expected


def test_exact_evidence_rescue_distinguishes_scope_and_numbers():
    assert r._has_extrema_metric_rescue("最低最高元/吨", [chunk("最低100最高200元/吨")])
    assert not r._has_extrema_metric_rescue("最低最高元/吨", [chunk("最低最高元/吨")])
    assert r._has_alias_definition_rescue("W4S1含义", [chunk("irrelevant"), chunk("W4S1表示风光场景", source="kg")])
    assert not r._has_alias_definition_rescue("W4S1含义", [chunk("W4S1", source="vector")])
    assert not r._has_figure_reference_rescue("所有图2", [chunk("图2")])
    assert r._adaptive_rerank_max_candidates("all", RetrievalConfig(rerank_max_candidates=0)) == 0


def test_candidate_projection_grounds_nearby_pages_and_strips_unsafe_metadata():
    graph = nx.DiGraph()
    for n, page in enumerate([1, 2, 3], 1):
        graph.add_node(f"n{n:04d}", label="alpha", entity_type="metric", properties={"value": "x"}, page_idx=page)
    candidate = chunk("alpha", metadata={"page_idx": 2, "section_path": ["Budget"], "entity_ids": "bad", "secret_internal": "not prompt safe"})
    projected = r.project_candidate(candidate, graph)
    assert projected["section_title"] == "Budget" and projected["entity_ids"][0] == "n0002"
    assert "secret_internal" not in projected["metadata"]
    assert r._infer_entity_ids_from_candidate({"text": "", "chunk_id": ""}, graph) == []


@pytest.mark.parametrize("query,expected", [("文档什么", False), ("W4S1 弃电量", True), ("impact factor 是多少", True)])
def test_unsupported_query_refusal_uses_actual_support(query, expected):
    contexts = [chunk("ordinary unrelated data")]
    if query == "W4S1 弃电量":
        assert not g._chunk_has_meaningful_support(query, "W4S2 弃电量")
        assert g._chunk_has_meaningful_support(query, "W4S1 弃电量173.7")
    else:
        assert g._should_short_circuit_unsupported_query(query, contexts) is expected
    assert not g._should_short_circuit_unsupported_query("impact factor 是多少", [chunk("impact factor 5")])


def test_generic_claim_refutation_and_storage_guard_conditions():
    supported = [chunk("并未降低，产量增加")]
    answer = g._deterministic_claim_refutation("措施反而降低对吗", supported)
    assert answer.startswith("不是") and "[c00001]" in answer
    assert g._find_claim_refutation_chunk("是否增加", supported) is None
    assert g._find_claim_refutation_chunk("减少对吗", [chunk("无证据")]) is None
    assert not g._needs_storage_claim_rescue("储能产量是多少")
    assert not g._needs_storage_claim_rescue("降低对吗")
    assert g._targeted_storage_claim_rescue_chunks("储能产量减少对吗", SimpleNamespace(config=RetrievalConfig(enabled_sources=["kg"]))) == []
    assert g._targeted_storage_claim_rescue_chunks("普通问题", SimpleNamespace()) == []
    assert g._targeted_storage_claim_rescue_chunks("储能产量减少对吗", SimpleNamespace()) == []


@pytest.mark.parametrize("broken", [False, True])
def test_pipeline_optimizer_and_dictionary_are_optional(monkeypatch, tmp_path, broken):
    import services.lineage_store as lineage
    store = lineage.LineageStore(tmp_path / "lineage")
    monkeypatch.setattr(lineage, "get_lineage_store", lambda: store)
    class Optimizer:
        def optimize(self, raw, history):
            if broken:
                raise ValueError("bad optimizer")
            return SimpleNamespace(enhanced_query=raw + " alpha")
    class Domain:
        def expand_query(self, query):
            if broken:
                raise OSError("missing dictionary")
            return query + " beta"
        def get_related_hints(self, query):
            return "alpha 是术语"
    graph = nx.DiGraph()
    graph.add_node("n0001", entity_type="metric", label="alpha", properties={"value": "10"})
    config = RetrievalConfig(enable_cross_encoder=False, include_evidence_trace=True, enabled_sources=["kg"])
    pipeline = r.RetrievalPipeline(None, None, graph, config=config, query_optimizer=Optimizer(), domain_dict=Domain())
    result = pipeline.retrieve("alpha")
    assert result.chunks and result.chunks[0].source == "kg"
    assert result.domain_hint == ("" if broken else "alpha 是术语")
    answer = g.RAGGenerator(pipeline, cfg(max_retries=0)).generate("alpha")
    assert answer["sources"] and answer["metadata"]["effective_config"]["budget"]["prompt_max_context_tokens"] == 12000
    assert answer["metadata"]["evidence_trace"]
    assert list((tmp_path / "lineage").glob("*.json"))


def test_cross_encoder_initialization_failure_is_cached(monkeypatch):
    calls = []
    class Broken:
        def __init__(self, *a, **kw):
            calls.append(a)
            raise OSError("offline weights")
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(CrossEncoder=Broken))
    for _ in range(2):
        with pytest.raises(r.CrossEncoderUnavailableError):
            r.get_cross_encoder("offline-model")
    assert len(calls) == 1


def test_cross_encoder_rechecks_cache_after_lock(monkeypatch):
    model = object()
    class Lock:
        def __enter__(self):
            r._cross_encoder_cache["race"] = model
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(r, "_cross_encoder_cache_lock", Lock())
    assert r.get_cross_encoder("race") is model
    class MissingLock(Lock):
        def __enter__(self):
            r._cross_encoder_cache["race2"] = r._CROSS_ENCODER_UNAVAILABLE
    monkeypatch.setattr(r, "_cross_encoder_cache_lock", MissingLock())
    with pytest.raises(r.CrossEncoderUnavailableError):
        r.get_cross_encoder("race2")


@pytest.mark.parametrize("text,expected", [("证书规化店量", "整数规划电量"), ("PYTHN nmpy panda matplot plup", "Python NumPy Pandas Matplotlib PuLP"), ("wind 4 solar 1 W4S1", "wind 4 solar 1 W4S1")])
def test_query_typo_normalization_preserves_existing_aliases(text, expected):
    assert r._normalize_query_typos(text) == expected


def test_kg_fallback_title_and_metric_boosts_without_specific_entity_types():
    graph = nx.DiGraph()
    graph.add_node("n0001", label="W4S1", entity_type="dataset", properties={"name": "maximum curtailment scenario"})
    graph.add_node("n0002", label="标题XYZ", entity_type="paper_metadata", properties={"title": "XYZ", "field": "title"})
    for query in ["W4S1 是什么", "XYZ 标题"]:
        preprocessed = r.PreprocessedQuery("original question", query, "hybrid", [])
        result = r.indexed_kg_recall(preprocessed, graph, RetrievalConfig())
        assert result and result[0]["protected_evidence"]
    assert r.indexed_kg_recall(r.PreprocessedQuery("a", "a", "hybrid", []), nx.DiGraph(), RetrievalConfig()) == []


@pytest.mark.parametrize("text", ['{"entity":{"entity_type":"metric","properties":{"name":"curtailment energy","value":"173.7","scenario":"W4S1"}}}', '[]', '{bad'])
def test_metric_candidate_parses_raw_json_without_crashing(text):
    result = r._candidate_matches_metric_query("W4S1 弃电量", chunk(text))
    assert result is (text.startswith('{"entity"'))


@pytest.mark.parametrize("invalid", ['{"entity":broken}', '{"entity":[1]}', '{"entity":{"properties":[1]}}', '{"entity":{"properties":{"name":"annual ammonia production","value":""}}}'])
def test_storage_metrics_reject_malformed_entity_shape(invalid):
    assert g._extract_storage_production_metrics([chunk(invalid)]) is None


@pytest.mark.parametrize("query,text", [("visualization", "irrelevant"), ("pandas role", "irrelevant"), ("python implementation", "irrelevant"), ("W4S1 是什么", "irrelevant")])
def test_completion_does_not_invent_tools_without_support(query, text):
    assert g._complete_answer_text("已有答案", query, [chunk(text)]) == "已有答案"


def test_storage_refutation_guard_and_snippet_ranking():
    contexts = [chunk("9023 10903 no relevant storage marker"), chunk("表 with storage 97200 9023 10903"), chunk("加装储能使产量从9023提升至10903", "c00002")]
    assert g._find_storage_contrast_chunk(contexts)["chunk_id"] == "c00002"
    assert g._extract_storage_contrast_snippet("其他句子。9023 10903 97200") == "其他句子。9023 10903 97200"
    assert g._deterministic_storage_claim_refutation("普通问题", contexts) is None
    assert g._deterministic_storage_claim_refutation("储能产量", contexts) is None
    assert g._deterministic_storage_claim_refutation("储能降低", contexts) is None


def test_storage_rescue_vector_boundary_filters_unrelated_results():
    class Embedding:
        def embed_query(self, query):
            assert "10903" in query
            return [1.0]
    class Store:
        def search(self, query_vector, top_k, **kw):
            assert top_k == 2
            return [chunk("普通信息"), chunk("储能使9023提升10903", "c00002")]
    pipeline = SimpleNamespace(config=RetrievalConfig(), embedding_client=Embedding(), vector_store=Store())
    result = g._targeted_storage_claim_rescue_chunks("储能产量降低对吗", pipeline)
    assert len(result) == 1 and result[0]["source"] == "vector" and "10903" in result[0]["text"]


def test_repair_preserves_refusal_without_supported_inventory_or_snippet():
    refusal = "文档中未提及此信息"
    assert g._repair_answer_text(refusal, "所有项", [chunk("ordinary")]) == refusal
    assert g._repair_answer_text(refusal, "what", [chunk("")]) == refusal
    assert g._repair_answer_text(refusal, "W4S1 弃电量", [chunk("W4S2 弃电量")]) == refusal
    assert g._looks_like_vague_alias_response("W4S1 表示最大弃电场景", "W4S1 是什么") is False
    assert g._find_supporting_chunk("q", []) is None
    assert g._supports_structured_inventory([]) is False


@pytest.mark.parametrize("query,expected", [("W4S1含义", True), ("W4S1是什么", True), ("xW4S1含义", False), ("W4S1x含义", False), ("W4S1_含义", False)])
def test_alias_definition_uses_ascii_identifier_boundaries(query, expected):
    assert r._is_alias_definition_query(query) is expected
    assert g._is_alias_definition_query(query) is expected
    assert g._scenario_alias_terms(query) == (["w4s1"] if expected else [])


def test_completion_alias_meaning_is_readable_and_cited():
    result = g._complete_answer_text("W4S1 maximum curtailment scenario 173.7 MWh/day curtailment [c00001]", "W4S1含义", [chunk("W4S1 maximum curtailment scenario 173.7 MWh/day")])
    assert "最大弃电场景" in result and "173.7" in result and "[c00001]" in result
    assert "???" not in result


def test_completion_extrema_uses_real_chinese_query_and_cites_both_values():
    result = g._complete_answer_text("仅有部分信息", "最低和最高成本分别多少元/吨", [chunk("最低3554元/吨", "c00001"), chunk("最高7111元/吨", "c00002")])
    assert "最低" in result and "3554" in result and "最高" in result and "7111" in result
    assert "[c00001]" in result and "[c00002]" in result and "???" not in result


@pytest.mark.parametrize("provider_text", ['[]', '[1]', '[" "]', 'no json'])
def test_multi_query_empty_or_invalid_provider_variants_do_not_search(monkeypatch, provider_text):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: Response(provider_text))
    class Embed:
        def embed_query(self, query):
            pytest.fail("Invalid query variants must never be embedded")
    with pytest.raises((r.SourceRecallSkipped, ValueError)):
        r._multi_query_recall_wrapper("original", Embed(), object(), RetrievalConfig(enable_multi_query=True))
    assert r._multi_query_recall_wrapper("original", Embed(), object(), RetrievalConfig(enable_multi_query=False)) == []


def test_vector_recall_deduplicates_same_evidence_using_highest_score():
    class Store:
        def search(self, query_vector, top_k, **kw):
            return [chunk("same", "c00001", score=query_vector[0]), chunk("other", "c00002", score=0.1)]
    result = r._vector_recall([[0.2], [0.9], [9]], Store(), RetrievalConfig(vector_top_k=2))
    assert len(result) == 2 and result[0]["score"] == 0.9
    assert r.cross_encoder_rerank("q", []) == ([], None)


def test_metric_raw_json_requires_metric_type_and_alias():
    text = json.dumps({"entity": {"entity_type": "metric", "properties": {"name": "curtailment energy", "value": "173.7", "scenario": "W4S1"}}})
    assert r._candidate_matches_metric_query("W4S1 弃电量", chunk(text, metadata={"properties": {}}))
    assert not r._candidate_matches_metric_query("W4S2 弃电量", chunk(text))
    assert r._candidate_matches_metric_query("弃电量", chunk(text))
    assert not r._candidate_matches_metric_query("unknown", chunk(text))


def test_summary_inventory_rescue_retains_page_one_metric_evidence():
    contexts = [chunk("summary", source="table"), chunk("ordinary", "n0001", source="kg", metadata={"entity_type": "metric", "page_idx": 1}), chunk("ordinary", "n0002", source="kg", metadata={"entity_type": "metric", "page_idx": 1})]
    assert r._has_summary_metric_inventory_rescue("摘要有哪些产量指标", contexts)
    assert not r._has_summary_metric_inventory_rescue("摘要有哪些产量指标", contexts[:2])
    assert r._candidate_matches_scenario_alias("plain", "W4S1", {}) is False
    assert r._title_or_id_field_boost("plain", "paper_metadata", {}) == 0.0
    assert r._query_exact_match_terms("") == []


def test_table_conflict_demotes_kg_and_preserves_table():
    kg = r.RetrievalChunk("n0001", "budget10", 1, "kg")
    table = r.RetrievalChunk("t", "budget11", 0.8, "table", metadata={"table_data": {"column_name": "budget"}})
    result = r._resolve_cross_path_conflicts([kg, table])
    assert result == [kg, table] and kg.score == 0.9 and table.score == 0.8
    assert r.filter_redundant([chunk("a", section_title="Explicit")])[0].section_title == "Explicit"
    assert len(r._dedup_by_jaccard([r.RetrievalChunk(str(i), "same", 1, "vector") for i in range(3)])) == 1


def test_rewrite_provider_plain_json_without_object_downgrades(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: Response("[]"))
    result = r.preprocess_query("Budget")
    assert result.rewritten == "Budget" and result.intent == "hybrid"


def test_raw_kg_summary_handles_label_without_properties_and_empty_entity():
    assert g._summarize_raw_kg_json('{"entity":{"label":"x","properties":{"name":"x"}}}') == "x"
    assert g._summarize_raw_kg_json('{"entity":{}}') == ""
    assert g._chunk_has_meaningful_support("W4S1", '{"entity":{"label":"W4S1"}}') is False
    assert not g._has_meaningful_support("specific anchors", [chunk("unrelated")])
    assert g._deterministic_refusal_for_query("english") == "This information is not mentioned in the documents."
    assert g._deterministic_refusal_for_query("中文") == "文档中未提及此信息。"


def test_completion_preserves_already_complete_or_insufficient_extrema():
    for query, answer in [("visualization", "Matplotlib is used"), ("pandas role", "Pandas data processing"), ("python implementation", "Python implementation")]:
        assert g._complete_answer_text(answer, query, [chunk("Python Pandas Matplotlib")]) == answer
    assert g._complete_answer_text("已知3554和7111", "最低最高元/吨", [chunk("3554 7111")]) == "已知3554和7111"
    assert g._complete_answer_text("已知", "最低最高元/吨", [chunk("3554")]) == "已知"


def test_storage_rescue_no_evidence_does_not_generate_refutation():
    assert g._needs_storage_claim_rescue("储能产量降低") is False
    assert g._deterministic_claim_refutation("降低对吗", [chunk("plain unrelated")]) is None
    assert g._supplement_context_with_retrieved_kg_chunks([chunk("base")], [], None) == [chunk("base")]


def test_query_terms_do_not_count_generic_words_as_anchors():
    assert g._anchor_query_terms("an x1 a-b 数据") == ["x1", "a-b"]
    assert not g._has_meaningful_support("specific anchor", [chunk("unrelated")])
    assert g._should_short_circuit_unsupported_query("BERT 是什么", [chunk('{"entity":{"label":"BERT"}}')]) is True


def test_support_ranking_prefers_relevant_entity_over_unrelated_prose():
    raw = chunk('{"entity":{"label":"specific budget title"}}', "n0001")
    assert g._find_supporting_chunk("specific budget title", [chunk("unrelated"), raw]) is raw
    assert g._find_chunk_with_terms([chunk("Python"), chunk("ordinary")], "Python", "") == chunk("Python")
    assert g._summarize_raw_kg_json('{"entity":{"properties":[]}}') == ""
    assert g._summarize_raw_kg_json('{"entity":{"properties":{"description":"detail"}}}') == "detail"
    assert g._extract_supporting_snippet("标题", "ordinary。title: A paper") == "title: A paper"


@pytest.mark.parametrize("query,text,expected", [
    ("x1", "x1", False),
    ("x1 x2", "x1 x2", True),
    ("W4S1 弃电量", "W4S2 弃电量", False),
    ("W4S1 弃电量", "W4S1 弃电量173.7MWh", True),
])
def test_meaningful_support_requires_scenario_and_sufficient_anchors(query, text, expected):
    assert g._chunk_has_meaningful_support(query, text) is expected


def test_out_of_scope_marker_searches_past_unrelated_and_raw_entities():
    contexts = [chunk("unrelated"), chunk('{"entity":{"label":"BERT"}}'), chunk("BERT encoder is explicitly documented")]
    assert not g._should_short_circuit_unsupported_query("BERT 是什么", contexts)
    assert g._should_short_circuit_unsupported_query("gpu cost", [chunk("ordinary")])
    assert not g._should_short_circuit_unsupported_query("gpu cost", [chunk("gpu cost is 12")])
    assert g._has_meaningful_support("gpu cost", [chunk("ordinary"), chunk("gpu cost is 12")])


def test_storage_metric_records_ignore_unrelated_and_incomplete_entries():
    def metric(name, value):
        return chunk(json.dumps({"entity": {"properties": {"name": name, "value": value}}}))
    contexts = [chunk("plain"), chunk('{"entity":'), metric("annual ammonia production with storage", ""),
                metric("other annual metric", "12"), metric("annual ammonia production baseline", "10"),
                metric("annual ammonia production with storage", "12"), metric("annual ammonia production without storage", "10")]
    with_storage, without_storage = g._extract_storage_production_metrics(contexts)
    assert with_storage["value"] == "12" and without_storage["value"] == "10"
    answer = g._deterministic_storage_claim_refutation("储能产量降低对吗", contexts)
    assert "12吨" in answer and "10吨" in answer
    assert g._find_claim_refutation_chunk("产量降低对吗", [chunk("无关"), chunk("并未降低，相反增加")])["text"] == "并未降低，相反增加"


def test_storage_rescue_reports_embedding_failure_and_missing_resources():
    from source_control import build_effective_config
    class Embedding:
        def embed_query(self, query):
            raise RuntimeError("offline embedding unavailable")
    configuration = RetrievalConfig()
    trace = build_effective_config(configuration)
    pipeline = SimpleNamespace(config=configuration, embedding_client=Embedding(), vector_store=object())
    assert g._targeted_storage_claim_rescue_chunks("储能产量降低对吗", pipeline, execution_trace=trace) == []
    assert trace["stages"]["generator_rescue"]["vector"]["status"] == "failed"
    assert g._targeted_storage_claim_rescue_chunks("储能产量降低对吗", SimpleNamespace()) == []
    assert g._targeted_storage_claim_rescue_chunks("普通问题", pipeline) == []


def test_completion_does_not_add_unsupported_tools_or_duplicate_resolution():
    for query in ("visualization", "pandas role", "python implementation"):
        assert g._complete_answer_text("original", query, [chunk("ordinary")]) == "original"
    answer = "最大弃电场景（maximum curtailment scenario）"
    assert g._complete_answer_text(answer, "W4S1含义", []) == answer
    assert g._repair_answer_text("文档中未提及此信息", "gpu cost", [chunk("unrelated")]) == "文档中未提及此信息"


def test_metric_candidate_parsing_keeps_type_scenario_and_table_scope():
    candidate = chunk('{"entity":{"entity_type":"metric","properties":{"name":"curtailment energy","value":"173.7","scenario":"W4S1"}}}')
    assert r._candidate_matches_metric_query("W4S1弃电量", candidate)
    assert not r._candidate_matches_metric_query("W4S2弃电量", candidate)
    assert not r._candidate_matches_metric_query("弃电量", chunk('{"entity":{}}'))
    assert not r._candidate_matches_metric_query("弃电量", chunk("[]"))
    assert not r._candidate_matches_metric_query("弃电量", chunk("invalid json"))


def test_redundancy_retains_empty_and_distinct_text_beside_duplicate_cluster():
    chunks = [r.RetrievalChunk(str(i), text, 1, "vector") for i, text in enumerate(["same", "same", "same", "", "distinct"])]
    result = r._dedup_by_jaccard(chunks)
    assert [item.text for item in result] == ["same", "", "distinct"]
