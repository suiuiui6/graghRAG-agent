"""RAG evaluation behavior; only provider/storage boundaries are doubled."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run_evaluation as evaluation_cli
from retrieval import RetrievalChunk, RetrievalResult


@pytest.mark.parametrize("fenced", [False, True, "unclosed"])
def test_judge_parses_json_and_bounds_provider_prompt(monkeypatch, fenced):
    scores = {"recall": 4, "precision": 3, "notes": "中文评价"}
    observed = {}
    def post(url, **kwargs):
        observed.update(url=url, **kwargs)
        raw = json.dumps(scores, ensure_ascii=False)
        if fenced:
            raw = "```json\n" + raw + ("\n```" if fenced != "unclosed" else "")
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"choices": [{"message": {"content": raw}}]})
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setenv("LANGEXTRACT_BASE_URL", "https://example.invalid/v1/")
    result = evaluation_cli.llm_judge("问题", "答" * 3200,
                                      [{"source": "vector", "text": "证" * 600} for _ in range(20)])
    assert result == scores
    assert observed["url"] == "https://example.invalid/v1/chat/completions"
    prompt = observed["json"]["messages"][0]["content"]
    assert "[...truncated...]" in prompt
    assert "答" * 3000 in prompt and "答" * 3001 not in prompt
    assert observed["timeout"] == 60


@pytest.mark.parametrize("failure", ["http", "json", "missing"])
def test_judge_failures_produce_explicit_zero_scores(monkeypatch, failure, capsys):
    def status():
        if failure == "http":
            raise requests.HTTPError("judge unavailable")
    raw = {} if failure == "missing" else {"choices": [{"message": {"content": "not-json"}}]}
    monkeypatch.setattr(requests, "post", lambda *a, **k: SimpleNamespace(raise_for_status=status, json=lambda: raw))
    result = evaluation_cli.llm_judge("问题", "答案", [{}])
    assert {result[k] for k in ["recall", "precision", "relevance", "accuracy", "comprehensiveness"]} == {0}
    assert result["notes"].startswith("Judge error:")
    assert "LLM judge failed" in capsys.readouterr().out


def retrieval_result():
    return RetrievalResult(chunks=[RetrievalChunk("c001", "响应时间为10毫秒。", .9, "vector"),
                                   RetrievalChunk("c002", "检索补充。", .7, "bm25")],
                           total_candidates=12, pipeline={}, query_intent="metric", entity_types_used=["metric"])


@pytest.mark.parametrize("generation_fails", [False, True])
def test_single_evaluation_computes_real_citation_metrics_and_recovers_generation(monkeypatch, generation_fails):
    result = retrieval_result()
    captured = {}
    def generation(**kwargs):
        captured.update(kwargs)
        if generation_fails:
            raise RuntimeError("provider offline")
        return SimpleNamespace(answer_text="响应时间为10毫秒[c001]。额外推断。", latency_ms=17)
    monkeypatch.setattr(evaluation_cli, "generate_answer", generation)
    monkeypatch.setattr(evaluation_cli, "llm_judge", lambda *args: {"recall": 4, "notes": "指标"})
    clocks = iter([1.0, 1.125])
    monkeypatch.setattr(evaluation_cli.time, "perf_counter", lambda: next(clocks))
    evaluator = evaluation_cli.ComprehensiveEvaluator(SimpleNamespace(retrieve=lambda q: result))
    measured = evaluator.evaluate_single({"query": "响应时间是多少？"})
    assert measured["expected_intent"] == "unknown" and measured["actual_intent"] == "metric"
    assert measured["num_chunks"] == 2 and measured["pre_rrf_candidates"] == 12
    assert set(measured["chunk_sources"]) == {"vector", "bm25"}
    assert measured["retrieval_ms"] == 125
    assert measured["generation_ms"] == (0 if generation_fails else 17)
    assert measured["total_ms"] == (125 if generation_fails else 142)
    assert measured["auto_faithfulness"] == (0 if generation_fails else .5)
    assert measured["auto_grounded_count"] == (0 if generation_fails else 1)
    assert measured["auto_sentence_count"] == (1 if generation_fails else 2)
    assert measured["judge_precision"] == 0 and measured["judge_recall"] == 4
    assert captured["context_chunks"][0]["chunk_id"] == "c001"
    assert "响应时间" in str(captured["messages"])
    if generation_fails:
        assert measured["answer"] == "[生成失败: provider offline]"


def report_metrics(score, hallucination=.2, latency=100):
    return {"retrieval_layer": {"avg_judge_recall": score, "avg_judge_precision": score},
            "generation_layer": {"avg_judge_relevance": score, "avg_judge_accuracy": score,
                                  "avg_judge_comprehensiveness": score, "avg_faithfulness": 1-hallucination,
                                  "avg_hallucination_rate": hallucination, "avg_total_ms": latency}}


@pytest.mark.parametrize("score,rating", [(2.4, "poor"), (2.5, "fair"), (3.5, "good"), (4.2, "excellent")])
def test_assessment_respects_quality_thresholds_and_formats_rates(score, rating):
    evaluator = evaluation_cli.ComprehensiveEvaluator(None)
    assessment = evaluator._generate_assessment(report_metrics(score))
    assert assessment["retrieval_quality"]["overall"] == rating
    assert assessment["generation_quality"]["overall"] == rating
    assert assessment["generation_quality"]["faithfulness"] == "80.0%"
    assert assessment["generation_quality"]["hallucination_rate"] == "20.0%"
    assert assessment["avg_latency_ms"] == 100


@pytest.mark.parametrize("score,hallucination,latency,expected", [
    (2, .5, 16000, {"召回率", "精确率", "幻觉率", "全面性", "延迟", "评估自动化", "MRR/排序质量"}),
    (3.8, .3, 15000, {"评估自动化", "MRR/排序质量"}),
    (4.2, .1, 100, {"评估自动化", "MRR/排序质量"}),
])
def test_recommendations_only_target_metric_gaps(score, hallucination, latency, expected):
    evaluator = evaluation_cli.ComprehensiveEvaluator(None)
    recommendations = evaluator._generate_recommendations(report_metrics(score, hallucination, latency))
    assert {item["metric"] for item in recommendations} == expected
    assert all(item["recommendation"] and item["expected_impact"] for item in recommendations)


def test_full_evaluation_aggregates_per_query_results_without_losing_sources(monkeypatch):
    responses = iter(["有引用[c001]。", "没有引用。"])
    monkeypatch.setattr(evaluation_cli, "generate_answer", lambda **kwargs: SimpleNamespace(answer_text=next(responses), latency_ms=10))
    monkeypatch.setattr(evaluation_cli, "llm_judge", lambda *args: {"recall": 4, "precision": 3,
                        "relevance": 5, "accuracy": 4, "comprehensiveness": 3, "notes": "中文说明"})
    evaluator = evaluation_cli.ComprehensiveEvaluator(SimpleNamespace(retrieve=lambda q: retrieval_result()))
    report = evaluator.run_full_eval([{"query": "问题一", "intent": "metric"}, {"query": "问题二", "intent": "metric"}])
    assert report["eval_metadata"]["total_queries"] == 2
    assert report["eval_metadata"]["intent_distribution"] == {"metric": 2}
    assert report["retrieval_layer"]["source_coverage"] == {"vector": 2, "bm25": 2}
    assert report["retrieval_layer"]["avg_pre_rrf_candidates"] == 12
    assert report["generation_layer"]["avg_faithfulness"] == .5
    assert report["generation_layer"]["avg_hallucination_rate"] == .5
    assert [row["query"] for row in report["per_query"]] == ["问题一", "问题二"]
    assert json.loads(json.dumps(report, ensure_ascii=False)) == report


def test_full_evaluation_rejects_empty_queries_with_clear_input_error():
    evaluator = evaluation_cli.ComprehensiveEvaluator(None)
    with pytest.raises(ValueError, match="(?i)(quer|empty|至少|不能为空)"):
        evaluator.run_full_eval([])


@pytest.mark.parametrize("broken_graph", [False, True])
@pytest.mark.parametrize("missing_indices", [False, True, "failure", "empty"])
def test_main_reads_local_graph_and_serializes_report_offline(monkeypatch, tmp_path, broken_graph, missing_indices, capsys):
    import index_registry
    monkeypatch.chdir(tmp_path)
    graph_dir = tmp_path / "output" / "kg" / "fixture"
    graph_dir.mkdir(parents=True)
    (graph_dir / "nodes.json").write_text("invalid" if broken_graph else json.dumps({"nodes": [
        {"node_id": "n1", "label": "响应时间"}, {"id": "n2", "label": "指标"}]}), encoding="utf-8")
    (graph_dir / "edges.json").write_text(json.dumps([{"source": "n1", "target": "n2", "relation": "related"},
                                                    {"from": "", "to": "n2"}]), encoding="utf-8")
    store = SimpleNamespace(collection_name="fixture", count=lambda: 1,
                            _collection=SimpleNamespace(get=lambda **kwargs: {"ids": ["c001"],
                            "documents": ["<table><tr><td>10</td></tr></table>"], "metadatas": [{"content_type": "table"}]}))
    monkeypatch.setattr(evaluation_cli, "VectorStore", lambda: store)
    monkeypatch.setattr(evaluation_cli, "EmbeddingClient", lambda: SimpleNamespace(model="offline", dim=3))
    table = SimpleNamespace(count=lambda: 1)
    monkeypatch.setattr(index_registry, "get_bm25_index", lambda: None if missing_indices else "existing-bm25")
    monkeypatch.setattr(index_registry, "get_table_index", lambda: None if missing_indices else table)
    built = {}
    def build_bm25(chunks):
        built["chunks"] = chunks
        if missing_indices == "failure":
            raise RuntimeError("index unavailable")
        if missing_indices == "empty":
            return None
        return "built-bm25"
    monkeypatch.setattr(index_registry, "build_bm25_from_chunks", build_bm25)
    monkeypatch.setattr(index_registry, "build_table_index_from_chunks", lambda chunks: None if missing_indices == "empty" else table)
    monkeypatch.setattr(index_registry, "set_bm25_index", lambda index: built.update(bm25=index))
    monkeypatch.setattr(index_registry, "set_table_index", lambda index: built.update(table=index))
    observed = {}
    def retrieval(**kwargs):
        observed.update(kwargs)
        return SimpleNamespace(retrieve=lambda q: retrieval_result())
    monkeypatch.setattr(evaluation_cli, "RetrievalPipeline", retrieval)
    monkeypatch.setattr(evaluation_cli, "TEST_QUERIES", [{"query": "响应时间？", "intent": "metric"}])
    monkeypatch.setattr(evaluation_cli, "generate_answer", lambda **kwargs: SimpleNamespace(answer_text="10毫秒[c001]。", latency_ms=10))
    monkeypatch.setattr(evaluation_cli, "llm_judge", lambda *args: {"recall": 4, "precision": 4,
                        "relevance": 4, "accuracy": 4, "comprehensiveness": 4, "notes": "通过"})
    report = evaluation_cli.main()
    path = tmp_path / "output" / "eval" / "eval_report.json"
    assert json.loads(path.read_text(encoding="utf-8")) == report
    assert "响应时间" in path.read_text(encoding="utf-8")
    assert report["generation_layer"]["avg_faithfulness"] == 1
    if broken_graph:
        assert observed["kg_graph"] is None
        assert "KG load failed" in capsys.readouterr().out
    else:
        graph = observed["kg_graph"]
        assert set(graph.nodes) == {"n1", "n2"} and graph.number_of_edges() == 1
        assert graph.edges["n1", "n2"] == {"relation": "related"}
    if missing_indices is True:
        assert built["chunks"][0].chunk_id == "c001"
        assert built["chunks"][0].content_type == "table"
        assert built["bm25"] == observed["bm25_index"] == "built-bm25"
    elif missing_indices in ("failure", "empty"):
        assert observed["bm25_index"] is None and observed["table_index"] is None
        assert "bm25" not in built and "table" not in built
