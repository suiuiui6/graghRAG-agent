"""Request-owned graphs loaded only from authorized, registered documents."""
import json
import re
from pathlib import Path

import networkx as nx
from fastapi import HTTPException


def contained_asset(value: str, root: Path) -> Path:
    path = Path(value).absolute()
    root = root.resolve()
    def linked(candidate: Path) -> bool:
        return candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)()
    if linked(path) or any(linked(parent) for parent in path.parents if parent != root):
        raise HTTPException(409, "Linked document assets are not supported")
    resolved = path.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise HTTPException(409, "Document asset is outside its storage root")
    return resolved


def graph_directory(doc: dict, root: Path) -> Path:
    doc_id = doc["document_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", doc_id):
        raise HTTPException(409, "Invalid stored document identifier")
    if doc.get("kg_path"):
        return contained_asset(doc["kg_path"], root)
    # Both historical storage conventions are document-specific, never global.
    exact = contained_asset(str(root / doc_id), root)
    alternate = contained_asset(str(root / f"doc_{doc_id}"), root)
    return exact if exact.exists() else alternate


def document_graph(doc: dict, root: Path) -> nx.Graph:
    directory = graph_directory(doc, root)
    version = 0
    meta_path = contained_asset(str(directory / "versions.json"), root)
    if meta_path.exists():
        version = int(json.loads(meta_path.read_text(encoding="utf-8")).get("active_version", 0))
        if version < 0:
            raise HTTPException(409, "Invalid active graph version")
    if version:
        directory = contained_asset(str(directory / f"v{version}"), root)
    nodes_path = contained_asset(str(directory / "nodes.json"), root)
    edges_path = contained_asset(str(directory / "edges.json"), root)
    graph = nx.Graph()
    if not nodes_path.exists():
        return graph
    raw = json.loads(nodes_path.read_text(encoding="utf-8"))
    nodes = raw.get("nodes", []) if isinstance(raw, dict) else raw
    raw_edges = json.loads(edges_path.read_text(encoding="utf-8")) if edges_path.exists() else []
    edges = raw_edges.get("edges", []) if isinstance(raw_edges, dict) else raw_edges
    prefix = doc["document_id"] + "__"
    for node in nodes:
        data = dict(node)
        data.update(document_id=doc["document_id"], document_version=version,
                    source_file=doc.get("filename", ""))
        graph.add_node(prefix + node["node_id"], **data)
    for edge in edges:
        source = prefix + edge.get("source_node_id", edge.get("from", ""))
        target = prefix + edge.get("target_node_id", edge.get("to", ""))
        if source in graph and target in graph:
            graph.add_edge(source, target, **edge)
    return graph


def authorized_graph(docs: list[dict], root: Path) -> nx.Graph:
    merged = nx.Graph()
    for doc in docs:
        merged = nx.compose(merged, document_graph(doc, root))
    return merged
