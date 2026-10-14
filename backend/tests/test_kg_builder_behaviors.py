"""Graph construction contracts using grounded business entities, without model calls."""
import json

import pytest

from kg_builder import build_knowledge_graph, serialize_kg, print_kg_summary
from schema import GroundedExtraction, KGNode


def entity(kind, label, attributes=None, page=0):
    return GroundedExtraction(kind, label, attributes, (0, len(label)), page,
                              [0.1, 0.2, 0.3, 0.4], "text", "grounded")


def relations(extractions):
    nodes, edges = build_knowledge_graph(extractions)
    labels = {node.node_id: node.label for node in nodes}
    return {(labels[e.source_node_id], e.relation_type, labels[e.target_node_id]): e.properties
            for e in edges}


def test_empty_graph_and_section_identity():
    assert build_knowledge_graph([]) == ([], [])
    section = KGNode("old", "section", "Chapter", {}, None, None, "ungrounded")
    nodes, edges = build_knowledge_graph([entity("metric", "Latency", page=None)], [section])
    assert [n.node_id for n in nodes] == ["n0001", "n0002"]
    assert nodes[0].properties == {}
    assert nodes[0].bbox_norm == [0.1, 0.2, 0.3, 0.4]
    assert nodes[1].label == "Chapter"
    assert not any(e.relation_type == "co_occurs_with" for e in edges)


def test_same_page_edges_have_bounded_window_and_do_not_cross_pages():
    data = [entity("metric", f"m{i}") for i in range(7)] + [entity("metric", "other", page=1)]
    graph = relations(data)
    assert ("m0", "co_occurs_with", "m5") in graph
    assert ("m0", "co_occurs_with", "m6") not in graph
    assert ("m6", "co_occurs_with", "other") not in graph
    assert ("m6", "same_type", "other") in graph
    assert ("m6", "adjacent_to", "other") in graph


@pytest.mark.parametrize("source_kind,key,target_kind,relation", [
    ("person_role", "reports_to", "person_role", "reports_to"),
    ("project_metadata", "department", "department", "owned_by"),
    ("process_step", "owner_dept", "department", "owned_by"),
    ("process_step", "regulation_ref", "regulation_ref", "references"),
    ("risk_item", "references", "regulation_ref", "references"),
    ("project_metadata", "milestones", "milestone", "has_milestone"),
    ("process_step", "produces", "deliverable", "produces"),
    ("process_step", "output", "deliverable", "produces"),
    ("process_step", "deliverable", "deliverable", "produces"),
    ("project_metadata", "metrics", "metric", "has_metric"),
    ("milestone", "metric", "metric", "has_metric"),
])
def test_attribute_relations_resolve_normalized_target_and_reject_wrong_type(source_kind, key, target_kind, relation):
    graph = relations([entity(source_kind, "Source", {key: " TARGET "}),
                       entity(target_kind, "Target"), entity("unrelated", "Target")])
    assert ("Source", relation, "Target") in graph
    nodes, edges = build_knowledge_graph([entity(source_kind, "Source", {key: "Target"}),
                                         entity("unrelated", "Target")])
    assert not any(e.relation_type == relation for e in edges)
    missing = relations([entity(source_kind, "Source", {key: "missing"})])
    assert not any(r == relation for _, r, _ in missing)


@pytest.mark.parametrize("kind,key,target,relation", [
    ("process_step", "references", "regulation_ref", "references"),
    ("project_metadata", "milestones", "milestone", "has_milestone"),
    ("process_step", "produces", "deliverable", "produces"),
    ("milestone", "metrics", "metric", "has_metric"),
])
def test_multivalue_relations_keep_all_existing_targets(kind, key, target, relation):
    graph = relations([entity(kind, "Source", {key: ["A", "missing", "B"]}),
                       entity(target, "A"), entity(target, "B")])
    assert {(s, t) for s, r, t in graph if r == relation} == {("Source", "A"), ("Source", "B")}


def test_department_fuzzy_ownership_and_mitigation_mentions():
    graph = relations([entity("project_metadata", "Project", {"department": "Engineering division"}),
                       entity("department", "Engineering"),
                       entity("risk_item", "Delay", {"mitigation": "Perform REVIEW before release"}),
                       entity("risk_item", "Defect", {"mitigation_measure": "Review and audit"}),
                       entity("risk_item", "Missing", {"mitigation": "unknown action"}),
                       entity("process_step", "Review"), entity("process_step", "Audit")])
    assert ("Project", "owned_by", "Engineering") in graph
    assert ("Delay", "mitigates", "Review") in graph
    assert ("Defect", "mitigates", "Audit") in graph
    assert not any(s == "Missing" and r == "mitigates" for s, r, _ in graph)


def test_serialization_round_trip_preserves_graph_and_schema(tmp_path):
    nodes, edges = build_knowledge_graph([entity("metric", "响应时间"), entity("metric", "Latency")])
    node_path, edge_path = serialize_kg(nodes, edges, {"source": "fixture"}, str(tmp_path / "graph"))
    with open(node_path, encoding="utf-8") as stream:
        document = json.load(stream)
    with open(edge_path, encoding="utf-8") as stream:
        connections = json.load(stream)
    assert document["metadata"] == {"source": "fixture", "schema_version": "1.1"}
    assert document["node_count"] == 2
    assert document["nodes"][0]["label"] == "响应时间"
    assert connections["edge_count"] == len(edges)
    assert {e["source_node_id"] for e in connections["edges"]} <= {n["node_id"] for n in document["nodes"]}


def test_summary_logs_business_counts():
    import structlog
    nodes, edges = build_knowledge_graph([entity("metric", "Latency")])
    with structlog.testing.capture_logs() as events:
        print_kg_summary(nodes, edges)
    assert len(events) == 1
    assert events[0]["event"] == "kg_summary"
    assert events[0]["nodes"] == 1 and events[0]["edges"] == 0
    assert events[0]["grounded"] == 1
    assert events[0]["entity_types"] == {"metric": 1}
    assert events[0]["relation_types"] == {}


def test_serialized_entity_lineage_is_persisted_with_source_identity(monkeypatch, tmp_path):
    from services import lineage_store
    store = lineage_store.LineageStore(tmp_path / "lineage")
    monkeypatch.setattr(lineage_store, "get_lineage_store", lambda: store)
    nodes, edges = build_knowledge_graph([entity("metric", "Latency", page=2)])
    serialize_kg(nodes, edges, {"document_id": "doc-fixture"}, str(tmp_path / "graph"))
    restored = lineage_store.LineageStore(tmp_path / "lineage")
    trace = restored.trace_entity(nodes[0].node_id)
    assert trace is not None
    source, = trace.trace
    assert source.parent_ids == ["document:doc-fixture"]
    assert source.metadata["doc_id"] == "doc-fixture"
    assert source.metadata["page_idx"] == 2
    assert source.metadata["bbox_norm"] == [0.1, 0.2, 0.3, 0.4]
    assert restored.trace_document("doc-fixture")["total"] == 1


def test_lineage_failure_does_not_discard_serialized_graph(monkeypatch, tmp_path):
    from services import lineage_store

    def unavailable():
        raise OSError("optional lineage disk unavailable")

    monkeypatch.setattr(lineage_store, "get_lineage_store", unavailable)
    nodes, edges = build_knowledge_graph([entity("metric", "Latency")])
    nodes_path, edges_path = serialize_kg(nodes, edges, {"document_id": "doc-fixture"}, str(tmp_path))
    with open(nodes_path, encoding="utf-8") as stream:
        assert json.load(stream)["node_count"] == 1
    with open(edges_path, encoding="utf-8") as stream:
        assert json.load(stream)["edge_count"] == 0
