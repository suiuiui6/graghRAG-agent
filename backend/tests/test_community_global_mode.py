from pathlib import Path
import sys
import types

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if "structlog" not in sys.modules:
    sys.modules["structlog"] = types.SimpleNamespace(
        configure=lambda *args, **kwargs: None,
        get_logger=lambda *args, **kwargs: types.SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        ),
        make_filtering_bound_logger=lambda *args, **kwargs: object,
        processors=types.SimpleNamespace(
            TimeStamper=lambda *args, **kwargs: None,
            add_log_level=lambda *args, **kwargs: None,
            StackInfoRenderer=lambda *args, **kwargs: None,
            format_exc_info=lambda *args, **kwargs: None,
            UnicodeDecoder=lambda *args, **kwargs: None,
            JSONRenderer=lambda *args, **kwargs: None,
        ),
        stdlib=types.SimpleNamespace(
            LoggerFactory=lambda *args, **kwargs: None,
            BoundLogger=object,
            add_logger_name=lambda *args, **kwargs: None,
            add_log_level=lambda *args, **kwargs: None,
            PositionalArgumentsFormatter=lambda *args, **kwargs: None,
        ),
        contextvars=types.SimpleNamespace(
            merge_contextvars=lambda *args, **kwargs: None,
            bind_contextvars=lambda *args, **kwargs: None,
        ),
        dev=types.SimpleNamespace(ConsoleRenderer=lambda *args, **kwargs: None),
    )

from config import RetrievalConfig
from retrieval import PreprocessedQuery, choose_query_mode, global_community_recall


def _build_global_graph() -> nx.Graph:
    graph = nx.Graph()

    communities = {
        "risk": [
            ("risk_1", "risk_item", "主要风险"),
            ("risk_2", "department", "风控部"),
        ],
        "budget": [
            ("budget_1", "metric", "预算执行率"),
            ("budget_2", "department", "财务部"),
        ],
        "timeline": [
            ("timeline_1", "timeline_event", "总体进度"),
            ("timeline_2", "department", "PMO"),
        ],
        "noise": [
            ("noise_1", "deliverable", "培训材料"),
            ("noise_2", "department", "行政部"),
        ],
    }

    for nodes in communities.values():
        first = None
        for node_id, entity_type, label in nodes:
            graph.add_node(
                node_id,
                entity_type=entity_type,
                label=label,
                properties={"label": label},
                grounding_status="grounded",
            )
            if first is None:
                first = node_id
            else:
                graph.add_edge(first, node_id, relation="related_to")
        if len(nodes) > 2:
            for node_id, _, _ in nodes[1:]:
                graph.add_edge(first, node_id, relation="related_to")

    return graph


def test_build_community_index_creates_summary_records():
    from community_index import build_community_index

    graph = nx.karate_club_graph()
    for node_id in graph.nodes:
        graph.nodes[node_id]["label"] = f"Node {node_id}"
        graph.nodes[node_id]["entity_type"] = "member"

    idx = build_community_index(graph)

    assert idx["communities"]
    assert "summary_text" in idx["communities"][0]
    assert idx["communities"][0]["node_ids"]
    assert idx["communities"][0]["community_id"].startswith("c")
    assert len(idx["communities"][0]["community_id"]) == 6


def test_community_ids_follow_existing_citation_shape():
    from generator import validate_output_format

    assert validate_output_format("社区摘要 [c00001]")["has_citations"] is True


def test_global_mode_prefers_community_records():
    mode = choose_query_mode("总结所有主要风险与部门关系", enable_global_mode=True)
    assert mode == "global"


def test_global_mode_requires_flag():
    mode = choose_query_mode("总结所有主要风险与部门关系", enable_global_mode=False)
    assert mode == "local"


def test_non_global_query_stays_local_even_when_flag_enabled():
    mode = choose_query_mode("主要风险来自哪个部门", enable_global_mode=True)
    assert mode == "local"


def test_global_mode_descends_only_into_top_scoring_communities():
    from community_index import build_community_index

    graph = _build_global_graph()
    community_index = build_community_index(graph)
    preprocessed = PreprocessedQuery(
        original="总结主要风险、预算和总体进度",
        rewritten="总结主要风险、预算和总体进度",
        intent="hybrid",
        entity_types=["risk_item", "metric", "timeline_event", "department"],
        table_conditions=[],
    )
    config = RetrievalConfig(enable_global_mode=True, kg_top_k=8)

    recall = global_community_recall(
        preprocessed,
        graph,
        config,
        community_index=community_index,
        top_community_limit=3,
    )

    selected_ids = [item["community_id"] for item in recall["selected_communities"]]
    descendant_ids = [item["chunk_id"] for item in recall["descendant_hits"]]

    assert len(selected_ids) == 3
    assert all("noise_" not in chunk_id for chunk_id in descendant_ids)


def test_retrieval_pipeline_preserves_local_and_global_branches(monkeypatch):
    from retrieval import RetrievalPipeline

    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    pipeline = RetrievalPipeline(
        vector_store=object(),
        embedding_client=DummyEmbeddingClient(),
        kg_graph=_build_global_graph(),
        bm25_index=None,
        table_index=None,
        config=RetrievalConfig(enable_cross_encoder=False, max_total_candidates=2, max_context_tokens=256),
    )

    monkeypatch.setattr(
        "retrieval.preprocess_query",
        lambda raw_query, chat_history=None, **kwargs: PreprocessedQuery(
            original=raw_query,
            rewritten=raw_query,
            intent="hybrid",
            entity_types=["risk_item", "department"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.embed_queries",
        lambda preprocessed, embedding_client, generate_variants=False: [[0.1, 0.2]],
    )

    branch_calls = {"global": 0, "local": 0}

    monkeypatch.setattr(
        "retrieval.global_community_recall",
        lambda *args, **kwargs: branch_calls.__setitem__("global", branch_calls["global"] + 1) or {
            "community_hits": [
                {
                    "chunk_id": "community:c0000",
                    "community_id": "c0000",
                    "text": "主要风险 | 风控部",
                    "score": 1.0,
                    "source": "community",
                    "metadata": {"node_ids": ["risk_1"], "community_size": 2},
                }
            ],
            "selected_communities": [{"community_id": "c0000"}],
            "descendant_hits": [
                {
                    "chunk_id": "risk_1",
                    "text": "risk node",
                    "score": 0.9,
                    "source": "kg",
                    "metadata": {"page_idx": 1},
                }
            ],
        },
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: branch_calls.__setitem__("local", branch_calls["local"] + 1) or [
            (
                "vector",
                [
                    {
                        "chunk_id": "local_1",
                        "text": "local node",
                        "score": 0.8,
                        "source": "vector",
                        "metadata": {"page_idx": 2},
                    }
                ],
            )
        ],
    )

    global_config = RetrievalConfig(
        enable_global_mode=True,
        enable_cross_encoder=False,
        max_total_candidates=2,
        max_context_tokens=256,
    )
    local_config = RetrievalConfig(
        enable_global_mode=True,
        enable_cross_encoder=False,
        max_total_candidates=2,
        max_context_tokens=256,
    )

    global_result = pipeline.retrieve("总结所有主要风险与部门关系", retrieval_config=global_config)
    local_result = pipeline.retrieve("主要风险来自哪个部门", retrieval_config=local_config)

    assert branch_calls["global"] == 1
    assert branch_calls["local"] == 1
    assert global_result.pipeline["query_mode"] == "global"
    assert local_result.pipeline["query_mode"] == "local"


def test_global_mode_falls_back_to_local_paths_without_descendants(monkeypatch):
    from retrieval import RetrievalPipeline

    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    pipeline = RetrievalPipeline(
        vector_store=object(),
        embedding_client=DummyEmbeddingClient(),
        kg_graph=_build_global_graph(),
        bm25_index=None,
        table_index=None,
        config=RetrievalConfig(enable_cross_encoder=False, max_total_candidates=2, max_context_tokens=256),
    )

    monkeypatch.setattr(
        "retrieval.preprocess_query",
        lambda raw_query, chat_history=None, **kwargs: PreprocessedQuery(
            original=raw_query,
            rewritten=raw_query,
            intent="hybrid",
            entity_types=["risk_item"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.embed_queries",
        lambda preprocessed, embedding_client, generate_variants=False: [[0.1, 0.2]],
    )

    branch_calls = {"global": 0, "local": 0}

    monkeypatch.setattr(
        "retrieval.global_community_recall",
        lambda *args, **kwargs: branch_calls.__setitem__("global", branch_calls["global"] + 1) or {
            "community_hits": [
                {
                    "chunk_id": "c00001",
                    "community_id": "c00001",
                    "text": "主要风险 | 风控部",
                    "score": 1.0,
                    "source": "community",
                    "metadata": {"node_ids": ["risk_1"], "community_size": 2},
                }
            ],
            "selected_communities": [{"community_id": "c00001"}],
            "descendant_hits": [],
        },
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: branch_calls.__setitem__("local", branch_calls["local"] + 1) or [
            (
                "vector",
                [
                    {
                        "chunk_id": "local_fallback",
                        "text": "fallback evidence",
                        "score": 0.7,
                        "source": "vector",
                        "metadata": {"page_idx": 3},
                    }
                ],
            )
        ],
    )

    result = pipeline.retrieve(
        "总结所有主要风险与部门关系",
        retrieval_config=RetrievalConfig(
            enable_global_mode=True,
            enable_cross_encoder=True,
            max_total_candidates=2,
            max_context_tokens=256,
        ),
    )

    assert branch_calls["global"] == 1
    assert branch_calls["local"] == 1
    assert result.pipeline["query_mode"] == "global"
    assert result.pipeline["global_mode_grounded"] is False
    assert result.pipeline["rerank_skipped"] == "global_mode"
    assert result.pipeline["rerank_ms"] == 0
    assert [chunk.chunk_id for chunk in result.chunks] == ["local_fallback"]


def test_grounded_global_mode_skips_embedding_and_local_fallback(monkeypatch):
    from retrieval import RetrievalPipeline

    pipeline = RetrievalPipeline(
        vector_store=object(),
        embedding_client=object(),
        kg_graph=_build_global_graph(),
        bm25_index=None,
        table_index=None,
        config=RetrievalConfig(enable_cross_encoder=False, max_total_candidates=2, max_context_tokens=256),
    )

    monkeypatch.setattr(
        "retrieval.preprocess_query",
        lambda raw_query, chat_history=None, **kwargs: PreprocessedQuery(
            original=raw_query,
            rewritten=raw_query,
            intent="hybrid",
            entity_types=["risk_item", "department"],
            table_conditions=[],
        ),
    )

    def fail_if_embed(*args, **kwargs):
        raise AssertionError("grounded global mode should not embed query vectors")

    def fail_if_local_recall(**kwargs):
        raise AssertionError("grounded global mode should not call local multi_path_recall")

    monkeypatch.setattr("retrieval.embed_queries", fail_if_embed)
    monkeypatch.setattr("retrieval.multi_path_recall", fail_if_local_recall)
    monkeypatch.setattr(
        "retrieval.global_community_recall",
        lambda *args, **kwargs: {
            "community_hits": [
                {
                    "chunk_id": "c00001",
                    "community_id": "c00001",
                    "text": "主要风险 | 风控部",
                    "score": 1.0,
                    "source": "community",
                    "metadata": {"node_ids": ["risk_1"], "community_size": 2},
                }
            ],
            "selected_communities": [{"community_id": "c00001"}],
            "descendant_hits": [
                {
                    "chunk_id": "risk_1",
                    "text": "risk node",
                    "score": 0.9,
                    "source": "kg",
                    "metadata": {"page_idx": 1},
                }
            ],
        },
    )

    result = pipeline.retrieve(
        "总结所有主要风险与部门关系",
        retrieval_config=RetrievalConfig(
            enable_global_mode=True,
            enable_cross_encoder=False,
            max_total_candidates=2,
            max_context_tokens=256,
        ),
    )

    assert result.pipeline["query_mode"] == "global"
    assert result.pipeline["global_mode_grounded"] is True
    assert result.pipeline["embed_query_ms"] == 0
