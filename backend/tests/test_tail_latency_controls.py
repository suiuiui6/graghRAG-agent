from tests.request_helpers import admin_request
import asyncio
import time
from types import SimpleNamespace

from config import RetrievalConfig
from models import QueryOptions, QueryRequest
from retrieval import RetrievalPipeline
from retrieval import _needs_priority_kg_rescue
import routes.rag_query as rag_query_module


def test_query_degrades_before_cross_encoder_runs_over_budget(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 2, "bm25": 2, "table": 2, "multi_query": 2},
        rerank_budget_ms=0,
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
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {"chunk_id": f"v{i}", "text": f"vector-{i}", "score": 0.9 - i * 0.01, "source": "vector", "metadata": {}}
                    for i in range(6)
                ],
            )
        ],
    )
    def slow_rrf_fusion(labeled_results, k=60, top_n=20):
        time.sleep(0.01)
        return [
            {"chunk_id": f"v{i}", "text": f"vector-{i}", "score": 0.9 - i * 0.01, "rrf_score": 0.9 - i * 0.01, "source": "vector", "metadata": {}}
            for i in range(6)
        ]

    monkeypatch.setattr("retrieval.rrf_fusion", slow_rrf_fusion)
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("复杂问题", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "budget"


def test_query_degrades_before_cross_encoder_when_rerank_workload_is_too_large(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 2, "bm25": 2, "table": 2, "multi_query": 2},
    )
    config.rerank_max_chars = 800
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
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": f"v{i}",
                        "text": "x" * 600,
                        "score": 0.9 - i * 0.01,
                        "source": "vector",
                        "metadata": {},
                    }
                    for i in range(6)
                ],
            )
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("一个需要长上下文重排的复杂问题", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "workload"
    assert result.pipeline["rerank_workload_chars"] > config.rerank_max_chars


def test_cross_encoder_timeout_falls_back_to_pre_rerank_order(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 2, "bm25": 2, "table": 2, "multi_query": 2},
        rerank_budget_ms=20,
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
            intent="metric",
            entity_types=["metric"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": f"v{i}",
                        "text": f"vector-{i}",
                        "score": 0.9 - i * 0.01,
                        "source": "vector",
                        "metadata": {},
                    }
                    for i in range(4)
                ],
            ),
            (
                "bm25",
                [
                    {
                        "chunk_id": f"b{i}",
                        "text": f"bm25-{i}",
                        "score": 0.5 - i * 0.01,
                        "source": "bm25",
                        "metadata": {},
                    }
                    for i in range(2)
                ],
            ),
        ],
    )
    def slow_cross_encoder(query, candidates, top_k=10, model_name="BAAI/bge-reranker-base"):
        time.sleep(0.05)
        return list(reversed(candidates[:top_k]))

    monkeypatch.setattr("retrieval.cross_encoder_rerank", slow_cross_encoder)

    result = pipeline.retrieve("企业级 tail latency 风险问题", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "timeout"
    assert result.pipeline["pre_rerank_chunk_ids"][0] == result.pipeline["retrieval_chunk_ids"][0]


def test_cross_encoder_timeout_preserves_protected_table_candidate_outside_rerank_shortlist(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 2, "bm25": 2, "table": 2, "multi_query": 2},
        rerank_budget_ms=20,
    )
    config.rerank_max_candidates = 5
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
            intent="metric",
            entity_types=["metric", "dataset"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": f"v{i}",
                        "text": f"泛化背景块-{i}",
                        "score": 0.95 - i * 0.01,
                        "source": "vector",
                        "metadata": {},
                    }
                    for i in range(6)
                ],
            ),
            (
                "bm25",
                [
                    {
                        "chunk_id": "b0",
                        "text": "摘要里给出全满足率从39.2%跃升至69.2%",
                        "score": 0.40,
                        "source": "bm25",
                        "metadata": {},
                    }
                ],
            ),
            (
                "table",
                [
                    {
                        "chunk_id": "table_row_scenario_summary_99_指标摘要",
                        "text": '{"source_file":"paper.pdf","sheet_name":"scenario_summary","row_number":99,"column_name":"指标摘要","column_value":"95%","context":{"场景":"W2S2","指标摘要":"95%","弃电量":"120MWh/日"}}',
                        "score": 0.30,
                        "source": "table",
                        "metadata": {
                            "protected_evidence": True,
                            "table_data": {
                                "source_file": "paper.pdf",
                                "sheet_name": "scenario_summary",
                                "row_number": 99,
                                "column_name": "指标摘要",
                                "column_value": "95%",
                                "context": {
                                    "场景": "W2S2",
                                    "指标摘要": "95%",
                                    "弃电量": "120MWh/日",
                                },
                            },
                        },
                    }
                ],
            ),
        ],
    )

    def slow_cross_encoder(query, candidates, top_k=10, model_name="BAAI/bge-reranker-base"):
        time.sleep(0.05)
        return list(reversed(candidates[:top_k]))

    monkeypatch.setattr("retrieval.cross_encoder_rerank", slow_cross_encoder)

    result = pipeline.retrieve("在W2S2场景下，绿电消纳率是多少？", retrieval_config=config)

    assert result.pipeline["rerank_skipped"] == "timeout"
    assert "table_row_scenario_summary_99_指标摘要" in result.pipeline["pre_rerank_chunk_ids"]
    assert "table_row_scenario_summary_99_指标摘要" in result.pipeline["retrieval_chunk_ids"]


def test_query_degrades_before_cross_encoder_when_only_one_path_hits(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
    )
    pipeline = RetrievalPipeline(
        vector_store=DummyVectorStore(),
        embedding_client=DummyEmbeddingClient(),
        kg_graph=object(),
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
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "kg",
                [
                    {
                        "chunk_id": f"k{i}",
                        "text": f"kg-{i}",
                        "score": 0.9 - i * 0.01,
                        "source": "kg",
                        "entity_ids": [f"n{i:04d}"],
                        "metadata": {},
                    }
                    for i in range(6)
                ],
            )
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("一个实际上只有单路命中的问题", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "single_path"


def test_query_degrades_before_cross_encoder_for_summary_metric_queries_with_protected_kg(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            intent="metric",
            entity_types=["metric"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "kg",
                [
                    {
                        "chunk_id": "d0_n0012",
                        "text": '{"entity":{"node_id":"d0_n0012","entity_type":"metric","label":"603.45MWh","properties":{"name":"renewable generation","value":"603.45"}}}',
                        "score": 0.92,
                        "source": "kg",
                        "entity_ids": ["d0_n0012"],
                        "metadata": {
                            "entity_ids": ["d0_n0012"],
                            "entity_type": "metric",
                            "page_idx": 1,
                            "protected_evidence": True,
                        },
                        "protected_evidence": True,
                    },
                    {
                        "chunk_id": "d0_n0013",
                        "text": '{"entity":{"node_id":"d0_n0013","entity_type":"metric","label":"558.72MWh","properties":{"name":"total electricity use","value":"558.72"}}}',
                        "score": 0.88,
                        "source": "kg",
                        "entity_ids": ["d0_n0013"],
                        "metadata": {"entity_ids": ["d0_n0013"], "entity_type": "metric", "page_idx": 1},
                    },
                ],
            ),
            (
                "vector",
                [
                    {"chunk_id": f"v{i}", "text": f"vector-{i}", "score": 0.8 - i * 0.01, "source": "vector", "metadata": {}}
                    for i in range(4)
                ],
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("论文摘要中可再生能源发电量是多少 MWh？", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "summary_metric"


def test_query_degrades_before_cross_encoder_for_alias_definition_queries_with_protected_kg(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            entity_types=["dataset"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "kg",
                [
                    {
                        "chunk_id": "d0_n0035",
                        "text": '{"entity":{"node_id":"d0_n0035","entity_type":"dataset","label":"W4S1","properties":{"name":"maximum curtailment scenario"}}}',
                        "score": 0.92,
                        "source": "kg",
                        "entity_ids": ["d0_n0035"],
                        "metadata": {
                            "entity_ids": ["d0_n0035"],
                            "entity_type": "dataset",
                            "protected_evidence": True,
                        },
                        "protected_evidence": True,
                    },
                ],
            ),
            (
                "vector",
                [
                    {"chunk_id": f"v{i}", "text": f"vector-{i}", "score": 0.8 - i * 0.01, "source": "vector", "metadata": {}}
                    for i in range(5)
                ],
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("论文中提到的wind 4 solar 1场景代表什么含义?", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "alias_definition"


def test_query_degrades_before_cross_encoder_for_figure_inventory_queries_with_inventory_chunk(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            entity_types=["section_header", "dataset"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": "fig_inventory",
                        "text": "图 1、图 2、图 3、图 4、图 5、图 6 的分析结果汇总",
                        "score": 0.91,
                        "source": "vector",
                        "metadata": {},
                    },
                    *[
                        {"chunk_id": f"v{i}", "text": f"vector-{i}", "score": 0.8 - i * 0.01, "source": "vector", "metadata": {}}
                        for i in range(5)
                    ],
                ],
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("论文中所有的图(figure)有哪些？", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "figure_inventory"


def test_query_degrades_before_cross_encoder_for_specific_figure_reference_with_exact_chunk(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            intent="policy_lookup",
            entity_types=["section_header", "dataset"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": "c00031",
                        "text": "图 5— 问题四离网与储能分析（左：三种模式经济性对比；右：储能充放电调度）",
                        "score": 0.92,
                        "source": "vector",
                        "metadata": {},
                    },
                    *[
                        {"chunk_id": f"v{i}", "text": f"background-{i}", "score": 0.8 - i * 0.01, "source": "vector", "metadata": {}}
                        for i in range(5)
                    ],
                ],
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("图 5 展示了什么内容？", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "figure_reference"


def test_query_degrades_before_cross_encoder_for_compliance_metric_inventory_queries(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            intent="metric",
            entity_types=["metric"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": "c00002",
                        "text": "问题二绿电指标全满足率39.2%，问题三绿电指标全满足率69.2%，新能源自发自用率28.2%，上网电量比例35.9%",
                        "score": 0.94,
                        "source": "vector",
                        "metadata": {},
                    },
                    *[
                        {"chunk_id": f"v{i}", "text": f"background-{i}", "score": 0.8 - i * 0.01, "source": "vector", "metadata": {}}
                        for i in range(2)
                    ],
                ],
            ),
            (
                "kg",
                [
                    {
                        "chunk_id": "d0_n0146",
                        "text": '{"entity":{"node_id":"d0_n0146","entity_type":"metric","label":"39.2%","properties":{"name":"green compliance rate","value":"39.2"}}}',
                        "score": 0.9,
                        "source": "kg",
                        "entity_ids": ["d0_n0146"],
                        "metadata": {"entity_ids": ["d0_n0146"], "entity_type": "metric", "page_idx": 1},
                    },
                    {
                        "chunk_id": "d0_n0147",
                        "text": '{"entity":{"node_id":"d0_n0147","entity_type":"metric","label":"69.2%","properties":{"name":"green compliance rate","value":"69.2"}}}',
                        "score": 0.88,
                        "source": "kg",
                        "entity_ids": ["d0_n0147"],
                        "metadata": {"entity_ids": ["d0_n0147"], "entity_type": "metric", "page_idx": 1},
                    },
                    {
                        "chunk_id": "d0_n0148",
                        "text": '{"entity":{"node_id":"d0_n0148","entity_type":"metric","label":"28.2%","properties":{"name":"self-consumption rate","value":"28.2"}}}',
                        "score": 0.87,
                        "source": "kg",
                        "entity_ids": ["d0_n0148"],
                        "metadata": {"entity_ids": ["d0_n0148"], "entity_type": "metric", "page_idx": 1},
                    },
                ],
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("论文里出现了哪些关于'绿电指标合规率'的具体数值？", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "compliance_metric_inventory"


def test_query_degrades_before_cross_encoder_for_extrema_metric_queries_with_summary_anchor(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            intent="compare",
            entity_types=["metric"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": "c00015",
                        "text": "成本最低的模式为3554元/吨，成本最高的模式为7111元/吨，均在摘要中给出",
                        "score": 0.95,
                        "source": "vector",
                        "metadata": {},
                    },
                    *[
                        {"chunk_id": f"v{i}", "text": f"background-{i}", "score": 0.8 - i * 0.01, "source": "vector", "metadata": {}}
                        for i in range(4)
                    ],
                ],
            ),
            (
                "kg",
                [
                    {
                        "chunk_id": "d0_n0015",
                        "text": '{"entity":{"node_id":"d0_n0015","entity_type":"metric","label":"3554元/吨","properties":{"name":"lowest cost","value":"3554"}}}',
                        "score": 0.86,
                        "source": "kg",
                        "entity_ids": ["d0_n0015"],
                        "metadata": {"entity_ids": ["d0_n0015"], "entity_type": "metric", "page_idx": 1},
                    },
                    {
                        "chunk_id": "d0_n0016",
                        "text": '{"entity":{"node_id":"d0_n0016","entity_type":"metric","label":"7111元/吨","properties":{"name":"highest cost","value":"7111"}}}',
                        "score": 0.85,
                        "source": "kg",
                        "entity_ids": ["d0_n0016"],
                        "metadata": {"entity_ids": ["d0_n0016"], "entity_type": "metric", "page_idx": 1},
                    },
                ],
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("成本最低和最高的两种运营模式分别对应多少元/吨？", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "extrema_metric"


def test_query_degrades_before_cross_encoder_for_method_lookup_with_exact_method_chunk(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            intent="policy_lookup",
            entity_types=["claim"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": "c00002",
                        "text": "问题二采用混合整数线性规划（MILP）模型求解，并使用大M法处理购售电互斥。",
                        "score": 0.95,
                        "source": "vector",
                        "metadata": {},
                    },
                    {"chunk_id": "c00005", "text": "全文问题设置概述", "score": 0.88, "source": "vector", "metadata": {}},
                    {
                        "chunk_id": "d0_n0153",
                        "text": '{"entity":{"node_id":"d0_n0153","entity_type":"metric","label":"216.77MWh","properties":{"name":"feed-in electricity","value":"216.77"}}}',
                        "score": 0.86,
                        "source": "kg",
                        "entity_ids": ["d0_n0153"],
                        "metadata": {"entity_ids": ["d0_n0153"], "entity_type": "metric", "page_idx": 1},
                    },
                    {
                        "chunk_id": "d0_n0160",
                        "text": '{"entity":{"node_id":"d0_n0160","entity_type":"metric","label":"97,781元","properties":{"name":"electricity purchase cost","value":"97781"}}}',
                        "score": 0.84,
                        "source": "kg",
                        "entity_ids": ["d0_n0160"],
                        "metadata": {"entity_ids": ["d0_n0160"], "entity_type": "metric", "page_idx": 1},
                    },
                    {"chunk_id": "k_bg_1", "text": "kg-background-1", "score": 0.83, "source": "kg", "metadata": {}},
                    {"chunk_id": "k_bg_2", "text": "kg-background-2", "score": 0.82, "source": "kg", "metadata": {}},
                ],
            )
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("这篇论文采用了什么方法求解问题2？(混合证书线性规化方法?)", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "claim_verification"


def test_query_degrades_before_cross_encoder_for_numeric_delta_claim_with_exact_evidence(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            intent="compare",
            entity_types=["claim"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": "c00002",
                        "text": "离网无储能场景产量为9023吨，离网带储能场景产量为10903吨，产量提升20.8%。",
                        "score": 0.95,
                        "source": "vector",
                        "metadata": {},
                    },
                    {"chunk_id": "c00026", "text": "问题四与政策建议", "score": 0.9, "source": "vector", "metadata": {}},
                    {
                        "chunk_id": "d0_n0061",
                        "text": '{"entity":{"node_id":"d0_n0061","entity_type":"metric","label":"10903","properties":{"name":"annual ammonia production","value":"10903","unit":"tons/year","context":"off-grid with storage"}},"neighbors":[{"node_id":"d0_n0080","entity_type":"scenario","label":"storage_enabled","relation":"reported_in"},{"node_id":"d0_n0081","entity_type":"metric_family","label":"annual ammonia production","relation":"same_metric"}]}',
                        "score": 0.89,
                        "source": "kg",
                        "entity_ids": ["d0_n0061"],
                        "metadata": {"entity_ids": ["d0_n0061"], "entity_type": "metric"},
                    },
                    {
                        "chunk_id": "d0_n0060",
                        "text": '{"entity":{"node_id":"d0_n0060","entity_type":"metric","label":"9023","properties":{"name":"annual ammonia production","value":"9023","unit":"tons/year","context":"off-grid without storage"}},"neighbors":[{"node_id":"d0_n0080","entity_type":"scenario","label":"storage_enabled","relation":"reported_in"},{"node_id":"d0_n0081","entity_type":"metric_family","label":"annual ammonia production","relation":"same_metric"}]}',
                        "score": 0.88,
                        "source": "kg",
                        "entity_ids": ["d0_n0060"],
                        "metadata": {"entity_ids": ["d0_n0060"], "entity_type": "metric"},
                    },
                    {"chunk_id": "k_bg_1", "text": "kg-background-1", "score": 0.87, "source": "kg", "metadata": {}},
                    {"chunk_id": "k_bg_2", "text": "kg-background-2", "score": 0.86, "source": "kg", "metadata": {}},
                ],
            )
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("离网带储能场景相比无储能场景，产量提升了多少？", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "claim_verification"


def test_query_degrades_before_cross_encoder_for_claim_validation_with_supported_refutation(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            intent="claim_check",
            entity_types=["claim"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": "c00023",
                        "text": "文档未证明储能会降低产量；相反，带储能场景年产量10903吨，高于无储能场景9023吨。",
                        "score": 0.95,
                        "source": "vector",
                        "metadata": {},
                    },
                    {"chunk_id": "c00007", "text": "储能模型假设与约束", "score": 0.9, "source": "vector", "metadata": {}},
                    {
                        "chunk_id": "d0_n0061",
                        "text": '{"entity":{"node_id":"d0_n0061","entity_type":"metric","label":"10903","properties":{"name":"annual ammonia production","value":"10903"}}}',
                        "score": 0.89,
                        "source": "kg",
                        "entity_ids": ["d0_n0061"],
                        "metadata": {"entity_ids": ["d0_n0061"], "entity_type": "metric"},
                    },
                    {
                        "chunk_id": "d0_n0060",
                        "text": '{"entity":{"node_id":"d0_n0060","entity_type":"metric","label":"9023","properties":{"name":"annual ammonia production","value":"9023"}}}',
                        "score": 0.88,
                        "source": "kg",
                        "entity_ids": ["d0_n0060"],
                        "metadata": {"entity_ids": ["d0_n0060"], "entity_type": "metric"},
                    },
                    {"chunk_id": "k_bg_1", "text": "kg-background-1", "score": 0.87, "source": "kg", "metadata": {}},
                    {"chunk_id": "k_bg_2", "text": "kg-background-2", "score": 0.86, "source": "kg", "metadata": {}},
                ],
            )
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("本论文证明了储能装置反而会降低园区产量，这个结论对吗？", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "claim_verification"


def test_claim_validation_preserves_paired_metric_evidence_after_redundancy_filter(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            intent="claim_check",
            entity_types=["claim"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": "c00023",
                        "text": "联网模式的核心价值在于提升产量与降低吨氨成本。",
                        "score": 0.95,
                        "source": "vector",
                        "metadata": {},
                    },
                    {"chunk_id": "c00007", "text": "储能模型假设与约束", "score": 0.9, "source": "vector", "metadata": {}},
                ],
            ),
            (
                "kg",
                [
                    {
                        "chunk_id": "d0_n0061",
                        "text": '{"entity":{"node_id":"d0_n0061","entity_type":"metric","label":"10903","properties":{"name":"annual ammonia production","value":"10903"}}}',
                        "score": 0.89,
                        "source": "kg",
                        "entity_ids": ["d0_n0061"],
                        "metadata": {"entity_ids": ["d0_n0061"], "entity_type": "metric"},
                    },
                    {
                        "chunk_id": "d0_n0060",
                        "text": '{"entity":{"node_id":"d0_n0060","entity_type":"metric","label":"9023","properties":{"name":"annual ammonia production","value":"9023"}}}',
                        "score": 0.88,
                        "source": "kg",
                        "entity_ids": ["d0_n0060"],
                        "metadata": {"entity_ids": ["d0_n0060"], "entity_type": "metric"},
                    },
                ],
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("本论文证明了储能装置反而会降低园区产量，这个结论对吗？", retrieval_config=config)

    final_chunk_ids = result.pipeline["final_context_chunk_ids"]
    assert "d0_n0061" in final_chunk_ids
    assert "d0_n0060" in final_chunk_ids


def test_query_degrades_before_cross_encoder_for_direct_lookup_when_shortlist_is_compact(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            intent="policy_lookup",
            entity_types=["claim"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
                (
                    "vector",
                    [
                        {
                            "chunk_id": "c00028",
                        "text": "建立碳-电-氢-氨多市场耦合优化模型，属于未纳入碳交易收益这一模型不足的改进方向。",
                        "score": 0.93,
                        "source": "vector",
                        "metadata": {},
                    },
                        {"chunk_id": "v1", "text": "other", "score": 0.8, "source": "vector", "metadata": {}},
                        {"chunk_id": "v2", "text": "other-2", "score": 0.79, "source": "vector", "metadata": {}},
                        {"chunk_id": "v3", "text": "other-3", "score": 0.78, "source": "vector", "metadata": {}},
                        {"chunk_id": "v4", "text": "other-4", "score": 0.77, "source": "vector", "metadata": {}},
                    ],
                ),
                ("kg", [{"chunk_id": "k1", "text": "kg-other", "score": 0.5, "source": "kg", "metadata": {}}]),
            ],
        )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("碳-电-氢-氨多市场耦合优化模型属于什么改进方向？", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "direct_lookup"


def test_query_degrades_before_cross_encoder_for_summary_metric_inventory_queries(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
    )
    pipeline = RetrievalPipeline(
        vector_store=DummyVectorStore(),
        embedding_client=DummyEmbeddingClient(),
        kg_graph=None,
        bm25_index=None,
        table_index=object(),
        config=config,
    )

    monkeypatch.setattr(
        "retrieval.preprocess_query",
        lambda raw_query, chat_history=None, **kwargs: SimpleNamespace(
            original=raw_query,
            rewritten=raw_query,
            intent="metric",
            entity_types=["metric"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "kg",
                [
                    {
                        "chunk_id": "d0_n0147",
                        "text": '{"entity":{"node_id":"d0_n0147","entity_type":"metric","label":"81918元","properties":{"name":"selling revenue","value":"81918"}}}',
                        "score": 0.94,
                        "source": "kg",
                        "entity_ids": ["d0_n0147"],
                        "metadata": {"entity_ids": ["d0_n0147"], "entity_type": "metric", "page_idx": 1},
                    },
                    {
                        "chunk_id": "d0_n0146",
                        "text": '{"entity":{"node_id":"d0_n0146","entity_type":"metric","label":"97721元","properties":{"name":"power purchase cost","value":"97721"}}}',
                        "score": 0.93,
                        "source": "kg",
                        "entity_ids": ["d0_n0146"],
                        "metadata": {"entity_ids": ["d0_n0146"], "entity_type": "metric", "page_idx": 1},
                    },
                    {
                        "chunk_id": "d0_n0148",
                        "text": '{"entity":{"node_id":"d0_n0148","entity_type":"metric","label":"53000元","properties":{"name":"wind solar generation cost","value":"53000"}}}',
                        "score": 0.92,
                        "source": "kg",
                        "entity_ids": ["d0_n0148"],
                        "metadata": {"entity_ids": ["d0_n0148"], "entity_type": "metric", "page_idx": 1},
                    },
                ],
            ),
            (
                "table",
                [
                    {
                        "chunk_id": "table_metrics",
                        "text": "购电成本、售电收益、自发自用率、上网比例等摘要指标汇总",
                        "score": 0.90,
                        "source": "table",
                        "metadata": {},
                    }
                ],
            ),
            (
                "vector",
                [
                    {"chunk_id": "c00024", "text": "连续制氨模式下自发自用率均值 69.2%", "score": 0.80, "source": "vector", "metadata": {}},
                    {"chunk_id": "c00013", "text": "离散模式下上网比例为 35.9%", "score": 0.79, "source": "vector", "metadata": {}},
                ],
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("在摘要中给出的电力流向相关 metric (购电、售电、自发自用率等)有哪些？", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "summary_metric_inventory"


def test_query_degrades_before_cross_encoder_for_method_comparison_queries_with_grounded_summary(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=6,
        per_source_caps={"vector": 6, "kg": 6, "bm25": 2, "table": 2, "multi_query": 2},
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
            entity_types=["process_step", "metric"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": "c00005",
                        "text": "问题二采用混合整数线性规划（MILP），问题三采用线性规划（LP），两者差异体现在离散启停与连续调节。",
                        "score": 0.95,
                        "source": "vector",
                        "metadata": {},
                    },
                    {
                        "chunk_id": "c00027",
                        "text": "问题二到问题三的对比揭示了连续柔性调节相较离散启停的改进。",
                        "score": 0.90,
                        "source": "vector",
                        "metadata": {},
                    },
                    {"chunk_id": "v1", "text": "background-1", "score": 0.82, "source": "vector", "metadata": {}},
                    {"chunk_id": "v2", "text": "background-2", "score": 0.81, "source": "vector", "metadata": {}},
                    {"chunk_id": "v3", "text": "background-3", "score": 0.80, "source": "vector", "metadata": {}},
                    {"chunk_id": "v4", "text": "background-4", "score": 0.79, "source": "vector", "metadata": {}},
                ],
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("解决问题二的核心建模方法及其与问题三方法的差异是什么？", retrieval_config=config)

    assert result.pipeline["rerank_budget_triggered"] is True
    assert result.pipeline["rerank_skipped"] == "comparison_rescue"


def test_cross_encoder_only_reranks_budgeted_shortlist(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=8,
        per_source_caps={"vector": 8, "kg": 4, "bm25": 2, "table": 2, "multi_query": 2},
    )
    config.rerank_max_candidates = 4
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
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {"chunk_id": f"v{i}", "text": f"vector-{i}", "score": 1.0 - i * 0.01, "source": "vector", "metadata": {}}
                    for i in range(4)
                ],
            ),
            (
                "bm25",
                [
                    {"chunk_id": f"b{i}", "text": f"bm25-{i}", "score": 0.8 - i * 0.01, "source": "bm25", "metadata": {}}
                    for i in range(4)
                ],
            ),
        ],
    )

    seen = {}

    def record_cross_encoder(query, candidates, top_k=10, model_name="BAAI/bge-reranker-base"):
        seen["count"] = len(candidates)
        return candidates[:top_k], None

    monkeypatch.setattr("retrieval.cross_encoder_rerank", record_cross_encoder)

    result = pipeline.retrieve("一个需要多路召回但只应重排短名单的问题", retrieval_config=config)

    assert seen["count"] == config.rerank_max_candidates
    assert result.pipeline["rerank_candidate_count"] == config.rerank_max_candidates


def test_direct_lookup_queries_skip_rerank_when_exact_evidence_is_already_present(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=8,
        per_source_caps={"vector": 8, "kg": 4, "bm25": 2, "table": 2, "multi_query": 2},
    )
    config.rerank_max_candidates = 4
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
            intent="policy_lookup",
            entity_types=["metric"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {"chunk_id": "g1", "text": "generic chunk 1", "score": 0.99, "source": "vector", "metadata": {}},
                    {"chunk_id": "g2", "text": "generic chunk 2", "score": 0.98, "source": "vector", "metadata": {}},
                    {"chunk_id": "g3", "text": "generic chunk 3", "score": 0.97, "source": "vector", "metadata": {}},
                    {"chunk_id": "g4", "text": "generic chunk 4", "score": 0.96, "source": "vector", "metadata": {}},
                    {"chunk_id": "python", "text": "The implementation uses Python 3.10 and Pandas.", "score": 0.40, "source": "vector", "metadata": {}},
                ],
            ),
            (
                "bm25",
                [
                    {"chunk_id": "b1", "text": "other evidence", "score": 0.50, "source": "bm25", "metadata": {}},
                ],
            ),
        ],
    )

    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("代码实现使用了哪个版本的 Python？", retrieval_config=config)

    assert result.pipeline["rerank_skipped"] == "direct_lookup"
    assert "python" in result.pipeline["pre_rerank_chunk_ids"]


def test_high_recall_queries_expand_rerank_shortlist_before_workload_guard(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=8,
        per_source_caps={"vector": 8, "kg": 4, "bm25": 2, "table": 2, "multi_query": 2},
    )
    config.rerank_max_candidates = 4
    config.rerank_max_chars = 4096
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
            intent="policy_lookup",
            entity_types=["section_header", "dataset"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {
                        "chunk_id": f"f{i}",
                        "text": "图内容 " + ("x" * 500),
                        "score": 0.95 - i * 0.01,
                        "source": "vector",
                        "metadata": {},
                    }
                    for i in range(9)
                ],
            ),
            (
                "bm25",
                [
                    {"chunk_id": "b1", "text": "figure summary", "score": 0.4, "source": "bm25", "metadata": {}},
                ],
            ),
        ],
    )

    seen = {}

    def record_cross_encoder(query, candidates, top_k=10, model_name="BAAI/bge-reranker-base"):
        seen["count"] = len(candidates)
        return candidates[:top_k], None

    monkeypatch.setattr("retrieval.cross_encoder_rerank", record_cross_encoder)

    result = pipeline.retrieve("论文中所有的图(figure)有哪些？", retrieval_config=config)

    assert seen["count"] == 6
    assert result.pipeline.get("rerank_skipped") is None
    assert result.pipeline["rerank_candidate_count"] == 6
    assert result.pipeline["rerank_workload_chars"] < config.rerank_max_chars


def test_all_figure_queries_preserve_inventory_chunk_in_rerank_shortlist(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=8,
        per_source_caps={"vector": 8, "kg": 4, "bm25": 2, "table": 2, "multi_query": 2},
    )
    config.rerank_max_candidates = 4
    config.rerank_high_recall_max_candidates = 6
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
            intent="policy_lookup",
            entity_types=["section_header", "dataset"],
            table_conditions=[],
        ),
    )
    generic_chunks = [
        {
            "chunk_id": f"g{i}",
            "text": f"泛化背景总结 {i}",
            "score": 0.99 - i * 0.01,
            "source": "vector",
            "metadata": {},
        }
        for i in range(6)
    ]
    inventory_chunk = {
        "chunk_id": "fig_inventory",
        "text": "图 1、图 2、图 3、图 4、图 5、图 6 的分析结果汇总",
        "score": 0.20,
        "source": "vector",
        "metadata": {},
    }
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            ("vector", [*generic_chunks, inventory_chunk]),
            ("bm25", [{"chunk_id": "b1", "text": "图示目录", "score": 0.3, "source": "bm25", "metadata": {}}]),
        ],
    )

    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("论文中所有的图(figure)有哪些？", retrieval_config=config)

    assert result.pipeline["rerank_skipped"] == "figure_inventory"
    assert "fig_inventory" in result.pipeline["final_context_chunk_ids"]


def test_metric_queries_do_not_protect_generic_english_term_chunks(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyVectorStore:
        pass

    config = RetrievalConfig(
        enable_cross_encoder=True,
        max_total_candidates=8,
        per_source_caps={"vector": 8, "kg": 4, "bm25": 2, "table": 2, "multi_query": 2},
    )
    config.rerank_max_candidates = 4
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
            intent="metric",
            entity_types=["metric"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            (
                "vector",
                [
                    {"chunk_id": "m1", "text": "95.4% renewable utilization", "score": 0.99, "source": "vector", "metadata": {}},
                    {"chunk_id": "m2", "text": "9023 tons output", "score": 0.98, "source": "vector", "metadata": {}},
                    {"chunk_id": "m3", "text": "10903 tons output", "score": 0.97, "source": "vector", "metadata": {}},
                    {"chunk_id": "m4", "text": "173.7 MWh curtailment", "score": 0.96, "source": "vector", "metadata": {}},
                    {"chunk_id": "policy", "text": "curtailment rate should stay below 10% according to policy advice", "score": 0.40, "source": "vector", "metadata": {}},
                ],
            ),
            (
                "bm25",
                [
                    {"chunk_id": "b1", "text": "other metric evidence", "score": 0.50, "source": "bm25", "metadata": {}},
                ],
            ),
        ],
    )

    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cross encoder should be skipped")),
    )

    result = pipeline.retrieve("论文摘要给出的可再生能源弃电率(curtailment rate)是多少？", retrieval_config=config)

    assert result.pipeline["rerank_skipped"] == "direct_lookup"
    assert result.pipeline["rerank_candidate_count"] == 4
    assert "policy" not in result.pipeline["pre_rerank_chunk_ids"][: result.pipeline["rerank_candidate_count"]]


def test_summary_metric_queries_preserve_matching_kg_metric_candidate(monkeypatch):
    preprocessed = SimpleNamespace(
        original="论文摘要给出的可再生能源弃电率(curtailment rate)是多少？",
        rewritten="论文摘要给出的可再生能源弃电率(curtailment rate)是多少？",
        intent="metric",
        entity_types=["metric"],
        table_conditions=[],
    )

    assert _needs_priority_kg_rescue(preprocessed) is True


def test_rag_query_marks_degraded_mode_in_metadata(monkeypatch):
    class DummyPipeline:
        pass

    class DummyGenerator:
        def __init__(self, retrieval_pipeline, config=None):
            self.retrieval_pipeline = retrieval_pipeline
            self.config = config

        def generate(
            self,
            query,
            chat_history=None,
            max_context_tokens=12000,
            retrieval_config=None,
        ):
            return {
                "answer": "degraded answer",
                "sources": [],
                "metadata": {
                    "model": "test-model",
                    "intent": "hybrid",
                    "retrieval_latency_ms": 2,
                    "generation_latency_ms": 3,
                    "total_latency_ms": 5,
                    "has_citations": False,
                    "has_table": False,
                    "token_usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    "rerank_budget_triggered": True,
                    "pre_rerank_chunk_ids": ["c1", "c2", "c3"],
                    "final_context_chunk_ids": ["c1", "c2"],
                },
            }

    monkeypatch.setattr(rag_query_module, "_rag_pipeline", DummyPipeline())
    monkeypatch.setattr(rag_query_module, "_init_rag_pipeline", lambda: True)
    monkeypatch.setattr("generator.RAGGenerator", DummyGenerator)

    response = asyncio.run(
        rag_query_module.rag_query(
            QueryRequest(query="复杂问题", options=QueryOptions(include_sources=True)),
            request=admin_request(),
        )
    )

    assert response.metadata["degraded_mode"] == "rerank_skipped"
