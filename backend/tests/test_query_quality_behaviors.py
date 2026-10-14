"""Offline behavior contracts; HTTP doubles are not provider integration evidence."""

import json
import builtins
import os
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest
import requests

import evaluation
import query_optimizer as qo
from evaluation import EvalDataset, Evaluator, save_eval_report
from self_correction import SelfCorrection


@pytest.fixture(autouse=True)
def no_external_http(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("External HTTP is forbidden in offline behavior tests")

    monkeypatch.setattr(requests.sessions.Session, "request", reject)
    monkeypatch.setenv("LANGEXTRACT_API_KEY", "offline-test-placeholder")
    monkeypatch.setenv("LANGEXTRACT_BASE_URL", "https://offline.invalid/")


def test_domain_expansion_ignores_case_and_already_present_terms():
    dictionary = qo.DomainDictionary({"KPI": ["指标", "kpi", "考核"], "预算": ["成本"]})
    assert dictionary.expand("kPi 指标") == ["考核"]
    assert dictionary.expand("天气") == []


def test_optimizer_expansion_limits_search_terms_but_preserves_metadata():
    synonyms = [f"term{i}" for i in range(12)]
    result = qo.QueryOptimizer(domain_dict={"预算": synonyms}).optimize("预算")
    assert result.raw_query == result.resolved_query == "预算"
    assert result.enhanced_query == "预算 " + " ".join(synonyms[:5])
    assert result.expanded_terms == synonyms
    assert result.profile is None and result.profile_hint == ""
    prompt = qo.build_enhanced_system_prompt("依据资料回答", result)
    assert "term9" in prompt and "term10" not in prompt
    assert "[DOMAIN TERMS]" in prompt and prompt.startswith("依据资料回答")


@pytest.mark.parametrize("profile,expected", [
    (qo.UserProfile(), ""),
    (qo.UserProfile(role="unknown", preferred_language="zh", detail_level="concise"), "200字"),
    (qo.UserProfile(role="engineer", preferred_language="en", detail_level="detailed"), "English"),
    (qo.UserProfile(role="executive"), "高层摘要"),
    (qo.UserProfile(role="analyst"), "Markdown 表格"),
])
def test_profile_hints_reach_system_prompt(profile, expected):
    result = qo.QueryOptimizer().optimize("天气", profile=profile)
    assert result.profile is profile
    assert expected in result.profile_hint
    prompt = qo.build_enhanced_system_prompt("基础", result)
    if result.profile_hint:
        assert prompt == f"基础\n\n[USER CONTEXT]\n{result.profile_hint}"
    else:
        assert prompt == "基础"


def test_optimized_query_defaults_and_explicit_values():
    assert qo.OptimizedQuery("问题").enhanced_query == "问题"
    result = qo.OptimizedQuery("问题", resolved_query="解析", enhanced_query="扩展")
    assert result.resolved_query == "解析" and result.enhanced_query == "扩展"


@pytest.mark.parametrize("query,history", [("它怎么样", None), ("预算", [{"role": "user", "content": "项目甲"}])])
def test_pronoun_resolution_short_circuits_without_context_or_pronouns(monkeypatch, query, history):
    def forbidden(*args):
        pytest.fail("Unnecessary model boundary call")
    monkeypatch.setattr(qo, "_llm_resolve_pronouns", forbidden)
    assert qo._resolve_pronouns(query, history) == query


@pytest.mark.parametrize("response", [None, "它的预算"])
def test_pronoun_resolution_uses_latest_user_entity_on_llm_fallback(monkeypatch, response):
    monkeypatch.setattr(qo, "_llm_resolve_pronouns", lambda *args: response)
    history = [{"role": "user", "content": "项目甲"},
               {"role": "assistant", "content": "系统乙"},
               {"role": "user", "content": "工程丙"}]
    assert qo._resolve_pronouns("它的预算", history) == "工程丙的预算"
    assert qo._heuristic_resolve_pronouns("它的预算", history[:1], 1) == "项目甲的预算"
    assert qo._heuristic_resolve_pronouns("它的预算", history[1:2], 1) == "它的预算"


def test_pronoun_resolution_accepts_rewritten_query(monkeypatch):
    monkeypatch.setattr(qo, "_llm_resolve_pronouns", lambda *args: "项目甲的预算")
    result = qo.QueryOptimizer().optimize("它的预算", [{"role": "user", "content": "项目甲"}])
    assert result.resolved_query == "项目甲的预算"
    assert "预算管理" in result.expanded_terms


def test_recent_history_preserves_short_history_and_truncates_old_turns():
    history = [{"role": "user", "content": str(i)} for i in range(4)]
    assert qo._recent_history(history, 4) == history
    assert qo._recent_history(history, 2) == history[2:]


def test_llm_boundary_builds_bounded_prompt_and_parses_text(monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"choices": [{"message": {"content": "  项目甲预算  "}}]})
    monkeypatch.setattr(requests, "post", post)
    result = qo._llm_resolve_pronouns("它的预算", [
        {"role": "user", "content": "old-turn"},
        {"role": "assistant", "content": "x" * 350},
        {"role": "user", "content": "项目甲"}], 2)
    assert result == "项目甲预算"
    url, options = calls[0]
    assert url == "https://offline.invalid/chat/completions"
    prompt = options["json"]["messages"][0]["content"]
    assert "old-turn" not in prompt and "x" * 300 in prompt and "x" * 301 not in prompt
    assert "Latest query: 它的预算" in prompt
    assert options["timeout"] == 15 and options["json"]["temperature"] == 0.0


@pytest.mark.parametrize("failure", ["http", "json", "schema"])
def test_llm_boundary_failure_returns_none_for_heuristic_fallback(monkeypatch, failure):
    def check_status():
        if failure == "http":
            raise requests.HTTPError("provider unavailable")
    def decode():
        if failure == "json":
            raise ValueError("invalid JSON")
        return {"choices": []}
    monkeypatch.setattr(requests, "post", lambda *a, **k: SimpleNamespace(raise_for_status=check_status, json=decode))
    assert qo._llm_resolve_pronouns("它", [{"role": "user", "content": "项目甲"}], 1) is None


@pytest.fixture
def source_chunks(tmp_path):
    path = tmp_path / "context.json"
    path.write_text(json.dumps([{"chunk_id": "c00001", "text": 'Budget 42; rate 12.5%; {"node_id": "n0001"}'},
                               {"text": "No numeric facts"}], ensure_ascii=False), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def test_citation_validation_accepts_chunk_and_embedded_node_ids(source_chunks):
    corrector = SelfCorrection()
    assert corrector._verify_citations("来源 [c00001] [n0001]", source_chunks) == (True, [])
    assert corrector._verify_citations("无引用陈述", []) == (True, [])
    passed, hints = corrector._verify_citations("[c99999] [c99999] [n9999]", source_chunks)
    assert not passed and len(hints) == 2
    assert "c99999" in hints[0] and "n9999" in hints[1]


def test_numeric_validation_supports_sources_small_integers_and_deduplication(source_chunks):
    corrector = SelfCorrection()
    assert corrector._verify_numbers("42 and 12.5% with 3 steps", source_chunks) == (True, [])
    assert corrector._verify_numbers("没有数值", []) == (True, [])
    passed, hints = corrector._verify_numbers("100 100 0.5", source_chunks)
    assert not passed and len(hints) == 2
    assert '"100"' in hints[0] and '"0.5"' in hints[1]


@pytest.mark.parametrize("answer,passed", [
    ("但是不", True), ("项目进度已完成，但是仍然没有通过验收", False),
    ("项目进度已完成，然而无法按期交付", False),
    ("项目进度已完成，不过未达到质量要求", False),
    ("项目进度已完成，但是验收工作按计划进行", True),
    ("项目进度正常。审批已经完成", True),
])
def test_contradiction_heuristic_flags_only_long_negated_turns(answer, passed):
    actual, hints = SelfCorrection()._check_contradictions(answer)
    assert actual is passed
    assert len(hints) == (0 if passed else 1)


def test_corrector_preserves_valid_answer_without_regeneration(source_chunks):
    def forbidden(**kwargs):
        pytest.fail("Valid answer must not trigger regeneration")
    result = SelfCorrection().correct("Budget 42 [c00001]", source_chunks, "预算", forbidden)
    assert result.final_passed and result.correction_rounds == 0
    assert result.answer_text == "Budget 42 [c00001]" and result.corrections_made == []


def test_corrector_passes_errors_to_generator_and_rechecks_answer(source_chunks):
    calls = []
    def regenerate(*, error_hints):
        calls.append(error_hints)
        return "Budget 42 [c00001]"
    result = SelfCorrection(2).correct("Budget 100 [c99999]", source_chunks, "预算", regenerate)
    assert result.final_passed and result.correction_rounds == 1
    assert result.answer_text == "Budget 42 [c00001]"
    assert len(calls) == 1 and len(calls[0]) == 2
    assert result.corrections_made == calls[0]


def test_corrector_generator_exception_keeps_original_answer_and_warning(source_chunks):
    calls = []
    def fail(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("offline generator unavailable")
    result = SelfCorrection(2).correct("Budget 100", source_chunks, "预算", fail)
    assert not result.final_passed and result.answer_text.startswith("Budget 100")
    assert "自修正警告" in result.answer_text
    assert "offline generator unavailable" in result.corrections_made[-1]
    assert len(calls) == 1


def test_corrector_repeated_invalid_answers_stop_at_max_rounds(source_chunks):
    calls = []
    def invalid(**kwargs):
        calls.append(kwargs)
        return "Budget 100"
    result = SelfCorrection(2).correct("Budget 100", source_chunks, "预算", invalid)
    assert len(calls) == 2 and result.correction_rounds == 2 and not result.final_passed
    assert len(result.corrections_made) == 2 and "仅供参考" in result.answer_text


def test_negative_correction_budget_is_rejected():
    with pytest.raises(ValueError, match="max_rounds must be >= 0"):
        SelfCorrection(-1)


def test_retrieval_metrics_cutoffs_duplicates_empty_and_late_relevant_result():
    assert Evaluator.evaluate_retrieval([], ["a"] ) == {
        "recall@5": 0.0, "recall@10": 0.0, "precision@10": 0.0, "mrr": 0.0}
    assert Evaluator.evaluate_retrieval(["a"], []) == {
        "recall@5": 1.0, "recall@10": 1.0, "precision@10": 0.0, "mrr": 0.0}
    ids = ["x", "a", "a", "x", "x", "b", "x", "x", "x", "x", "c"]
    assert Evaluator.evaluate_retrieval(ids, ["a", "b", "c", "a"]) == {
        "recall@5": 0.3333, "recall@10": 0.6667, "precision@10": 0.2, "mrr": 0.5}
    assert Evaluator.evaluate_retrieval(["x"] * 10 + ["a"], ["a"])["mrr"] == 0.0909


@pytest.mark.parametrize("answer,expected", [
    (" 。!?\n", (0.0, 1.0, 0, 0)),
    ("预算 [c00001]。进度 [n0001]!没有来源?", (0.6667, 0.3333, 3, 2)),
    ("来源 [c12]", (0.0, 1.0, 1, 0)),
])
def test_generation_metric_counts_citation_markers_not_factual_verification(answer, expected):
    result = Evaluator.evaluate_generation(answer, [{"chunk_id": "unrelated"}])
    assert tuple(result[key] for key in ("faithfulness", "hallucination_rate", "sentence_count", "grounded_count")) == expected


def test_eval_pipeline_aggregates_local_retrieval_and_serializes_report(tmp_path, monkeypatch):
    corpus = {"预算": ("c00001", "预算 42 [c00001]。"), "进度": ("c00002", "进度正常。")}
    ticks = iter([1.0, 1.012, 2.0, 2.024])
    monkeypatch.setattr(evaluation.time, "perf_counter", lambda: next(ticks))
    def retrieve(query):
        return [corpus[query][0]]
    def generate(query, ids):
        assert ids == [corpus[query][0]]
        return corpus[query][1]
    report = Evaluator().run_eval([EvalDataset("预算", ["c00001"]), EvalDataset("进度", ["missing"])], retrieve, generate)
    assert report["retrieval"] == {"recall@5": 0.5, "recall@10": 0.5, "precision@10": 0.5, "mrr": 0.5}
    assert report["generation"] == {"faithfulness": 0.5, "hallucination_rate": 0.5, "avg_latency_ms": 18.0}
    assert [r["latency_ms"] for r in report["per_query"]] == [12.0, 24.0]
    assert "Evaluated 2 queries" in report["summary"]
    path = tmp_path / "nested" / "报告.json"
    save_eval_report(report, str(path))
    assert json.loads(path.read_text(encoding="utf-8")) == report
    assert "预算" in path.read_text(encoding="utf-8")


def test_eval_empty_dataset_does_not_invoke_callbacks():
    def forbidden(*args):
        pytest.fail("Empty dataset must not invoke pipeline")
    report = Evaluator().run_eval([], forbidden, forbidden)
    assert report["per_query"] == [] and report["retrieval"]["recall@10"] == 0.0
    assert report["generation"]["avg_latency_ms"] == 0.0
    assert report["summary"] == "Empty dataset — nothing to evaluate."


def test_eval_retrieval_failure_is_not_silently_reported_as_success():
    def fail(query):
        raise RuntimeError("local index unavailable")
    with pytest.raises(RuntimeError, match="local index unavailable"):
        Evaluator().run_eval([EvalDataset("预算", ["c00001"])], fail, lambda *a: "")


def test_final_allowed_correction_is_validated_before_warning(source_chunks):
    result = SelfCorrection(1).correct("Budget 100", source_chunks, "预算",
                                       lambda **kwargs: "Budget 42 [c00001]")
    assert result.final_passed
    assert result.correction_rounds == 1
    assert result.answer_text == "Budget 42 [c00001]"


@pytest.mark.parametrize("answer,expected_passed", [("Budget 42 [c00001]", True), ("Budget 100", False)])
def test_zero_correction_budget_still_validates_without_generator(source_chunks, answer, expected_passed):
    def forbidden(**kwargs):
        pytest.fail("Zero correction budget must not invoke generator")
    result = SelfCorrection(0).correct(answer, source_chunks, "预算", forbidden)
    assert result.final_passed is expected_passed
    assert result.correction_rounds == 0
    if expected_passed:
        assert result.answer_text == answer
    else:
        assert result.answer_text.startswith(answer) and "自修正警告" in result.answer_text


@pytest.fixture
def legacy_kg(tmp_path, monkeypatch):
    """Execute the real demo against temporary JSON and model-construction doubles."""
    import importlib
    agent_module = importlib.import_module("langchain.agents")
    import langchain_openai
    from langchain_core.tools import tool as real_tool
    # Older recall tests install a process-wide decorator stub during collection.
    # This fixture verifies real tool invocation/metadata and restores that state.
    monkeypatch.setattr(importlib.import_module("langchain.tools"), "tool", real_tool)

    nodes = [
        {"node_id": "n0001", "entity_type": "project_metadata", "label": "项目甲",
         "properties": {"owner": "ALICE"}, "page_idx": 1, "grounding_status": "grounded"},
        {"node_id": "n0002", "entity_type": "metric", "label": "预算", "properties": {"value": 42},
         "page_idx": 2, "grounding_status": "grounded"},
        {"node_id": "n0003", "entity_type": "milestone", "label": "终验", "grounding_status": "grounded"},
        {"node_id": "n0004", "entity_type": "risk_item", "label": "未核实风险"},
    ]
    edges = [
        {"source_node_id": "n0001", "target_node_id": "n0002", "relation_type": "has_budget"},
        {"source_node_id": "n0002", "target_node_id": "n0003", "relation_type": "supports"},
        {"source_node_id": "n0001", "target_node_id": "n0004", "relation_type": "has_risk"},
    ]
    for name, value in [("nodes", nodes), ("edges", edges)]:
        (tmp_path / f"{name}.json").write_text(json.dumps({name: value}, ensure_ascii=False), encoding="utf-8")

    source = Path(__file__).resolve().parents[1] / "agentic_rag_mvp.py"
    redirected = {os.path.normcase(str(source.parent / "output" / "kg" / f"{name}.json")):
                  tmp_path / f"{name}.json" for name in ("nodes", "edges")}
    original_open = builtins.open
    def temporary_open(file, *args, **kwargs):
        replacement = redirected.get(os.path.normcase(os.fspath(file)))
        return original_open(replacement if replacement else file, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", temporary_open)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "offline-test-placeholder")
    model_options = []
    def local_model(**kwargs):
        model_options.append(kwargs)
        return object()
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", local_model)
    monkeypatch.setattr(agent_module, "create_agent", lambda **kwargs: SimpleNamespace(config=kwargs))
    module = runpy.run_path(str(source), run_name="offline_legacy_demo")
    assert len(model_options) == 1
    assert module["G"].number_of_nodes() == 4
    assert module["G_grounded"].number_of_nodes() == 3
    assert module["agent"].config["tools"] == module["TOOLS"]
    return module


def test_legacy_search_filters_grounded_type_properties_and_limit(legacy_kg):
    search = legacy_kg["search_kg_by_type"].invoke
    matches = json.loads(search({"keyword": "alice"}))
    assert [item["node_id"] for item in matches] == ["n0001"]
    assert matches[0]["page_idx"] == 1 and matches[0]["properties"] == {"owner": "ALICE"}
    assert [item["node_id"] for item in json.loads(search({"entity_type": "metric"}))] == ["n0002"]
    assert len(json.loads(search({"max_results": 1}))) == 1
    assert "No entities found" in search({"entity_type": "risk_item"})
    assert "No entities found" in search({"keyword": "absent"})


def test_legacy_neighbors_use_real_graph_hops_relations_and_grounding(legacy_kg):
    neighbors = legacy_kg["get_entity_neighbors"].invoke
    direct = json.loads(neighbors({"label_keyword": "项目"}))
    assert direct["source"]["node_id"] == "n0001"
    assert direct["neighbors_count"] == 1
    assert direct["neighbors"][0]["relation"] == "has_budget"
    two_hops = json.loads(neighbors({"node_id": "n0001", "k_hops": 2}))
    assert {item["node_id"] for item in two_hops["neighbors"]} == {"n0002", "n0003"}
    assert next(item for item in two_hops["neighbors"] if item["node_id"] == "n0003")["relation"] == "connected"
    assert json.loads(neighbors({"node_id": "n0001", "max_results": 0}))["neighbors"] == []
    assert "Entity not found" in neighbors({"node_id": "n0004"})
    assert "Entity not found" in neighbors({"label_keyword": "absent"})


def test_legacy_entity_details_include_only_grounded_relationships(legacy_kg):
    detail = legacy_kg["get_entity_detail"].invoke
    result = json.loads(detail({"node_id": "n0001"}))
    assert result["properties"] == {"owner": "ALICE"}
    assert result["grounding_status"] == "grounded"
    assert [item["target_node_id"] for item in result["relationships"]] == ["n0002"]
    assert "not found" in detail({"node_id": "missing"})


def test_legacy_statistics_distinguish_grounded_subgraph_from_full_graph(legacy_kg):
    stats = json.loads(legacy_kg["get_kg_statistics"].invoke({}))
    assert (stats["total_nodes"], stats["grounded_nodes"], stats["ungrounded_nodes"], stats["total_edges"]) == (4, 3, 1, 3)
    assert stats["grounding_rate"] == "75.0%"
    assert stats["entity_type_distribution"]["metric"] == 1
    assert stats["relation_type_distribution"] == {"has_budget": 1, "supports": 1, "has_risk": 1}


@pytest.mark.parametrize("mode", ["content", "string", "empty", "error"])
def test_legacy_query_display_extracts_final_answer_and_handles_empty_failure(legacy_kg, capsys, mode):
    capsys.readouterr()
    requests_seen = []
    def invoke(payload):
        requests_seen.append(payload)
        if mode == "error":
            raise RuntimeError("offline agent failure")
        messages = {"content": [SimpleNamespace(content="先前"), SimpleNamespace(content="甲" * 2001)],
                    "string": ["最后答案"], "empty": []}
        return {"messages": messages[mode]}
    legacy_kg["run_query"](SimpleNamespace(invoke=invoke), "预算？", 3)
    output = capsys.readouterr().out
    assert requests_seen == [{"messages": [("user", "预算？")]}]
    assert "Query 3: 预算？" in output
    if mode == "content":
        assert "甲" * 2000 in output and "甲" * 2001 not in output and "(truncated)" in output
        assert "先前" not in output
    elif mode == "string":
        assert "最后答案" in output
    elif mode == "empty":
        assert "[No response]" in output
    else:
        assert "[ERROR] offline agent failure" in output
