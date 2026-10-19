"""
KG version management — §3.4 of enterprise-evolution-blueprint.

Wraps NetworkX graph loading with versioned per-document storage:
  output/kg/doc_{id}/v{1,2,3,...}/nodes.json + edges.json
  output/kg/doc_{id}/versions.json

Repeated ingest → auto increment version. Version switching → hot-reload graph.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

import networkx as nx
from filelock import FileLock
from logging_config import get_logger

logger = get_logger(__name__)

KG_BASE_DIR = Path("output/kg")


def _tokenize_kg_lookup_text(text: str) -> list[str]:
    """Build lenient lookup tokens for mixed Chinese/English KG search."""
    tokens: set[str] = set()
    normalized = (text or "").strip().lower()
    if normalized:
        tokens.add(normalized)

    for word in re.findall(r"[a-zA-Z0-9]+", normalized):
        if len(word) >= 2:
            tokens.add(word)

    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text or "")
    for i, char in enumerate(chinese_chars):
        tokens.add(char)
        if i + 1 < len(chinese_chars):
            tokens.add(char + chinese_chars[i + 1])
        if i + 2 < len(chinese_chars):
            tokens.add(char + chinese_chars[i + 1] + chinese_chars[i + 2])
        if i + 3 < len(chinese_chars):
            tokens.add(char + chinese_chars[i + 1] + chinese_chars[i + 2] + chinese_chars[i + 3])

    return [token for token in tokens if token]


def build_kg_lookup_indexes(graph: nx.Graph) -> dict[str, Any]:
    """Build reusable lookup indexes for candidate-first KG recall."""
    entity_type_to_nodes: dict[str, list[str]] = {}
    token_to_nodes: dict[str, list[str]] = {}
    label_token_to_nodes: dict[str, list[str]] = {}
    node_text: dict[str, str] = {}
    label_text: dict[str, str] = {}
    all_nodes: list[str] = []
    neighbor_preview: dict[str, list[dict[str, Any]]] = {}

    for node_id, data in graph.nodes(data=True):
        all_nodes.append(node_id)
        entity_type = str(data.get("entity_type", "") or "")
        entity_type_to_nodes.setdefault(entity_type, []).append(node_id)

        properties = data.get("properties", {}) or {}
        label = str(data.get("label", "") or "")
        searchable_parts = [label]
        searchable_parts.extend(str(value) for value in properties.values())
        searchable_text = " ".join(part for part in searchable_parts if part).strip()
        node_text[node_id] = searchable_text.lower()
        label_text[node_id] = label.lower()

        for token in _tokenize_kg_lookup_text(searchable_text):
            bucket = token_to_nodes.setdefault(token, [])
            if node_id not in bucket:
                bucket.append(node_id)
        for token in _tokenize_kg_lookup_text(label):
            bucket = label_token_to_nodes.setdefault(token, [])
            if node_id not in bucket:
                bucket.append(node_id)

        preview = []
        for neighbor_id in graph.neighbors(node_id):
            neighbor_data = graph.nodes[neighbor_id]
            preview.append({
                "node_id": neighbor_id,
                "entity_type": neighbor_data.get("entity_type", ""),
                "label": neighbor_data.get("label", ""),
                "relation": graph.get_edge_data(node_id, neighbor_id, {}).get("relation", "connected"),
            })
            if len(preview) >= 10:
                break
        neighbor_preview[node_id] = preview

    return {
        "entity_type_to_nodes": entity_type_to_nodes,
        "token_to_nodes": token_to_nodes,
        "label_token_to_nodes": label_token_to_nodes,
        "node_text": node_text,
        "label_text": label_text,
        "all_nodes": all_nodes,
        "neighbor_preview": neighbor_preview,
    }


def get_kg_lookup_indexes(graph: nx.Graph) -> dict[str, Any]:
    """Return cached KG lookup indexes for the provided graph."""
    cached = graph.graph.get("_kg_lookup_indexes")
    if cached is None:
        cached = build_kg_lookup_indexes(graph)
        graph.graph["_kg_lookup_indexes"] = cached
    return cached


def get_community_index(graph: nx.Graph) -> dict[str, Any]:
    """Return cached community summary index for the provided graph."""
    cached = graph.graph.get("_community_index")
    if cached is None:
        from community_index import build_community_index

        cached = build_community_index(graph)
        graph.graph["_community_index"] = cached
    return cached


def lookup_kg_nodes(
    graph: nx.Graph,
    *,
    entity_types: list[str] | None = None,
    keyword: str = "",
    limit: int = 10,
    indexes: dict[str, Any] | None = None,
) -> list[tuple[str, dict]]:
    """Resolve KG candidates through lookup indexes instead of full-graph scans."""
    if limit <= 0:
        return []

    resolved_indexes = indexes or get_kg_lookup_indexes(graph)
    entity_map = resolved_indexes.get("entity_type_to_nodes", {})
    token_map = resolved_indexes.get("token_to_nodes", {})
    node_text = resolved_indexes.get("node_text", {})
    all_nodes = resolved_indexes.get("all_nodes", [])

    ordered_type_nodes: list[str] = []
    if entity_types:
        for entity_type in entity_types:
            for node_id in entity_map.get(entity_type, []):
                if node_id not in ordered_type_nodes:
                    ordered_type_nodes.append(node_id)

    normalized_keyword = (keyword or "").strip().lower()
    keyword_candidate_ids: list[str] = []
    if normalized_keyword:
        token_hits: dict[str, int] = {}
        token_order: dict[str, int] = {}
        query_tokens = _tokenize_kg_lookup_text(keyword)

        for token in query_tokens:
            for node_id in token_map.get(token, []):
                token_hits[node_id] = token_hits.get(node_id, 0) + 1
                if node_id not in token_order:
                    token_order[node_id] = len(token_order)

        keyword_candidate_ids = sorted(
            token_hits,
            key=lambda node_id: (
                0 if normalized_keyword in node_text.get(node_id, "") else 1,
                -token_hits[node_id],
                token_order[node_id],
            ),
        )

        if not keyword_candidate_ids:
            substring_matches = [
                node_id
                for node_id in all_nodes
                if normalized_keyword in node_text.get(node_id, "")
            ]
            keyword_candidate_ids = substring_matches

    if entity_types and normalized_keyword:
        candidate_ids = [
            node_id for node_id in ordered_type_nodes if node_id in keyword_candidate_ids
        ]
    elif entity_types:
        candidate_ids = ordered_type_nodes
    elif normalized_keyword:
        candidate_ids = keyword_candidate_ids
    else:
        candidate_ids = list(all_nodes)

    node_store = getattr(graph, "_node", {})
    return [
        (node_id, node_store[node_id])
        for node_id in candidate_ids[:limit]
        if node_id in node_store
    ]


def bounded_neighbor_lookup(
    graph: nx.Graph,
    source_id: str,
    *,
    k_hops: int = 1,
    fanout: int = 10,
    indexes: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return a bounded neighbor preview for legacy tools without full ego expansion."""
    if source_id not in graph or fanout <= 0:
        return []

    resolved_indexes = indexes or get_kg_lookup_indexes(graph)
    if k_hops <= 1:
        return list(resolved_indexes.get("neighbor_preview", {}).get(source_id, []))[:fanout]

    seen = {source_id}
    frontier = [source_id]
    neighbors: list[dict[str, Any]] = []

    for _ in range(max(1, k_hops)):
        next_frontier: list[str] = []
        for node_id in frontier:
            for neighbor_id in graph.neighbors(node_id):
                if neighbor_id in seen:
                    continue
                seen.add(neighbor_id)
                neighbor_data = graph.nodes[neighbor_id]
                neighbors.append({
                    "node_id": neighbor_id,
                    "entity_type": neighbor_data.get("entity_type", ""),
                    "label": neighbor_data.get("label", ""),
                    "relation": graph.get_edge_data(node_id, neighbor_id, {}).get("relation", "connected"),
                })
                next_frontier.append(neighbor_id)
                if len(neighbors) >= fanout:
                    return neighbors
        frontier = next_frontier
        if not frontier:
            break

    return neighbors


def lookup_kg_label_nodes(
    graph: nx.Graph,
    *,
    keyword: str,
    limit: int = 1,
    indexes: dict[str, Any] | None = None,
) -> list[tuple[str, dict]]:
    """Resolve KG candidates against label-only indexes for legacy source selection."""
    if limit <= 0 or not keyword.strip():
        return []

    resolved_indexes = indexes or get_kg_lookup_indexes(graph)
    label_token_map = resolved_indexes.get("label_token_to_nodes", {})
    label_text = resolved_indexes.get("label_text", {})
    all_nodes = resolved_indexes.get("all_nodes", [])
    normalized_keyword = keyword.strip().lower()

    token_hits: dict[str, int] = {}
    token_order: dict[str, int] = {}
    for token in _tokenize_kg_lookup_text(keyword):
        for node_id in label_token_map.get(token, []):
            token_hits[node_id] = token_hits.get(node_id, 0) + 1
            if node_id not in token_order:
                token_order[node_id] = len(token_order)

    candidate_ids = sorted(
        token_hits,
        key=lambda node_id: (
            0 if normalized_keyword in label_text.get(node_id, "") else 1,
            -token_hits[node_id],
            token_order[node_id],
        ),
    )

    if not candidate_ids:
        candidate_ids = [
            node_id for node_id in all_nodes
            if normalized_keyword in label_text.get(node_id, "")
        ]

    node_store = getattr(graph, "_node", {})
    return [
        (node_id, node_store[node_id])
        for node_id in candidate_ids[:limit]
        if node_id in node_store
    ]


class KgVersionManager:
    """Manages versioned KG storage for a single document."""

    def __init__(self, doc_id: str, base_dir: Path | None = None):
        self.doc_id = doc_id
        self.base_dir = base_dir or KG_BASE_DIR
        self.doc_dir = self.base_dir / f"doc_{doc_id}"
        self.versions_file = self.doc_dir / "versions.json"

    # ── read ──────────────────────────────────────────────────────────

    def _read_versions_meta(self) -> dict:
        if not self.versions_file.exists():
            return {"doc_id": self.doc_id, "versions": [], "active_version": 0}
        return json.loads(self.versions_file.read_text(encoding="utf-8"))

    def _write_versions_meta(self, meta: dict) -> None:
        self.doc_dir.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".versions-", suffix=".tmp", dir=self.doc_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(meta, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.versions_file)
        finally:
            Path(name).unlink(missing_ok=True)

    def write_lock(self) -> FileLock:
        """创建、激活及保留清理共享同一进程间锁。"""
        self.doc_dir.mkdir(parents=True, exist_ok=True)
        return FileLock(self.doc_dir / ".versions.lock")

    def _next_version(self, meta: dict) -> int:
        if not isinstance(meta, dict) or not isinstance(meta.get('versions'), list):
            raise ValueError('invalid KG versions metadata')
        highwater = meta.get('next_version', 1)
        if type(highwater) is not int or highwater < 1:
            raise ValueError('next_version must be a positive integer')
        if any(not isinstance(v, dict) or type(v.get('version')) is not int
               or v['version'] < 0 for v in meta['versions']):
            raise ValueError('invalid KG version identifier')
        disk = [int(p.name[1:]) for p in self.doc_dir.iterdir()
                if re.fullmatch(r"v(0|[1-9][0-9]*)", p.name)]
        return max([0, highwater - 1,
                    *[v["version"] for v in meta["versions"]], *disk]) + 1

    def active_version(self) -> int:
        return self._read_versions_meta().get("active_version", 0)

    def list_versions(self) -> list[dict]:
        return self._read_versions_meta().get("versions", [])

    # ── write ─────────────────────────────────────────────────────────

    def create_version(
        self,
        nodes: list[dict],
        edges: list[dict],
        status: str = "active",
    ) -> int:
        """Write a new version. Returns the new version number."""
        with self.write_lock():
            meta = self._read_versions_meta()
            new_v = self._next_version(meta)

            v_dir = self.doc_dir / f"v{new_v}"
            v_dir.mkdir(parents=True, exist_ok=False)

            (v_dir / "nodes.json").write_text(
                json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (v_dir / "edges.json").write_text(
                json.dumps(edges, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            meta["versions"].append({
                "version": new_v,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "nodes": len(nodes),
                "edges": len(edges),
                "status": status,
            })
            meta["active_version"] = new_v
            meta["next_version"] = new_v + 1
            self._write_versions_meta(meta)
        logger.info(
            "kg_version_created",
            doc_id=self.doc_id,
            version=new_v,
            nodes=len(nodes),
            edges=len(edges),
        )
        # Publish event + audit log
        try:
            from services.event_bus import get_event_bus
            get_event_bus().publish("kg.version_created", {
                "doc_id": self.doc_id,
                "version": new_v,
                "nodes": len(nodes),
                "edges": len(edges),
            })
        except Exception:  # noqa: S110, BLE001  # 事件发布为 fire-and-forget，投递失败不阻塞版本创建
            pass
        try:
            from services.audit_logger import get_audit_logger
            get_audit_logger().log("kg.version_created", doc_id=self.doc_id,
                                   version=new_v, nodes=len(nodes), edges=len(edges))
        except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
            pass
        return new_v

    # ── version switching ─────────────────────────────────────────────

    def activate_version(self, version: int) -> bool:
        with self.write_lock():
            meta = self._read_versions_meta()
            if (type(version) is not int or version < 0
                    or not any(v["version"] == version for v in meta["versions"])
                    or not (self.doc_dir / f"v{version}").is_dir()
                or (self.doc_dir / f"v{version}").is_symlink()
                or (self.doc_dir / f"v{version}").is_junction()
                or not (self.doc_dir / f"v{version}").resolve().is_relative_to(self.base_dir.resolve())):
                logger.warning("kg_version_not_found", doc_id=self.doc_id, version=version)
                return False
            meta["active_version"] = version
            self._write_versions_meta(meta)
        logger.info("kg_version_activated", doc_id=self.doc_id, version=version)
        try:
            from services.event_bus import get_event_bus
            get_event_bus().publish("kg.version_switched", {
                "doc_id": self.doc_id, "version": version,
            })
        except Exception:  # noqa: S110, BLE001  # 事件发布为 fire-and-forget，投递失败不阻塞版本切换
            pass
        try:
            from services.audit_logger import get_audit_logger
            get_audit_logger().log("kg.version_switched", doc_id=self.doc_id, version=version)
        except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
            pass
        return True

    def load_graph(self, id_prefix: str = "") -> nx.Graph:
        """Load the active version's KG into a NetworkX graph.

        Falls back to flat format (nodes.json directly under doc_dir) if no
        versioned storage exists — backward compat with pre-Phase-0 data.
        """
        v = self.active_version()

        # Version-aware path
        if v > 0:
            nodes_path = self.doc_dir / f"v{v}" / "nodes.json"
            edges_path = self.doc_dir / f"v{v}" / "edges.json"
        else:
            # Fallback: flat format (legacy)
            nodes_path = self.doc_dir / "nodes.json"
            edges_path = self.doc_dir / "edges.json"

        if not nodes_path.exists():
            logger.warning("kg_nodes_missing", doc_id=self.doc_id, version=v)
            return nx.Graph()

        nodes_data = json.loads(nodes_path.read_text(encoding="utf-8"))
        # Handle both {"nodes": [...]} and bare [...] formats
        if isinstance(nodes_data, dict) and "nodes" in nodes_data:
            node_list = nodes_data["nodes"]
        else:
            node_list = nodes_data if isinstance(nodes_data, list) else []

        edges_data = []
        if edges_path.exists():
            raw_edges = json.loads(edges_path.read_text(encoding="utf-8"))
            if isinstance(raw_edges, dict) and "edges" in raw_edges:
                edges_data = raw_edges["edges"]
            elif isinstance(raw_edges, list):
                edges_data = raw_edges

        G = nx.Graph()
        for node in node_list:
            nid = id_prefix + node.get("node_id", node.get("id", str(len(G.nodes()))))
            G.add_node(nid, **node)

        for edge in edges_data:
            src = edge.get("source_node_id", edge.get("from", ""))
            tgt = edge.get("target_node_id", edge.get("to", ""))
            if src and tgt:
                G.add_edge(id_prefix + src, id_prefix + tgt, **edge)

        logger.info(
            "kg_graph_loaded",
            doc_id=self.doc_id,
            version=v if v > 0 else "flat",
            nodes=G.number_of_nodes(),
            edges=G.number_of_edges(),
        )
        return G


# ── aggregate loader (for server startup) ──────────────────────────────

def load_all_kg_graphs(base_dir: Path | None = None, org_id: str | None = None,
                       project_id: str | None = None) -> nx.Graph:
    """Load and merge KGs from all documents' active versions.

    Handles three formats (newest → oldest):
    1. Versioned: doc_{id}/v{N}/nodes.json + edges.json
    2. Per-document flat: doc_{id}/nodes.json + edges.json
    3. Global legacy flat: output/kg/nodes.json + edges.json
    """
    base = base_dir or KG_BASE_DIR
    if org_id and project_id:
        base = base / org_id / project_id
    if not base.exists():
        return nx.Graph()

    merged = nx.Graph()
    doc_count = 0

    for entry in sorted(base.iterdir()):
        if not entry.is_dir() or not entry.name.startswith("doc_"):
            continue
        doc_id = entry.name[4:]
        mgr = KgVersionManager(doc_id, base_dir=base)
        g = mgr.load_graph(id_prefix=f"d{doc_count}_")
        if g.number_of_nodes() > 0:
            merged = nx.compose(merged, g)
            doc_count += 1

    # Fallback: global legacy flat format
    if doc_count == 0:
        global_nodes = base / "nodes.json"
        global_edges = base / "edges.json"
        if global_nodes.exists():
            nodes_data = json.loads(global_nodes.read_text(encoding="utf-8"))
            if isinstance(nodes_data, dict) and "nodes" in nodes_data:
                node_list = nodes_data["nodes"]
            else:
                node_list = nodes_data if isinstance(nodes_data, list) else []

            edge_list = []
            if global_edges.exists():
                edges_data = json.loads(global_edges.read_text(encoding="utf-8"))
                if isinstance(edges_data, dict) and "edges" in edges_data:
                    edge_list = edges_data["edges"]
                elif isinstance(edges_data, list):
                    edge_list = edges_data

            for node in node_list:
                nid = node.get("node_id", node.get("id", str(len(merged.nodes()))))
                merged.add_node(nid, **node)
            for edge in edge_list:
                src = edge.get("source_node_id", edge.get("from", ""))
                tgt = edge.get("target_node_id", edge.get("to", ""))
                if src and tgt:
                    merged.add_edge(src, tgt, **edge)
            doc_count = 1

    logger.info(
        "kg_all_loaded",
        documents=doc_count,
        total_nodes=merged.number_of_nodes(),
        total_edges=merged.number_of_edges(),
    )
    return merged


def get_tenant_kg_path(org_id: str, project_id: str) -> Path:
    """Return the KG storage path for a specific tenant."""
    return KG_BASE_DIR / org_id / project_id
