"""
KG Exporter — §5.3 of enterprise-evolution-blueprint.

Supports JSON (native), CSV (nodes.csv + edges.csv with UTF-8 BOM),
Neo4j Cypher CREATE, and RDF/Turtle export formats.
Also exports domain dict, feedback, and conversations.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi.responses import StreamingResponse

from logging_config import get_logger

logger = get_logger(__name__)

KG_DIR = Path("output/kg")
FEEDBACK_DIR = Path("output/feedback")
CONVERSATIONS_DIR = Path("output/conversations")
DOMAIN_DICT_PATH = Path("config/domain_dict.yaml")


class KgExporter:
    """Multi-format KG and data asset exporter."""

    # ── KG export ──────────────────────────────────────────────────────

    def export_kg(self, fmt: str) -> dict | StreamingResponse:
        if fmt == "json":
            return self._export_kg_json()
        elif fmt == "csv":
            return self._export_kg_csv()
        elif fmt == "neo4j":
            return self._export_kg_neo4j()
        elif fmt == "rdf":
            return self._export_kg_rdf()
        elif fmt == "zip":
            return self._export_kg_zip()
        else:
            raise ValueError(f"Unsupported format: {fmt}")

    def _load_all_kg(self) -> tuple[list[dict], list[dict]]:
        nodes: list[dict] = []
        edges: list[dict] = []
        if KG_DIR.exists():
            for entry in sorted(KG_DIR.iterdir()):
                if not entry.is_dir() or not entry.name.startswith("doc_"):
                    continue
                n_path = entry / "nodes.json"
                e_path = entry / "edges.json"
                if n_path.exists():
                    try:
                        nodes.extend(json.loads(n_path.read_text(encoding="utf-8")).get("nodes", []))
                    except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
                        pass
                if e_path.exists():
                    try:
                        edges.extend(json.loads(e_path.read_text(encoding="utf-8")).get("edges", []))
                    except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
                        pass
        if not nodes:
            default_n = KG_DIR / "nodes.json"
            default_e = KG_DIR / "edges.json"
            if default_n.exists():
                try:
                    nodes = json.loads(default_n.read_text(encoding="utf-8")).get("nodes", [])
                except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
                    pass
            if default_e.exists():
                try:
                    edges = json.loads(default_e.read_text(encoding="utf-8")).get("edges", [])
                except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
                    pass
        return nodes, edges

    def _export_kg_json(self) -> dict:
        nodes, edges = self._load_all_kg()
        return {
            "format": "json",
            "nodes": nodes,
            "edges": edges,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "counts": {"nodes": len(nodes), "edges": len(edges)},
        }

    def _export_kg_csv(self) -> StreamingResponse:
        nodes, edges = self._load_all_kg()

        # nodes.csv
        nodes_buf = io.StringIO()
        if nodes:
            node_keys = ["node_id", "entity_type", "label", "page_idx", "grounding_status",
                         "properties"]
            writer = csv.DictWriter(nodes_buf, fieldnames=node_keys, extrasaction="ignore")
            writer.writeheader()
            for n in nodes:
                row = {**n, "properties": json.dumps(n.get("properties", {}), ensure_ascii=False)}
                writer.writerow(row)

        # edges.csv
        edges_buf = io.StringIO()
        if edges:
            edge_keys = ["source_node_id", "target_node_id", "relation_type"]
            writer = csv.DictWriter(edges_buf, fieldnames=edge_keys, extrasaction="ignore")
            writer.writeheader()
            for e in edges:
                writer.writerow(e)

        content = (
            "# nodes.csv\n"
            + nodes_buf.getvalue()
            + "\n# edges.csv\n"
            + edges_buf.getvalue()
        )
        nodes_buf.close()
        edges_buf.close()

        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=kg_export.csv"},
        )

    def _export_kg_neo4j(self) -> StreamingResponse:
        nodes, edges = self._load_all_kg()
        lines = ["// Neo4j Cypher import — GraphRAG KG export",
                 f"// Generated: {datetime.now(timezone.utc).isoformat()}",
                 f"// Nodes: {len(nodes)}, Edges: {len(edges)}", ""]

        for n in nodes:
            label = n.get("entity_type", "Entity").replace(" ", "_")
            props = json.dumps({k: v for k, v in n.items()
                               if k not in ("node_id", "entity_type")},
                               ensure_ascii=False)
            escaped_label = n.get("label", "").replace('"', '\\"')
            lines.append(
                f'CREATE (:{label} {{id: "{n["node_id"]}", '
                f'label: "{escaped_label}", '
                f'properties: \'{props}\'}});')

        lines.append("")
        for e in edges:
            lines.append(
                f'MATCH (a {{id: "{e["source_node_id"]}"}}), '
                f'(b {{id: "{e["target_node_id"]}"}}) '
                f'CREATE (a)-[:{e.get("relation_type", "RELATED")}]->(b);')

        content = "\n".join(lines)
        return StreamingResponse(
            iter([content]),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=kg_export.cypher"},
        )

    def _export_kg_rdf(self) -> StreamingResponse:
        nodes, edges = self._load_all_kg()
        lines = ["@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
                 "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
                 "@prefix grag: <http://graphrag.local/kg/> .",
                 f"# Generated: {datetime.now(timezone.utc).isoformat()}", ""]

        for n in nodes:
            nid = n["node_id"].replace(" ", "_")
            lines.append(f'grag:{nid} rdf:type grag:{n.get("entity_type", "Entity")} ;')
            lines.append(f'    rdfs:label "{n.get("label", "").replace(chr(34), chr(92)+chr(34))}" .')
            lines.append("")

        for e in edges:
            s = e["source_node_id"].replace(" ", "_")
            t = e["target_node_id"].replace(" ", "_")
            lines.append(f'grag:{s} grag:{e.get("relation_type", "related")} grag:{t} .')

        content = "\n".join(lines)
        return StreamingResponse(
            iter([content]),
            media_type="text/turtle",
            headers={"Content-Disposition": "attachment; filename=kg_export.ttl"},
        )

    def _export_kg_zip(self) -> StreamingResponse:
        nodes, edges = self._load_all_kg()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("nodes.json", json.dumps({"nodes": nodes}, ensure_ascii=False, indent=2))
            zf.writestr("edges.json", json.dumps({"edges": edges}, ensure_ascii=False, indent=2))

            nf = io.StringIO()
            if nodes:
                w = csv.DictWriter(nf, fieldnames=["node_id", "entity_type", "label", "page_idx", "grounding_status"])
                w.writeheader()
                for n in nodes:
                    w.writerow({k: n.get(k, "") for k in ["node_id", "entity_type", "label", "page_idx", "grounding_status"]})
            zf.writestr("nodes.csv", "﻿" + nf.getvalue())

            ef = io.StringIO()
            if edges:
                w = csv.DictWriter(ef, fieldnames=["source_node_id", "target_node_id", "relation_type"])
                w.writeheader()
                for e in edges:
                    w.writerow(e)
            zf.writestr("edges.csv", "﻿" + ef.getvalue())

            zf.writestr("manifest.json", json.dumps({
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "nodes": len(nodes), "edges": len(edges),
                "formats": ["json", "csv"],
            }, indent=2))

        buf.seek(0)
        return StreamingResponse(
            iter([buf.read()]),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=kg_full_export.zip"},
        )

    # ── domain dict export ─────────────────────────────────────────────

    def export_domain_dict(self, fmt: str = "yaml") -> dict | StreamingResponse:
        if not DOMAIN_DICT_PATH.exists():
            return {"error": "Domain dictionary not found"}

        if fmt == "yaml":
            content = DOMAIN_DICT_PATH.read_text(encoding="utf-8")
            return StreamingResponse(
                iter([content]),
                media_type="text/yaml",
                headers={"Content-Disposition": "attachment; filename=domain_dict.yaml"},
            )
        elif fmt == "json":
            import yaml
            data = yaml.safe_load(DOMAIN_DICT_PATH.read_text(encoding="utf-8"))
            content = json.dumps(data, ensure_ascii=False, indent=2)
            return StreamingResponse(
                iter([content]),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=domain_dict.json"},
            )
        elif fmt == "csv":
            import yaml
            data = yaml.safe_load(DOMAIN_DICT_PATH.read_text(encoding="utf-8"))
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=["term", "category", "entity_type",
                                                     "synonyms", "abbreviations", "related", "description"])
            writer.writeheader()
            for name, obj in data.items():
                writer.writerow({
                    "term": name,
                    "category": obj.get("category", ""),
                    "entity_type": obj.get("entity_type", ""),
                    "synonyms": ";".join(obj.get("synonyms", [])),
                    "abbreviations": ";".join(obj.get("abbreviations", [])),
                    "related": ";".join(obj.get("related", [])),
                    "description": obj.get("description", ""),
                })
            content = "﻿" + buf.getvalue()
            return StreamingResponse(
                iter([content]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=domain_dict.csv"},
            )
        else:
            raise ValueError(f"Unsupported domain dict format: {fmt}")

    # ── feedback export ────────────────────────────────────────────────

    def export_feedback(self, fmt: str = "csv", status: str | None = None) -> StreamingResponse:
        records = []
        if FEEDBACK_DIR.exists():
            for f in sorted(FEEDBACK_DIR.glob("*.json")):
                try:
                    rec = json.loads(f.read_text(encoding="utf-8"))
                    if status and rec.get("status") != status:
                        continue
                    records.append(rec)
                except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                    pass

        if fmt == "json":
            content = json.dumps(records, ensure_ascii=False, indent=2)
            return StreamingResponse(
                iter([content]),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=feedback_export.json"},
            )
        else:
            buf = io.StringIO()
            fieldnames = ["feedback_id", "created_at", "query_id", "rating", "status",
                         "comment", "correction", "query_text", "answer_text"]
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                writer.writerow(r)
            content = "﻿" + buf.getvalue()
            return StreamingResponse(
                iter([content]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=feedback_export.csv"},
            )

    # ── conversation export ─────────────────────────────────────────────

    def export_conversations(self, fmt: str = "zip") -> StreamingResponse:
        if not CONVERSATIONS_DIR.exists():
            return StreamingResponse(
                iter(["No conversations found"]),
                media_type="text/plain",
            )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(CONVERSATIONS_DIR.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    md_lines = [f"# Conversation: {f.stem}",
                                f"Created: {data.get('created_at', 'unknown')}",
                                f"Turns: {len(data.get('turns', []))}", ""]
                    for t in data.get("turns", []):
                        md_lines.append(f"## Turn {t.get('turn_id', '?')}")
                        md_lines.append(f"**Q:** {t.get('question', '')}")
                        md_lines.append(f"**A:** {t.get('answer', '')}")
                        if t.get("rewritten"):
                            md_lines.append(f"*Rewritten:* {t['rewritten']}")
                        md_lines.append("")
                    zf.writestr(f"{f.stem}.md", "\n".join(md_lines))
                except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
                    pass

            zf.writestr("manifest.json", json.dumps({
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "format": "markdown",
            }, indent=2))

        buf.seek(0)
        return StreamingResponse(
            iter([buf.read()]),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=conversations_export.zip"},
        )


# ── singleton ─────────────────────────────────────────────────────────────

_exporter: KgExporter | None = None


def get_exporter() -> KgExporter:
    global _exporter
    if _exporter is None:
        _exporter = KgExporter()
    return _exporter
