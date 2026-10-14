"""One-off local research audit. Reads sources; writes only new report directory.

No production imports, model weights, inference, network or credential reads.
Candidate bodies are hashed as opaque bytes, never extracted or tokenized.
Only the three already-exposed development texts are tokenized.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.metadata
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import yaml
from tokenizers import Tokenizer


def fingerprint(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    assert output.is_relative_to(root / "docs" / "review" / "scope-holdout-20261012")
    assert not output.exists(), "Use a new output directory; never overwrite a run."
    tokenizer_path = Path(args.tokenizer).resolve()
    assert tokenizer_path.is_file()
    gold_path = root / "docs/superpowers/plans/scope-pilot/gold-review-v2/gold-v2.yaml"
    plan_path = root / "docs/superpowers/plans/scope-pilot/api-runs/20261007-live-v1/plan.json"
    store_path = root / "backend/output/docs_store.json"
    initial = {str(p): fingerprint(p) for p in [gold_path, plan_path, store_path, tokenizer_path]}
    scope = ["backend/uploads", "backend/output/mineru", "mineru-mvp-test"]
    paths = []
    for base in scope:
        for path in (root / base).rglob("*"):
            if path.is_file() and not path.is_symlink() and (
                path.suffix.lower() in {".pdf", ".docx", ".doc", ".pptx"}
                or path.name == "full.md"
            ):
                paths.append(path)
    paths = sorted(set(paths))
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for path in paths:
        groups[fingerprint(path)].append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size})
    inventory = []
    candidates = []
    keywords = ("零容忍", "隐患判定", "危险化学品", "施工安全", "停工", "高压线")
    store = json.loads(store_path.read_text(encoding="utf-8"))
    for digest, copies in sorted(groups.items()):
        row = {"sha256": digest, "copies": copies, "copy_count": len(copies)}
        inventory.append(row)
        safety = [x for x in copies if x["path"].startswith("backend/uploads/") and any(k in x["path"] for k in keywords)]
        if not safety:
            continue
        representative = min(safety, key=lambda x: x["path"])["path"]
        names = {Path(x["path"]).name.split("_", 2)[-1] for x in copies if x["path"].startswith("backend/uploads/")}
        matching_store = [r for r in store if r.get("filename") in names]
        candidates.append({
            "candidate_id": "C-" + digest[:12], "sha256": digest,
            "representative_path": representative, "copies": copies,
            "local_use": "USER_CONFIRMED_LOCAL_RESEARCH_20261012",
            "public_release": "NOT_AUTHORIZED_OR_VERIFIED",
            "third_party_transfer": "NOT_AUTHORIZED_OR_VERIFIED",
            "exposure": "UNKNOWN_NOT_CLEARED_FOR_HOLDOUT",
            "body_read_in_this_audit": False,
            "prior_ingest_label_matches": len(matching_store),
            "ingest_label_match_is_content_identity": False,
            "source_family": "PENDING_NEAR_DUPLICATE_AND_PROVENANCE_AUDIT",
            "admission": "QUARANTINE_PENDING_EXPOSURE_AND_FAMILY_CLEARANCE",
        })
    gold = yaml.safe_load(gold_path.read_text(encoding="utf-8"))
    texts = {}
    source_before = {}
    for key, doc in gold["documents"].items():
        path = root / doc["path"]
        digest = fingerprint(path)
        assert digest == doc["sha256"], "Frozen development source drift."
        source_before[str(path)] = digest
        texts[key] = path.read_text(encoding="utf-8")
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.no_truncation()
    tokenizer.no_padding()

    def count(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False).ids)

    whole_documents = [{"doc": key, "codepoints": len(text), "utf8_bytes": len(text.encode("utf-8")),
                        "proxy_tokens": count(text)} for key, text in texts.items()]
    question_rows = []
    for question in gold["questions"]:
        target = question.get("coverage_adjudication_target", question["scope"])
        text = texts[question["doc"]][target["start"]:target["end"]]
        question_rows.append({"qid": question["id"], "doc": question["doc"],
                              "query_version": question["query_version"],
                              "target_codepoints": len(text), "target_utf8_bytes": len(text.encode("utf-8")),
                              "target_proxy_tokens": count(text), "query_proxy_tokens": count(question["query"]),
                              "is_generator_token_count": False})
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    legacy_rows = []
    for i, row in enumerate(plan["rows"]):
        response_path = plan_path.parent / f"{i:03d}-response.json"
        initial[str(response_path)] = fingerprint(response_path)
        response = json.loads(response_path.read_text(encoding="utf-8"))
        usage = response["usage"]
        user = json.loads(row["payload"]["messages"][1]["content"])
        source_text = "\n\n".join(x["text"] for x in user["source_contexts"])
        legacy_rows.append({"index": i, "qid": row["qid"], "arm": row["baseline"],
                            "source_utf8_bytes": len(source_text.encode("utf-8")),
                            "source_proxy_tokens": count(source_text),
                            "prompt_tokens_recorded": usage["prompt_tokens"],
                            "completion_tokens_recorded": usage["completion_tokens"],
                            "total_tokens_recorded": usage["total_tokens"],
                            "response_sha256": initial[str(response_path)],
                            "request_max_output": row["payload"]["max_tokens"],
                            "request_model": row["payload"]["model"],
                            "response_model": response["model"],
                            "finish_reason": response["choices"][0]["finish_reason"]})
    summary = []
    for arm in sorted({r["arm"] for r in legacy_rows}):
        rows = [r for r in legacy_rows if r["arm"] == arm]
        summary.append({"arm": arm, "n": len(rows),
                        "prompt_min": min(r["prompt_tokens_recorded"] for r in rows),
                        "prompt_median": statistics.median(r["prompt_tokens_recorded"] for r in rows),
                        "prompt_max": max(r["prompt_tokens_recorded"] for r in rows),
                        "completion_max": max(r["completion_tokens_recorded"] for r in rows),
                        "total_sum": sum(r["total_tokens_recorded"] for r in rows)})
    guards = {**initial, **source_before}
    source_drift = [name for name, digest in guards.items() if fingerprint(Path(name)) != digest]
    report = {
        "project_id": "graphrag-paper-001", "stage": "M2_OPEN", "created_utc": datetime.now(timezone.utc).isoformat(),
        "script_sha256": fingerprint(Path(__file__)), "scope": scope,
        "inventory_scope_note": "Bounded source asset directories; tests/temp/isolated snapshots and project prose are not new raw documents.",
        "inventory_file_count": len(paths), "exact_hash_group_count": len(groups),
        "candidates": candidates, "opaque_file_groups": inventory,
        "holdout_admitted": [], "holdout_H1": [], "holdout_H2": [],
        "split_status": "BLOCKED_UNVERIFIED_EXPOSURE_FAMILY_AND_INSUFFICIENT_DOCUMENTS",
        "development_documents": whole_documents, "development_questions": question_rows,
        "tokenizer": {"path": str(tokenizer_path), "sha256": initial[str(tokenizer_path)],
                      "purpose": "LOCAL_BGE_M3_RETRIEVAL_TOKENIZER_PROXY_ONLY_NOT_GENERATOR",
                      "package": "tokenizers", "version": importlib.metadata.version("tokenizers"),
                      "truncation": False, "padding": False, "add_special_tokens": False},
        "historical_provider_usage": legacy_rows, "historical_arm_summary": summary,
        "legacy_scope_resolution": plan["scope_resolution"], "legacy_budget_type": plan["budget_type"],
        "historical_usage_is_new_v2_or_scan_experiment": False,
        "generator_tokenizer": "UNAVAILABLE_NOT_IDENTIFIED", "execution_budget_frozen": False,
        "new_model_calls": 0, "network_calls": 0, "candidate_body_extraction": False,
        "source_drift": source_drift,
        "guards_before_and_after": {str(Path(name).relative_to(root)) if Path(name).is_relative_to(root) else name:
                                    {"before": digest, "after": fingerprint(Path(name))} for name, digest in guards.items()},
    }
    assert not source_drift, "Inputs changed during audit; do not publish a consistent snapshot."
    output.mkdir(parents=True)
    (output / "inventory-budget.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(paths), "hash_groups": len(groups), "candidate_groups": len(candidates),
                      "candidate_copies": sum(len(x["copies"]) for x in candidates), "admitted_holdout": 0,
                      "whole_development": whole_documents, "target_proxy_counts": question_rows,
                      "historical_usage": summary, "input_drift": source_drift,
                      "output": str(output / "inventory-budget.json")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
