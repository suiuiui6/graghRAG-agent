"""Knowledge Graph construction from grounded extractions."""

import json
from collections import defaultdict

from schema import GroundedExtraction, KGNode, KGEdge


def build_knowledge_graph(
    grounded_extractions: list[GroundedExtraction],
    section_nodes: list[KGNode] | None = None,
) -> tuple[list[KGNode], list[KGEdge]]:
    """Build nodes and edges from grounded extractions.

    Returns (nodes, edges).
    """
    nodes: list[KGNode] = []
    edges: list[KGEdge] = []
    node_counter = 1
    edge_counter = 1

    # ---------- Create entity nodes ----------
    entity_nodes: dict[int, str] = {}  # index → node_id

    for i, ext in enumerate(grounded_extractions):
        nid = f"n{node_counter:04d}"
        node = KGNode(
            node_id=nid,
            entity_type=ext.extraction_class,
            label=ext.extraction_text,
            properties=ext.attributes or {},
            page_idx=ext.page_idx,
            bbox_norm=ext.bbox_norm,
            grounding_status=ext.grounding_status,
        )
        nodes.append(node)
        entity_nodes[i] = nid
        node_counter += 1

    # ---------- Create section nodes ----------
    if section_nodes:
        for sn in section_nodes:
            sn.node_id = f"n{node_counter:04d}"
            nodes.append(sn)
            node_counter += 1

    # ---------- Build edges ----------

    # Edge 1: Co-occurrence (same page)
    by_page: dict[int, list[int]] = defaultdict(list)
    for i, g in enumerate(grounded_extractions):
        if g.page_idx is not None:
            by_page[g.page_idx].append(i)

    for page_idx, indices in by_page.items():
        for a in range(len(indices)):
            for b in range(a + 1, min(a + 6, len(indices))):
                ei, ej = indices[a], indices[b]
                edges.append(KGEdge(
                    edge_id=f"e{edge_counter:04d}",
                    source_node_id=entity_nodes[ei],
                    target_node_id=entity_nodes[ej],
                    relation_type="co_occurs_with",
                    properties={"rule": "same_page", "page_idx": page_idx},
                ))
                edge_counter += 1

    # Edge 2: Same entity_type
    by_type: dict[str, list[int]] = defaultdict(list)
    for i, g in enumerate(grounded_extractions):
        by_type[g.extraction_class].append(i)

    for etype, indices in by_type.items():
        if len(indices) <= 1:
            continue
        # Link consecutive items of the same type
        for a, b in zip(indices[:-1], indices[1:]):
            edges.append(KGEdge(
                edge_id=f"e{edge_counter:04d}",
                source_node_id=entity_nodes[a],
                target_node_id=entity_nodes[b],
                relation_type="same_type",
                properties={"rule": "same_entity_type", "entity_type": etype},
            ))
            edge_counter += 1

    # Edge 3: Sequential adjacency
    for i in range(len(grounded_extractions) - 1):
        if entity_nodes.get(i) and entity_nodes.get(i + 1):
            edges.append(KGEdge(
                edge_id=f"e{edge_counter:04d}",
                source_node_id=entity_nodes[i],
                target_node_id=entity_nodes[i + 1],
                relation_type="adjacent_to",
                properties={"rule": "sequential_order"},
            ))
            edge_counter += 1

    return nodes, edges


def serialize_kg(
    nodes: list[KGNode],
    edges: list[KGEdge],
    metadata: dict,
    output_dir: str,
) -> tuple[str, str]:
    """Serialize KG to nodes.json and edges.json."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    nodes_path = os.path.join(output_dir, "nodes.json")
    edges_path = os.path.join(output_dir, "edges.json")

    nodes_data = {
        "metadata": metadata,
        "node_count": len(nodes),
        "nodes": [
            {
                "node_id": n.node_id,
                "entity_type": n.entity_type,
                "label": n.label,
                "properties": n.properties,
                "page_idx": n.page_idx,
                "bbox_norm": n.bbox_norm,
                "grounding_status": n.grounding_status,
            }
            for n in nodes
        ],
    }

    edges_data = {
        "edge_count": len(edges),
        "edges": [
            {
                "edge_id": e.edge_id,
                "source_node_id": e.source_node_id,
                "target_node_id": e.target_node_id,
                "relation_type": e.relation_type,
                "properties": e.properties,
            }
            for e in edges
        ],
    }

    with open(nodes_path, "w", encoding="utf-8") as f:
        json.dump(nodes_data, f, ensure_ascii=False, indent=2)
    with open(edges_path, "w", encoding="utf-8") as f:
        json.dump(edges_data, f, ensure_ascii=False, indent=2)

    return nodes_path, edges_path


def print_kg_summary(nodes: list[KGNode], edges: list[KGEdge]):
    """Print a human-readable KG summary."""
    print(f"\n{'=' * 60}")
    print(f"  Knowledge Graph Summary")
    print(f"{'=' * 60}")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {len(edges)}")

    # Entity type distribution
    type_counts: dict[str, int] = defaultdict(int)
    grounded_count = 0
    for n in nodes:
        type_counts[n.entity_type] += 1
        if n.grounding_status == "grounded":
            grounded_count += 1

    print(f"  Grounded: {grounded_count}/{len(nodes)}")

    print(f"\n  Entity types:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t:25s} {c:4d}")

    # Edge relation distribution
    rel_counts: dict[str, int] = defaultdict(int)
    for e in edges:
        rel_counts[e.relation_type] += 1

    print(f"\n  Relation types:")
    for r, c in sorted(rel_counts.items(), key=lambda x: -x[1]):
        print(f"    {r:25s} {c:4d}")

    print(f"{'=' * 60}")
