from types import SimpleNamespace

import networkx as nx

from index_registry import _tokenize_for_bm25, build_bm25_from_chunks
from prompt_builder import build_prompt
from retrieval import (
    RetrievalConfig,
    RetrievalChunk,
    RetrievalResult,
    _bm25_recall,
    filter_redundant,
    multi_path_recall,
    trim_chunks_by_source_budget,
)


def test_bm25_query_uses_same_tokenizer_as_index():
    query = "预算执行率超过80%的项目"
    chunk = SimpleNamespace(
        chunk_id="bm25-1",
        text="预算执行率超过80%的项目需要复核。",
        metadata=SimpleNamespace(source_file="report.md"),
    )

    assert _tokenize_for_bm25(query) != [query.lower()]

    bm25_index = build_bm25_from_chunks([chunk])
    results = _bm25_recall(query, bm25_index, RetrievalConfig(bm25_top_k=1))

    assert [item["chunk_id"] for item in results] == ["bm25-1"]


def test_project_candidate_keeps_prompt_safe_fields_only():
    from retrieval import project_candidate

    projected = project_candidate(
        {
            "chunk_id": "v1",
            "text": "A" * 1600,
            "score": 0.9,
            "source": "vector",
            "metadata": {
                "page_idx": 4,
                "section_title": "Budget",
                "entity_ids": ["n1", "n2"],
                "source_file": "secret.pdf",
                "table_data": {"raw": "payload"},
            },
        }
    )

    assert projected == {
        "chunk_id": "v1",
        "text": "A" * 1200,
        "score": 0.9,
        "source": "vector",
        "page_idx": 4,
        "section_title": "Budget",
        "entity_ids": ["n1", "n2"],
        "metadata": {
            "page_idx": 4,
            "entity_ids": ["n1", "n2"],
        },
    }


def test_project_candidate_infers_entity_ids_from_chunk_text_when_metadata_is_missing():
    from retrieval import project_candidate

    graph = nx.Graph()
    graph.add_node("n0001", label="A 题绿电直连型电氢氨园区优化运行", entity_type="paper_metadata", page_idx=0, properties={"field": "title"})
    graph.add_node("n0002", label="002196", entity_type="paper_metadata", page_idx=0, properties={"field": "id"})
    graph.add_node("n0015", label="3554元/吨", entity_type="metric", page_idx=1, properties={"field": "cost"})

    projected = project_candidate(
        {
            "chunk_id": "c00002",
            "text": "A 题绿电直连型电氢氨园区优化运行（编号 002196）",
            "score": 0.95,
            "source": "vector",
            "metadata": {
                "page_idx": 0,
                "section_path": ["摘 要"],
            },
        },
        kg_graph=graph,
    )

    assert projected["entity_ids"][:2] == ["n0001", "n0002"]
    assert projected["metadata"]["entity_ids"][:2] == ["n0001", "n0002"]


def test_source_aware_trim_honors_caps():
    from retrieval import trim_results_by_source_budget

    candidates = [
        {"chunk_id": "v1", "source": "vector", "score": 0.9},
        {"chunk_id": "v2", "source": "vector", "score": 0.8},
        {"chunk_id": "kg1", "source": "kg", "score": 0.7},
    ]

    trimmed = trim_results_by_source_budget(
        candidates,
        {"vector": 1, "kg": 1},
        max_total=2,
    )

    assert [item["chunk_id"] for item in trimmed] == ["v1", "kg1"]


def test_build_prompt_reapplies_source_caps_before_context():
    retrieval_result = RetrievalResult(
        chunks=[
            RetrievalChunk(
                chunk_id="v1",
                text="Vector primary",
                score=0.9,
                source="vector",
                section_title="Vector A",
            ),
            RetrievalChunk(
                chunk_id="v2",
                text="Vector overflow",
                score=0.8,
                source="vector",
                section_title="Vector B",
            ),
            RetrievalChunk(
                chunk_id="kg1",
                text="KG supporting fact",
                score=0.7,
                source="kg",
                section_title="KG A",
            ),
        ],
        total_candidates=3,
        pipeline={
            "per_source_caps": {"vector": 1, "kg": 1},
            "max_total_candidates": 2,
        },
        query_intent="hybrid",
        entity_types_used=["metric"],
    )

    messages = build_prompt(
        retrieval_result=retrieval_result,
        user_query="预算执行率超过80%的项目有哪些？",
    )

    prompt_text = messages[1]["content"]
    assert "[v1]" in prompt_text
    assert "[kg1]" in prompt_text
    assert "[v2]" not in prompt_text


def test_vector_search_projection_only_returns_whitelisted_metadata(monkeypatch):
    from vector_store import VectorStore

    store = VectorStore.__new__(VectorStore)

    class DummyCollection:
        def query(self, **kwargs):
            return {
                "ids": [["c0001"]],
                "documents": [["X" * 2000]],
                "metadatas": [[{
                    "page_idx": 3,
                    "section_path": '["Budget", "Execution"]',
                    "entity_ids": '["n1"]',
                    "source_file": "secret.pdf",
                }]],
                "distances": [[0.2]],
            }

    store._collection = DummyCollection()
    results = store.search(
        query_vector=[0.1, 0.2],
        top_k=1,
        text_char_limit=32,
        metadata_keys=["page_idx", "section_path", "entity_ids"],
    )

    assert len(results[0]["text"]) == 32
    assert set(results[0]["metadata"]) == {"page_idx", "section_path", "entity_ids"}
    assert "source_file" not in results[0]["metadata"]
    assert results[0]["metadata"]["entity_ids"] == ["n1"]


def test_retrieval_pipeline_trims_before_and_after_rerank(monkeypatch):
    from retrieval import RetrievalPipeline

    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=False,
        max_total_candidates=2,
        per_source_caps={"vector": 1, "kg": 1, "bm25": 2, "table": 2, "multi_query": 2},
        max_context_tokens=512,
    )
    pipeline = RetrievalPipeline(
        vector_store=DummyVectorStore(),
        embedding_client=DummyEmbeddingClient(),
        kg_graph=None,
        bm25_index=None,
        table_index=None,
        config=config,
    )

    monkeypatch.setattr(
        "retrieval.preprocess_query",
        lambda raw_query, chat_history=None, **kwargs: SimpleNamespace(
            original=raw_query,
            rewritten=raw_query,
            intent="hybrid",
            entity_types=["metric"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr("retrieval.embed_queries", lambda preprocessed, embedding_client, generate_variants=False: [[0.1, 0.2]])
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            ("vector", [
                {"chunk_id": "v1", "text": "vector-1", "score": 0.91, "source": "vector", "metadata": {"page_idx": 1}},
                {"chunk_id": "v2", "text": "vector-2", "score": 0.90, "source": "vector", "metadata": {"page_idx": 2}},
            ]),
            ("kg", [
                {"chunk_id": "kg1", "text": "kg-1", "score": 0.89, "source": "kg", "metadata": {"page_idx": 3}},
            ]),
        ],
    )
    monkeypatch.setattr(
        "retrieval.rrf_fusion",
        lambda labeled_results, k=60, top_n=20: [
            {"chunk_id": "v1", "text": "vector-1", "score": 0.91, "rrf_score": 0.91, "source": "vector", "metadata": {"page_idx": 1}},
            {"chunk_id": "v2", "text": "vector-2", "score": 0.90, "rrf_score": 0.90, "source": "vector", "metadata": {"page_idx": 2}},
            {"chunk_id": "kg1", "text": "kg-1", "score": 0.89, "rrf_score": 0.89, "source": "kg", "metadata": {"page_idx": 3}},
        ],
    )

    result = pipeline.retrieve("预算执行率超过80%的项目", retrieval_config=config)

    assert result.pipeline["pre_rerank_trimmed"] == 2
    assert result.pipeline["post_rerank_trimmed"] == 2
    assert result.pipeline["final_trimmed"] == 2
    assert [chunk.chunk_id for chunk in result.chunks] == ["v1", "kg1"]


def test_trim_chunks_by_source_budget_prefers_grounded_chunk_within_same_source_cap():
    chunks = [
        RetrievalChunk(
            chunk_id="v-generic",
            text="泛化背景说明",
            score=0.95,
            source="vector",
            entity_ids=[],
        ),
        RetrievalChunk(
            chunk_id="v-grounded",
            text="W4S1 表示风电4、光伏1的容量配比场景。",
            score=0.70,
            source="vector",
            entity_ids=["n0035"],
            metadata={"protected_evidence": True},
        ),
    ]

    trimmed = trim_chunks_by_source_budget(
        chunks,
        {"vector": 1},
        max_total=1,
    )

    assert [chunk.chunk_id for chunk in trimmed] == ["v-grounded"]


def test_filter_redundant_keeps_grounded_chunk_under_tight_token_budget():
    candidates = [
        {
            "chunk_id": "v-generic",
            "text": "A" * 800,
            "score": 0.95,
            "source": "vector",
            "metadata": {},
        },
        {
            "chunk_id": "kg-exact",
            "text": "W4S1 表示风电4、光伏1的容量配比场景。",
            "score": 0.70,
            "source": "kg",
            "metadata": {
                "entity_ids": ["n0035"],
                "entity_type": "metric",
                "protected_evidence": True,
            },
        },
    ]

    filtered = filter_redundant(candidates, max_context_tokens=30)

    assert [chunk.chunk_id for chunk in filtered] == ["kg-exact"]


def test_project_candidate_keeps_retrieval_critical_metadata():
    from retrieval import project_candidate

    kg_projected = project_candidate(
        {
            "chunk_id": "kg1",
            "text": "KG entity",
            "score": 0.7,
            "source": "kg",
            "metadata": {
                "page_idx": 2,
                "entity_type": "metric",
                "section_path": ["Overview"],
                "table_data": {"value": "82%"},
                "entity_ids": ["n1"],
                "source_file": "drop-me.pdf",
            },
        }
    )

    assert kg_projected["metadata"] == {
        "page_idx": 2,
        "section_path": ["Overview"],
        "entity_type": "metric",
        "entity_ids": ["n1"],
    }

    table_projected = project_candidate(
        {
            "chunk_id": "table1",
            "text": "Table row",
            "score": 0.8,
            "source": "table",
            "metadata": {
                "page_idx": 5,
                "table_data": {"value": "82%"},
                "entity_ids": ["n2"],
                "source_file": "drop-me.pdf",
            },
        }
    )

    assert table_projected["metadata"] == {
        "page_idx": 5,
        "table_data": {"value": "82%"},
        "entity_ids": ["n2"],
    }


def test_multi_path_recall_skips_vector_paths_when_vector_store_is_unavailable(monkeypatch):
    preprocessed = SimpleNamespace(
        original="原始问题",
        rewritten="改写问题",
        intent="hybrid",
    )

    monkeypatch.setattr(
        "retrieval._vector_recall",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("vector recall should be skipped")),
    )
    monkeypatch.setattr(
        "retrieval._multi_query_recall_wrapper",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("multi-query recall should be skipped")),
    )
    monkeypatch.setattr(
        "retrieval._kg_recall",
        lambda *args, **kwargs: [{"chunk_id": "kg1", "score": 0.8, "source": "kg"}],
    )

    results = multi_path_recall(
        preprocessed=preprocessed,
        query_vectors=[[0.1, 0.2]],
        vector_store=None,
        config=RetrievalConfig(enable_multi_query=True),
        kg_graph=object(),
        bm25_index=None,
        table_index=None,
        embedding_client=object(),
    )

    assert results == [("kg", [{"chunk_id": "kg1", "score": 0.8, "source": "kg"}])]
