"""Knowledge Graph construction from grounded extractions."""

import json
from collections import Counter, defaultdict

from logging_config import get_logger
from schema import GroundedExtraction, KGNode, KGEdge

logger = get_logger(__name__)


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

    # ---- Build lookup tables for enterprise edge inference ----
    nodes_by_id: dict[str, KGNode] = {n.node_id: n for n in nodes}

    label_to_nodes: dict[str, list[str]] = defaultdict(list)
    for n in nodes:
        label_lower = n.label.lower().strip()
        label_to_nodes[label_lower].append(n.node_id)

    type_to_nodes: dict[str, list[str]] = defaultdict(list)
    for n in nodes:
        type_to_nodes[n.entity_type].append(n.node_id)

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

    # ---------- Edge 4-10: Enterprise relation types (from entity properties) ----------

    # Edge 4: reports_to (person_role -> person_role)
    for n in nodes:
        if n.entity_type != "person_role":
            continue
        reports_to_val = n.properties.get("reports_to")
        if not reports_to_val:
            continue
        reports_to_str = str(reports_to_val).lower().strip()
        if reports_to_str in label_to_nodes:
            for target_id in label_to_nodes[reports_to_str]:
                target = nodes_by_id.get(target_id)
                if target and target.entity_type == "person_role":
                    edges.append(KGEdge(
                        edge_id=f"e{edge_counter:04d}",
                        source_node_id=n.node_id,
                        target_node_id=target_id,
                        relation_type="reports_to",
                        properties={"rule": "attribute", "key": "reports_to"},
                    ))
                    edge_counter += 1
        else:
            logger.warning("kg_relation_target_missing", relation="reports_to",
                           target=reports_to_val, source_node_id=n.node_id)

    # Edge 5: owned_by (project_metadata / process_step -> department)
    for n in nodes:
        if n.entity_type not in ("project_metadata", "process_step"):
            continue
        dept_val = n.properties.get("department") or n.properties.get("owner_dept")
        if not dept_val:
            continue
        dept_str = str(dept_val).lower().strip()
        matched = False
        if dept_str in label_to_nodes:
            for target_id in label_to_nodes[dept_str]:
                target = nodes_by_id.get(target_id)
                if target and target.entity_type == "department":
                    edges.append(KGEdge(
                        edge_id=f"e{edge_counter:04d}",
                        source_node_id=n.node_id,
                        target_node_id=target_id,
                        relation_type="owned_by",
                        properties={"rule": "attribute", "key": "department" if n.properties.get("department") else "owner_dept"},
                    ))
                    edge_counter += 1
                    matched = True
        # Fallback: fuzzy match against any department label
        if not matched:
            for dept_id in type_to_nodes.get("department", []):
                dept_node = nodes_by_id.get(dept_id)
                if dept_node and (dept_str in dept_node.label.lower() or dept_node.label.lower() in dept_str):
                    edges.append(KGEdge(
                        edge_id=f"e{edge_counter:04d}",
                        source_node_id=n.node_id,
                        target_node_id=dept_id,
                        relation_type="owned_by",
                        properties={"rule": "attribute_fuzzy", "key": "department" if n.properties.get("department") else "owner_dept"},
                    ))
                    edge_counter += 1
                    matched = True
        if not matched:
            logger.warning("kg_relation_target_missing", relation="owned_by",
                           target=dept_val, source_node_id=n.node_id)

    # Edge 6: references (process_step / risk_item -> regulation_ref)
    for n in nodes:
        if n.entity_type not in ("process_step", "risk_item"):
            continue
        ref_val = n.properties.get("regulation_ref") or n.properties.get("references")
        if not ref_val:
            continue
        ref_names = [ref_val] if isinstance(ref_val, str) else ref_val
        for ref_name in ref_names:
            ref_str = str(ref_name).lower().strip()
            if ref_str in label_to_nodes:
                for target_id in label_to_nodes[ref_str]:
                    target = nodes_by_id.get(target_id)
                    if target and target.entity_type == "regulation_ref":
                        edges.append(KGEdge(
                            edge_id=f"e{edge_counter:04d}",
                            source_node_id=n.node_id,
                            target_node_id=target_id,
                            relation_type="references",
                            properties={"rule": "attribute", "key": "regulation_ref" if n.properties.get("regulation_ref") else "references"},
                        ))
                        edge_counter += 1
            else:
                logger.warning("kg_relation_target_missing", relation="references",
                               target=ref_name, source_node_id=n.node_id)

    # Edge 7: has_milestone (project_metadata -> milestone)
    for n in nodes:
        if n.entity_type != "project_metadata":
            continue
        ms_val = n.properties.get("milestones")
        if not ms_val:
            continue
        ms_names = [ms_val] if isinstance(ms_val, str) else ms_val
        for ms_name in ms_names:
            ms_str = str(ms_name).lower().strip()
            if ms_str in label_to_nodes:
                for target_id in label_to_nodes[ms_str]:
                    target = nodes_by_id.get(target_id)
                    if target and target.entity_type == "milestone":
                        edges.append(KGEdge(
                            edge_id=f"e{edge_counter:04d}",
                            source_node_id=n.node_id,
                            target_node_id=target_id,
                            relation_type="has_milestone",
                            properties={"rule": "attribute", "key": "milestones"},
                        ))
                        edge_counter += 1
            else:
                logger.warning("kg_relation_target_missing", relation="has_milestone",
                               target=ms_name, source_node_id=n.node_id)

    # Edge 8: produces (process_step -> deliverable)
    for n in nodes:
        if n.entity_type != "process_step":
            continue
        output_val = n.properties.get("produces") or n.properties.get("output") or n.properties.get("deliverable")
        if not output_val:
            continue
        output_names = [output_val] if isinstance(output_val, str) else output_val
        for out_name in output_names:
            out_str = str(out_name).lower().strip()
            if out_str in label_to_nodes:
                for target_id in label_to_nodes[out_str]:
                    target = nodes_by_id.get(target_id)
                    if target and target.entity_type == "deliverable":
                        edges.append(KGEdge(
                            edge_id=f"e{edge_counter:04d}",
                            source_node_id=n.node_id,
                            target_node_id=target_id,
                            relation_type="produces",
                            properties={"rule": "attribute", "key": "produces" if n.properties.get("produces") else "output" if n.properties.get("output") else "deliverable"},
                        ))
                        edge_counter += 1
            else:
                logger.warning("kg_relation_target_missing", relation="produces",
                               target=out_name, source_node_id=n.node_id)

    # Edge 9: mitigates (risk_item -> process_step)
    for n in nodes:
        if n.entity_type != "risk_item":
            continue
        mitigation_val = n.properties.get("mitigation") or n.properties.get("mitigation_measure")
        if not mitigation_val:
            continue
        mitigation_text = str(mitigation_val).lower()
        matched = False
        for ps_id in type_to_nodes.get("process_step", []):
            ps_node = nodes_by_id.get(ps_id)
            if ps_node and ps_node.label.lower() in mitigation_text:
                edges.append(KGEdge(
                    edge_id=f"e{edge_counter:04d}",
                    source_node_id=n.node_id,
                    target_node_id=ps_id,
                    relation_type="mitigates",
                    properties={"rule": "attribute_substring", "key": "mitigation" if n.properties.get("mitigation") else "mitigation_measure"},
                ))
                edge_counter += 1
                matched = True
        if not matched:
            logger.warning("kg_relation_target_missing", relation="mitigates",
                           target=mitigation_val, source_node_id=n.node_id)

    # Edge 10: has_metric (project_metadata / milestone -> metric)
    for n in nodes:
        if n.entity_type not in ("project_metadata", "milestone"):
            continue
        metric_val = n.properties.get("metrics") or n.properties.get("metric")
        if not metric_val:
            continue
        metric_names = [metric_val] if isinstance(metric_val, str) else metric_val
        for m_name in metric_names:
            m_str = str(m_name).lower().strip()
            if m_str in label_to_nodes:
                for target_id in label_to_nodes[m_str]:
                    target = nodes_by_id.get(target_id)
                    if target and target.entity_type == "metric":
                        edges.append(KGEdge(
                            edge_id=f"e{edge_counter:04d}",
                            source_node_id=n.node_id,
                            target_node_id=target_id,
                            relation_type="has_metric",
                            properties={"rule": "attribute", "key": "metrics" if n.properties.get("metrics") else "metric"},
                        ))
                        edge_counter += 1
            else:
                logger.warning("kg_relation_target_missing", relation="has_metric",
                               target=m_name, source_node_id=n.node_id)

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

    # Inject schema version into metadata
    metadata["schema_version"] = "1.1"

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

    # Serialize edges with missing-key validation
    serialized_edges = []
    for e in edges:
        edge_dict = {}
        for key in ("edge_id", "source_node_id", "target_node_id", "relation_type", "properties"):
            val = getattr(e, key, None)
            if val is None:
                logger.warning("kg_edge_key_missing", key=key, edge=e)
            edge_dict[key] = val
        serialized_edges.append(edge_dict)

    edges_data = {
        "metadata": {"schema_version": "1.1"},
        "edge_count": len(edges),
        "edges": serialized_edges,
    }

    with open(nodes_path, "w", encoding="utf-8") as f:
        json.dump(nodes_data, f, ensure_ascii=False, indent=2)
    with open(edges_path, "w", encoding="utf-8") as f:
        json.dump(edges_data, f, ensure_ascii=False, indent=2)

    # §5.1: Record lineage for each entity
    doc_id = metadata.get("document_id", "")
    if doc_id:
        try:
            from services.lineage_store import get_lineage_store
            store = get_lineage_store()
            for n in nodes:
                store.record_entity(
                    entity_id=n.node_id,
                    entity_type=n.entity_type,
                    label=n.label,
                    doc_id=doc_id,
                    page_idx=n.page_idx,
                    bbox_norm=n.bbox_norm,
                )
        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass

    return nodes_path, edges_path


def print_kg_summary(nodes: list[KGNode], edges: list[KGEdge]):
    """记录 KG 汇总。函数名与签名保持向后兼容（pipeline.py 仍以该名 import）。

    历史名带 print_ 前缀，但输出走 structlog —— 库路径（worker.py）不应污染 stdout。
    """
    logger.info(
        "kg_summary",
        nodes=len(nodes),
        edges=len(edges),
        entity_types=dict(Counter(n.entity_type for n in nodes)),
        relation_types=dict(Counter(e.relation_type for e in edges)),
        grounded=sum(1 for n in nodes if getattr(n, "grounding_status", None) == "grounded"),
    )
