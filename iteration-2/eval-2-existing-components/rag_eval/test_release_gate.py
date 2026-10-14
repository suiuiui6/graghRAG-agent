from __future__ import annotations

import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_gate import (
    _load_json,
    _with_validation_checks,
    evaluate_release_gate,
    build_report_markdown,
)


def test_release_gate_fails_when_p95_latency_exceeds_target() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 6500, "p99": 12000}}},
    )

    assert verdict["passed"] is False
    assert verdict["checks"]["a5_p95_latency_ms_max"]["passed"] is False


def test_release_gate_fails_when_a1_final_context_recall_is_below_target() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.30},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )

    assert verdict["passed"] is False
    assert verdict["checks"]["a1_final_context_recall_min"]["passed"] is False


def test_release_gate_fails_when_final_context_surface_has_no_data() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 0,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )

    assert verdict["passed"] is False
    assert verdict["checks"]["a1_final_context_surface_ready"]["passed"] is False


def test_release_gate_passes_only_when_all_checks_pass() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )

    assert verdict["passed"] is True
    assert verdict["waivers_required"] == []


def test_release_gate_markdown_includes_provenance_and_non_gated_notes() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            },
            "by_category": {
                "T5": {"refusal_for_t5_macro": 0.20}
            },
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )
    verdict["_meta"] = {
        "raw_runs_path": "raw_runs.jsonl",
        "raw_runs_sha256": "abc123",
        "run_log_path": "run.log",
        "backend_validation": {
            "command": "python -m pytest tests -q",
            "summary": "220 passed in 16.00s",
        },
        "non_gated_notes": [
            "T5 refusal keyword hit rate remains below 100% and is tracked as a non-blocking weakness.",
        ],
    }

    report = build_report_markdown(verdict)

    assert "Broader Backend Validation" in report
    assert "python -m pytest tests -q" in report
    assert "220 passed in 16.00s" in report
    assert "Known Non-Gated Notes" in report
    assert "T5 refusal keyword hit rate remains below 100%" in report
    assert "raw_runs.jsonl" in report
    assert "abc123" in report


def test_release_gate_markdown_marks_backend_validation_fail_from_exit_code() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )
    verdict["_meta"] = {
        "raw_runs_path": "raw_runs.jsonl",
        "raw_runs_sha256": "abc123",
        "run_log_path": "run.log",
        "backend_validation": {
            "command": "python -m pytest tests -q",
            "summary": "2 failed, 230 passed in 16.00s",
            "exit_code": 1,
        },
        "non_gated_notes": [],
    }

    report = build_report_markdown(verdict)

    assert "- Result: `FAIL`" in report
    assert "2 failed, 230 passed in 16.00s" in report


def test_with_validation_checks_blocks_release_when_conversation_validation_fails() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )

    augmented = _with_validation_checks(
        verdict,
        backend_validation={"exit_code": 0, "summary": "232 passed in 14.26s"},
        conversation_validation={"exit_code": 1, "summary": "1 failed in 0.44s"},
    )

    assert augmented["passed"] is False
    assert augmented["checks"]["conversation_rewrite_validation_passed"]["passed"] is False
    assert any(
        check["name"] == "conversation_rewrite_validation_passed"
        for check in augmented["waivers_required"]
    )


def test_release_gate_markdown_marks_rewrite_stability_from_validation_exit_code() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )
    verdict = _with_validation_checks(
        verdict,
        backend_validation={"exit_code": 0, "summary": "232 passed in 14.26s"},
        conversation_validation={"exit_code": 1, "summary": "1 failed in 0.44s"},
    )
    verdict["_meta"] = {
        "raw_runs_path": "raw_runs.jsonl",
        "raw_runs_sha256": "abc123",
        "run_log_path": "run.log",
        "backend_validation": {
            "command": "python -m pytest tests -q",
            "summary": "232 passed in 14.26s",
            "exit_code": 0,
        },
        "conversation_validation": {
            "command": "python -m pytest tests/test_conversation_rewrite.py -q -s --capture=no",
            "summary": "1 failed in 0.44s",
            "exit_code": 1,
        },
        "non_gated_notes": [],
    }

    report = build_report_markdown(verdict)

    assert "Multi-turn rewrite stability: `FAIL`" in report
    assert "Conversation Rewrite Validation" in report
    assert "1 failed in 0.44s" in report


def test_release_gate_markdown_includes_corpus_drift_note_from_conversation_rewrite_metrics() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )
    verdict["_meta"] = {
        "raw_runs_path": "raw_runs.jsonl",
        "raw_runs_sha256": "abc123",
        "run_log_path": "run.log",
        "backend_validation": {
            "command": "python -m pytest tests -q",
            "summary": "232 passed in 14.26s",
            "exit_code": 0,
        },
        "conversation_validation": {
            "command": "python -m pytest tests/test_conversation_rewrite.py -q -s --capture=no",
            "summary": "4 passed in 2.77s",
            "exit_code": 0,
        },
        "conversation_rewrite_metrics": {
            "_meta": {
                "ground_truth_path": "ground_truth_multiturn_smoke.json",
                "raw_runs_path": "raw_runs_multiturn_smoke.jsonl",
            },
            "global": {
                "followup_questions": 3,
                "rewrite_success_rate_macro": 1.0,
                "session_id_match_rate_macro": 1.0,
                "keyword_coverage_macro": 0.67,
                "corpus_drift_cases": 2,
                "invalid_eval_cases": 0,
                "valid_questions_for_scoring": 1,
            },
        },
        "non_gated_notes": [],
    }

    report = build_report_markdown(verdict)

    assert "Known Non-Gated Notes" in report
    assert "possible corpus drift / invalid eval cases" in report


def test_release_gate_markdown_includes_conversation_rewrite_metrics_as_supplemental_evidence() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )
    verdict["_meta"] = {
        "raw_runs_path": "raw_runs.jsonl",
        "raw_runs_sha256": "abc123",
        "run_log_path": "run.log",
        "backend_validation": {
            "command": "python -m pytest tests -q",
            "summary": "232 passed in 14.26s",
            "exit_code": 0,
        },
        "conversation_validation": {
            "command": "python -m pytest tests/test_conversation_rewrite.py -q -s --capture=no",
            "summary": "4 passed in 2.77s",
            "exit_code": 0,
        },
        "conversation_rewrite_metrics": {
            "_meta": {
                "ground_truth_path": "ground_truth_multiturn_smoke.json",
                "raw_runs_path": "raw_runs_multiturn_smoke.jsonl",
            },
            "global": {
                "followup_questions": 1,
                "rewrite_success_rate_macro": 1.0,
                "session_id_match_rate_macro": 1.0,
                "keyword_coverage_macro": 1.0,
            },
        },
        "non_gated_notes": [],
    }

    report = build_report_markdown(verdict)

    assert "Conversation Rewrite Supplemental Metrics" in report
    assert "rewrite_success_rate_macro" in report
    assert "raw_runs_multiturn_smoke.jsonl" in report


def test_release_gate_markdown_omits_conversation_rewrite_supplemental_section_when_missing() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )
    verdict["_meta"] = {
        "raw_runs_path": "raw_runs.jsonl",
        "raw_runs_sha256": "abc123",
        "run_log_path": "run.log",
        "backend_validation": {
            "command": "python -m pytest tests -q",
            "summary": "232 passed in 14.26s",
            "exit_code": 0,
        },
        "conversation_validation": {
            "command": "python -m pytest tests/test_conversation_rewrite.py -q -s --capture=no",
            "summary": "4 passed in 2.77s",
            "exit_code": 0,
        },
        "non_gated_notes": [],
    }

    report = build_report_markdown(verdict)

    assert "Conversation Rewrite Supplemental Metrics" not in report


def test_conversation_rewrite_supplemental_metrics_do_not_change_verdict_or_waivers() -> None:
    base_verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )
    without_supplemental = {
        **base_verdict,
        "checks": dict(base_verdict["checks"]),
        "waivers_required": list(base_verdict["waivers_required"]),
    }
    with_supplemental = {
        **base_verdict,
        "checks": dict(base_verdict["checks"]),
        "waivers_required": list(base_verdict["waivers_required"]),
        "_meta": {
            "conversation_rewrite_metrics": {
                "ground_truth_path": "ground_truth_multiturn_smoke.json",
                "raw_runs_path": "raw_runs_multiturn_smoke.jsonl",
                "global": {
                    "followup_questions": 1,
                    "rewrite_success_rate_macro": 1.0,
                    "session_id_match_rate_macro": 1.0,
                    "keyword_coverage_macro": 1.0,
                },
            }
        },
    }

    assert with_supplemental["passed"] == without_supplemental["passed"]
    assert with_supplemental["waivers_required"] == without_supplemental["waivers_required"]


def test_load_json_accepts_utf8_bom() -> None:
    payload = Path(tempfile.gettempdir()) / "with-bom-release-gate.json"
    payload.write_text('{"ok": true}', encoding="utf-8-sig")

    data = _load_json(payload)

    assert data == {"ok": True}
    payload.unlink(missing_ok=True)


def test_release_gate_markdown_adds_sample_size_note_for_small_multiturn_eval() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )
    verdict["_meta"] = {
        "raw_runs_path": "raw_runs.jsonl",
        "raw_runs_sha256": "abc123",
        "run_log_path": "run.log",
        "conversation_rewrite_metrics": {
            "_meta": {
                "ground_truth_path": "ground_truth_multiturn_smoke.json",
                "raw_runs_path": "raw_runs_multiturn_smoke.jsonl",
            },
            "global": {
                "followup_questions": 1,
                "rewrite_success_rate_macro": 1.0,
                "session_id_match_rate_macro": 1.0,
                "keyword_coverage_macro": 1.0,
            },
        },
        "non_gated_notes": [],
    }

    report = build_report_markdown(verdict)

    assert "sample size is too small for release gating" in report


def test_release_gate_markdown_omits_sample_size_note_when_multiturn_eval_is_large_enough() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )
    verdict["_meta"] = {
        "raw_runs_path": "raw_runs.jsonl",
        "raw_runs_sha256": "abc123",
        "run_log_path": "run.log",
        "conversation_rewrite_metrics": {
            "_meta": {
                "ground_truth_path": "ground_truth_multiturn.json",
                "raw_runs_path": "raw_runs_multiturn.jsonl",
            },
            "global": {
                "followup_questions": 8,
                "rewrite_success_rate_macro": 0.875,
                "session_id_match_rate_macro": 1.0,
                "keyword_coverage_macro": 0.90,
            },
        },
        "non_gated_notes": [],
    }

    report = build_report_markdown(verdict)

    assert "sample size is too small for release gating" not in report


def test_release_gate_markdown_omits_sample_size_note_at_threshold() -> None:
    verdict = evaluate_release_gate(
        a1={
            "surfaces": {
                "final_context": {
                    "global": {"recall_macro": 0.40},
                    "surface_data_coverage": 39,
                }
            }
        },
        a2={
            "global": {
                "keyword_coverage_macro": 0.80,
                "cited_in_retrieved_rate_macro": 1.0,
            }
        },
        a5={"latency_ms": {"global": {"p95": 5000, "p99": 12000}}},
    )
    verdict["_meta"] = {
        "raw_runs_path": "raw_runs.jsonl",
        "raw_runs_sha256": "abc123",
        "run_log_path": "run.log",
        "conversation_rewrite_metrics": {
            "_meta": {
                "ground_truth_path": "ground_truth_multiturn_smoke.json",
                "raw_runs_path": "raw_runs_multiturn_smoke.jsonl",
            },
            "global": {
                "followup_questions": 3,
                "rewrite_success_rate_macro": 1.0,
                "session_id_match_rate_macro": 1.0,
                "keyword_coverage_macro": 1.0,
            },
        },
        "non_gated_notes": [],
    }

    report = build_report_markdown(verdict)

    assert "sample size is too small for release gating" not in report
