"""Graph data endpoint — returns aggregated KG for all indexed docs."""

import json, os
from collections import defaultdict
from fastapi import APIRouter, HTTPException

router = APIRouter()
BASE = os.path.dirname(os.path.dirname(__file__))
KG_DIR = os.path.join(BASE, "output", "kg")

TYPE_COLORS = {
    "paper_metadata": "#3b82f6", "section_header": "#22c55e", "model_component": "#a855f7",
    "metric": "#eab308", "dataset": "#f97316", "method": "#ec4899",
    "definition": "#8b5cf6", "equation": "#14b8a6", "reference": "#94a3b8", "claim": "#ef4444",
    "task": "#06b6d4", "table": "#84cc16", "figure": "#f43f5e", "equation_parameter": "#8b5cf6",
}

DOC_COLORS = ["#3b82f6", "#f97316", "#22c55e", "#a855f7", "#ef4444", "#eab308", "#14b8a6", "#ec4899"]


@router.get("/graph/{document_id}")
async def get_graph(document_id: str = "all"):
    """Return aggregated graph nodes + edges for vis.js.

    If document_id='all', aggregate all indexed docs.
    Otherwise, return single document's KG.
    """
    from routes import get_docs_snapshot

    indexed_docs = [d for d in get_docs_snapshot() if d.get("status") == "indexed"]

    if document_id != "all" and document_id != "default":
        # Single document
        indexed_docs = [d for d in indexed_docs if d["document_id"] == document_id]
        if not indexed_docs:
            # Try without doc_ prefix
            clean = document_id.replace("doc_", "", 1)
            indexed_docs = [d for d in get_docs_snapshot() if d["document_id"] in (document_id, f"doc_{clean}", clean)]
        if not indexed_docs:
            raise HTTPException(404, detail=f"Document {document_id} not found or not indexed")

    if not indexed_docs:
        # Fallback to default KG
        default_n = os.path.join(KG_DIR, "nodes.json")
        default_e = os.path.join(KG_DIR, "edges.json")
        if not os.path.exists(default_n):
            raise HTTPException(404, detail="No KG data. Index a document first.")
        indexed_docs = [{
            "document_id": "default", "filename": "default",
            "kg_nodes": 0, "kg_edges": 0,
        }]
        # Override paths
        for d in indexed_docs:
            d["_n_path"] = default_n
            d["_e_path"] = default_e
    else:
        for d in indexed_docs:
            doc_id = d["document_id"]
            # Try multiple path patterns: doc_id as-is, without "doc_" prefix
            candidates = [doc_id]
            if doc_id.startswith("doc_"):
                candidates.append(doc_id[4:])  # Remove "doc_" prefix

            found = False
            for candidate in candidates:
                kg_path = os.path.join(KG_DIR, candidate)
                n = os.path.join(kg_path, "nodes.json")
                e = os.path.join(kg_path, "edges.json")
                if os.path.exists(n):
                    d["_n_path"] = n
                    d["_e_path"] = e
                    found = True
                    break

            if not found:
                # Fallback to default
                d["_n_path"] = os.path.join(KG_DIR, "nodes.json")
                d["_e_path"] = os.path.join(KG_DIR, "edges.json")

    # Aggregate
    all_vis_nodes = []
    all_vis_edges = []
    type_counts = defaultdict(int)
    grounded_count = 0
    edge_id_counter = 0

    for di, doc in enumerate(indexed_docs):
        doc_color = DOC_COLORS[di % len(DOC_COLORS)]
        doc_filename = doc.get("filename", "unknown")[:30]

        if not os.path.exists(doc["_n_path"]):
            continue

        with open(doc["_n_path"], encoding="utf-8") as f:
            nd = json.load(f)
        with open(doc["_e_path"], encoding="utf-8") as f:
            ed = json.load(f)

        # Prefix node IDs to avoid collisions across docs
        prefix = f"d{di}_"
        node_id_map = {}

        for n in nd.get("nodes", []):
            old_id = n["node_id"]
            new_id = prefix + old_id
            node_id_map[old_id] = new_id

            color = TYPE_COLORS.get(n["entity_type"], "#64748b")
            grounded = n.get("grounding_status") == "grounded"

            all_vis_nodes.append({
                "id": new_id,
                "label": n["label"][:30] if n.get("label") else "",
                "entity_type": n["entity_type"],
                "color": color,
                "size": 12 if grounded else 7,
                "borderWidth": 2 if grounded else 1,
                "borderColor": "#ffffff" if grounded else "#ef4444",
                "grounded": grounded,
                "page_idx": n.get("page_idx"),
                "bbox_norm": n.get("bbox_norm"),
                "properties": n.get("properties", {}),
                "source_doc": doc_filename,
                "source_doc_color": doc_color,
            })
            type_counts[n["entity_type"]] += 1
            if grounded: grounded_count += 1

        for e in ed.get("edges", []):
            edge_id_counter += 1
            from_id = node_id_map.get(e.get("source_node_id", e.get("from", "")))
            to_id = node_id_map.get(e.get("target_node_id", e.get("to", "")))
            if from_id and to_id:
                all_vis_edges.append({
                    "id": f"e{edge_id_counter}",
                    "from": from_id,
                    "to": to_id,
                    "relation": e.get("relation_type", e.get("relation", "connected")),
                    "color": "rgba(148,163,184,0.12)",
                    "width": 0.5,
                })

    return {
        "nodes": all_vis_nodes,
        "edges": all_vis_edges,
        "documents": [{"id": d["document_id"], "filename": d["filename"]} for d in indexed_docs],
        "stats": {
            "total_nodes": len(all_vis_nodes),
            "total_edges": len(all_vis_edges),
            "grounded_nodes": grounded_count,
            "entity_types": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
        },
    }
