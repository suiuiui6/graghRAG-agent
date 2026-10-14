"""KG Service — knowledge graph loading, merging, and filtering operations.

Extracted from routes/query.py per P3 architecture enhancement.
Stateless functions; global reference management remains in query.py.
"""

import json
import os

import networkx as nx


BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)))
KG_DIR = os.path.join(BASE_DIR, "output", "kg")
DEFAULT_NODES_PATH = os.path.join(KG_DIR, "nodes.json")
DEFAULT_EDGES_PATH = os.path.join(KG_DIR, "edges.json")


def load_single_kg(nodes_path: str, edges_path: str, id_prefix: str = "") -> nx.Graph:
    """Load a single KG from nodes.json + edges.json. Optionally prefix node IDs."""
    with open(nodes_path, encoding="utf-8") as f:
        nodes_data = json.load(f)
    with open(edges_path, encoding="utf-8") as f:
        edges_data = json.load(f)

    G = nx.Graph()
    for n in nodes_data["nodes"]:
        nid = id_prefix + n["node_id"]
        G.add_node(nid, entity_type=n["entity_type"], label=n["label"],
                   properties=n.get("properties", {}), page_idx=n.get("page_idx"),
                   bbox_norm=n.get("bbox_norm"), grounding_status=n.get("grounding_status", "ungrounded"),
                   origin_id=n["node_id"])
    for e in edges_data["edges"]:
        G.add_edge(id_prefix + e["source_node_id"],
                   id_prefix + e["target_node_id"],
                   relation=e.get("relation_type", "connected"))
    return G


def load_all_kgs() -> nx.Graph:
    """Scan output/kg/ subdirectories for per-document KGs, merge into one graph.
    Falls back to default KG if no subdirectory KGs found.
    """
    merged = nx.Graph()
    kg_dirs: list[tuple[str, str, str]] = []

    if os.path.isdir(KG_DIR):
        for entry in sorted(os.listdir(KG_DIR)):
            entry_path = os.path.join(KG_DIR, entry)
            if not os.path.isdir(entry_path):
                continue
            n_path = os.path.join(entry_path, "nodes.json")
            e_path = os.path.join(entry_path, "edges.json")
            if os.path.exists(n_path) and os.path.exists(e_path):
                kg_dirs.append((entry, n_path, e_path))

    if kg_dirs:
        for di, (dname, n_path, e_path) in enumerate(kg_dirs):
            prefix = f"d{di}_"
            sub_g = load_single_kg(n_path, e_path, id_prefix=prefix)
            merged = nx.compose(merged, sub_g)
    elif os.path.exists(DEFAULT_NODES_PATH) and os.path.exists(DEFAULT_EDGES_PATH):
        merged = load_single_kg(DEFAULT_NODES_PATH, DEFAULT_EDGES_PATH)

    return merged


def build_kg_from_full(full_g: nx.Graph) -> nx.Graph | None:
    """Filter full graph to only grounded nodes. Returns None if empty."""
    grounded = full_g.subgraph(
        [n for n, d in full_g.nodes(data=True) if d.get("grounding_status") == "grounded"]
    ).copy()
    if grounded.number_of_nodes() == 0:
        return None
    return grounded


def count_kg_nodes() -> int:
    """Count total nodes across all KGs (subdirectories, fallback to default)."""
    total = 0
    has_subdirs = False
    if os.path.isdir(KG_DIR):
        for entry in os.listdir(KG_DIR):
            entry_path = os.path.join(KG_DIR, entry)
            n_path = os.path.join(entry_path, "nodes.json")
            if os.path.isdir(entry_path) and os.path.exists(n_path):
                has_subdirs = True
                try:
                    with open(n_path, encoding="utf-8") as f:
                        total += len(json.load(f).get("nodes", []))
                except Exception:  # noqa: S110, BLE001  # 统计聚合降级：单维读取失败不应让整个接口失败
                    pass
        if not has_subdirs:
            default_n = os.path.join(KG_DIR, "nodes.json")
            if os.path.exists(default_n):
                try:
                    with open(default_n, encoding="utf-8") as f:
                        total += len(json.load(f).get("nodes", []))
                except Exception:  # noqa: S110, BLE001  # 统计聚合降级：单维读取失败不应让整个接口失败
                    pass
    return total
