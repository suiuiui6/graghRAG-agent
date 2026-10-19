"""Offline retrieval boundaries over real SQLite and in-memory graph records."""
import json
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import networkx as nx
import pytest

import community_index as community
import retrieval as subject
from config import RetrievalConfig


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Retrieval boundary tests must remain offline")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def query(text, *, intent="metric"):
    return subject.PreprocessedQuery(text, text, intent, [])


@pytest.mark.parametrize("graph", [None, nx.Graph()])
def test_empty_graph_has_no_community_or_search_fallback(graph):
    index = community.build_community_index(graph)
    assert index == {"communities": [], "community_by_id": {},
                     "node_to_community": {}, "token_to_communities": {}}
    assert community.search_community_records("alpha", index) == []


def graph_index():
    graph = nx.Graph()
    for prefix, size, label in (("a", 2, "alpha beta"), ("b", 4, "alpha gamma beta"), ("c", 3, "delta")):
        for i in range(size):
            graph.add_node(f"{prefix}{i}", label=label, entity_type="method")
        nx.add_path(graph, [f"{prefix}{i}" for i in range(size)])
    return graph, community.build_community_index(graph)


def test_community_search_prefers_exact_phrase_then_size_and_respects_limit():
    graph, index = graph_index()
    hits = community.search_community_records("alpha beta", index, limit=2)
    assert len(hits) == 2
    assert "alpha beta" in hits[0]["summary_text"]
    assert hits[0]["size"] == 2 and hits[1]["size"] == 4
    # Phrase preference outranks the larger community even at equal token count.
    assert hits[0]["score"] == hits[1]["score"] == 2.0
    assert community.search_community_records("alpha", index, limit=0) == []
    assert community.search_community_records("alpha", index, limit=-1) == []
    assert graph.number_of_nodes() == 9
    assert all(len(ids) == len(set(ids)) for ids in index["token_to_communities"].values())


@pytest.mark.parametrize("text", ["unseen-token", ""])
def test_unmatched_community_search_falls_back_by_size_without_claiming_relevance(text):
    _, index = graph_index()
    hits = community.search_community_records(text, index, limit=3)
    assert [row["size"] for row in hits] == [4, 3, 2]
    assert [row["score"] for row in hits] == [0.0, 0.0, 0.0]


def test_sqlite_rewrite_cache_initialization_is_shared_under_real_lock_contention(tmp_path, monkeypatch):
    barrier, lock = threading.Barrier(2), threading.Lock()

    class ContendedLock:
        def __enter__(self):
            # Both callers have passed the outer None check before acquiring.
            barrier.wait(timeout=5)
            lock.acquire()

        def __exit__(self, *args):
            lock.release()

    path = tmp_path / "rewrite.sqlite3"
    monkeypatch.setattr(subject, "_rewrite_cache", None)
    monkeypatch.setattr(subject, "_rewrite_cache_lock", ContendedLock())
    monkeypatch.setattr(subject, "REWRITE_CACHE_PATH", path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        caches = list(pool.map(lambda _: subject.get_query_rewrite_cache(), range(2)))
    assert caches[0] is caches[1]
    caches[0].set("same", {"rewritten": "中文 preserved"})
    assert caches[1].get("same") == {"rewritten": "中文 preserved"}
    assert subject.QueryRewriteCache(path).get("same") == {"rewritten": "中文 preserved"}
    assert subject.QueryRewriteCache(path).get("missing") is None


def test_search_tokenization_ignores_single_ascii_letters_but_keeps_cjk_and_words():
    assert set(subject._tokenize_for_search("x Z abc 中")) == {"abc", "中"}
    assert subject._title_or_id_field_boost("编号", "paper_metadata", {"field": "ID"}) == 0.35
    assert subject._title_or_id_field_boost("编号", "method", {"field": "id"}) == 0


def test_grounding_exact_node_text_outweighs_distant_page_hints():
    graph = nx.Graph()
    graph.add_node("n1", label="alpha", properties={}, entity_type="method", page_idx=8)
    graph.add_node("n2", label="alpha", properties={}, entity_type="method", page_idx=1)
    assert subject._infer_entity_ids_from_candidate({"text": "alpha", "metadata": {"page_idx": 1}}, graph) == ["n2", "n1"]


@pytest.mark.parametrize("config,graph", [
    (RetrievalConfig(enabled_sources=("bm25",)), nx.path_graph(2)),
    (RetrievalConfig(kg_top_k=0), nx.path_graph(2)),
    (RetrievalConfig(), None),
])
def test_global_recall_disabled_or_unavailable_graph_returns_no_descendants(config, graph):
    assert subject.global_community_recall(query("alpha"), graph, config) == {
        "community_hits": [], "selected_communities": [], "descendant_hits": []}


def test_priority_kg_rescue_honors_source_exclusion_before_touching_graph():
    assert subject._priority_kg_rescue_candidates(query("W4S1是什么"), None,
               RetrievalConfig(enabled_sources=("bm25",))) == []


@pytest.mark.parametrize("text,bm25_k,table_k", [("ordinary", 2, 2), ("W4S1", 2, 2), ("W4S1发电量", 0, 0)])
def test_scenario_rescues_require_alias_metric_and_positive_source_budget(text, bm25_k, table_k):
    config = RetrievalConfig(bm25_top_k=bm25_k, table_top_k=table_k)
    assert subject._scenario_metric_text_rescue_candidates(query(text), (None, []), config) == []
    assert subject._scenario_metric_table_rescue_candidates(query(text), SimpleNamespace(rows=[]), config) == []


def test_table_scenario_rescue_ignores_malformed_context_but_retains_row_evidence():
    row = {"column_name": "generation", "column_value": 12, "sheet_name": "W4S1",
           "row_number": 2, "context": ["legacy context"], "source_file": "synthetic.csv"}
    hits = subject._scenario_metric_table_rescue_candidates(query("W4S1发电量"),
               SimpleNamespace(rows=[row]), RetrievalConfig())
    assert len(hits) == 1 and hits[0]["chunk_id"] == "table_row_W4S1_2_generation"
    assert hits[0]["metadata"]["protected_evidence"] is True
    assert hits[0]["metadata"]["table_data"] == row
    assert "generation" in hits[0]["metadata"]["matched_metric_fragments"]


def test_rrf_duplicate_within_path_is_counted_once_but_independent_paths_add_weight():
    item = {"chunk_id": "same", "text": "synthetic evidence", "source": "kg", "score": 1,
            "metadata": {"source_file": "one.json", "object_type": "entity"}}
    one = subject.rrf_fusion([("kg", [item])])
    duplicate = subject.rrf_fusion([("kg", [item, item])])
    assert duplicate == one
    multi = subject.rrf_fusion([("kg", [item, item]), ("bm25", [item])])
    assert len(multi) == 1 and multi[0]["rrf_score"] == round(2 / 61, 4)
    assert multi[0]["source_paths"] == ["kg", "bm25"]


@pytest.mark.parametrize("entity_type", ["", "metric"])
def test_legacy_json_entity_metric_survives_nondict_table_metadata(entity_type):
    candidate = {"text": json.dumps({"entity": {"entity_type": "metric",
                  "properties": {"name": "renewable generation", "value": 12}}}),
                 "metadata": {"table_data": "legacy", "entity_type": entity_type}}
    assert subject._candidate_matches_metric_query("发电量", candidate) is True
    assert subject._candidate_matches_metric_query("弃电率", candidate) is False


def test_table_metric_matches_without_alias_and_invalid_context_never_becomes_properties():
    table = {"text": "generation = 12", "source": "table", "metadata": {
        "table_data": {"column_name": "renewable generation", "column_value": 12}}}
    assert subject._candidate_matches_metric_query("发电量", table) is True
    bad_context = {"text": "unrelated", "metadata": {"table_data": {"context": ["generation"]}}}
    assert subject._candidate_matches_metric_query("发电量", bad_context) is False


def test_summary_inventory_requires_table_anchor_and_three_matching_metrics():
    metric = {"source": "kg", "text": "renewable generation", "metadata": {
        "entity_type": "metric", "properties": {"name": "renewable generation"}}}
    table = {"source": "table", "text": "generation = 12"}
    assert subject._has_summary_metric_inventory_rescue("摘要有哪些发电量", [table, metric, metric]) is True
    assert subject._has_summary_metric_inventory_rescue("摘要有哪些发电量", [table, metric]) is False
    assert subject._has_summary_metric_inventory_rescue("摘要有哪些发电量", [metric] * 3) is False


def test_scenario_table_rescue_requires_matching_scenario_and_metric_not_just_table_source():
    candidate = {"source": "table", "text": "W4S1 renewable generation = 12", "metadata": {
        "table_data": {"column_name": "renewable generation", "column_value": 12,
                       "context": {"scenario": "W4S1"}}}}
    assert subject._has_scenario_metric_table_rescue("W4S1发电量", [candidate]) is True
    assert subject._has_scenario_metric_table_rescue("W9S9发电量", [candidate]) is False


def test_alias_definition_and_claim_queries_do_not_promote_irrelevant_evidence():
    assert subject._has_alias_definition_rescue("W4S1是什么", [{"source": "kg", "text": "unrelated"}]) is False
    assert subject._has_claim_verification_rescue("问题二的方法", []) is False
    assert subject._candidate_has_exact_query_evidence("图7说明", {"text": "图7: local caption"}) is True


def test_unnamed_table_column_does_not_demote_unrelated_kg_metric():
    table = subject.RetrievalChunk("t", "unlabelled value", 1, "table", metadata={"table_data": {"column_value": 12}})
    kg = subject.RetrievalChunk("k", "unrelated metric", 1, "kg")
    result = subject._resolve_cross_path_conflicts([table, kg])
    assert result == [table, kg] and kg.score == 1


def test_jaccard_dedup_skips_already_removed_later_chunk_without_dropping_other_evidence():
    chunks = [subject.RetrievalChunk("a", "alpha evidence", 3, "vector"),
              subject.RetrievalChunk("b", "beta distinct", 2, "bm25"),
              subject.RetrievalChunk("a-copy", "alpha evidence", 1, "vector")]
    assert [c.chunk_id for c in subject._dedup_by_jaccard(chunks)] == ["a", "b"]
