from types import SimpleNamespace

from domain_dict import DomainDict
from prompt_builder import build_prompt
from retrieval import (
    RetrievalConfig,
    RetrievalChunk,
    RetrievalPipeline,
    RetrievalResult,
    _candidate_has_exact_query_evidence,
    _candidate_matches_direct_lookup_query,
    _candidate_matches_figure_inventory,
    _candidate_matches_metric_query,
    _heuristic_entity_types_for_query,
    _select_rerank_candidates,
    indexed_kg_recall,
)


def test_indexed_kg_recall_boosts_exact_keyword_match_over_generic_match(monkeypatch):
    class DummyGraph:
        def number_of_nodes(self):
            return 2

    monkeypatch.setattr(
        "retrieval.lookup_kg_nodes",
        lambda *args, **kwargs: [
            (
                "n_generic",
                {
                    "entity_type": "metric",
                    "label": "风光配比场景",
                    "properties": {"description": "用于场景说明"},
                },
            ),
            (
                "n_exact",
                {
                    "entity_type": "metric",
                    "label": "W4S1 场景",
                    "properties": {"description": "wind 4 solar 1"},
                },
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval._build_kg_result",
        lambda nid, data, kg_graph: {
            "chunk_id": nid,
            "text": data["label"],
            "score": 0.75,
            "source": "kg",
            "metadata": {
                "entity_type": data.get("entity_type"),
                "entity_ids": [nid],
            },
        },
    )
    monkeypatch.setattr("retrieval.get_kg_lookup_indexes", lambda kg_graph: {"stub": True})

    preprocessed = SimpleNamespace(
        rewritten="W4S1 是什么？",
        entity_types=["metric"],
    )

    results = indexed_kg_recall(
        preprocessed=preprocessed,
        kg_graph=DummyGraph(),
        config=RetrievalConfig(kg_top_k=2),
        indexes={"stub": True},
    )

    assert [item["chunk_id"] for item in results] == ["n_exact", "n_generic"]


def test_indexed_kg_recall_maps_wind_solar_alias_to_w4s1(monkeypatch):
    class DummyGraph:
        def number_of_nodes(self):
            return 2

    monkeypatch.setattr(
        "retrieval.lookup_kg_nodes",
        lambda *args, **kwargs: [
            (
                "n_dataset",
                {
                    "entity_type": "dataset",
                    "label": "24种风光出力场景",
                    "properties": {"name": "24 wind-solar power output scenarios"},
                },
            ),
            (
                "n_exact",
                {
                    "entity_type": "dataset",
                    "label": "W4S1",
                    "properties": {"name": "maximum curtailment scenario"},
                },
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval._build_kg_result",
        lambda nid, data, kg_graph: {
            "chunk_id": nid,
            "text": data["label"],
            "score": 0.75,
            "source": "kg",
            "metadata": {
                "entity_type": data.get("entity_type"),
                "entity_ids": [nid],
            },
        },
    )
    monkeypatch.setattr("retrieval.get_kg_lookup_indexes", lambda kg_graph: {"stub": True})

    preprocessed = SimpleNamespace(
        original="论文中提到的wind 4 solar 1场景代表什么含义?",
        rewritten="wind 4 solar 1 project report",
        entity_types=["project_metadata", "metric"],
    )

    results = indexed_kg_recall(
        preprocessed=preprocessed,
        kg_graph=DummyGraph(),
        config=RetrievalConfig(kg_top_k=2),
        indexes={"stub": True},
    )

    assert [item["chunk_id"] for item in results] == ["n_exact", "n_dataset"]


def test_indexed_kg_recall_boosts_title_field_for_title_questions(monkeypatch):
    class DummyGraph:
        def number_of_nodes(self):
            return 2

    monkeypatch.setattr(
        "retrieval.lookup_kg_nodes",
        lambda *args, **kwargs: [
            (
                "n_claim",
                {
                    "entity_type": "claim",
                    "label": "论文使用了混合整数线性规划。",
                    "properties": {"field": "summary"},
                },
            ),
            (
                "n_title",
                {
                    "entity_type": "paper_metadata",
                    "label": "A 题绿电直连型电氢氨园区优化运行",
                    "properties": {"field": "title"},
                },
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval._build_kg_result",
        lambda nid, data, kg_graph: {
            "chunk_id": nid,
            "text": data["label"],
            "score": 0.70,
            "source": "kg",
            "metadata": {
                "entity_type": data.get("entity_type"),
                "entity_ids": [nid],
            },
        },
    )
    monkeypatch.setattr("retrieval.get_kg_lookup_indexes", lambda kg_graph: {"stub": True})

    preprocessed = SimpleNamespace(
        original="这篇论文的标题是什么？",
        rewritten="enterprise project report analysis",
        entity_types=["project_metadata", "metric"],
    )

    results = indexed_kg_recall(
        preprocessed=preprocessed,
        kg_graph=DummyGraph(),
        config=RetrievalConfig(kg_top_k=2),
        indexes={"stub": True},
    )

    assert [item["chunk_id"] for item in results] == ["n_title", "n_claim"]


def test_indexed_kg_recall_uses_original_query_to_recover_title_entity_type(monkeypatch):
    class DummyGraph:
        def __init__(self):
            self.graph = {"_kg_lookup_indexes": {"token_to_nodes": {}, "label_token_to_nodes": {}, "node_text": {}, "label_text": {}}}

        def number_of_nodes(self):
            return 1

    captured_entity_types = []

    def fake_lookup(kg_graph, entity_types=None, **kwargs):
        captured_entity_types.append(tuple(entity_types or []))
        return []

    monkeypatch.setattr("retrieval.lookup_kg_nodes", fake_lookup)
    monkeypatch.setattr("retrieval.get_kg_lookup_indexes", lambda kg_graph: {"stub": True})

    preprocessed = SimpleNamespace(
        original="这篇论文的标题是什么？",
        rewritten="enterprise project report analysis",
        entity_types=["project_metadata", "metric"],
    )

    indexed_kg_recall(
        preprocessed=preprocessed,
        kg_graph=DummyGraph(),
        config=RetrievalConfig(kg_top_k=1),
        indexes={"stub": True},
    )

    assert any("paper_metadata" in entity_types for entity_types in captured_entity_types)


def test_indexed_kg_recall_queries_lookup_with_original_and_rewritten_text(monkeypatch):
    class DummyGraph:
        def number_of_nodes(self):
            return 1

    captured_keywords = []

    def fake_lookup(kg_graph, keyword=None, **kwargs):
        captured_keywords.append(keyword)
        return []

    monkeypatch.setattr("retrieval.lookup_kg_nodes", fake_lookup)
    monkeypatch.setattr("retrieval.get_kg_lookup_indexes", lambda kg_graph: {"stub": True})

    preprocessed = SimpleNamespace(
        original="这篇论文的标题是什么？",
        rewritten="论文标题查询",
        entity_types=["project_metadata"],
    )

    indexed_kg_recall(
        preprocessed=preprocessed,
        kg_graph=DummyGraph(),
        config=RetrievalConfig(kg_top_k=1),
        indexes={"stub": True},
    )

    assert "这篇论文的标题是什么？" in captured_keywords
    assert "论文标题查询" in captured_keywords


def test_indexed_kg_recall_adds_canonical_metric_lookup_terms_for_summary_metric_queries(monkeypatch):
    class DummyGraph:
        def number_of_nodes(self):
            return 1

    captured_keywords = []

    def fake_lookup(kg_graph, keyword=None, **kwargs):
        captured_keywords.append(keyword)
        return []

    monkeypatch.setattr("retrieval.lookup_kg_nodes", fake_lookup)
    monkeypatch.setattr("retrieval.get_kg_lookup_indexes", lambda kg_graph: {"stub": True})

    preprocessed = SimpleNamespace(
        original="论文摘要中可再生能源发电量是多少 MWh？",
        rewritten="论文摘要中可再生能源发电量是多少 MWh？",
        entity_types=["metric"],
    )

    indexed_kg_recall(
        preprocessed=preprocessed,
        kg_graph=DummyGraph(),
        config=RetrievalConfig(kg_top_k=2),
        indexes={"stub": True},
    )

    assert "renewable generation" in captured_keywords


def test_indexed_kg_recall_boosts_canonical_metric_match_for_summary_metric_queries(monkeypatch):
    class DummyGraph:
        def number_of_nodes(self):
            return 2

    monkeypatch.setattr(
        "retrieval.lookup_kg_nodes",
        lambda *args, **kwargs: [
            (
                "n_generic",
                {
                    "entity_type": "metric",
                    "label": "210.4MWh",
                    "properties": {"name": "storage capacity", "value": "210.4"},
                    "page_idx": 7,
                },
            ),
            (
                "n_exact",
                {
                    "entity_type": "metric",
                    "label": "603.45MWh",
                    "properties": {"name": "renewable generation", "value": "603.45"},
                    "page_idx": 1,
                },
            ),
        ],
    )
    monkeypatch.setattr(
        "retrieval._build_kg_result",
        lambda nid, data, kg_graph: {
            "chunk_id": nid,
            "text": data["label"],
            "score": 0.75,
            "source": "kg",
            "metadata": {
                "entity_type": data.get("entity_type"),
                "entity_ids": [nid],
                "page_idx": data.get("page_idx"),
            },
        },
    )
    monkeypatch.setattr("retrieval.get_kg_lookup_indexes", lambda kg_graph: {"stub": True})

    preprocessed = SimpleNamespace(
        original="论文摘要中可再生能源发电量是多少 MWh？",
        rewritten="论文摘要中可再生能源发电量是多少 MWh？",
        entity_types=["metric"],
    )

    results = indexed_kg_recall(
        preprocessed=preprocessed,
        kg_graph=DummyGraph(),
        config=RetrievalConfig(kg_top_k=2),
        indexes={"stub": True},
    )

    assert [item["chunk_id"] for item in results] == ["n_exact", "n_generic"]
    assert results[0]["metadata"]["protected_evidence"] is True


def test_heuristic_entity_types_include_figure_friendly_types_for_figure_queries():
    entity_types = _heuristic_entity_types_for_query("图 5 展示了什么内容？")

    assert "section_header" in entity_types
    assert "dataset" in entity_types


def test_build_prompt_prioritizes_grounded_kg_context_over_generic_vector_context():
    retrieval_result = RetrievalResult(
        chunks=[
            RetrievalChunk(
                chunk_id="v1",
                text="泛化背景说明，没有直接实体锚点。",
                score=0.95,
                source="vector",
                section_title="Vector Background",
                entity_ids=[],
            ),
            RetrievalChunk(
                chunk_id="kg1",
                text='{"entity":{"node_id":"n0035","label":"W4S1"}}',
                score=0.70,
                source="kg",
                section_title="KG Exact Match",
                entity_ids=["n0035"],
                metadata={"entity_type": "metric"},
            ),
        ],
        total_candidates=2,
        pipeline={
            "per_source_caps": {"vector": 1, "kg": 1},
            "max_total_candidates": 2,
        },
        query_intent="hybrid",
        entity_types_used=["metric"],
    )

    messages = build_prompt(
        retrieval_result=retrieval_result,
        user_query="W4S1 是什么？",
    )

    prompt_text = messages[1]["content"]
    assert prompt_text.index("[kg1]") < prompt_text.index("[v1]")


def test_build_prompt_prioritizes_exact_figure_chunk_over_generic_process_summary():
    retrieval_result = RetrievalResult(
        chunks=[
            RetrievalChunk(
                chunk_id="c00005",
                text="五个问题形成基准线建立、灵活性引入、调节方式升级、独立性检验、宏观扩展的递进逻辑链。",
                score=0.96,
                source="vector",
                section_title="Generic Summary",
                entity_ids=[],
            ),
            RetrievalChunk(
                chunk_id="c00031",
                text="图 5— 问题四离网与储能分析（左：三种模式经济性对比；右：储能充放电调度）",
                score=0.82,
                source="vector",
                section_title="Figure 5",
                entity_ids=[],
            ),
        ],
        total_candidates=2,
        pipeline={
            "per_source_caps": {"vector": 2},
            "max_total_candidates": 2,
        },
        query_intent="hybrid",
        entity_types_used=["section_header", "dataset"],
    )

    messages = build_prompt(
        retrieval_result=retrieval_result,
        user_query="图 5 展示了什么内容？",
    )

    prompt_text = messages[1]["content"]
    assert prompt_text.index("[c00031]") < prompt_text.index("[c00005]")


def test_build_prompt_prioritizes_scenario_anchored_metric_chunk_over_generic_metric_summary():
    retrieval_result = RetrievalResult(
        chunks=[
            RetrievalChunk(
                chunk_id="c-generic-metric",
                text="三项绿电直连指标中，新能源自发自用率28.2%，上网电量比例35.9%。",
                score=0.96,
                source="vector",
                section_title="Generic Metric Summary",
                entity_ids=[],
            ),
            RetrievalChunk(
                chunk_id="kg-w2s2-metric",
                text='{"entity":{"node_id":"n0036","label":"W2S2 绿电消纳率","properties":{"name":"green power utilization rate","value":"95%"}}}',
                score=0.70,
                source="kg",
                section_title="W2S2 Exact Metric",
                entity_ids=["n0036"],
                metadata={"entity_type": "metric"},
            ),
        ],
        total_candidates=2,
        pipeline={
            "per_source_caps": {"vector": 1, "kg": 1},
            "max_total_candidates": 2,
        },
        query_intent="metric",
        entity_types_used=["metric", "dataset"],
    )

    messages = build_prompt(
        retrieval_result=retrieval_result,
        user_query="在W2S2场景中，绿电消纳率是多少？",
    )

    prompt_text = messages[1]["content"]
    assert prompt_text.index("[kg-w2s2-metric]") < prompt_text.index("[c-generic-metric]")


def test_build_prompt_prioritizes_exact_scenario_metric_chunk_for_multi_metric_followup():
    retrieval_result = RetrievalResult(
        chunks=[
            RetrievalChunk(
                chunk_id="c-w4s1-storage",
                text="针对最大弃电场景W4S1，最优储能配置为210.4MWh/30MW。",
                score=0.97,
                source="vector",
                section_title="W4S1 Storage Summary",
                entity_ids=[],
            ),
            RetrievalChunk(
                chunk_id="kg-w3s3-metric",
                text='{"entity":{"node_id":"n0037","label":"W3S3 弃电量与绿电消纳率","properties":{"curtailment":"120MWh/日","utilization_rate":"91%"}}}',
                score=0.68,
                source="kg",
                section_title="W3S3 Exact Metric",
                entity_ids=["n0037"],
                metadata={"entity_type": "metric"},
            ),
        ],
        total_candidates=2,
        pipeline={
            "per_source_caps": {"vector": 1, "kg": 1},
            "max_total_candidates": 2,
        },
        query_intent="metric",
        entity_types_used=["metric", "dataset"],
    )

    messages = build_prompt(
        retrieval_result=retrieval_result,
        user_query="W3S3 场景的弃电量和消纳率分别是多少？",
    )

    prompt_text = messages[1]["content"]
    assert prompt_text.index("[kg-w3s3-metric]") < prompt_text.index("[c-w4s1-storage]")


def test_build_prompt_prioritizes_scenario_table_chunk_over_generic_summary_for_followup_metric_query():
    retrieval_result = RetrievalResult(
        chunks=[
            RetrievalChunk(
                chunk_id="c00002",
                text="问题一新能源自发自用率28.2%，问题二绿电指标全满足率39.2%，问题三全满足率69.2%，问题四风光利用率95.4%。",
                score=0.98,
                source="vector",
                section_title="Generic Summary",
                entity_ids=[],
            ),
            RetrievalChunk(
                chunk_id="table_w3s3_metric",
                text='{"source_file":"paper.pdf","sheet_name":"scenario_summary","row_number":3,"column_name":"绿电消纳率","column_value":"91%","context":{"场景":"W3S3","绿电消纳率":"91%","弃电量":"120MWh/日"}}',
                score=0.70,
                source="table",
                section_title="W3S3 Scenario Table",
                entity_ids=[],
                metadata={
                    "table_data": {
                        "column_name": "绿电消纳率",
                        "column_value": "91%",
                        "context": {
                            "场景": "W3S3",
                            "绿电消纳率": "91%",
                            "弃电量": "120MWh/日",
                        },
                    }
                },
            ),
        ],
        total_candidates=2,
        pipeline={
            "per_source_caps": {"vector": 1, "table": 1},
            "max_total_candidates": 2,
        },
        query_intent="metric",
        entity_types_used=["metric", "dataset"],
    )

    messages = build_prompt(
        retrieval_result=retrieval_result,
        user_query="W3S3 场景的弃电量和消纳率分别是多少？",
    )

    prompt_text = messages[1]["content"]
    assert prompt_text.index("[table_w3s3_metric]") < prompt_text.index("[c00002]")


def test_candidate_matches_metric_query_requires_scenario_anchor_for_followup_metric_queries():
    query = "W3S3 场景的弃电量和消纳率分别是多少？"

    exact_candidate = {
        "chunk_id": "kg-w3s3",
        "text": '{"entity":{"node_id":"n0037","label":"W3S3 弃电量与绿电消纳率","properties":{"curtailment":"120MWh/日","utilization_rate":"91%"}}}',
        "source": "kg",
        "metadata": {
            "entity_type": "metric",
            "properties": {
                "curtailment": "120MWh/日",
                "utilization_rate": "91%",
            },
        },
    }
    wrong_scenario_candidate = {
        "chunk_id": "kg-w4s1",
        "text": '{"entity":{"node_id":"n0035","label":"W4S1 最大弃电场景","properties":{"curtailment":"173.7MWh/日"}}}',
        "source": "kg",
        "metadata": {
            "entity_type": "metric",
            "properties": {
                "curtailment": "173.7MWh/日",
            },
        },
    }
    generic_summary_candidate = {
        "chunk_id": "c00002",
        "text": "三项绿电直连指标中，新能源自发自用率28.2%，上网电量比例35.9%，经济效益满足率39.2%。",
        "source": "vector",
        "metadata": {},
    }

    assert _candidate_matches_metric_query(query, exact_candidate) is True
    assert _candidate_matches_metric_query(query, wrong_scenario_candidate) is False
    assert _candidate_matches_metric_query(query, generic_summary_candidate) is False


def test_candidate_has_exact_query_evidence_rejects_wrong_scenario_metric_chunk():
    query = "在W2S2场景中，绿电消纳率是多少？"

    exact_candidate = {
        "chunk_id": "kg-w2s2",
        "text": '{"entity":{"node_id":"n0036","label":"W2S2 绿电消纳率","properties":{"name":"green power utilization rate","value":"95%"}}}',
        "source": "kg",
        "metadata": {
            "entity_type": "metric",
            "properties": {
                "name": "green power utilization rate",
                "value": "95%",
            },
        },
    }
    wrong_scenario_candidate = {
        "chunk_id": "kg-w4s1",
        "text": '{"entity":{"node_id":"n0035","label":"W4S1 最大弃电场景","properties":{"name":"maximum curtailment scenario","value":"173.7MWh/日"}}}',
        "source": "kg",
        "metadata": {
            "entity_type": "metric",
            "properties": {
                "name": "maximum curtailment scenario",
                "value": "173.7MWh/日",
            },
        },
    }

    assert _candidate_has_exact_query_evidence(query, exact_candidate) is True
    assert _candidate_has_exact_query_evidence(query, wrong_scenario_candidate) is False


def test_retrieval_pipeline_rescues_scenario_metric_chunk_from_bm25_text_for_followup_query(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyChunk:
        def __init__(self, chunk_id, text):
            self.chunk_id = chunk_id
            self.text = text
            self.metadata = SimpleNamespace(source_file="")

    class DummyGraph:
        def __init__(self):
            self.graph = {"_kg_lookup_indexes": {"token_to_nodes": {}, "label_token_to_nodes": {}, "node_text": {}, "label_text": {}}}

        def number_of_nodes(self):
            return 1

    pipeline = RetrievalPipeline(
        vector_store=object(),
        embedding_client=DummyEmbeddingClient(),
        kg_graph=DummyGraph(),
        bm25_index=(
            object(),
            [
                DummyChunk(
                    "c00019",
                    "5.3.3各场景运行状况分析 W2S2 场景下绿电消纳率约95%，W3S3 场景弃电量120MWh/日，消纳率91%。",
                )
            ],
        ),
        table_index=None,
        config=RetrievalConfig(enable_cross_encoder=True, kg_top_k=3),
    )

    monkeypatch.setattr(
        "retrieval.preprocess_query",
        lambda raw_query, chat_history=None, **kwargs: SimpleNamespace(
            original=raw_query,
            rewritten=raw_query,
            intent="metric",
            entity_types=["metric", "project_metadata"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            ("bm25", [
                {
                    "chunk_id": "c00002",
                    "text": "三项绿电直连指标中，新能源自发自用率28.2%，上网电量比例35.9%，绿电指标全满足率39.2%。",
                    "score": 0.96,
                    "source": "bm25",
                    "entity_ids": [],
                    "metadata": {},
                }
            ]),
            ("kg", [
                {
                    "chunk_id": "d0_n0141",
                    "text": '{"entity":{"node_id":"d0_n0141","label":"全满足率从39.2%跃升至69.2%"}}',
                    "score": 0.78,
                    "source": "kg",
                    "entity_ids": ["d0_n0141"],
                    "metadata": {"entity_ids": ["d0_n0141"], "entity_type": "metric"},
                }
            ]),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda query, candidates, top_k=10, model_name="BAAI/bge-reranker-base": candidates,
    )
    monkeypatch.setattr(
        "retrieval.indexed_kg_recall",
        lambda preprocessed, kg_graph, config, indexes=None: [],
    )

    result = pipeline.retrieve("在W2S2场景中，绿电消纳率是多少？")

    assert "c00019" in result.pipeline["pre_rerank_chunk_ids"] or "c00019" in result.pipeline["final_context_chunk_ids"]


def test_candidate_matches_metric_query_accepts_table_row_with_exact_scenario_and_metric():
    query = "在W2S2场景中，绿电消纳率是多少？"
    table_candidate = {
        "chunk_id": "table_row_w2s2",
        "text": '{"source_file":"paper.pdf","sheet_name":"table_9","row_number":1,"column_name":"绿电消纳率","column_value":"95%","context":{"场景":"W2S2","绿电消纳率":"95%","弃电量":"120MWh/日"}}',
        "source": "table",
        "metadata": {
            "table_data": {
                "source_file": "paper.pdf",
                "sheet_name": "table_9",
                "row_number": 1,
                "column_name": "绿电消纳率",
                "column_value": "95%",
                "context": {
                    "场景": "W2S2",
                    "绿电消纳率": "95%",
                    "弃电量": "120MWh/日",
                },
            }
        },
    }
    wrong_scenario_candidate = {
        "chunk_id": "table_row_w4s1",
        "text": '{"source_file":"paper.pdf","sheet_name":"table_9","row_number":3,"column_name":"绿电消纳率","column_value":"100%","context":{"场景":"W4S1","绿电消纳率":"100%","弃电量":"173.7MWh/日"}}',
        "source": "table",
        "metadata": {
            "table_data": {
                "source_file": "paper.pdf",
                "sheet_name": "table_9",
                "row_number": 3,
                "column_name": "绿电消纳率",
                "column_value": "100%",
                "context": {
                    "场景": "W4S1",
                    "绿电消纳率": "100%",
                    "弃电量": "173.7MWh/日",
                },
            }
        },
    }

    assert _candidate_matches_metric_query(query, table_candidate) is True
    assert _candidate_matches_metric_query(query, wrong_scenario_candidate) is False


def test_retrieval_pipeline_rescues_exact_table_row_for_scenario_metric_followup(monkeypatch):
    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    class DummyGraph:
        def __init__(self):
            self.graph = {"_kg_lookup_indexes": {"token_to_nodes": {}, "label_token_to_nodes": {}, "node_text": {}, "label_text": {}}}

        def number_of_nodes(self):
            return 1

    class DummyTableIndex:
        def query(self, conditions=None, top_k=20, prefer_wide=True):
            return [
                {
                    "source_file": "paper.pdf",
                    "sheet_name": "scenario_summary",
                    "row_number": 1,
                    "column_name": "绿电消纳率",
                    "column_value": "95%",
                    "column_value_numeric": 95.0,
                    "unit": "%",
                    "context": {
                        "场景": "W2S2",
                        "绿电消纳率": "95%",
                        "弃电量": "120MWh/日",
                    },
                }
            ]

    pipeline = RetrievalPipeline(
        vector_store=object(),
        embedding_client=DummyEmbeddingClient(),
        kg_graph=DummyGraph(),
        bm25_index=None,
        table_index=DummyTableIndex(),
        config=RetrievalConfig(enable_cross_encoder=True, kg_top_k=3, table_top_k=3),
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
            ("vector", [
                {
                    "chunk_id": "c00002",
                    "text": "问题二绿电指标全满足率39.2%，问题三全满足率69.2%，问题四风光利用率95.4%。",
                    "score": 0.96,
                    "source": "vector",
                    "entity_ids": [],
                    "metadata": {},
                }
            ]),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda query, candidates, top_k=10, model_name="BAAI/bge-reranker-base": candidates,
    )
    monkeypatch.setattr(
        "retrieval.indexed_kg_recall",
        lambda preprocessed, kg_graph, config, indexes=None: [],
    )

    result = pipeline.retrieve("在W2S2场景中，绿电消纳率是多少？")

    assert "table_row_scenario_summary_1_绿电消纳率" in result.pipeline["pre_rerank_chunk_ids"]


def test_scenario_metric_table_rescue_scans_restored_table_rows_beyond_recent_query_window():
    from retrieval import _scenario_metric_table_rescue_candidates

    restored_rows = [
        {
            "source_file": "paper.pdf",
            "sheet_name": "scenario_summary",
            "row_number": idx,
            "column_name": "普通字段",
            "column_value": f"value-{idx}",
            "context": {"场景": f"X{idx}", "普通字段": f"value-{idx}"},
        }
        for idx in range(5)
    ]
    restored_rows.append(
        {
            "source_file": "paper.pdf",
            "sheet_name": "scenario_summary",
            "row_number": 99,
            "column_name": "绿电消纳率",
            "column_value": "95%",
            "context": {
                "场景": "W2S2",
                "绿电消纳率": "95%",
                "弃电量": "120MWh/日",
            },
        }
    )

    class RestoredTableIndex:
        def __init__(self, rows):
            self.rows = rows

        def query(self, conditions=None, top_k=20, prefer_wide=True):
            return self.rows[:top_k]

    rescued = _scenario_metric_table_rescue_candidates(
        preprocessed=SimpleNamespace(
            original="在W2S2场景中，绿电消纳率是多少？",
            rewritten="在W2S2场景中，绿电消纳率是多少？",
        ),
        table_index=RestoredTableIndex(restored_rows),
        config=RetrievalConfig(table_top_k=2),
    )

    assert rescued
    assert rescued[0]["metadata"]["table_data"]["context"]["场景"] == "W2S2"


def test_scenario_metric_table_rescue_scans_full_table_index_snapshot_beyond_recent_query_window():
    from retrieval import _scenario_metric_table_rescue_candidates

    leading_rows = [
        {
            "source_file": "paper.pdf",
            "sheet_name": "scenario_summary",
            "row_number": idx,
            "column_name": "普通字段",
            "column_value": f"value-{idx}",
            "context": {"场景": f"X{idx}", "普通字段": f"value-{idx}"},
        }
        for idx in range(5)
    ]
    target_row = {
        "source_file": "paper.pdf",
        "sheet_name": "scenario_summary",
        "row_number": 99,
        "column_name": "绿电消纳率",
        "column_value": "95%",
        "context": {
            "场景": "W2S2",
            "绿电消纳率": "95%",
            "弃电量": "120MWh/日",
        },
    }

    class QueryOnlyTableIndex:
        def __init__(self, rows):
            self._rows = rows

        def query(self, conditions=None, top_k=20, prefer_wide=True):
            return self._rows[:top_k]

        def export_rows(self):
            return list(self._rows)

    rescued = _scenario_metric_table_rescue_candidates(
        preprocessed=SimpleNamespace(
            original="在W2S2场景中，绿电消纳率是多少？",
            rewritten="在W2S2场景中，绿电消纳率是多少？",
        ),
        table_index=QueryOnlyTableIndex([*leading_rows, target_row]),
        config=RetrievalConfig(table_top_k=2),
    )

    assert rescued
    assert rescued[0]["metadata"]["table_data"]["context"]["场景"] == "W2S2"


def test_retrieval_pipeline_rescues_title_kg_candidate_from_noisy_paths(monkeypatch):
    class DummyGraph:
        def number_of_nodes(self):
            return 1

    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    pipeline = RetrievalPipeline(
        vector_store=object(),
        embedding_client=DummyEmbeddingClient(),
        kg_graph=DummyGraph(),
        bm25_index=None,
        table_index=None,
        config=RetrievalConfig(enable_cross_encoder=True, kg_top_k=3),
    )

    monkeypatch.setattr(
        "retrieval.preprocess_query",
        lambda raw_query, chat_history=None, **kwargs: SimpleNamespace(
            original=raw_query,
            rewritten="论文标题查询",
            intent="policy_lookup",
            entity_types=["project_metadata"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            ("vector", [
                {
                    "chunk_id": "c-noisy-title",
                    "text": "附录说明，没有论文标题。",
                    "score": 0.95,
                    "source": "vector",
                    "entity_ids": ["d0_n0313"],
                    "metadata": {"entity_ids": ["d0_n0313"]},
                }
            ]),
            ("kg", [
                {
                    "chunk_id": "d0_n0073",
                    "text": '{"entity":{"node_id":"d0_n0073","label":"其他结论"}}',
                    "score": 0.75,
                    "source": "kg",
                    "entity_ids": ["d0_n0073"],
                    "metadata": {"entity_ids": ["d0_n0073"], "entity_type": "claim"},
                }
            ]),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda query, candidates, top_k=10, model_name="BAAI/bge-reranker-base": candidates,
    )
    monkeypatch.setattr(
        "retrieval.indexed_kg_recall",
        lambda preprocessed, kg_graph, config, indexes=None: [
            {
                "chunk_id": "d0_n0001",
                "text": '{"entity":{"node_id":"d0_n0001","label":"A 题绿电直连型电氢氨园区优化运行","properties":{"field":"title"}}}',
                "score": 1.45,
                "source": "kg",
                "entity_ids": ["d0_n0001"],
                "metadata": {
                    "entity_ids": ["d0_n0001"],
                    "entity_type": "paper_metadata",
                    "protected_evidence": True,
                },
            }
        ],
    )

    result = pipeline.retrieve("这篇论文的标题是什么？")

    assert result.pipeline["pre_rerank_chunk_ids"][0] == "d0_n0001"
    assert "n0001" in result.pipeline["pre_rerank_node_ids"]
    assert [chunk.chunk_id for chunk in result.chunks][0] == "d0_n0001"


def test_retrieval_pipeline_rescues_exact_alias_kg_candidate_after_rerank_noise(monkeypatch):
    class DummyGraph:
        def number_of_nodes(self):
            return 1

    class DummyEmbeddingClient:
        def embed_queries(self, queries):
            return [[0.1, 0.2] for _ in queries]

    pipeline = RetrievalPipeline(
        vector_store=object(),
        embedding_client=DummyEmbeddingClient(),
        kg_graph=DummyGraph(),
        bm25_index=None,
        table_index=None,
        config=RetrievalConfig(enable_cross_encoder=True, kg_top_k=3),
    )

    monkeypatch.setattr(
        "retrieval.preprocess_query",
        lambda raw_query, chat_history=None, **kwargs: SimpleNamespace(
            original=raw_query,
            rewritten=raw_query,
            intent="policy_lookup",
            entity_types=["dataset"],
            table_conditions=[],
        ),
    )
    monkeypatch.setattr(
        "retrieval.multi_path_recall",
        lambda **kwargs: [
            ("kg", [
                {
                    "chunk_id": "d1_n0039",
                    "text": '{"entity":{"node_id":"d1_n0039","label":"24种风光出力场景"}}',
                    "score": 0.95,
                    "source": "kg",
                    "entity_ids": ["d1_n0039"],
                    "metadata": {"entity_ids": ["d1_n0039"], "entity_type": "dataset"},
                }
            ]),
            ("vector", [
                {
                    "chunk_id": "c-generic-alias",
                    "text": "泛化场景背景说明。",
                    "score": 0.82,
                    "source": "vector",
                    "entity_ids": ["d0_n0328"],
                    "metadata": {"entity_ids": ["d0_n0328"]},
                }
            ]),
        ],
    )
    monkeypatch.setattr(
        "retrieval.cross_encoder_rerank",
        lambda query, candidates, top_k=10, model_name="BAAI/bge-reranker-base": [
            next(item for item in candidates if item["chunk_id"] == "d1_n0039"),
            *[item for item in candidates if item["chunk_id"] != "d1_n0039"],
        ][:top_k],
    )
    monkeypatch.setattr(
        "retrieval.indexed_kg_recall",
        lambda preprocessed, kg_graph, config, indexes=None: [
            {
                "chunk_id": "d0_n0035",
                "text": '{"entity":{"node_id":"d0_n0035","label":"W4S1","properties":{"name":"maximum curtailment scenario"}}}',
                "score": 1.65,
                "source": "kg",
                "entity_ids": ["d0_n0035"],
                "metadata": {
                    "entity_ids": ["d0_n0035"],
                    "entity_type": "dataset",
                    "protected_evidence": True,
                },
            }
        ],
    )

    result = pipeline.retrieve("论文中提到的wind 4 solar 1场景代表什么含义?")

    assert result.pipeline["pre_rerank_chunk_ids"][0] == "d0_n0035"
    assert [chunk.chunk_id for chunk in result.chunks][0] == "d0_n0035"
    assert "n0035" in result.pipeline["final_context_node_ids"]


def test_domain_dict_expand_query_skips_broadening_when_multiple_terms_match():
    domain_dict = DomainDict()
    domain_dict.add(
        {
            "term": "储能",
            "synonyms": ["电池储能"],
            "abbreviations": ["ESS"],
            "related": [],
            "category": "energy",
            "description": "储能系统",
        }
    )
    domain_dict.add(
        {
            "term": "弃电量",
            "synonyms": ["弃电"],
            "abbreviations": [],
            "related": [],
            "category": "energy",
            "description": "弃风弃光电量",
        }
    )

    expanded = domain_dict.expand_query("储能对弃电量有什么影响？")

    assert "储能" in expanded
    assert "弃电" in expanded
    assert len(expanded) > len("储能对弃电量有什么影响？")  # multi-term expansion now allowed


def test_domain_dict_expand_query_still_expands_single_abbreviation_match():
    domain_dict = DomainDict()
    domain_dict.add(
        {
            "term": "储能",
            "synonyms": ["电池储能"],
            "abbreviations": ["ESS"],
            "related": [],
            "category": "energy",
            "description": "储能系统",
        }
    )

    expanded = domain_dict.expand_query("ESS 优化策略是什么？")

    assert expanded.startswith("ESS 优化策略是什么？ ")
    assert "储能" in expanded
    assert "电池储能" in expanded

def test_direct_lookup_query_protects_visualization_library_chunk_without_explicit_library_name():
    candidate = {
        "chunk_id": "c00152",
        "text": "行 MILP/LP 求解，使用 NumPy和 Pandas 进行数据处理，使用 Matplotlib 进行可视化。",
        "source": "vector",
        "metadata": {
            "section_title": "附录 B：支撑材料文件说明",
        },
    }

    assert _candidate_matches_direct_lookup_query("论文用什么库做可视化？", candidate) is True
    assert _candidate_has_exact_query_evidence("论文用什么库做可视化？", candidate) is True


def test_figure_inventory_query_treats_single_caption_chunk_as_exact_evidence():
    candidate = {
        "chunk_id": "c00031",
        "text": "图 5 问题四分析结果（左：三种模式经济性对比；右：储能充放电调度曲线）",
        "source": "vector",
        "metadata": {
            "section_title": "问题四分析结果",
        },
    }

    assert _candidate_matches_figure_inventory("论文中所有的图(figure)有哪些？", candidate) is True
    assert _candidate_has_exact_query_evidence("论文中所有的图(figure)有哪些？", candidate) is True


def test_summary_cost_inventory_query_matches_page_one_cost_metrics():
    candidate = {
        "chunk_id": "d0_n0015",
        "text": "吨氨成本3554元/吨",
        "source": "kg",
        "metadata": {
            "entity_type": "metric",
            "page_idx": 1,
            "properties": {
                "name": "吨氨成本",
                "value": "3554元/吨",
                "field": "summary",
            },
        },
    }

    query = "论文摘要中提到的吨氨成本类经济指标分别有哪些？"

    assert _candidate_matches_metric_query(query, candidate) is True
    assert _candidate_has_exact_query_evidence(query, candidate) is True


def test_build_prompt_adds_exhaustive_instruction_for_inventory_queries():
    retrieval_result = RetrievalResult(
        chunks=[
            RetrievalChunk(
                chunk_id="c00031",
                text="图 5 问题四分析结果（左：三种模式经济性对比；右：储能充放电调度曲线）",
                score=0.9,
                source="vector",
                section_title="问题四分析结果",
            )
        ],
        total_candidates=1,
        pipeline={},
        query_intent="inventory",
        entity_types_used=["figure"],
    )

    messages, _ = build_prompt(
        retrieval_result=retrieval_result,
        user_query="论文中所有的图(figure)有哪些？",
        max_context_tokens=256,
        return_metadata=True,
    )

    assert "尽量完整列出" in messages[1]["content"]
    assert "不要压缩成单句总结" in messages[1]["content"]
    assert "即使答案较长" in messages[1]["content"]

def test_library_lookup_query_prioritizes_method_entities():
    entity_types = _heuristic_entity_types_for_query("论文用什么库做可视化？")

    assert "method" in entity_types
    assert entity_types.index("method") < entity_types.index("metric")


def test_figure_inventory_query_prioritizes_reference_entities():
    entity_types = _heuristic_entity_types_for_query("论文中所有的图(figure)有哪些？")

    assert "reference" in entity_types
    assert "section_header" in entity_types
    assert entity_types.index("reference") < entity_types.index("metric")
    assert entity_types.index("section_header") < entity_types.index("metric")



def test_select_rerank_candidates_prioritizes_exact_evidence_over_generic_protected_chunks():
    query = "论文用什么库做可视化？"
    candidates = [
        {
            "chunk_id": "d0_n0074",
            "text": "提出政策建议并给出论证依据。",
            "score": 0.99,
            "source": "kg",
            "entity_ids": ["n0074"],
            "metadata": {"entity_ids": ["n0074"]},
        },
        {
            "chunk_id": "c00002",
            "text": "论文题目：A题绿电直连型电氢氨园区优化运行",
            "score": 0.97,
            "source": "vector",
            "entity_ids": ["n0001"],
            "metadata": {"entity_ids": ["n0001"]},
        },
        {
            "chunk_id": "c00030",
            "text": "使用 Pandas 进行数据处理，使用 Matplotlib 进行可视化。",
            "score": 0.72,
            "source": "vector",
            "entity_ids": ["n0300"],
            "metadata": {"entity_ids": ["n0300"]},
        },
    ]

    selected = _select_rerank_candidates(query, candidates, max_candidates=2)

    assert [candidate["chunk_id"] for candidate in selected] == ["c00030", "d0_n0074"]