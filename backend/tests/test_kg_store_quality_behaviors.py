"""Real NetworkX/JSON/YAML fixtures for graph storage and source-position contracts."""
import json
import sys
from pathlib import Path

import networkx as nx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bridge
import kg_store
from schema import PositionMap, SectionSplit


def put_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def graph():
    result = nx.Graph()
    result.add_node("n1", label="储氢 tank", entity_type="equipment", properties={"pressure": "30 MPa"})
    result.add_node("n2", label="氢气压力", entity_type="metric", properties={"value": 30})
    result.add_node("n3", label="安全阀", entity_type="equipment", properties=None)
    result.add_node("isolated", label="无连接")
    result.add_edge("n1", "n2", relation="monitors")
    result.add_edge("n2", "n3")
    result.add_edge("n3", "n1", relation="protects")
    return result


def test_lookup_indexes_include_properties_but_label_search_does_not(graph):
    indexes = kg_store.get_kg_lookup_indexes(graph)
    assert kg_store.get_kg_lookup_indexes(graph) is indexes
    assert indexes["entity_type_to_nodes"]["equipment"] == ["n1", "n3"]
    assert indexes["node_text"]["n1"] == "储氢 tank 30 mpa"
    assert [key for key, _ in kg_store.lookup_kg_nodes(graph, keyword="MPa")] == ["n1"]
    assert kg_store.lookup_kg_label_nodes(graph, keyword="MPa") == []
    assert [key for key, _ in kg_store.lookup_kg_label_nodes(graph, keyword="TANK")] == ["n1"]
    assert {row["relation"] for row in indexes["neighbor_preview"]["n2"]} == {"monitors", "connected"}


def test_community_cache_covers_all_nodes_without_model_calls(graph):
    index = kg_store.get_community_index(graph)
    assert kg_store.get_community_index(graph) is index
    assert set(index["node_to_community"]) == set(graph.nodes)
    assert sum(row["size"] for row in index["communities"]) == graph.number_of_nodes()


def test_lookup_tokenizer_normalizes_ascii_and_extracts_chinese_ngrams():
    assert kg_store._tokenize_kg_lookup_text("") == []
    tokens = set(kg_store._tokenize_kg_lookup_text("  A tank 储氢安全阀 "))
    assert {"tank", "储", "储氢", "储氢安", "储氢安全", "阀"} <= tokens
    assert "a" not in tokens


@pytest.mark.parametrize("options,expected", [
    ({"limit": 0}, []), ({"entity_types": ["equipment", "equipment"]}, ["n1", "n3"]),
    ({"entity_types": ["metric"], "keyword": "压力"}, ["n2"]),
    ({"entity_types": ["equipment"], "keyword": "压力"}, []),
    ({"keyword": "unknown"}, []), ({"limit": 2}, ["n1", "n2"]),
])
def test_graph_lookup_intersects_types_and_keywords_without_duplicate_ids(graph, options, expected):
    assert [key for key, _ in kg_store.lookup_kg_nodes(graph, **options)] == expected


def test_substring_fallback_handles_single_ascii_character_not_indexed_as_word(graph):
    assert [key for key, _ in kg_store.lookup_kg_nodes(graph, keyword="k")] == ["n1"]
    assert [key for key, _ in kg_store.lookup_kg_label_nodes(graph, keyword="k")] == ["n1"]
    assert kg_store.lookup_kg_label_nodes(graph, keyword=" ") == []
    assert kg_store.lookup_kg_label_nodes(graph, keyword="tank", limit=0) == []


def test_neighbor_lookup_bounds_cycles_hops_and_disconnected_nodes(graph):
    assert kg_store.bounded_neighbor_lookup(graph, "absent") == []
    assert kg_store.bounded_neighbor_lookup(graph, "n1", fanout=0) == []
    assert len(kg_store.bounded_neighbor_lookup(graph, "n1", fanout=1)) == 1
    neighbors = kg_store.bounded_neighbor_lookup(graph, "n1", k_hops=5, fanout=10)
    assert {row["node_id"] for row in neighbors} == {"n2", "n3"}
    assert kg_store.bounded_neighbor_lookup(graph, "isolated", k_hops=3) == []
    assert len(kg_store.bounded_neighbor_lookup(graph, "n1", k_hops=2, fanout=1)) == 1


def test_neighbor_preview_is_bounded_at_ten_and_keeps_real_neighbors():
    graph = nx.star_graph(15)
    indexes = kg_store.build_kg_lookup_indexes(graph)
    assert len(indexes["neighbor_preview"][0]) == 10
    assert {row["node_id"] for row in indexes["neighbor_preview"][0]} <= set(graph.neighbors(0))


@pytest.mark.parametrize("wrapper", [False, True])
def test_legacy_graph_roundtrip_supports_wrappers_and_prefixes(tmp_path, wrapper):
    manager = kg_store.KgVersionManager("fixture", tmp_path)
    nodes = [{"node_id": "1", "label": "甲"}, {"id": "b", "label": "乙"}, {"label": "丙"}]
    edges = [{"from": "1", "to": "b", "relation": "knows"}]
    put_json(manager.doc_dir / "nodes.json", {"nodes": nodes} if wrapper else nodes)
    put_json(manager.doc_dir / "edges.json", {"edges": edges} if wrapper else edges)
    graph = manager.load_graph(id_prefix="doc:")
    assert set(graph.nodes) == {"doc:1", "doc:b", "doc:2"}
    assert graph.nodes["doc:2"]["label"] == "丙"
    assert graph.edges["doc:1", "doc:b"]["relation"] == "knows"


@pytest.mark.parametrize("nodes,edges", [({}, {}), ([], []), ({"other": []}, {"other": []})])
def test_unsupported_or_empty_legacy_documents_produce_empty_graph(tmp_path, nodes, edges):
    manager = kg_store.KgVersionManager("empty", tmp_path)
    put_json(manager.doc_dir / "nodes.json", nodes)
    put_json(manager.doc_dir / "edges.json", edges)
    assert manager.load_graph().number_of_nodes() == 0


def test_missing_graph_and_invalid_json_are_distinct(tmp_path):
    manager = kg_store.KgVersionManager("missing", tmp_path)
    assert manager.active_version() == 0 and manager.list_versions() == []
    assert manager.load_graph().number_of_nodes() == 0
    manager.doc_dir.mkdir()
    (manager.doc_dir / "nodes.json").write_text("invalid", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        manager.load_graph()


@pytest.mark.parametrize("service_failure", [False, True])
def test_version_storage_is_durable_and_survives_optional_event_failure(monkeypatch, tmp_path, service_failure):
    import services.event_bus
    import services.audit_logger
    events = []
    def publish(event, payload):
        if service_failure:
            raise RuntimeError("event unavailable")
        events.append((event, payload))
    class Audit:
        def log(self, *args, **kwargs):
            if service_failure:
                raise OSError("audit unavailable")
    class Bus:
        def publish(self, event, payload):
            publish(event, payload)
    monkeypatch.setattr(services.event_bus, "get_event_bus", lambda: Bus())
    monkeypatch.setattr(services.audit_logger, "get_audit_logger", lambda: Audit())
    manager = kg_store.KgVersionManager("versioned", tmp_path)
    assert manager.create_version([{"node_id": "n", "label": "初版"}], []) == 1
    assert manager.create_version([{"node_id": "n", "label": "新版"}], [], status="review") == 2
    fresh = kg_store.KgVersionManager("versioned", tmp_path)
    assert fresh.active_version() == 2
    assert fresh.list_versions()[1]["status"] == "review"
    assert fresh.load_graph().nodes["n"]["label"] == "新版"
    assert not fresh.activate_version(99) and fresh.active_version() == 2
    assert fresh.activate_version(1)
    assert fresh.load_graph().nodes["n"]["label"] == "初版"
    if not service_failure:
        assert [event for event, _ in events] == ["kg.version_created", "kg.version_created", "kg.version_switched"]


@pytest.mark.parametrize("wrapper", [False, True])
def test_global_legacy_aggregate_fallback(tmp_path, wrapper):
    nodes = [{"id": "n1", "label": "甲"}, {"node_id": "n2", "label": "乙"}]
    edges = [{"from": "n1", "to": "n2"}, {"from": "", "to": "n2"}]
    put_json(tmp_path / "nodes.json", {"nodes": nodes} if wrapper else nodes)
    put_json(tmp_path / "edges.json", {"edges": edges} if wrapper else edges)
    (tmp_path / "unrelated").mkdir()
    (tmp_path / "doc_empty").mkdir()
    graph = kg_store.load_all_kg_graphs(tmp_path)
    assert set(graph.nodes) == {"n1", "n2"} and graph.number_of_edges() == 1


def test_aggregate_preserves_document_identity_and_tenant_scope(tmp_path):
    base = tmp_path / "org" / "project"
    for name in ["a", "b"]:
        manager = kg_store.KgVersionManager(name, base)
        put_json(manager.doc_dir / "nodes.json", [{"node_id": "same", "label": name}])
    put_json(tmp_path / "nodes.json", [{"node_id": "outside"}])
    graph = kg_store.load_all_kg_graphs(tmp_path, "org", "project")
    assert set(graph.nodes) == {"d0_same", "d1_same"}
    assert {data["label"] for _, data in graph.nodes(data=True)} == {"a", "b"}
    assert kg_store.load_all_kg_graphs(tmp_path / "missing").number_of_nodes() == 0


@pytest.mark.parametrize("edge", [{"source_node_id": "", "target_node_id": "n1"},
    {"source_node_id": "n1", "target_node_id": None}, {"from": "n1"}, {}])
def test_prefixed_graph_does_not_create_phantom_nodes_for_missing_edge_endpoint(tmp_path, edge):
    manager = kg_store.KgVersionManager("bad-edge", tmp_path)
    put_json(manager.doc_dir / "nodes.json", [{"node_id": "n1", "label": "甲"}])
    put_json(manager.doc_dir / "edges.json", [edge])
    graph = manager.load_graph(id_prefix="doc:")
    assert set(graph.nodes) == {"doc:n1"}
    assert graph.number_of_edges() == 0


@pytest.mark.parametrize("item,expected", [
    ({"type": "equation", "text": "x=1"}, "x=1"),
    ({"type": "image", "image_caption": ["图", "说明"]}, "图 说明"),
    ({"type": "image"}, "[Image]"), ({"type": "chart"}, "[Chart]"),
    ({"type": "chart", "chart_caption": ["趋势"]}, "趋势"),
    ({"type": "table"}, "[Table]"),
    ({"type": "table", "table_caption": ["表"], "table_body": "<tr><td>A</td><td>B</td></tr>"}, "表\nA | B"),
    ({"type": "footer", "text": "注"}, "注"), ({"type": "list", "text": "条目"}, "条目"),
    ({"type": "unknown"}, ""),
])
def test_content_types_produce_searchable_display_text(item, expected):
    assert bridge._item_to_text(item) == expected


def test_position_map_normalizes_whitespace_and_falls_back_after_last_segment():
    items = [{"type": "text", "text": "  甲\n乙  ", "page_idx": 2},
             {"type": "text", "text": "missing", "page_idx": 3}, {"type": "unknown"}]
    positions = bridge.build_position_map(items, "prefix 甲 乙 suffix")
    assert len(positions.segments) == 2
    first, second = positions.segments
    assert first.char_start == 7 and first.char_end == 10
    assert second.char_start == first.char_end and second.char_end == first.char_end + 7
    assert second.page_idx == 3
    fallback = bridge.build_position_map([{"type": "text", "text": "not found"}], "")
    assert fallback.segments[0].char_start == 0


def test_heading_split_preserves_long_preamble_and_merges_short_trailing_section():
    text = "序" * 160 + "第一节\n" + "甲" * 160 + "第二节\n短尾"
    items = [{"type": "text", "text": "第一节", "text_level": 1},
             {"type": "text", "text": "第二节", "text_level": 2},
             {"type": "text", "text": "忽略", "text_level": 3},
             {"type": "text", "text": "", "text_level": 1},
             {"type": "text", "text": "缺失标题", "text_level": 1}]
    sections = bridge.find_section_boundaries(items, text, PositionMap([]))
    assert len(sections) == 2
    assert sections[0].title == "(Preamble)" and sections[0].char_end == 160
    assert sections[1].title == "第一节" and sections[1].char_end == len(text)
    assert "第二节" in bridge.extract_section_text(text, sections[1])
    assert bridge._slugify(" !!! ") == "section"
    assert len(bridge._slugify("x" * 80)) == 40


def test_no_headings_builds_whole_document_and_skips_short_sections():
    text = "完整中文文档内容超过十个字符"
    sections = bridge.find_section_boundaries([], text, PositionMap([]))
    docs, offsets = bridge.build_documents(sections, text)
    assert len(docs) == 1 and docs[0].text == text
    assert offsets == {"sec_0_full": 0}
    assert bridge.build_documents([SectionSplit("empty", "空", 0, 0, 0), SectionSplit("short", "短", 0, 0, 2)], text) == ([], {})
    assert bridge._merge_short_sections([], text) == []


def test_bridge_loaders_read_real_utf8_files_and_propagate_missing_input(tmp_path):
    path = tmp_path / "content_list.json"
    data = [{"type": "text", "text": "中文"}]
    put_json(path, data)
    md = tmp_path / "full.md"
    md.write_text("# 中文\n内容", encoding="utf-8")
    assert bridge.load_content_list(str(path)) == data
    assert bridge.load_full_md(str(md)) == "# 中文\n内容"
    with pytest.raises(FileNotFoundError):
        bridge.load_full_md(str(tmp_path / "missing.md"))


@pytest.mark.parametrize("leading,trailing", [(" \n  ", "  "), ("", " \t\n"), ("\u3000\t", "")])
def test_stripped_document_offsets_still_map_to_original_source_characters(leading, trailing):
    text = leading + "项目响应时间为10毫秒。" + trailing
    documents, offsets = bridge.build_documents([SectionSplit("section", "项目", 1, 0, len(text))], text)
    assert documents[0].text == "项目响应时间为10毫秒。"
    start = offsets[documents[0].document_id]
    assert start == len(leading)
    assert text[start:start + len(documents[0].text)] == documents[0].text


def test_whitespace_only_section_does_not_produce_document_or_offset():
    text = " \n\t\u3000  \r\n "
    assert bridge.build_documents([SectionSplit("blank", "空", 1, 0, len(text))], text) == ([], {})
