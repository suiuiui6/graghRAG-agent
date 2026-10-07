"""
Lineage Store — §5.1 of enterprise-evolution-blueprint.

Records full data lineage from document ingestion through retrieval to answer
generation and feedback. Each entity gets its own lineage file under
output/lineage/.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from models import LineageNode, LineageNodeType, LineageTrace
from logging_config import get_logger

logger = get_logger(__name__)

LINEAGE_DIR = Path("output/lineage")


class LineageStore:
    """Records and queries data lineage across the full lifecycle."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or LINEAGE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, entity_id: str) -> Path:
        return self.base_dir / f"{entity_id}.json"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── write ──────────────────────────────────────────────────────────

    def record_entity(self, entity_id: str, entity_type: str, label: str,
                      doc_id: str, page_idx: int | None = None,
                      bbox_norm: list[float] | None = None,
                      kg_version: int | None = None) -> LineageNode:
        """Record entity extraction from a document."""
        node = LineageNode(
            node_id=f"entity:{entity_id}",
            node_type=LineageNodeType.ENTITY,
            label=label,
            metadata={
                "entity_type": entity_type,
                "doc_id": doc_id,
                "page_idx": page_idx,
                "bbox_norm": bbox_norm,
            },
            parent_ids=[f"document:{doc_id}"],
            kg_version=kg_version,
            timestamp=self._now(),
        )
        self._append(entity_id, node)
        logger.info("lineage_entity_recorded", entity_id=entity_id, doc_id=doc_id)
        return node

    def record_retrieval(self, query_id: str, query_text: str,
                         paths_hit: list[str], candidate_count: int,
                         domain_terms: list[str] | None = None,
                         session_id: str | None = None) -> LineageNode:
        """Record retrieval step for a query."""
        node = LineageNode(
            node_id=f"retrieval:{query_id}",
            node_type=LineageNodeType.RETRIEVAL,
            label=f"Retrieval: {query_text[:60]}",
            metadata={
                "query_text": query_text,
                "paths_hit": paths_hit,
                "candidate_count": candidate_count,
            },
            session_id=session_id,
            domain_terms=domain_terms,
            timestamp=self._now(),
        )
        rec = self._load(query_id) or {"nodes": [], "entity_refs": []}
        rec["nodes"].append(node)
        self._save(query_id, rec)
        return node

    def record_generation(self, query_id: str, answer_text: str,
                          citations: list[str], entity_refs: list[str],
                          session_id: str | None = None) -> LineageNode:
        """Record answer generation with citations."""
        node = LineageNode(
            node_id=f"generation:{query_id}",
            node_type=LineageNodeType.GENERATION,
            label=f"Answer: {answer_text[:80]}",
            metadata={
                "answer_preview": answer_text[:200],
                "citations": citations,
            },
            parent_ids=[f"retrieval:{query_id}"],
            session_id=session_id,
            timestamp=self._now(),
        )
        rec = self._load(query_id) or {"nodes": [], "entity_refs": []}
        rec["nodes"].append(node)
        current_refs = set(rec.get("entity_refs", []))
        rec["entity_refs"] = list(current_refs | set(entity_refs))
        self._save(query_id, rec)

        # Link back to entity lineage files
        for eid in entity_refs:
            entity_rec = self._load(eid) or {"nodes": [], "entity_refs": []}
            eref_node = LineageNode(
                node_id=f"answer:{query_id}",
                node_type=LineageNodeType.ANSWER,
                label="Answer reference",
                parent_ids=[f"generation:{query_id}"],
                session_id=session_id,
                timestamp=self._now(),
            )
            entity_rec["nodes"].append(eref_node)
            self._save(eid, entity_rec)

        return node

    def record_domain_expand(self, query_id: str, original: str,
                             expanded: str, terms: list[str]) -> LineageNode:
        """Record domain dictionary query expansion."""
        node = LineageNode(
            node_id=f"domain_expand:{query_id}",
            node_type=LineageNodeType.DOMAIN_EXPAND,
            label=f"Domain expand: {', '.join(terms)}",
            metadata={"original": original, "expanded": expanded, "terms": terms},
            timestamp=self._now(),
        )
        rec = self._load(query_id) or {"nodes": [], "entity_refs": []}
        rec["nodes"].append(node)
        self._save(query_id, rec)
        return node

    def record_feedback(self, feedback_id: str, query_id: str,
                        rating: str, status: str = "open") -> LineageNode:
        """Link feedback to its query lineage."""
        node = LineageNode(
            node_id=f"feedback:{feedback_id}",
            node_type=LineageNodeType.FEEDBACK,
            label=f"Feedback: {rating}",
            metadata={"rating": rating, "status": status},
            parent_ids=[f"generation:{query_id}"],
            feedback_id=feedback_id,
            timestamp=self._now(),
        )
        rec = self._load(query_id) or {"nodes": [], "entity_refs": []}
        rec["nodes"].append(node)
        self._save(query_id, rec)
        return node

    def record_kg_version(self, entity_id: str, doc_id: str,
                          version: int, status: str) -> LineageNode:
        """Record KG version change for an entity."""
        node = LineageNode(
            node_id=f"kg_version:{entity_id}:v{version}",
            node_type=LineageNodeType.KG_VERSION,
            label=f"KG v{version} ({status})",
            metadata={"doc_id": doc_id, "version": version, "status": status},
            kg_version=version,
            timestamp=self._now(),
        )
        self._append(entity_id, node)
        return node

    # ── query ───────────────────────────────────────────────────────────

    def trace_entity(self, entity_id: str) -> LineageTrace | None:
        """Get full lineage for an entity (document → entity → answers → feedback)."""
        rec = self._load(entity_id)
        if not rec or not rec.get("nodes"):
            return None
        nodes = [n if isinstance(n, LineageNode) else LineageNode(**n)
                 for n in rec["nodes"]]
        return LineageTrace(entity_id=entity_id, trace=nodes, direction="forward")

    def trace_answer(self, query_id: str) -> LineageTrace | None:
        """Get full lineage for a query/answer (retrieval → generation → entity → doc)."""
        rec = self._load(query_id)
        if not rec or not rec.get("nodes"):
            return None
        nodes = [n if isinstance(n, LineageNode) else LineageNode(**n)
                 for n in rec["nodes"]]
        return LineageTrace(entity_id=query_id, trace=nodes, direction="backward")

    def trace_document(self, doc_id: str) -> dict:
        """List all entities derived from a document."""
        entities = []
        for f in sorted(self.base_dir.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
                for n in rec.get("nodes", []):
                    meta = n.get("metadata", {})
                    if meta.get("doc_id") == doc_id and n.get("node_type") == "entity":
                        entities.append(n)
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return {"doc_id": doc_id, "entities": entities, "total": len(entities)}

    def trace_feedback(self, feedback_id: str) -> LineageTrace | None:
        """Trace from feedback back to entity → document."""
        for f in sorted(self.base_dir.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
                for n in rec.get("nodes", []):
                    if (n.get("node_type") == "feedback" and
                            n.get("feedback_id") == feedback_id):
                        nodes = [LineageNode(**x) if isinstance(x, dict) else x
                                for x in rec["nodes"]]
                        return LineageTrace(entity_id=f.stem, trace=nodes, direction="backward")
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return None

    def trace_conversation(self, session_id: str) -> dict:
        """Get all lineage nodes for a conversation session."""
        nodes: list[LineageNode] = []
        for f in sorted(self.base_dir.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
                for n in rec.get("nodes", []):
                    if n.get("session_id") == session_id:
                        nodes.append(LineageNode(**n) if isinstance(n, dict) else n)
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return {"session_id": session_id, "nodes": [n.model_dump() for n in nodes],
                "total": len(nodes)}

    def trace_term(self, term: str) -> dict:
        """Find queries where a domain term was expanded."""
        matches = []
        for f in sorted(self.base_dir.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
                for n in rec.get("nodes", []):
                    if n.get("node_type") == "domain_expand":
                        terms = n.get("metadata", {}).get("terms", [])
                        if term in terms:
                            matches.append(n)
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return {"term": term, "queries": matches, "total": len(matches)}

    # ── internal ────────────────────────────────────────────────────────

    def _load(self, key: str) -> dict | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data.setdefault("entity_refs", [])
            return data
        except Exception:  # noqa: BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
            return None

    def _save(self, key: str, rec: dict) -> None:
        out = dict(rec)
        # Serialize LineageNode objects in nodes list
        if "nodes" in out:
            out["nodes"] = [
                n.model_dump() if isinstance(n, LineageNode) else n
                for n in out["nodes"]
            ]
        self._path(key).write_text(
            json.dumps(out, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")

    def _append(self, entity_id: str, node: LineageNode) -> None:
        rec = self._load(entity_id) or {"nodes": [], "entity_refs": []}
        rec["nodes"].append(node.model_dump())
        self._save(entity_id, rec)

    # ── export ──────────────────────────────────────────────────────────

    def export_dot(self, entity_id: str, max_depth: int = 3) -> str | None:
        """Export entity lineage as Graphviz DOT format."""
        trace = self.trace_entity(entity_id)
        if not trace:
            return None

        lines = ["digraph lineage {", "  rankdir=LR;",
                 '  node [shape=box, style=rounded];']
        seen: set[str] = set()

        def _add(node: LineageNode, depth: int):
            if depth > max_depth or node.node_id in seen:
                return
            seen.add(node.node_id)
            color = {
                "entity": "lightblue", "document": "lightgreen",
                "retrieval": "lightyellow", "generation": "lightsalmon",
                "feedback": "lightcoral", "domain_expand": "lightcyan",
                "kg_version": "lightgray",
            }.get(node.node_type.value if hasattr(node.node_type, 'value')
                  else node.node_type, "white")
            lines.append(
                f'  "{node.node_id}" [label="{node.label[:50]}", '
                f'fillcolor={color}, style=filled];')
            for pid in node.parent_ids:
                lines.append(f'  "{pid}" -> "{node.node_id}";')

        for n in trace.trace:
            _add(n, 0)

        lines.append("}")
        return "\n".join(lines)


# ── singleton ─────────────────────────────────────────────────────────────

_store: LineageStore | None = None


def get_lineage_store() -> LineageStore:
    global _store
    if _store is None:
        _store = LineageStore()
    return _store
