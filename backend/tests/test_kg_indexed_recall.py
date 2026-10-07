import json
import asyncio
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

if "langchain.agents" not in sys.modules:
    sys.modules["langchain.agents"] = types.SimpleNamespace(
        create_agent=lambda *args, **kwargs: types.SimpleNamespace(
            invoke=lambda payload: {"messages": []}
        )
    )

if "langchain.tools" not in sys.modules:
    def _tool_decorator(func):
        class ToolWrapper:
            def __init__(self, wrapped):
                self.func = wrapped

            def invoke(self, payload):
                return self.func(**payload)

        return ToolWrapper(func)

    sys.modules["langchain.tools"] = types.SimpleNamespace(tool=_tool_decorator)

if "langchain_openai" not in sys.modules:
    sys.modules["langchain_openai"] = types.SimpleNamespace(
        ChatOpenAI=lambda *args, **kwargs: object()
    )

from config import RetrievalConfig
from kg_store import build_kg_lookup_indexes, lookup_kg_label_nodes
from models import QueryOptions, QueryRequest
from retrieval import PreprocessedQuery, indexed_kg_recall
import routes.query as query_route


def _build_sample_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_node(
        "metric_budget",
        entity_type="metric",
        label="预算执行率",
        properties={"description": "预算执行率超过80%的项目"},
        page_idx=2,
        grounding_status="grounded",
    )
    graph.add_node(
        "metric_cost",
        entity_type="metric",
        label="成本偏差",
        properties={"description": "成本偏差控制"},
        page_idx=3,
        grounding_status="grounded",
    )
    graph.add_node(
        "dept_finance",
        entity_type="department",
        label="财务部",
        properties={"owner": "预算治理"},
        page_idx=4,
        grounding_status="grounded",
    )
    graph.add_edge("metric_budget", "dept_finance", relation="owned_by")
    return graph


def test_build_kg_lookup_indexes_supports_entity_type_and_token_lookup():
    graph = _build_sample_graph()

    indexes = build_kg_lookup_indexes(graph)

    assert indexes["entity_type_to_nodes"]["metric"] == ["metric_budget", "metric_cost"]
    assert "metric_budget" in indexes["token_to_nodes"]["预算"]
    assert "metric_budget" in indexes["token_to_nodes"]["执行率"]
    assert "dept_finance" in indexes["token_to_nodes"]["财务部"]


def test_indexed_kg_recall_uses_candidates_without_full_graph_scan():
    graph = _build_sample_graph()
    indexes = build_kg_lookup_indexes(graph)
    config = RetrievalConfig(kg_top_k=2)
    preprocessed = PreprocessedQuery(
        original="预算执行率",
        rewritten="预算执行率",
        intent="metric",
        entity_types=["metric"],
    )

    original_nodes = graph.nodes

    def fail_on_full_scan(*args, **kwargs):
        raise AssertionError("full graph scan should not happen")

    graph.nodes = fail_on_full_scan
    try:
        results = indexed_kg_recall(preprocessed, graph, config, indexes=indexes)
    finally:
        graph.nodes = original_nodes

    assert [item["chunk_id"] for item in results] == ["metric_budget"]
    assert results[0]["metadata"]["neighbor_count"] == 1


def test_indexed_kg_recall_matches_split_keyword_tokens():
    graph = _build_sample_graph()
    indexes = build_kg_lookup_indexes(graph)
    config = RetrievalConfig(kg_top_k=2)
    preprocessed = PreprocessedQuery(
        original="预算 执行率",
        rewritten="预算 执行率",
        intent="metric",
        entity_types=["metric"],
    )

    results = indexed_kg_recall(preprocessed, graph, config, indexes=indexes)

    assert [item["chunk_id"] for item in results] == ["metric_budget"]


def test_lookup_kg_nodes_supports_english_partial_keyword_fallback():
    from kg_store import lookup_kg_nodes

    graph = nx.Graph()
    graph.add_node(
        "metric_en",
        entity_type="metric",
        label="Budget Variance",
        properties={"description": "Budget variance review"},
        grounding_status="grounded",
    )
    indexes = build_kg_lookup_indexes(graph)

    matches = lookup_kg_nodes(graph, keyword="budg", limit=3, indexes=indexes)

    assert [node_id for node_id, _ in matches] == ["metric_en"]


def test_lookup_kg_label_nodes_uses_label_only_index_without_full_scan():
    graph = nx.Graph()
    graph.add_node(
        "label_only",
        entity_type="metric",
        label="预算执行率",
        properties={"description": "属性里也有预算执行率"},
        grounding_status="grounded",
    )
    indexes = build_kg_lookup_indexes(graph)

    original_nodes = graph.nodes

    def fail_on_full_scan(*args, **kwargs):
        raise AssertionError("label lookup should not full-scan graph nodes")

    graph.nodes = fail_on_full_scan
    try:
        matches = lookup_kg_label_nodes(graph, keyword="预算执行率", limit=1, indexes=indexes)
    finally:
        graph.nodes = original_nodes

    assert [node_id for node_id, _ in matches] == ["label_only"]


def test_legacy_query_search_tool_limits_results_and_uses_index():
    graph = _build_sample_graph()
    graph.graph["_kg_lookup_indexes"] = build_kg_lookup_indexes(graph)
    tool = query_route._make_search_tool(graph)

    graph.nodes = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("legacy search should use index lookup")
    )
    payload = tool.invoke({"entity_type": "metric", "keyword": "预算", "max_results": 99})

    assert payload.count("\"node_id\"") == 1
    assert "metric_budget" in payload
    assert "metric_cost" not in payload


def test_build_kg_from_full_primes_lookup_indexes():
    full_graph = _build_sample_graph()

    grounded = query_route._build_kg_from_full(full_graph)

    assert grounded is not None
    assert "_kg_lookup_indexes" in grounded.graph
    assert "metric" in grounded.graph["_kg_lookup_indexes"]["entity_type_to_nodes"]


def test_legacy_neighbor_tool_is_bounded_and_indexed():
    graph = _build_sample_graph()
    for idx in range(20):
        graph.add_node(
            f"neighbor_{idx}",
            entity_type="risk_item",
            label=f"邻居{idx}",
            properties={"kind": "risk"},
            grounding_status="grounded",
        )
        graph.add_edge("metric_budget", f"neighbor_{idx}", relation="related_to")

    graph.graph["_kg_lookup_indexes"] = build_kg_lookup_indexes(graph)
    tool = query_route._make_neighbors_tool(graph)

    original_neighbors = graph.neighbors

    def fail_if_full_scan(node_id):
        if node_id == "metric_budget":
            raise AssertionError("legacy neighbor tool should use bounded preview instead of full fanout")
        return original_neighbors(node_id)

    graph.neighbors = fail_if_full_scan
    try:
        payload = tool.invoke({"label_keyword": "预算", "k_hops": 1, "max_results": 99})
    finally:
        graph.neighbors = original_neighbors

    assert payload.count("\"node_id\"") <= 1 + query_route.LEGACY_QUERY_TOOL_LIMIT
    assert "metric_budget" in payload


def test_legacy_neighbor_tool_prefers_label_match_over_property_match():
    graph = nx.Graph()
    graph.add_node(
        "label_target",
        entity_type="metric",
        label="预算执行率",
        properties={"description": "直接标签命中"},
        grounding_status="grounded",
    )
    graph.add_node(
        "property_only",
        entity_type="metric",
        label="成本偏差",
        properties={"description": "预算执行率来自属性匹配"},
        grounding_status="grounded",
    )
    graph.add_node(
        "neighbor_label",
        entity_type="department",
        label="财务部",
        properties={},
        grounding_status="grounded",
    )
    graph.add_node(
        "neighbor_property",
        entity_type="department",
        label="审计部",
        properties={},
        grounding_status="grounded",
    )
    graph.add_edge("label_target", "neighbor_label", relation="owned_by")
    graph.add_edge("property_only", "neighbor_property", relation="owned_by")
    graph.graph["_kg_lookup_indexes"] = build_kg_lookup_indexes(graph)

    tool = query_route._make_neighbors_tool(graph)
    payload = json.loads(tool.invoke({"label_keyword": "预算执行率", "k_hops": 1, "max_results": 5}))

    assert payload["source"]["node_id"] == "label_target"
    assert payload["neighbors"][0]["node_id"] == "neighbor_label"


def test_load_all_kgs_reads_versioned_storage_layout(sandbox_tmp_path):
    version_dir = sandbox_tmp_path / "doc_alpha" / "v1"
    version_dir.mkdir(parents=True)
    (sandbox_tmp_path / "doc_alpha" / "versions.json").write_text(
        json.dumps({"doc_id": "alpha", "versions": [{"version": 1}], "active_version": 1}),
        encoding="utf-8",
    )
    (version_dir / "nodes.json").write_text(
        json.dumps([{"node_id": "n1", "entity_type": "metric", "label": "预算执行率", "grounding_status": "grounded"}], ensure_ascii=False),
        encoding="utf-8",
    )
    (version_dir / "edges.json").write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")

    original_dir = query_route.KG_DIR
    try:
        query_route.KG_DIR = str(sandbox_tmp_path)
        loaded = query_route._load_all_kgs()
    finally:
        query_route.KG_DIR = original_dir

    assert loaded.number_of_nodes() == 1


def test_legacy_query_invoke_passes_recursion_limit():
    captured = {}

    class DummyAgent:
        def invoke(self, payload, config=None):
            captured["payload"] = payload
            captured["config"] = config
            return {"messages": []}

    query_route._invoke_legacy_agent(DummyAgent(), "预算执行率", language="ch")

    assert captured["payload"] == {"messages": [("user", "预算执行率")]}
    assert captured["config"] == {
        "recursion_limit": query_route.LEGACY_QUERY_RECURSION_LIMIT
    }


def test_legacy_query_route_degrades_gracefully_on_graph_recursion_limit(monkeypatch):
    class DummyAgent:
        def invoke(self, payload, config=None):
            raise query_route.GraphRecursionError("limit reached")

    monkeypatch.setattr(query_route, "_get_agent", lambda: DummyAgent())
    monkeypatch.setattr(query_route, "G_grounded", None)

    response = asyncio.run(
        query_route.query(
            QueryRequest(
                query="这个问题太宽了",
                options=QueryOptions(language="ch", include_sources=False),
            )
        )
    )

    assert "步数预算" in response.answer
    assert response.metadata["step_limited"] is True
    assert response.metadata["error_code"] == "GRAPH_RECURSION_LIMIT"
    assert (
        response.metadata["legacy_agent_recursion_limit"]
        == query_route.LEGACY_QUERY_RECURSION_LIMIT
    )

