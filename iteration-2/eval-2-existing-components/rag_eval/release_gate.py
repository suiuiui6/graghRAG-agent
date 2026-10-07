from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVAL_DIR = Path(r"D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval")
A1_PATH = EVAL_DIR / "metrics_a1_retrieval.json"
A2_PATH = EVAL_DIR / "metrics_a2_faithfulness.json"
A5_PATH = EVAL_DIR / "metrics_a5_performance.json"
RAW_RUNS_PATH = EVAL_DIR / "raw_runs.jsonl"
RUN_LOG_PATH = EVAL_DIR / "run.log"
BACKEND_VALIDATION_PATH = EVAL_DIR / "backend_validation_summary.json"
CONVERSATION_VALIDATION_PATH = EVAL_DIR / "conversation_validation_summary.json"
CONVERSATION_REWRITE_METRICS_PATH = EVAL_DIR / "conversation_rewrite_metrics.json"
OUT_JSON = EVAL_DIR / "release_gate_report.json"
OUT_MD = EVAL_DIR / "release_gate_report.md"
MULTITURN_GATING_SAMPLE_THRESHOLD = 3

TARGETS = {
    "a1_final_context_recall_min": 0.35,
    "a2_keyword_coverage_min": 0.75,
    "a2_cited_in_retrieved_min": 0.98,
    "a5_p95_latency_ms_max": 6000,
    "a5_p99_latency_ms_max": 15000,
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_min(name: str, actual: float | None, target: float) -> dict[str, Any]:
    passed = actual is not None and actual >= target
    return {
        "name": name,
        "operator": ">=",
        "target": target,
        "actual": actual,
        "passed": passed,
    }


def _check_max(name: str, actual: float | None, target: float) -> dict[str, Any]:
    passed = actual is not None and actual <= target
    return {
        "name": name,
        "operator": "<=",
        "target": target,
        "actual": actual,
        "passed": passed,
    }


def evaluate_release_gate(
    a1: dict[str, Any],
    a2: dict[str, Any],
    a5: dict[str, Any],
) -> dict[str, Any]:
    final_context = ((a1.get("surfaces") or {}).get("final_context") or {})
    final_context_global = final_context.get("global") or {}
    a2_global = a2.get("global") or {}
    a5_latency_global = ((a5.get("latency_ms") or {}).get("global") or {})

    surface_coverage = final_context.get("surface_data_coverage")
    surface_ready = isinstance(surface_coverage, (int, float)) and surface_coverage > 0

    checks = {
        "a1_final_context_surface_ready": {
            "name": "a1_final_context_surface_ready",
            "operator": ">",
            "target": 0,
            "actual": surface_coverage,
            "passed": surface_ready,
        },
        "a1_final_context_recall_min": _check_min(
            "a1_final_context_recall_min",
            final_context_global.get("recall_macro"),
            TARGETS["a1_final_context_recall_min"],
        ),
        "a2_keyword_coverage_min": _check_min(
            "a2_keyword_coverage_min",
            a2_global.get("keyword_coverage_macro"),
            TARGETS["a2_keyword_coverage_min"],
        ),
        "a2_cited_in_retrieved_min": _check_min(
            "a2_cited_in_retrieved_min",
            a2_global.get("cited_in_retrieved_rate_macro"),
            TARGETS["a2_cited_in_retrieved_min"],
        ),
        "a5_p95_latency_ms_max": _check_max(
            "a5_p95_latency_ms_max",
            a5_latency_global.get("p95"),
            TARGETS["a5_p95_latency_ms_max"],
        ),
        "a5_p99_latency_ms_max": _check_max(
            "a5_p99_latency_ms_max",
            a5_latency_global.get("p99"),
            TARGETS["a5_p99_latency_ms_max"],
        ),
    }
    waivers_required = [check for check in checks.values() if not check["passed"]]

    return {
        "generated_at": _utc_now(),
        "passed": not waivers_required,
        "checks": checks,
        "waivers_required": waivers_required,
        "targets": TARGETS,
        "inputs": {
            "a1_final_context_surface_data_coverage": surface_coverage,
            "a1_final_context_recall_macro": final_context_global.get("recall_macro"),
            "a2_keyword_coverage_macro": a2_global.get("keyword_coverage_macro"),
            "a2_cited_in_retrieved_rate_macro": a2_global.get("cited_in_retrieved_rate_macro"),
            "a5_p95_latency_ms": a5_latency_global.get("p95"),
            "a5_p99_latency_ms": a5_latency_global.get("p99"),
        },
    }


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _validation_check(name: str, validation: dict[str, Any] | None) -> dict[str, Any]:
    exit_code = validation.get("exit_code") if validation else None
    return {
        "name": name,
        "operator": "==",
        "target": 0,
        "actual": exit_code,
        "passed": exit_code == 0,
    }


def _with_validation_checks(
    verdict: dict[str, Any],
    *,
    backend_validation: dict[str, Any] | None,
    conversation_validation: dict[str, Any] | None,
) -> dict[str, Any]:
    validation_checks = {
        "backend_validation_passed": _validation_check(
            "backend_validation_passed",
            backend_validation,
        ),
        "conversation_rewrite_validation_passed": _validation_check(
            "conversation_rewrite_validation_passed",
            conversation_validation,
        ),
    }
    verdict["checks"].update(validation_checks)
    existing_waivers = {check["name"] for check in verdict["waivers_required"]}
    for check in validation_checks.values():
        if not check["passed"] and check["name"] not in existing_waivers:
            verdict["waivers_required"].append(check)
    verdict["passed"] = verdict["passed"] and all(check["passed"] for check in validation_checks.values())
    return verdict


def build_report_markdown(verdict: dict[str, Any]) -> str:
    meta = verdict.get("_meta", {}) or {}
    backend_validation = meta.get("backend_validation") or {}
    conversation_validation = meta.get("conversation_validation") or {}
    conversation_rewrite_metrics = meta.get("conversation_rewrite_metrics") or {}
    non_gated_notes = list(meta.get("non_gated_notes") or [])
    backend_validation_passed = backend_validation.get("exit_code") == 0 if backend_validation else None
    rewrite_validation_passed = (
        conversation_validation.get("exit_code") == 0 if conversation_validation else None
    )
    rewrite_global_metrics = conversation_rewrite_metrics.get("global") or {}
    corpus_drift_cases = rewrite_global_metrics.get("corpus_drift_cases")
    invalid_eval_cases = rewrite_global_metrics.get("invalid_eval_cases")
    if (
        isinstance(corpus_drift_cases, (int, float))
        and corpus_drift_cases > 0
        and not any("possible corpus drift / invalid eval cases" in note for note in non_gated_notes)
    ):
        non_gated_notes.append(
            "Conversation rewrite supplemental eval reports possible corpus drift / invalid eval cases; "
            "review per-question alias evidence before treating multiturn smoke misses as retrieval regressions."
        )
    lines = [
        "# Enterprise Release Gate Report",
        "",
        f"- Generated at (UTC): `{verdict['generated_at']}`",
        f"- Final verdict: `{'GO' if verdict['passed'] else 'NO-GO'}`",
        "",
        "## Enterprise Release Gate Summary",
        "",
        f"- Retrieval measurement surface: `{'PASS' if verdict['checks']['a1_final_context_surface_ready']['passed'] else 'FAIL'}`",
        f"- Multi-turn rewrite stability: `{'PASS' if rewrite_validation_passed else 'FAIL'}`",
        f"- Tail latency target: `{'PASS' if verdict['checks']['a5_p95_latency_ms_max']['passed'] and verdict['checks']['a5_p99_latency_ms_max']['passed'] else 'FAIL'}`",
    ]
    if backend_validation:
        lines.extend(
            [
                "",
                "## Broader Backend Validation",
                "",
                f"- Result: `{'PASS' if backend_validation_passed else 'FAIL'}`",
                f"- Evidence: `{backend_validation.get('command', 'python -m pytest tests -q')}` -> `{backend_validation.get('summary', 'n/a')}`.",
            ]
        )
    if conversation_validation:
        lines.extend(
            [
                "",
                "## Conversation Rewrite Validation",
                "",
                f"- Result: `{'PASS' if rewrite_validation_passed else 'FAIL'}`",
                f"- Evidence: `{conversation_validation.get('command', 'python -m pytest tests/test_conversation_rewrite.py -q -s --capture=no')}` -> `{conversation_validation.get('summary', 'n/a')}`.",
            ]
        )
    if conversation_rewrite_metrics:
        global_metrics = conversation_rewrite_metrics.get("global") or {}
        rewrite_metrics_meta = conversation_rewrite_metrics.get("_meta") or {}
        lines.extend(
            [
                "",
                "## Conversation Rewrite Supplemental Metrics",
                "",
                f"- Ground truth: `{rewrite_metrics_meta.get('ground_truth_path', 'n/a')}`",
                f"- Raw runs: `{rewrite_metrics_meta.get('raw_runs_path', 'n/a')}`",
                f"- followup_questions: `{global_metrics.get('followup_questions', 'n/a')}`",
                f"- rewrite_success_rate_macro: `{_format_value(global_metrics.get('rewrite_success_rate_macro'))}`",
                f"- session_id_match_rate_macro: `{_format_value(global_metrics.get('session_id_match_rate_macro'))}`",
                f"- keyword_coverage_macro: `{_format_value(global_metrics.get('keyword_coverage_macro'))}`",
                f"- corpus_drift_cases: `{_format_value(global_metrics.get('corpus_drift_cases'))}`",
                f"- invalid_eval_cases: `{_format_value(global_metrics.get('invalid_eval_cases'))}`",
                f"- valid_questions_for_scoring: `{_format_value(global_metrics.get('valid_questions_for_scoring'))}`",
            ]
        )
        followup_questions = global_metrics.get("followup_questions")
        if isinstance(followup_questions, (int, float)) and followup_questions < MULTITURN_GATING_SAMPLE_THRESHOLD:
            lines.append(
                f"- Note: conversation rewrite sample size is too small for release gating "
                f"(`{int(followup_questions)}` < `{MULTITURN_GATING_SAMPLE_THRESHOLD}`); treat this section as supplemental evidence only."
            )
    lines.extend(
        [
            f"- Final enterprise verdict: `{'GO' if verdict['passed'] else 'NO-GO'}`",
            "",
            "## Checks",
            "",
            "| Check | Actual | Target | Result |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for check in verdict["checks"].values():
        lines.append(
            f"| `{check['name']}` | {_format_value(check['actual'])} | "
            f"`{check['operator']} {check['target']}` | "
            f"{'PASS' if check['passed'] else 'FAIL'} |"
        )

    lines.extend(
        [
            "",
            "## Provenance",
            "",
            f"- Raw runs: `{meta.get('raw_runs_path', 'n/a')}`",
            f"- Raw runs sha256: `{meta.get('raw_runs_sha256', 'n/a')}`",
            f"- Inference log: `{meta.get('run_log_path', 'n/a')}`",
            "",
            "## Decision Notes",
            "",
            "- `a1_final_context_surface_ready` blocks release when final-context retrieval evidence is absent; this avoids treating stale eval runs as production-ready proof.",
            "- `a1_final_context_recall_min` is the enterprise-critical retrieval threshold because it measures what actually reached generation.",
            "- `a2` checks protect answer grounding while retrieval tuning evolves.",
            "- `a5` checks bound both typical tail latency (`p95`) and extreme outliers (`p99`).",
        ]
    )

    if non_gated_notes:
        lines.extend(["", "## Known Non-Gated Notes", ""])
        for note in non_gated_notes:
            lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "## Waivers Required",
            "",
        ]
    )

    if verdict["waivers_required"]:
        for check in verdict["waivers_required"]:
            lines.append(
                f"- `{check['name']}` failed: actual={_format_value(check['actual'])}, "
                f"target=`{check['operator']} {check['target']}`"
            )
    else:
        lines.append("- None.")

    return "\n".join(lines)


def main() -> None:
    a1 = _load_json(A1_PATH)
    a2 = _load_json(A2_PATH)
    a5 = _load_json(A5_PATH)
    verdict = evaluate_release_gate(a1=a1, a2=a2, a5=a5)
    non_gated_notes: list[str] = []
    t5_refusal = (((a2.get("by_category") or {}).get("T5") or {}).get("refusal_for_t5_macro"))
    if isinstance(t5_refusal, (int, float)) and t5_refusal < 1.0:
        non_gated_notes.append(
            "T5 refusal keyword hit rate remains below 100% and is tracked as a non-blocking weakness."
        )

    backend_validation = None
    if BACKEND_VALIDATION_PATH.exists():
        backend_validation = _load_json(BACKEND_VALIDATION_PATH)
    conversation_validation = None
    if CONVERSATION_VALIDATION_PATH.exists():
        conversation_validation = _load_json(CONVERSATION_VALIDATION_PATH)
    conversation_rewrite_metrics = None
    if CONVERSATION_REWRITE_METRICS_PATH.exists():
        conversation_rewrite_metrics = _load_json(CONVERSATION_REWRITE_METRICS_PATH)
        followup_questions = ((conversation_rewrite_metrics.get("global") or {}).get("followup_questions"))
        if isinstance(followup_questions, (int, float)) and followup_questions < MULTITURN_GATING_SAMPLE_THRESHOLD:
            non_gated_notes.append(
                f"Conversation rewrite supplemental eval has only {int(followup_questions)} follow-up sample(s); it remains non-gating until sample size reaches at least {MULTITURN_GATING_SAMPLE_THRESHOLD}."
            )

    verdict = _with_validation_checks(
        verdict,
        backend_validation=backend_validation,
        conversation_validation=conversation_validation,
    )

    verdict["_meta"] = {
        "a1_path": str(A1_PATH),
        "a2_path": str(A2_PATH),
        "a5_path": str(A5_PATH),
        "report_path": str(OUT_MD),
        "raw_runs_path": str(RAW_RUNS_PATH),
        "raw_runs_sha256": _sha256(RAW_RUNS_PATH),
        "run_log_path": str(RUN_LOG_PATH),
        "backend_validation": backend_validation,
        "conversation_validation": conversation_validation,
        "conversation_rewrite_metrics": conversation_rewrite_metrics,
        "non_gated_notes": non_gated_notes,
    }

    with OUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(verdict, handle, ensure_ascii=False, indent=2)

    OUT_MD.write_text(build_report_markdown(verdict), encoding="utf-8")

    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print(f"Release verdict: {'GO' if verdict['passed'] else 'NO-GO'}")


if __name__ == "__main__":
    main()
