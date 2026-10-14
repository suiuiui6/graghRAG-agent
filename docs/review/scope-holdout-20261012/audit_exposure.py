"""Read existing QA metadata only; never extract candidate text or run retrieval."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent / "exposure-01"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    assert not OUT.exists(), "Keep previous audit outputs; select a new run directory."
    guards = {}

    def read(path):
        raw = path.read_bytes()
        guards[str(path.relative_to(ROOT))] = digest(raw)
        return raw

    manifest = json.loads(read(Path(__file__).parent / "run-02/inventory-budget.json"))
    registry = json.loads(read(ROOT / "backend/output/docs_store.json"))
    candidates = manifest["candidates"]
    alias_map = {}
    for c in candidates:
        for copy in c["copies"]:
            # Upload filenames carry ingest_<8hex>_ before the original label.
            label = Path(copy["path"]).name.split("_", 2)[-1]
            alias_map.setdefault(label, []).append(c["candidate_id"])
    alias_map = {k: sorted(set(v)) for k, v in alias_map.items()}
    dbpath = ROOT / "backend/output/vectordb/chroma.sqlite3"
    assert not Path(str(dbpath) + "-wal").exists(), "Cannot ignore a WAL."
    db = sqlite3.connect(":memory:")
    db.deserialize(read(dbpath))
    db.execute("PRAGMA query_only=ON")
    # Do not SELECT chroma:document, section text, labels, or embeddings.
    rows = db.execute("""SELECT e.embedding_id, m.string_value, e.created_at, e.segment_id
        FROM embeddings e JOIN embedding_metadata m ON e.id=m.id
        WHERE m.key='source_file'""").fetchall()
    source_index = {}
    for cid, label, created, segment in rows:
        source_index.setdefault(cid, []).append({"source_file": label,
            "created_at": created, "segment_id": segment,
            "candidate_label_matches": alias_map.get(label, [])})
    db.close()
    topics = ["安全", "零容忍", "高压线", "停工", "隐患", "50484", "HSE"]
    conversations = []
    scan_counts = {}
    roots = [ROOT / "backend/output/conversations",
             ROOT / "iteration-2/eval-2-existing-components/rag_eval/output/conversations"]
    for folder in roots:
        files = sorted(folder.glob("*.json"))
        turns = 0
        for path in files:
            data = json.loads(read(path))
            for i, turn in enumerate(data.get("turns", [])):
                turns += 1
                sources = turn.get("sources", [])
                source_ids = [s for s in sources if isinstance(s, str)]
                joins = [{"source_id": s, "current_metadata": source_index[s]}
                         for s in source_ids if any(x["candidate_label_matches"]
                                                   for x in source_index.get(s, []))]
                question = turn.get("question", "")
                if joins or any(t in question for t in topics):
                    conversations.append({"path": str(path.relative_to(ROOT)),
                        "pointer": f"/turns/{i}", "question": question,
                        "created_at": turn.get("created_at"),
                        "source_ids": source_ids, "current_source_label_joins": joins,
                        "qa_sources_not_exact_model_input_receipt": True,
                        "historical_index_snapshot_binding": "NOT_AVAILABLE"})
        scan_counts[str(folder.relative_to(ROOT))] = {"files": len(files), "turns": turns}
    lineages = []
    files = sorted((ROOT / "backend/output/lineage").glob("*.json"))
    for path in files:
        data = json.loads(read(path))
        for i, node in enumerate(data.get("nodes", [])):
            meta = node.get("metadata", {})
            citations = meta.get("citations", [])
            joins = [{"source_id": s, "current_metadata": source_index[s]}
                     for s in citations if isinstance(s, str)
                     and any(x["candidate_label_matches"] for x in source_index.get(s, []))]
            if joins or any(t in path.stem for t in topics):
                lineages.append({"path": str(path.relative_to(ROOT)), "pointer": f"/nodes/{i}",
                    "query_label": path.stem, "node_type": node.get("node_type"),
                    "timestamp": node.get("timestamp"), "citations": citations,
                    "candidate_count": meta.get("candidate_count"),
                    "current_source_label_joins": joins})
    scan_counts["backend/output/lineage"] = {"files": len(files)}
    decisions = []
    for c in candidates:
        cid = c["candidate_id"]
        qa = [r for r in conversations if any(cid in m["candidate_label_matches"]
              for j in r["current_source_label_joins"] for m in j["current_metadata"])]
        cites = [r for r in lineages if any(cid in m["candidate_label_matches"]
                 for j in r["current_source_label_joins"] for m in j["current_metadata"])]
        bindings = []
        for i, r in enumerate(registry):
            if r.get("filename") not in alias_map or cid not in alias_map[r["filename"]]:
                continue
            rawpath = r.get("filepath", "")
            resolved = Path(rawpath).resolve()
            in_manifest = [cp for cp in c["copies"] if (ROOT / cp["path"]).resolve() == resolved]
            exact = False
            if in_manifest:
                exact = digest(read(resolved)) == c["sha256"]
            bindings.append({"pointer": f"/{i}", "document_id": r.get("document_id"),
                "filename": r.get("filename"), "current_source_path_hash_verified": exact,
                "external_path_not_opened": not bool(in_manifest)})
        decisions.append({"candidate_id": cid, "sha256": c["sha256"],
            "registry_bindings": bindings, "qa_turn_label_join_count": len(qa),
            "lineage_node_label_join_count": len(cites),
            "exposure_status": "PRIOR_QA_SOURCE_LABEL_MATCH_EXACT_VERSION_UNVERIFIED" if qa or cites
                               else "UNKNOWN_NO_DOCUMENT_LEVEL_QA_PROOF",
            "paper_specific_use": "UNKNOWN", "prompt_or_router_tuning": "UNKNOWN",
            "admission": "QUARANTINE", "cleared_for_holdout": False})
    drift = [p for p, h in guards.items() if digest((ROOT / p).read_bytes()) != h]
    assert not drift
    result = {"project_id": "graphrag-paper-001", "stage_id": "M2",
        "task_id": "EXPOSURE-REVIEW-20261012", "created_utc": datetime.now(timezone.utc).isoformat(),
        "script_sha256": digest(Path(__file__).read_bytes()), "scan_counts": scan_counts,
        "candidate_decisions": decisions, "qa_metadata_evidence": conversations,
        "lineage_metadata_evidence": lineages, "source_file_metadata_rows": len(rows),
        "guards": guards, "source_drift": drift, "new_model_calls": 0,
        "new_network_calls": 0, "candidate_text_extraction": False,
        "candidate_content_fields_accessed": False, "answer_content_fields_accessed": False,
        "limitations": ["Current chunk IDs can be reused; no historical index hash receipt.",
            "KG dN prefixes depend on folder order; do not retrospectively bind by current order.",
            "Saved QA sources/citations do not prove the exact complete generation input.",
            "Source labels do not prove historical candidate binary hash identity.",
            "Missing histories or no references cannot clear exposure."]}
    OUT.mkdir()
    (OUT / "exposure-ledger.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scan_counts": scan_counts, "candidate_decisions": decisions,
        "qa_metadata_rows": len(conversations), "lineage_metadata_rows": len(lineages),
        "source_drift": drift}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
