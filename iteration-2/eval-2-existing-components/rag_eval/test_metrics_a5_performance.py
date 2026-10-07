from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics_a5_performance import build_report_markdown


def test_a5_markdown_uses_current_metric_values() -> None:
    metrics = {
        "_meta": {
            "raw_runs_path": "raw_runs.jsonl",
            "n_runs": 50,
            "generated_at": "2026-06-14T10:12:00+00:00",
        },
        "global": {
            "total_runs": 50,
            "total_latency_ms": 120000,
            "total_input_tokens": 1000,
            "total_output_tokens": 200,
            "total_tokens": 1200,
            "total_tool_calls": 80,
            "total_cost_usd": 0.42,
            "mean_cost_usd_per_question": 0.0084,
        },
        "latency_ms": {
            "global": {
                "mean": 2400,
                "median": 2100,
                "p50": 2100,
                "p75": 3000,
                "p90": 4200,
                "p95": 4680,
                "p99": 5433,
                "max": 6000,
            },
            "by_category": {},
            "by_tool_call_bucket": {},
        },
        "tokens": {
            "total": {
                "mean": 500,
                "median": 450,
                "p50": 450,
                "p75": 600,
                "p90": 800,
                "p95": 900,
                "p99": 1000,
                "max": 1100,
            }
        },
        "tool_calls": {
            "distribution": {
                "mean": 2.0,
                "median": 2.0,
                "p95": 4.0,
                "max": 5.0,
            },
            "bucket_counts": {"1-3": 40, "4-10": 10},
        },
        "cost": {
            "total_usd": 0.42,
            "per_question_mean_usd": 0.0084,
            "top5_most_expensive": [],
            "by_category": {},
            "monthly_projection": {
                "daily_1000_questions_usd": 8.4,
                "monthly_1000_per_day_usd": 252.0,
            },
        },
        "correlations_pearson": {
            "pearson_calls_vs_latency": 0.91,
            "pearson_calls_vs_total_tokens": 0.82,
        },
        "outliers_p95": {
            "thresholds": {
                "latency_ms_p95": 4680,
                "total_tokens_p95": 900,
                "tool_calls_p95": 4.0,
            },
            "triple_outlier_qids": ["Q31"],
        },
    }

    report = build_report_markdown(metrics)

    assert "评测日期：2026-06-14" in report
    assert "P95=4680ms" in report
    assert "P99=5433ms" in report
    assert "raw_runs.jsonl" in report
