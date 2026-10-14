from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

EVAL_DIR = Path(r"D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval")
GT_PATH = EVAL_DIR / "ground_truth_multiturn_smoke.json"
RUNS_PATH = EVAL_DIR / "raw_runs_multiturn_smoke.jsonl"
OUT_JSON = EVAL_DIR / "conversation_rewrite_metrics.json"
OUT_MD = EVAL_DIR / "conversation_rewrite_report.md"
SMALL_SAMPLE_THRESHOLD = 3


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute conversation rewrite supplemental metrics.")
    parser.add_argument("--gt-path", default=str(GT_PATH), help="Multiturn ground truth JSON path")
    parser.add_argument("--runs-path", default=str(RUNS_PATH), help="Raw runs JSONL path")
    parser.add_argument("--out-json", default=str(OUT_JSON), help="Output metrics JSON path")
    parser.add_argument("--out-md", default=str(OUT_MD), help="Output markdown report path")
    return parser.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _macro(values: list[float | int | None]) -> float | None:
    defined = [float(value) for value in values if value is not None]
    if not defined:
        return None
    return statistics.fmean(defined)


def _keyword_hits(keywords: list[str], text: str) -> tuple[list[str], list[str]]:
    normalized_text = (text or "").lower()
    found: list[str] = []
    missing: list[str] = []
    for keyword in keywords:
        if keyword.lower() in normalized_text:
            found.append(keyword)
        else:
            missing.append(keyword)
    return found, missing


def _normalize_node_ids(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        normalized.append(text.split("_")[-1] if "_" in text else text)
    return normalized


def _classify_eval_case(
    *,
    run: dict[str, Any],
    gold_aliases: list[str],
    gold_alias_found_in_rewrite: list[str],
    gold_alias_found_in_sources: list[str],
    expected_node_ids_hit: list[str],
) -> tuple[str, str | None]:
    if run.get("error"):
        return "execution_failure", "request_failed"

    if (
        gold_aliases
        and gold_alias_found_in_rewrite
        and not gold_alias_found_in_sources
        and not expected_node_ids_hit
    ):
        return "corpus_drift", "alias_missing_by_string_match"

    return "valid", None


def per_question_metrics(question: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    setup_turns = question.get("conversation_setup") or []
    is_followup = bool(setup_turns)
    rewritten_query = run.get("rewritten_query")
    rewrite_reason = run.get("rewrite_reason")
    expected_keywords = list(question.get("expected_keywords") or [])
    keyword_found, keyword_missing = _keyword_hits(
        expected_keywords,
        rewritten_query or run.get("final_answer") or "",
    )
    gold_aliases = list(question.get("gold_aliases") or question.get("anchor_aliases") or [])
    gold_alias_found_in_rewrite, gold_alias_missing_in_rewrite = _keyword_hits(
        gold_aliases,
        rewritten_query or "",
    )
    source_evidence_text = "\n".join(
        [
            *[str(value) for value in (run.get("source_labels") or []) if str(value).strip()],
            *[str(value) for value in (run.get("source_text_snippets") or []) if str(value).strip()],
        ]
    )
    gold_alias_found_in_sources, gold_alias_missing_in_sources = _keyword_hits(
        gold_aliases,
        source_evidence_text,
    )
    expected_node_ids = _normalize_node_ids(question.get("expected_node_ids") or [])
    retrieved_node_ids = _normalize_node_ids(run.get("retrieved_node_ids") or [])
    expected_node_ids_hit = [
        node_id for node_id in expected_node_ids if node_id in set(retrieved_node_ids)
    ]
    eval_case_status, eval_case_reason = _classify_eval_case(
        run=run,
        gold_aliases=gold_aliases,
        gold_alias_found_in_rewrite=gold_alias_found_in_rewrite,
        gold_alias_found_in_sources=gold_alias_found_in_sources,
        expected_node_ids_hit=expected_node_ids_hit,
    )
    keyword_coverage = (
        len(keyword_found) / len(expected_keywords)
        if expected_keywords
        else None
    )

    return {
        "qid": question["qid"],
        "category": question.get("category", ""),
        "question": question.get("question", ""),
        "is_followup": is_followup,
        "session_id_expected": question.get("session_id"),
        "session_id_actual": run.get("session_id"),
        "session_id_match": (
            1
            if question.get("session_id") and question.get("session_id") == run.get("session_id")
            else 0
        ),
        "rewritten_query": rewritten_query,
        "rewrite_reason": rewrite_reason,
        "rewrite_success": (
            1 if is_followup and rewritten_query and rewrite_reason else
            0 if is_followup else
            None
        ),
        "gold_aliases": gold_aliases,
        "gold_alias_found_in_rewrite": gold_alias_found_in_rewrite,
        "gold_alias_missing_in_rewrite": gold_alias_missing_in_rewrite,
        "gold_alias_found_in_sources": gold_alias_found_in_sources,
        "gold_alias_missing_in_sources": gold_alias_missing_in_sources,
        "expected_node_ids": expected_node_ids,
        "retrieved_node_ids": retrieved_node_ids,
        "expected_node_ids_hit": expected_node_ids_hit,
        "expected_keywords": expected_keywords,
        "keyword_found": keyword_found,
        "keyword_missing": keyword_missing,
        "keyword_coverage": keyword_coverage,
        "eval_case_status": eval_case_status,
        "eval_case_reason": eval_case_reason,
        "latency_ms": run.get("latency_ms"),
        "final_answer": run.get("final_answer", ""),
    }


def aggregate(rows: list[dict[str, Any]], *, expected_questions: int | None = None) -> dict[str, Any]:
    followups = [row for row in rows if row.get("is_followup")]
    matched_questions = len(rows)
    expected_total = expected_questions if expected_questions is not None else matched_questions
    dataset_coverage = (
        matched_questions / expected_total
        if expected_total
        else None
    )
    corpus_drift_cases = sum(1 for row in rows if row.get("eval_case_status") == "corpus_drift")
    invalid_eval_cases = sum(1 for row in rows if row.get("eval_case_status") == "invalid_eval_case")
    execution_failure_cases = sum(1 for row in rows if row.get("eval_case_status") == "execution_failure")
    valid_questions_for_scoring = sum(1 for row in rows if row.get("eval_case_status") == "valid")
    return {
        "n_questions": matched_questions,
        "expected_questions": expected_total,
        "matched_questions": matched_questions,
        "dataset_coverage_macro": dataset_coverage,
        "followup_questions": len(followups),
        "rewrite_success_rate_macro": _macro([row.get("rewrite_success") for row in rows]),
        "session_id_match_rate_macro": _macro([row.get("session_id_match") for row in rows]),
        "keyword_coverage_macro": _macro([row.get("keyword_coverage") for row in rows]),
        "corpus_drift_cases": corpus_drift_cases,
        "invalid_eval_cases": invalid_eval_cases,
        "execution_failure_cases": execution_failure_cases,
        "valid_questions_for_scoring": valid_questions_for_scoring,
        "sample_size_sufficient": len(followups) >= SMALL_SAMPLE_THRESHOLD,
    }


def build_metrics_payload(
    *,
    gt: dict[str, Any],
    runs: list[dict[str, Any]],
    ground_truth_path: Path,
    raw_runs_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    runs_by_qid = {run["qid"]: run for run in runs if run.get("qid")}
    missing_qids: list[str] = []
    per_question: list[dict[str, Any]] = []
    for question in gt.get("questions", []):
        qid = question.get("qid")
        if not qid:
            continue
        run = runs_by_qid.get(qid)
        if run is None:
            missing_qids.append(qid)
            continue
        per_question.append(per_question_metrics(question, run))

    global_metrics = aggregate(per_question, expected_questions=len(gt.get("questions", [])))
    return {
        "_meta": {
            "ground_truth_path": str(ground_truth_path),
            "raw_runs_path": str(raw_runs_path),
            "report_path": str(report_path),
            "missing_qids": missing_qids,
            "small_sample_followup_threshold": SMALL_SAMPLE_THRESHOLD,
        },
        "global": global_metrics,
        "per_question": per_question,
    }


def build_report(metrics: dict[str, Any]) -> str:
    global_metrics = metrics.get("global", {})
    per_question = metrics.get("per_question", [])
    meta = metrics.get("_meta", {})
    lines = [
        "# Conversation Rewrite Evaluation Report",
        "",
        f"- Questions matched: `{global_metrics.get('n_questions', 0)}` / `{global_metrics.get('expected_questions', 0)}`",
        f"- Dataset coverage: `{(global_metrics.get('dataset_coverage_macro') or 0):.4f}`",
        f"- Follow-up questions: `{global_metrics.get('followup_questions', 0)}`",
        f"- Rewrite success rate: `{(global_metrics.get('rewrite_success_rate_macro') or 0):.4f}`",
        f"- Session id match rate: `{(global_metrics.get('session_id_match_rate_macro') or 0):.4f}`",
        f"- Rewrite keyword coverage: `{(global_metrics.get('keyword_coverage_macro') or 0):.4f}`",
        f"- Corpus drift cases: `{global_metrics.get('corpus_drift_cases', 0)}`",
        f"- Invalid eval cases: `{global_metrics.get('invalid_eval_cases', 0)}`",
        f"- Valid questions for scoring: `{global_metrics.get('valid_questions_for_scoring', 0)}`",
        f"- Sample size sufficient for gating: `{global_metrics.get('sample_size_sufficient')}`",
    ]
    if meta.get("missing_qids"):
        lines.append(f"- Missing qids: `{', '.join(meta['missing_qids'])}`")
    lines.extend(
        [
            "",
            "| qid | followup | session match | rewrite success | eval status | rewritten query |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in per_question:
        lines.append(
            f"| `{row['qid']}` | {row['is_followup']} | {row['session_id_match']} | "
            f"{row['rewrite_success'] if row['rewrite_success'] is not None else 'n/a'} | "
            f"`{row.get('eval_case_status')}` | "
            f"{(row.get('rewritten_query') or '').replace('|', '\\|')} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    gt_path = Path(args.gt_path)
    runs_path = Path(args.runs_path)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)

    gt = _load_json(gt_path)
    runs = _load_jsonl(runs_path)
    payload = build_metrics_payload(
        gt=gt,
        runs=runs,
        ground_truth_path=gt_path,
        raw_runs_path=runs_path,
        report_path=out_md,
    )
    with out_json.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    out_md.write_text(build_report(payload), encoding="utf-8")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
