"""Graph data endpoint — returns aggregated KG for all indexed docs."""

import os
from collections import defaultdict
from fastapi import APIRouter, Request

from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()
BASE = os.path.dirname(os.path.dirname(__file__))
KG_DIR = os.path.join(BASE, "output", "kg")

TYPE_COLORS = {
    # Enterprise entity types (aligned with blueprint §2.4.3)
    "project_metadata": "#3b82f6", "person_role": "#22c55e", "process_step": "#a855f7",
    "metric": "#eab308", "milestone": "#f97316", "deliverable": "#ec4899",
    "risk_item": "#ef4444", "regulation_ref": "#8b5cf6", "department": "#14b8a6",
    "timeline_event": "#06b6d4",
    # Legacy academic types (kept for backward compatibility)
    "paper_metadata": "#3b82f6", "section_header": "#22c55e", "model_component": "#a855f7",
    "dataset": "#f97316", "method": "#ec4899",
    "definition": "#8b5cf6", "equation": "#14b8a6", "reference": "#94a3b8", "claim": "#ef4444",
    "task": "#06b6d4", "table": "#84cc16", "figure": "#f43f5e", "equation_parameter": "#8b5cf6",
}

DOC_COLORS = ["#3b82f6", "#f97316", "#22c55e", "#a855f7", "#ef4444", "#eab308", "#14b8a6", "#ec4899"]


@router.get("/graph/{document_id}")
async def get_graph(document_id: str, request: Request):
    from pathlib import Path
    from services.resource_access import authorized_documents
    from services.document_snapshot import authorized_graph
    docs = authorized_documents(request, None if document_id in {"all", "default"} else document_id)
    graph = authorized_graph(docs, Path(KG_DIR))
    nodes = []
    counts = defaultdict(int)
    grounded = 0
    for nid, data in graph.nodes(data=True):
        entity_type = data.get("entity_type", "unknown")
        valid = data.get("grounding_status") == "grounded"
        counts[entity_type] += 1
        grounded += int(valid)
        nodes.append({"id": nid, "label": data.get("label", "")[:30],
                      "entity_type": entity_type, "color": TYPE_COLORS.get(entity_type, "#64748b"),
                      "size": 12 if valid else 7, "borderWidth": 2 if valid else 1,
                      "borderColor": "#ffffff" if valid else "#ef4444", "grounded": valid,
                      "page_idx": data.get("page_idx"), "bbox_norm": data.get("bbox_norm"),
                      "properties": data.get("properties", {}), "source_doc": data["source_file"],
                      "document_id": data["document_id"], "document_version": data["document_version"],
                      "source_doc_color": DOC_COLORS[0]})
    edges = [{"id": f"e{i}", "from": source, "to": target,
              "relation": data.get("relation_type", data.get("relation", "connected")),
              "color": "rgba(148,163,184,0.12)", "width": 0.5}
             for i, (source, target, data) in enumerate(graph.edges(data=True))]
    return {"nodes": nodes, "edges": edges,
            "documents": [{"id": doc["document_id"], "filename": doc["filename"]} for doc in docs],
            "stats": {"total_nodes": len(nodes), "total_edges": len(edges),
                      "grounded_nodes": grounded, "entity_types": dict(sorted(counts.items()))}}
