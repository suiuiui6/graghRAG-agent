import asyncio

import pytest
from pydantic import ValidationError

from models import QueryOptions, QueryRequest
from prompt_builder import build_prompt
from generator import GenerationResult, RAGGenerator
from retrieval import RetrievalChunk, RetrievalConfig, RetrievalResult, _multi_query_recall_wrapper
import routes.rag_query as rag_query_module


def test_query_options_exposes_budget_controls():
    opts = QueryOptions()
    retrieval_config = rag_query_module._build_retrieval_config(opts)

    assert opts.max_total_candidates == 5
    assert opts.max_context_tokens == 4000
    assert opts.enable_multi_query is False
    assert opts.enable_cross_encoder is True
    assert retrieval_config.vector_top_k == 2
    assert retrieval_config.kg_top_k == 2
    assert retrieval_config.bm25_top_k == 1
    assert retrieval_config.table_top_k == 1
    assert retrieval_config.multi_query_top_k == 1


def test_budget_overrides_propagate_into_prompt_truncation():
    opts = QueryOptions(
        max_total_candidates=6,
        max_context_tokens=512,
        per_source_caps={"vector": 3, "kg": 2, "bm25": 1},
    )
    retrieval_result = RetrievalResult(
        chunks=[
            RetrievalChunk(
                chunk_id="c00001",
                text="A" * 6000,
                score=0.9,
                source="vector",
                section_title="Budget",
            )
        ],
        total_candidates=1,
        pipeline={},
        query_intent="metric",
        entity_types_used=["metric"],
    )

    messages, prompt_meta = build_prompt(
        retrieval_result=retrieval_result,
        user_query="What is the budget status?",
        max_context_tokens=opts.max_context_tokens,
        return_metadata=True,
    )

    assert opts.max_total_candidates == 6
    assert opts.per_source_caps["vector"] == 3
    assert prompt_meta["context_tokens"] <= opts.max_context_tokens
    assert messages[1]["role"] == "user"


def test_domain_hint_is_counted_inside_context_budget():
    retrieval_result = RetrievalResult(
        chunks=[
            RetrievalChunk(
                chunk_id="c00002",
                text="B" * 300,
                score=0.8,
                source="vector",
                section_title="Notes",
            )
        ],
        total_candidates=1,
        pipeline={},
        query_intent="hybrid",
        entity_types_used=["project_metadata"],
        domain_hint="H" * 100,
    )

    messages, prompt_meta = build_prompt(
        retrieval_result=retrieval_result,
        user_query="Explain the notes.",
        max_context_tokens=32,
        return_metadata=True,
    )

    assert "HHHH" in messages[1]["content"]
    assert prompt_meta["context_tokens"] <= 32


def test_build_prompt_prefers_compact_metric_answers_before_tables():
    retrieval_result = RetrievalResult(
        chunks=[
            RetrievalChunk(
                chunk_id="c00003",
                text="问题二绿电指标全满足率 39.2%，问题三绿电指标全满足率 69.2%。",
                score=0.9,
                source="vector",
                section_title="摘要",
            )
        ],
        total_candidates=1,
        pipeline={},
        query_intent="metric",
        entity_types_used=["metric"],
    )

    messages, _ = build_prompt(
        retrieval_result=retrieval_result,
        user_query="摘要中讨论的两种连续调节方式分别使绿电合规率达到了什么水平？",
        max_context_tokens=256,
        return_metadata=True,
    )

    assert "Use a Markdown table only when comparing 3 or more facts" in messages[1]["content"]
    assert "For 1-2 facts, prefer one short cited sentence" in messages[1]["content"]


def test_query_options_reject_invalid_per_source_caps():
    with pytest.raises(ValidationError):
        QueryOptions(per_source_caps={"vector": -1})

    with pytest.raises(ValidationError):
        QueryOptions(per_source_caps={"vector": 0})

    with pytest.raises(ValidationError):
        QueryOptions(per_source_caps={"unknown": 2})


def test_multi_query_top_k_limits_multi_query_recall(monkeypatch):
    class DummyEmbeddingClient:
        def embed_query(self, query):
            return [float(len(query))]

    class DummyVectorStore:
        def __init__(self):
            self.top_ks = []

        def search(self, query_vector, top_k):
            self.top_ks.append(top_k)
            return [
                {
                    "chunk_id": f"c{idx:05d}",
                    "text": f"chunk-{idx}",
                    "score": 0.9 - idx * 0.01,
                    "source": "vector",
                    "metadata": {},
                }
                for idx in range(top_k + 1)
            ]

    monkeypatch.setattr(
        "retrieval._generate_query_variants",
        lambda original_query, embedding_client: ["v1", "v2", "v3"],
    )

    store = DummyVectorStore()
    config = RetrievalConfig(enable_multi_query=True, multi_query_top_k=2)
    results = _multi_query_recall_wrapper(
        "query",
        DummyEmbeddingClient(),
        store,
        config,
    )

    assert store.top_ks == [2, 2]
    assert len(results) == 2
    assert all(result["source"] == "multi_query" for result in results)


def test_rag_query_uses_request_scoped_budget_without_mutating_shared_pipeline(monkeypatch):
    recorded_configs = []

    class DummyPipeline:
        def __init__(self):
            self.config = object()

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
            recorded_configs.append(retrieval_config)
            return {
                "answer": f"answer:{query}",
                "sources": [],
                "metadata": {
                    "model": "test-model",
                    "intent": "hybrid",
                    "retrieval_latency_ms": 1,
                    "generation_latency_ms": 1,
                    "total_latency_ms": 2,
                    "has_citations": False,
                    "has_table": False,
                    "token_usage": {},
                },
            }

    shared_pipeline = DummyPipeline()
    original_config = shared_pipeline.config

    monkeypatch.setattr(rag_query_module, "_rag_pipeline", shared_pipeline)
    monkeypatch.setattr(rag_query_module, "_init_rag_pipeline", lambda: True)
    monkeypatch.setattr("generator.RAGGenerator", DummyGenerator)

    first_req = QueryRequest(
        query="first",
        options=QueryOptions(
            max_total_candidates=6,
            max_context_tokens=2048,
            enable_multi_query=True,
            per_source_caps={"vector": 3, "kg": 1},
        ),
    )
    second_req = QueryRequest(
        query="second",
        options=QueryOptions(
            max_total_candidates=8,
            max_context_tokens=1024,
            enable_global_mode=True,
            per_source_caps={"bm25": 4},
        ),
    )

    async def run_two():
        return await asyncio.gather(
            rag_query_module.rag_query(first_req),
            rag_query_module.rag_query(second_req),
        )

    first_resp, second_resp = asyncio.run(run_two())

    assert shared_pipeline.config is original_config
    assert len(recorded_configs) == 2
    assert recorded_configs[0].max_total_candidates == 6
    assert recorded_configs[0].enable_multi_query is True
    assert recorded_configs[0].per_source_caps["vector"] == 3
    assert recorded_configs[0].per_source_caps["table"] == 1
    assert recorded_configs[1].max_total_candidates == 8
    assert recorded_configs[1].enable_global_mode is True
    assert recorded_configs[1].per_source_caps["bm25"] == 4
    assert first_resp.metadata["budget"]["per_source_caps"]["kg"] == 1
    assert second_resp.metadata["budget"]["per_source_caps"]["vector"] == 2


def test_rag_query_response_preserves_entity_ids_for_eval_consumers(monkeypatch):
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
                "answer": "Answer [d0_n0035]",
                "sources": [
                    {
                        "chunk_id": "c00031",
                        "text_snippet": 'Section cites {"node_id":"d0_n0035"}',
                        "source": "vector",
                        "score": 0.91,
                        "page_idx": 1,
                        "section_title": "摘要",
                        "entity_ids": ["d0_n0035", "d1_n0042"],
                    }
                ],
                "metadata": {
                    "model": "test-model",
                    "intent": "hybrid",
                    "retrieval_latency_ms": 2,
                    "generation_latency_ms": 3,
                    "total_latency_ms": 5,
                    "has_citations": True,
                    "has_table": False,
                    "token_usage": {"prompt_tokens": 10, "completion_tokens": 5},
                },
            }

    monkeypatch.setattr(rag_query_module, "_rag_pipeline", DummyPipeline())
    monkeypatch.setattr(rag_query_module, "_init_rag_pipeline", lambda: True)
    monkeypatch.setattr("generator.RAGGenerator", DummyGenerator)

    response = asyncio.run(
        rag_query_module.rag_query(
            QueryRequest(query="W4S1 是什么？", options=QueryOptions(include_sources=True))
        )
    )

    assert response.sources is not None
    assert response.sources[0].properties["entity_ids"] == ["d0_n0035", "d1_n0042"]


def test_rag_query_response_exposes_retrieval_node_ids_for_eval(monkeypatch):
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
                "answer": "Answer [d0_n0035]",
                "sources": [],
                "metadata": {
                    "model": "test-model",
                    "intent": "hybrid",
                    "retrieval_latency_ms": 2,
                    "generation_latency_ms": 3,
                    "total_latency_ms": 5,
                    "has_citations": True,
                    "has_table": False,
                    "token_usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    "retrieval_node_ids": ["n0035", "n0042"],
                    "path_hit_node_ids": {"kg": ["n0035"], "vector": ["n0042"]},
                },
            }

    monkeypatch.setattr(rag_query_module, "_rag_pipeline", DummyPipeline())
    monkeypatch.setattr(rag_query_module, "_init_rag_pipeline", lambda: True)
    monkeypatch.setattr("generator.RAGGenerator", DummyGenerator)

    response = asyncio.run(
        rag_query_module.rag_query(
            QueryRequest(query="W4S1 是什么？", options=QueryOptions(include_sources=True))
        )
    )

    assert response.metadata["retrieval_node_ids"] == ["n0035", "n0042"]
    assert response.metadata["path_hit_node_ids"] == {"kg": ["n0035"], "vector": ["n0042"]}


def test_rag_query_response_exposes_layered_retrieval_ids(monkeypatch):
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
                "answer": "Answer [d0_n0035]",
                "sources": [],
                "metadata": {
                    "model": "test-model",
                    "intent": "hybrid",
                    "retrieval_latency_ms": 2,
                    "generation_latency_ms": 3,
                    "total_latency_ms": 5,
                    "has_citations": True,
                    "has_table": False,
                    "token_usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    "retrieval_node_ids": ["n0035", "n0042"],
                    "pre_rerank_node_ids": ["n0035", "n0042", "n0043"],
                    "final_context_node_ids": ["n0035", "n0042"],
                    "retrieval_chunk_ids": ["c00031", "d0_n0035"],
                    "pre_rerank_chunk_ids": ["c00031", "d0_n0035", "c00099"],
                    "final_context_chunk_ids": ["c00031", "d0_n0035"],
                    "path_hit_node_ids": {"kg": ["n0035"], "vector": ["n0042", "n0043"]},
                },
            }

    monkeypatch.setattr(rag_query_module, "_rag_pipeline", DummyPipeline())
    monkeypatch.setattr(rag_query_module, "_init_rag_pipeline", lambda: True)
    monkeypatch.setattr("generator.RAGGenerator", DummyGenerator)

    response = asyncio.run(
        rag_query_module.rag_query(
            QueryRequest(query="W4S1 是什么？", options=QueryOptions(include_sources=True))
        )
    )

    assert response.metadata["pre_rerank_node_ids"] == ["n0035", "n0042", "n0043"]
    assert response.metadata["final_context_node_ids"] == ["n0035", "n0042"]
    assert response.metadata["pre_rerank_chunk_ids"] == ["c00031", "d0_n0035", "c00099"]
    assert response.metadata["final_context_chunk_ids"] == ["c00031", "d0_n0035"]


def test_real_generator_forwards_budget_to_retrieval_and_prompt(monkeypatch):
    captured = {}

    class DummyPipeline:
        def retrieve(self, query, chat_history=None, retrieval_config=None):
            captured["query"] = query
            captured["chat_history"] = chat_history
            captured["retrieval_config"] = retrieval_config
            return RetrievalResult(
                chunks=[
                    RetrievalChunk(
                        chunk_id="c12345",
                        text="C" * 400,
                        score=0.91,
                        source="vector",
                        section_title="Summary",
                    )
                ],
                total_candidates=3,
                pipeline={"total_ms": 5, "query_mode": "global"},
                query_intent="hybrid",
                entity_types_used=["metric"],
                domain_hint="GLOBAL HINT " * 10,
            )

    def fake_generate_answer(messages, config=None, context_chunks=None):
        captured["messages"] = messages
        captured["context_chunks"] = context_chunks
        return GenerationResult(
            answer_text="Answer [c12345]",
            cited_sources=["c12345"],
            token_usage={"prompt_tokens": 12},
            latency_ms=7,
            model="test-model",
            finish_reason="stop",
        )

    monkeypatch.setattr("generator.generate_answer", fake_generate_answer)

    retrieval_config = QueryOptions(
        max_total_candidates=7,
        max_context_tokens=512,
        enable_global_mode=True,
    )
    generator = RAGGenerator(DummyPipeline())

    result = generator.generate(
        "overall risk summary",
        chat_history=[{"role": "user", "content": "prior turn"}],
        max_context_tokens=retrieval_config.max_context_tokens,
        retrieval_config=rag_query_module._build_retrieval_config(retrieval_config),
    )

    assert captured["retrieval_config"].max_total_candidates == 7
    assert captured["retrieval_config"].enable_global_mode is True
    assert captured["chat_history"][0]["content"] == "prior turn"
    assert "GLOBAL HINT" in captured["messages"][1]["content"]
    assert result["metadata"]["prompt"]["context_tokens"] <= 512
    assert result["sources"][0]["chunk_id"] == "c12345"


def test_real_generator_marks_generation_fallback_when_llm_error_is_recovered(monkeypatch):
    class DummyPipeline:
        def retrieve(self, query, chat_history=None, retrieval_config=None):
            return RetrievalResult(
                chunks=[
                    RetrievalChunk(
                        chunk_id="c12345",
                        text="Paper title: Wind-Solar Hydrogen-Ammonia Cooperative Optimization.",
                        score=0.91,
                        source="vector",
                        section_title="Title",
                    )
                ],
                total_candidates=1,
                pipeline={"total_ms": 5, "query_mode": "local"},
                query_intent="policy_lookup",
                entity_types_used=["paper_metadata"],
            )

    monkeypatch.setattr(
        "generator.generate_answer",
        lambda *args, **kwargs: GenerationResult(
            answer_text="??????????????",
            cited_sources=[],
            token_usage={"prompt_tokens": 12},
            latency_ms=7,
            model="test-model",
            finish_reason="error",
        ),
    )

    generator = RAGGenerator(DummyPipeline())
    result = generator.generate("What is the paper title?")

    assert "Wind-Solar Hydrogen-Ammonia Cooperative Optimization" in result["answer"]
    assert result["metadata"]["finish_reason"] == "error_recovered"
    assert result["metadata"]["degraded_mode"] == "generation_fallback"
    assert result["metadata"]["has_citations"] is True



def test_real_generator_short_circuits_unsupported_query_without_llm_call(monkeypatch):
    class DummyPipeline:
        def retrieve(self, query, chat_history=None, retrieval_config=None):
            return RetrievalResult(
                chunks=[
                    RetrievalChunk(
                        chunk_id="c99999",
                        text="园区优化运行的背景介绍。",
                        score=0.4,
                        source="vector",
                        section_title="背景",
                    )
                ],
                total_candidates=1,
                pipeline={"total_ms": 5, "query_mode": "local"},
                query_intent="metric",
                entity_types_used=["metric"],
            )

    monkeypatch.setattr(
        "generator.generate_answer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should be skipped for unsupported query")),
    )

    generator = RAGGenerator(DummyPipeline())
    result = generator.generate("论文里讨论了煤化工成本是多少？")

    assert result["answer"] == "文档中未提及此信息。"
    assert result["metadata"]["generation_latency_ms"] == 0
    assert result["metadata"]["token_usage"]["completion_tokens"] == 0


def test_real_generator_does_not_short_circuit_supported_domain_query(monkeypatch):
    class DummyPipeline:
        def retrieve(self, query, chat_history=None, retrieval_config=None):
            return RetrievalResult(
                chunks=[
                    RetrievalChunk(
                        chunk_id="d0_n0001",
                        text='{"entity":{"node_id":"d0_n0001","label":"A题 绿电直连型电氢氨园区优化运行"}}',
                        score=0.9,
                        source="kg",
                        entity_ids=["d0_n0001"],
                        section_title="标题",
                    )
                ],
                total_candidates=1,
                pipeline={"total_ms": 5, "query_mode": "local"},
                query_intent="policy_lookup",
                entity_types_used=["paper_metadata"],
            )

    monkeypatch.setattr(
        "generator.generate_answer",
        lambda *args, **kwargs: GenerationResult(
            answer_text="这篇论文的标题是《A题 绿电直连型电氢氨园区优化运行》[d0_n0001]。",
            cited_sources=["d0_n0001"],
            token_usage={"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            latency_ms=7,
            model="test-model",
            finish_reason="stop",
        ),
    )

    generator = RAGGenerator(DummyPipeline())
    result = generator.generate("这篇论文的标题是什么？")

    assert "标题" in result["answer"]
    assert result["metadata"]["generation_latency_ms"] == 7


def test_real_generator_short_circuits_unsupported_gpt4_claim_without_llm_call(monkeypatch):
    class DummyPipeline:
        def retrieve(self, query, chat_history=None, retrieval_config=None):
            return RetrievalResult(
                chunks=[
                    RetrievalChunk(
                        chunk_id="c00030",
                        text="本文所有计算基于 Python 3.10 实现，使用 PuLP 库调用开源 CBC 求解器。",
                        score=0.8,
                        source="vector",
                        section_title="实现",
                    )
                ],
                total_candidates=1,
                pipeline={"total_ms": 5, "query_mode": "local"},
                query_intent="policy_lookup",
                entity_types_used=["paper_metadata"],
            )

    monkeypatch.setattr(
        "generator.generate_answer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should be skipped for unsupported GPT-4 claim")),
    )

    generator = RAGGenerator(DummyPipeline())
    result = generator.generate("论文用了 GPT-4 来辅助优化求解，对吗？")

    assert result["answer"] == "文档中未提及此信息。"
    assert result["metadata"]["finish_reason"] == "short_circuit_refusal"
    assert result["metadata"]["generation_latency_ms"] == 0


def test_real_generator_short_circuits_real_q41_impact_factor_without_llm_call(monkeypatch):
    class DummyPipeline:
        def retrieve(self, query, chat_history=None, retrieval_config=None):
            return RetrievalResult(
                chunks=[
                    RetrievalChunk(
                        chunk_id="c00001",
                        text="A题绿电直连型电氢氨园区优化运行。",
                        score=0.91,
                        source="vector",
                        section_title="标题",
                    ),
                    RetrievalChunk(
                        chunk_id="d0_n0145",
                        text='{"entity":{"node_id":"d0_n0145","entity_type":"metric","label":"3554","properties":{"name":"lowest ammonia cost","value":"3554"}}}',
                        score=0.89,
                        source="kg",
                        entity_ids=["d0_n0145"],
                        section_title="KG",
                    ),
                    RetrievalChunk(
                        chunk_id="c00019",
                        text="风光出力水平是吨氨成本的核心决定因素。最佳场景下成本约3500元/吨，最差场景下成本约8500元/吨。",
                        score=0.88,
                        source="vector",
                        section_title="结论",
                    ),
                ],
                total_candidates=3,
                pipeline={"total_ms": 5, "query_mode": "local"},
                query_intent="metric",
                entity_types_used=["metric"],
            )

    monkeypatch.setattr(
        "generator.generate_answer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should be skipped for unsupported impact-factor query")),
    )

    generator = RAGGenerator(DummyPipeline())
    result = generator.generate("本论文的影响因子(impact factor)是多少？")

    assert result["answer"] == "文档中未提及此信息。"
    assert result["metadata"]["finish_reason"] == "short_circuit_refusal"
    assert result["metadata"]["generation_latency_ms"] == 0


def test_real_generator_short_circuits_claim_check_with_supported_refutation_without_llm_call(monkeypatch):
    class DummyPipeline:
        def retrieve(self, query, chat_history=None, retrieval_config=None):
            return RetrievalResult(
                chunks=[
                    RetrievalChunk(
                        chunk_id="c00023",
                        text="文档未证明储能会降低产量；相反，带储能场景年产量10903吨，高于无储能场景9023吨。",
                        score=0.95,
                        source="vector",
                        section_title="结论",
                    ),
                    RetrievalChunk(
                        chunk_id="d0_n0060",
                        text='{"entity":{"node_id":"d0_n0060","entity_type":"metric","label":"9023","properties":{"name":"annual ammonia production","value":"9023"}}}',
                        score=0.89,
                        source="kg",
                        entity_ids=["d0_n0060"],
                        section_title="KG",
                    ),
                    RetrievalChunk(
                        chunk_id="d0_n0061",
                        text='{"entity":{"node_id":"d0_n0061","entity_type":"metric","label":"10903","properties":{"name":"annual ammonia production","value":"10903"}}}',
                        score=0.88,
                        source="kg",
                        entity_ids=["d0_n0061"],
                        section_title="KG",
                    ),
                ],
                total_candidates=3,
                pipeline={"total_ms": 5, "query_mode": "local", "rerank_skipped": "claim_verification"},
                query_intent="claim_check",
                entity_types_used=["claim", "metric"],
            )

    monkeypatch.setattr(
        "generator.generate_answer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should be skipped for supported claim refutation")),
    )

    generator = RAGGenerator(DummyPipeline())
    result = generator.generate("本论文证明了储能装置反而会降低园区产量，这个结论对吗？")

    assert result["answer"].startswith("不是")
    assert "10903" in result["answer"]
    assert "9023" in result["answer"]
    assert "[c00023]" in result["answer"]
    assert result["metadata"]["generation_latency_ms"] == 0


def test_real_generator_short_circuits_real_q49_claim_check_without_wrong_grid_support_fact(monkeypatch):
    class DummyPipeline:
        def retrieve(self, query, chat_history=None, retrieval_config=None):
            return RetrievalResult(
                chunks=[
                    RetrievalChunk(
                        chunk_id="c00007",
                        text="储能模型假设与约束。",
                        score=0.95,
                        source="vector",
                        section_title="模型",
                    ),
                    RetrievalChunk(
                        chunk_id="d0_n0060",
                        text='{"entity":{"node_id":"d0_n0060","entity_type":"metric","label":"9023","properties":{"name":"annual ammonia production without storage","value":"9023"}}}',
                        score=0.89,
                        source="kg",
                        entity_ids=["d0_n0060"],
                        section_title="KG",
                    ),
                    RetrievalChunk(
                        chunk_id="c00023",
                        text="电网支撑使园区年制氨量从9023吨跃升至97200吨（10.8倍），这是电网对园区最核心的价值体现。",
                        score=0.88,
                        source="vector",
                        section_title="电网价值",
                    ),
                    RetrievalChunk(
                        chunk_id="d0_n0061",
                        text='{"entity":{"node_id":"d0_n0061","entity_type":"metric","label":"10903","properties":{"name":"annual ammonia production with storage","value":"10903"}}}',
                        score=0.87,
                        source="kg",
                        entity_ids=["d0_n0061"],
                        section_title="KG",
                    ),
                ],
                total_candidates=4,
                pipeline={"total_ms": 5, "query_mode": "local", "rerank_skipped": "timeout"},
                query_intent="policy_lookup",
                entity_types_used=["metric", "claim"],
            )

    monkeypatch.setattr(
        "generator.generate_answer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should be skipped for real Q49 claim correction")),
    )

    generator = RAGGenerator(DummyPipeline())
    result = generator.generate("本论文证明了储能装置反而会降低园区产量，这个结论对吗？")

    assert result["answer"].startswith("不是")
    assert "10903" in result["answer"]
    assert "9023" in result["answer"]
    assert "97200" not in result["answer"]
    assert result["metadata"]["generation_latency_ms"] == 0


def test_real_generator_short_circuits_q49_when_with_storage_metric_only_exists_in_retrieval_lineage(monkeypatch):
    class DummyGraph:
        def __init__(self):
            self._node = {
                "n0061": {
                    "entity_type": "metric",
                    "label": "10903",
                    "properties": {
                        "name": "annual ammonia production with storage",
                        "value": "10903",
                    },
                }
            }

    class DummyPipeline:
        def __init__(self):
            self.kg_graph = DummyGraph()

        def retrieve(self, query, chat_history=None, retrieval_config=None):
            return RetrievalResult(
                chunks=[
                    RetrievalChunk(
                        chunk_id="c00007",
                        text="储能模型假设与约束。",
                        score=0.95,
                        source="vector",
                        section_title="模型",
                    ),
                    RetrievalChunk(
                        chunk_id="d0_n0060",
                        text='{"entity":{"node_id":"d0_n0060","entity_type":"metric","label":"9023","properties":{"name":"annual ammonia production without storage","value":"9023"}}}',
                        score=0.89,
                        source="kg",
                        entity_ids=["d0_n0060"],
                        section_title="KG",
                    ),
                    RetrievalChunk(
                        chunk_id="c00023",
                        text="电网支撑使园区年制氨量从9023吨跃升至97200吨（10.8倍），这是电网对园区最核心的价值体现。",
                        score=0.88,
                        source="vector",
                        section_title="电网价值",
                    ),
                ],
                total_candidates=4,
                pipeline={
                    "total_ms": 5,
                    "query_mode": "local",
                    "rerank_skipped": "timeout",
                    "retrieval_chunk_ids": ["c00007", "d0_n0060", "c00023", "d0_n0061"],
                },
                query_intent="policy_lookup",
                entity_types_used=["metric", "claim"],
            )

    monkeypatch.setattr(
        "generator.generate_answer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should be skipped when lineage still contains with-storage metric")),
    )

    generator = RAGGenerator(DummyPipeline())
    result = generator.generate("本论文证明了储能装置反而会降低园区产量，这个结论对吗？")

    assert result["answer"].startswith("不是")
    assert "10903" in result["answer"]
    assert "9023" in result["answer"]
    assert "97200" not in result["answer"]
    assert result["metadata"]["generation_latency_ms"] == 0


def test_real_generator_short_circuits_q41_even_if_raw_kg_mentions_impact_factor_term(monkeypatch):
    class DummyPipeline:
        def retrieve(self, query, chat_history=None, retrieval_config=None):
            return RetrievalResult(
                chunks=[
                    RetrievalChunk(
                        chunk_id="d0_n0145",
                        text='{"entity":{"node_id":"d0_n0145","entity_type":"metric","label":"3554","properties":{"name":"impact factor surrogate field","value":"3554"}}}',
                        score=0.95,
                        source="kg",
                        entity_ids=["d0_n0145"],
                        section_title="KG",
                    ),
                    RetrievalChunk(
                        chunk_id="c00019",
                        text="风光出力水平是吨氨成本的核心决定因素，对综合经济性影响显著。",
                        score=0.89,
                        source="vector",
                        section_title="结论",
                    ),
                ],
                total_candidates=2,
                pipeline={"total_ms": 5, "query_mode": "local", "rerank_skipped": "timeout"},
                query_intent="metric",
                entity_types_used=["metric"],
            )

    monkeypatch.setattr(
        "generator.generate_answer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should be skipped for unsupported impact-factor query")),
    )

    generator = RAGGenerator(DummyPipeline())
    result = generator.generate("本论文的影响因子(impact factor)是多少？")

    assert result["answer"] == "文档中未提及此信息。"
    assert result["metadata"]["generation_latency_ms"] == 0


def test_real_generator_short_circuits_q49_via_targeted_vector_rescue_when_initial_context_lacks_10903(monkeypatch):
    class DummyEmbeddingClient:
        def embed_query(self, query):
            assert "10903" in query
            return [0.1, 0.2, 0.3]

    class DummyVectorStore:
        def search(self, query_vector, top_k, text_char_limit=1200, metadata_keys=None):
            return [
                {
                    "chunk_id": "c00022",
                    "text": "最优储能配置为容量210.4MWh+功率30.0MW。加装储能后全年制氨总量从9023吨提升至10903吨（+20.8%），平均风光利用率从95.4%提升至100.0%。",
                    "score": 0.91,
                    "source": "vector",
                    "section_title": "储能最优配置",
                    "metadata": {},
                }
            ]

    class DummyPipeline:
        def __init__(self):
            self.kg_graph = None
            self.embedding_client = DummyEmbeddingClient()
            self.vector_store = DummyVectorStore()

        def retrieve(self, query, chat_history=None, retrieval_config=None):
            return RetrievalResult(
                chunks=[
                    RetrievalChunk(
                        chunk_id="c00007",
                        text="储能模型假设与约束。",
                        score=0.95,
                        source="vector",
                        section_title="模型",
                    ),
                    RetrievalChunk(
                        chunk_id="d0_n0060",
                        text='{"entity":{"node_id":"d0_n0060","entity_type":"metric","label":"9023","properties":{"name":"annual ammonia production without storage","value":"9023"}}}',
                        score=0.89,
                        source="kg",
                        entity_ids=["d0_n0060"],
                        section_title="KG",
                    ),
                    RetrievalChunk(
                        chunk_id="c00023",
                        text="电网支撑使园区年制氨量从9023吨跃升至97200吨（10.8倍），这是电网对园区最核心的价值体现。",
                        score=0.88,
                        source="vector",
                        section_title="电网价值",
                    ),
                ],
                total_candidates=4,
                pipeline={"total_ms": 5, "query_mode": "local", "rerank_skipped": "timeout"},
                query_intent="policy_lookup",
                entity_types_used=["metric", "claim"],
            )

    monkeypatch.setattr(
        "generator.generate_answer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should be skipped when vector rescue finds storage contrast evidence")),
    )

    generator = RAGGenerator(DummyPipeline())
    result = generator.generate("本论文证明了储能装置反而会降低园区产量，这个结论对吗？")

    assert result["answer"].startswith("不是")
    assert "10903" in result["answer"]
    assert "9023" in result["answer"]
    assert "97200" not in result["answer"]
    assert "[c00022]" in result["answer"]
    assert result["metadata"]["generation_latency_ms"] == 0
