import networkx as nx

from retrieval import (
    RetrievalChunk,
    _build_kg_result,
    _final_context_node_ids,
    _select_rerank_candidates,
    _ordered_unique_node_ids,
    _path_hit_node_ids,
    _retrieval_node_ids,
)


def test_path_hit_node_ids_are_grouped_by_source_and_normalized():
    all_paths = [
        (
            "kg",
            [
                {
                    "chunk_id": "d0_n0035",
                    "text": '{"entity":{"node_id":"d0_n0035"}}',
                    "metadata": {"entity_ids": ["d0_n0035"]},
                }
            ],
        ),
        (
            "vector",
            [
                {
                    "chunk_id": "c00031",
                    "text": 'Section cites {"node_id":"d1_n0042"}',
                    "entity_ids": ["d1_n0042", "d0_n0043"],
                    "metadata": {},
                }
            ],
        ),
    ]

    result = _path_hit_node_ids(all_paths)

    assert result == {"kg": ["n0035"], "vector": ["n0042", "n0043"]}


def test_retrieval_node_ids_preserve_first_seen_order_across_candidates():
    candidates = [
        {
            "chunk_id": "c00031",
            "text": 'Section cites {"node_id":"d1_n0042"}',
            "entity_ids": ["d1_n0042", "d0_n0043"],
            "metadata": {},
        },
        {
            "chunk_id": "d0_n0035",
            "text": '{"entity":{"node_id":"d0_n0035"}}',
            "metadata": {"entity_ids": ["d0_n0035"]},
        },
    ]

    assert _retrieval_node_ids(candidates) == ["n0042", "n0043", "n0035"]


def test_ordered_unique_node_ids_deduplicates_without_reordering():
    assert _ordered_unique_node_ids(["n0035", "n0042", "n0035", "n0043"]) == [
        "n0035",
        "n0042",
        "n0043",
    ]


def test_build_kg_result_preserves_entity_ids_for_final_context_accounting():
    graph = nx.Graph()
    graph.add_node("d0_n0035", entity_type="scenario", label="W4S1", properties={"value": "173.7"})
    graph.add_node("d0_n0042", entity_type="metric", label="弃电量")
    graph.add_edge("d0_n0035", "d0_n0042", relation="mentions")

    result = _build_kg_result("d0_n0035", graph.nodes["d0_n0035"], graph)

    assert result["entity_ids"] == ["d0_n0035"]
    assert result["metadata"]["entity_ids"] == ["d0_n0035"]


def test_final_context_node_ids_are_normalized_from_chunk_entity_ids():
    chunks = [
        RetrievalChunk(
            chunk_id="d0_n0035",
            text="kg",
            score=0.9,
            source="kg",
            entity_ids=["d0_n0035", "d1_n0042"],
        ),
        RetrievalChunk(
            chunk_id="c00031",
            text="vector",
            score=0.8,
            source="vector",
            entity_ids=["d0_n0035", "n0043"],
        ),
    ]

    assert _final_context_node_ids(chunks) == ["n0035", "n0042", "n0043"]


def test_final_context_node_ids_fallback_to_chunk_text_and_metadata_when_entity_ids_are_missing():
    chunks = [
        RetrievalChunk(
            chunk_id="d0_n0035",
            text='Section cites {"node_id":"d1_n0042"}',
            score=0.9,
            source="vector",
            entity_ids=[],
            metadata={"entity_ids": ["d0_n0035"]},
        ),
    ]

    assert _final_context_node_ids(chunks) == ["n0035", "n0042"]


def test_select_rerank_candidates_preserves_protected_table_evidence_even_without_exact_match():
    candidates = [
        {
            "chunk_id": "v1",
            "text": "泛化背景块-1",
            "score": 0.95,
            "source": "vector",
            "metadata": {},
        },
        {
            "chunk_id": "v2",
            "text": "泛化背景块-2",
            "score": 0.94,
            "source": "vector",
            "metadata": {},
        },
        {
            "chunk_id": "v3",
            "text": "泛化背景块-3",
            "score": 0.93,
            "source": "vector",
            "metadata": {},
        },
        {
            "chunk_id": "v4",
            "text": "泛化背景块-4",
            "score": 0.92,
            "source": "vector",
            "metadata": {},
        },
        {
            "chunk_id": "table_row_scenario_summary_99_绿电消纳率",
            "text": '{"column_name":"绿电消纳率","column_value":"95%","context":{"场景":"W2S2","绿电消纳率":"95%","弃电量":"120MWh/日"}}',
            "score": 0.50,
            "source": "table",
            "metadata": {
                "protected_evidence": True,
                "table_data": {
                    "column_name": "绿电消纳率",
                    "column_value": "95%",
                    "context": {"场景": "W2S2", "绿电消纳率": "95%", "弃电量": "120MWh/日"},
                },
            },
        },
    ]

    selected = _select_rerank_candidates(
        "在W2S2场景下，绿电消纳率是多少？",
        candidates,
        max_candidates=4,
    )

    assert "table_row_scenario_summary_99_绿电消纳率" in [item["chunk_id"] for item in selected]
