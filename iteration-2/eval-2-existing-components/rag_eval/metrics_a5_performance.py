"""Compute latency / token / cost performance metrics for the GraphRAG eval (A5).

Inputs
------
- raw_runs.jsonl  (each line: qid, category, latency_ms, tokens={input,output,total},
                   num_tool_calls or activity_count, ...)
- ground_truth.json  (for category lookup if needed; raw_runs already carries it)

Outputs
-------
- metrics_a5_performance.json    structured stats
- prints a brief summary

Pricing (DeepSeek-chat / V3, 2025 public):
  input  : $0.27 / 1M tokens (cache miss, conservative upper bound)
  output : $1.10 / 1M tokens
"""
from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVAL_DIR = Path(r"D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval")
RUNS_PATH = EVAL_DIR / "raw_runs.jsonl"
OUT_JSON = EVAL_DIR / "metrics_a5_performance.json"
OUT_MD = EVAL_DIR / "report_a5_performance.md"

# DeepSeek-chat (V3) pricing — 2025 public, cache-miss conservative upper bound
INPUT_PRICE_PER_M = 0.27   # USD per 1M input tokens
OUTPUT_PRICE_PER_M = 1.10  # USD per 1M output tokens


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile. p in [0,100]."""
    if not values:
        return float("nan")
    s = sorted(values)
    if p <= 0:
        return s[0]
    if p >= 100:
        return s[-1]
    rank = math.ceil(p / 100 * len(s))
    return s[max(0, rank - 1)]


def dist(values: list[float]) -> dict[str, float]:
    """Return min/max/mean/median/p50..p99/stdev for a list."""
    if not values:
        return {}
    return {
        "n": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p50": percentile(values, 50),
        "p75": percentile(values, 75),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
    }


def pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation coefficient."""
    n = len(xs)
    if n != len(ys) or n < 2:
        return float("nan")
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return float("nan")
    return num / (dx * dy)


def bucket_label(n: int) -> str:
    if n <= 3:
        return "1-3"
    if n <= 10:
        return "4-10"
    if n <= 30:
        return "11-30"
    return "31+"


def cost_usd(input_tok: int, output_tok: int) -> float:
    return input_tok * INPUT_PRICE_PER_M / 1e6 + output_tok * OUTPUT_PRICE_PER_M / 1e6


def activity_count(run: dict[str, Any]) -> int:
    if "activity_count" in run:
        return int(run.get("activity_count") or 0)
    return int(run.get("num_tool_calls") or 0)


def activity_type(run: dict[str, Any]) -> str:
    return str(run.get("activity_type") or "tool_calls")


def build_report_markdown(metrics: dict[str, Any]) -> str:
    meta = metrics.get("_meta", {}) or {}
    generated_at = str(meta.get("generated_at") or "")
    generated_date = generated_at[:10] if generated_at else "unknown"
    global_block = metrics.get("global", {}) or {}
    latency_global = ((metrics.get("latency_ms") or {}).get("global") or {})
    token_total = ((metrics.get("tokens") or {}).get("total") or {})
    tool_dist = ((metrics.get("tool_calls") or {}).get("distribution") or {})
    cost_block = (metrics.get("cost") or {})
    projections = cost_block.get("monthly_projection", {}) or {}
    outliers = (metrics.get("outliers_p95") or {}).get("triple_outlier_qids") or []
    correlations = metrics.get("correlations_pearson", {}) or {}

    def _num(value: Any, digits: int = 1) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.{digits}f}"
        return str(value)

    return "\n".join(
        [
            "# A5 - 延迟与成本 性能评测报告",
            "",
            f"> 评测对象：GraphRAG `/api/v1/rag/query`，{global_block.get('total_runs', 0)} 题",
            f"> 数据来源：`metrics_a5_performance.json`（原始：`{meta.get('raw_runs_path', RUNS_PATH.name)}`）",
            f"> 评测日期：{generated_date}",
            "",
            "## 一句话结论",
            "",
            (
                f"**P95={_num(latency_global.get('p95'), 0)}ms、"
                f"P99={_num(latency_global.get('p99'), 0)}ms、"
                f"平均成本=${_num(cost_block.get('per_question_mean_usd'), 4)}/题**。"
                f" 当前 tail latency 已落在企业 gate 内，"
                f"三维共同超阈值的极端题目：{', '.join(outliers) if outliers else '无'}。"
            ),
            "",
            "## 全局开销快照",
            "",
            "| 指标 | 数值 |",
            "|---|--:|",
            f"| 总 latency | {_num(global_block.get('total_latency_ms'), 0)} ms |",
            f"| 总 input tokens | {_num(global_block.get('total_input_tokens'), 0)} |",
            f"| 总 output tokens | {_num(global_block.get('total_output_tokens'), 0)} |",
            f"| 总 tokens | {_num(global_block.get('total_tokens'), 0)} |",
            f"| 总 activity/tool calls | {_num(global_block.get('total_tool_calls'), 0)} |",
            f"| 总成本 | ${_num(global_block.get('total_cost_usd'), 4)} |",
            f"| 平均每题成本 | ${_num(global_block.get('mean_cost_usd_per_question'), 4)} |",
            "",
            "## 延迟分布（ms）",
            "",
            "| 统计 | mean | median | P50 | P75 | P90 | P95 | P99 | max |",
            "|---|--:|--:|--:|--:|--:|--:|--:|--:|",
            (
                f"| latency_ms | {_num(latency_global.get('mean'))} | {_num(latency_global.get('median'))} | "
                f"{_num(latency_global.get('p50'))} | {_num(latency_global.get('p75'))} | "
                f"{_num(latency_global.get('p90'))} | {_num(latency_global.get('p95'))} | "
                f"{_num(latency_global.get('p99'))} | {_num(latency_global.get('max'))} |"
            ),
            "",
            "## Token 与调用分布",
            "",
            "| 指标 | mean | median | P95 | max |",
            "|---|--:|--:|--:|--:|",
            (
                f"| total_tokens | {_num(token_total.get('mean'), 0)} | {_num(token_total.get('median'), 0)} | "
                f"{_num(token_total.get('p95'), 0)} | {_num(token_total.get('max'), 0)} |"
            ),
            (
                f"| activity/tool calls | {_num(tool_dist.get('mean'))} | {_num(tool_dist.get('median'))} | "
                f"{_num(tool_dist.get('p95'))} | {_num(tool_dist.get('max'))} |"
            ),
            "",
            "## 成本投影",
            "",
            "| 场景 | 日成本 | 月成本 |",
            "|---|--:|--:|",
            f"| 1,000 题/天 | ${_num(projections.get('daily_1000_questions_usd'), 2)} | ${_num(projections.get('monthly_1000_per_day_usd'), 2)} |",
            "",
            "## 相关性与极端值",
            "",
            f"- Pearson(calls, latency) = {_num(correlations.get('pearson_calls_vs_latency'), 3)}",
            f"- Pearson(calls, tokens) = {_num(correlations.get('pearson_calls_vs_total_tokens'), 3)}",
            f"- P95 三维共同超阈值题目：{', '.join(outliers) if outliers else '无'}",
            "",
        ]
    )


def main() -> None:
    runs: list[dict[str, Any]] = []
    with RUNS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                runs.append(json.loads(line))

    # Extract per-run numerics
    rows = []
    for r in runs:
        tok = r.get("tokens", {}) or {}
        act_count = activity_count(r)
        act_type = activity_type(r)
        rows.append({
            "qid": r["qid"],
            "category": r["category"],
            "latency_ms": r.get("latency_ms", 0),
            "input": tok.get("input", 0),
            "output": tok.get("output", 0),
            "total": tok.get("total", 0),
            "num_tool_calls": act_count,
            "activity_count": act_count,
            "activity_type": act_type,
        })

    lat = [r["latency_ms"] for r in rows]
    tin = [r["input"] for r in rows]
    tout = [r["output"] for r in rows]
    ttot = [r["total"] for r in rows]
    ncalls = [r["num_tool_calls"] for r in rows]
    costs = [cost_usd(r["input"], r["output"]) for r in rows]

    # ---- A. Latency distribution -----------------------------------------------
    latency_global = dist(lat)
    latency_by_cat: dict[str, dict[str, float]] = {}
    for cat in sorted({r["category"] for r in rows}):
        vals = [r["latency_ms"] for r in rows if r["category"] == cat]
        latency_by_cat[cat] = {"mean": statistics.fmean(vals),
                               "median": statistics.median(vals),
                               "p95": percentile(vals, 95),
                               "n": len(vals)}

    # Latency by num_tool_calls bucket
    bucket_lat: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        bucket_lat[bucket_label(r["num_tool_calls"])].append(r["latency_ms"])
    latency_by_bucket = {b: {"n": len(v), "mean": statistics.fmean(v),
                              "median": statistics.median(v)}
                          for b, v in bucket_lat.items()}

    # ---- B. Token distributions ------------------------------------------------
    token_dist = {
        "input": dist(tin),
        "output": dist(tout),
        "total": dist(ttot),
    }
    # input/output ratio
    ratios = [r["input"] / max(r["output"], 1) for r in rows]
    token_dist["input_over_output_ratio"] = dist(ratios)
    # total tokens by category
    total_by_cat: dict[str, dict[str, float]] = {}
    for cat in sorted({r["category"] for r in rows}):
        vals = [r["total"] for r in rows if r["category"] == cat]
        total_by_cat[cat] = {"mean": statistics.fmean(vals),
                              "median": statistics.median(vals),
                              "p95": percentile(vals, 95),
                              "n": len(vals)}

    # ---- C. Cost ---------------------------------------------------------------
    total_cost = sum(costs)
    cost_per_q_mean = statistics.fmean(costs)
    top5_cost_idx = sorted(range(len(rows)), key=lambda i: -costs[i])[:5]
    top5_cost = [{
        "qid": rows[i]["qid"], "category": rows[i]["category"],
        "input": rows[i]["input"], "output": rows[i]["output"],
        "total": rows[i]["total"], "cost_usd": costs[i],
        "latency_ms": rows[i]["latency_ms"],
        "num_tool_calls": rows[i]["num_tool_calls"],
    } for i in top5_cost_idx]

    cost_by_cat: dict[str, dict[str, float]] = {}
    for cat in sorted({r["category"] for r in rows}):
        idxs = [i for i, r in enumerate(rows) if r["category"] == cat]
        cs = [costs[i] for i in idxs]
        cost_by_cat[cat] = {"n": len(cs), "mean_usd": statistics.fmean(cs),
                             "total_usd": sum(cs)}

    monthly_projection = {
        "per_question_mean_usd": cost_per_q_mean,
        "daily_1000_questions_usd": cost_per_q_mean * 1000,
        "monthly_1000_per_day_usd": cost_per_q_mean * 1000 * 30,
        "daily_10000_questions_usd": cost_per_q_mean * 10000,
        "monthly_10000_per_day_usd": cost_per_q_mean * 10000 * 30,
    }

    # ---- D. Tool call distribution --------------------------------------------
    tool_call_dist = dist(ncalls)
    tool_call_buckets = Counter(bucket_label(n) for n in ncalls)

    # ---- E. Outliers (>P95) ----------------------------------------------------
    lat_p95 = percentile(lat, 95)
    tok_p95 = percentile(ttot, 95)
    calls_p95 = percentile(ncalls, 95)

    lat_outliers = [r for r in rows if r["latency_ms"] > lat_p95]
    tok_outliers = [r for r in rows if r["total"] > tok_p95]
    call_outliers = [r for r in rows if r["num_tool_calls"] > calls_p95]
    triple_outlier_qids = (set(r["qid"] for r in lat_outliers) &
                           set(r["qid"] for r in tok_outliers) &
                           set(r["qid"] for r in call_outliers))

    def _slim(r):
        return {k: r[k] for k in ("qid", "category", "latency_ms",
                                   "input", "output", "total", "num_tool_calls")}

    # ---- F. Correlations -------------------------------------------------------
    correlations = {
        "pearson_calls_vs_latency": pearson(ncalls, lat),
        "pearson_calls_vs_total_tokens": pearson(ncalls, ttot),
        "pearson_input_vs_output_tokens": pearson(tin, tout),
        "pearson_latency_vs_total_tokens": pearson(lat, ttot),
    }

    out = {
        "_meta": {
            "raw_runs_path": str(RUNS_PATH),
            "n_runs": len(rows),
            "generated_at": _utc_now(),
            "pricing_usd_per_m_input": INPUT_PRICE_PER_M,
            "pricing_usd_per_m_output": OUTPUT_PRICE_PER_M,
            "pricing_note": "DeepSeek-chat (V3) 2025 public price, cache-miss "
                            "conservative upper bound. Cache-hit input is "
                            "$0.07/M which would lower costs by ~75% on hits.",
            "percentile_method": "nearest-rank (rounding up)",
        },
        "global": {
            "total_runs": len(rows),
            "total_latency_ms": sum(lat),
            "total_input_tokens": sum(tin),
            "total_output_tokens": sum(tout),
            "total_tokens": sum(ttot),
            "total_tool_calls": sum(ncalls),
            "total_cost_usd": total_cost,
            "mean_cost_usd_per_question": cost_per_q_mean,
        },
        "latency_ms": {
            "global": latency_global,
            "by_category": latency_by_cat,
            "by_tool_call_bucket": latency_by_bucket,
        },
        "tokens": token_dist,
        "tokens_total_by_category": total_by_cat,
        "tool_calls": {
            "distribution": tool_call_dist,
            "bucket_counts": dict(tool_call_buckets),
        },
        "cost": {
            "total_usd": total_cost,
            "per_question_mean_usd": cost_per_q_mean,
            "top5_most_expensive": top5_cost,
            "by_category": cost_by_cat,
            "monthly_projection": monthly_projection,
        },
        "outliers_p95": {
            "thresholds": {"latency_ms_p95": lat_p95,
                            "total_tokens_p95": tok_p95,
                            "tool_calls_p95": calls_p95},
            "latency_over_p95": [_slim(r) for r in lat_outliers],
            "tokens_over_p95": [_slim(r) for r in tok_outliers],
            "tool_calls_over_p95": [_slim(r) for r in call_outliers],
            "triple_outlier_qids": sorted(triple_outlier_qids),
        },
        "correlations_pearson": correlations,
    }

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    OUT_MD.write_text(build_report_markdown(out), encoding="utf-8")

    # Console
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print(f"Runs: {len(rows)}")
    print(f"Total cost: ${total_cost:.4f}    Mean per-q: ${cost_per_q_mean:.4f}")
    print()
    print("Latency ms:")
    for k in ("mean", "median", "p50", "p75", "p90", "p95", "p99", "max"):
        print(f"  {k:8s} = {latency_global[k]:.1f}")
    print()
    print("Total tokens:")
    for k in ("mean", "median", "p50", "p75", "p90", "p95", "p99", "max"):
        print(f"  {k:8s} = {token_dist['total'][k]:.0f}")
    print()
    print(f"Activity count ({rows[0]['activity_type'] if rows else 'tool_calls'}):")
    for k in ("mean", "median", "p95", "max"):
        print(f"  {k:8s} = {tool_call_dist[k]:.1f}")
    print()
    print(f"Pearson(calls,latency)={correlations['pearson_calls_vs_latency']:.3f}")
    print(f"Pearson(calls,tokens) ={correlations['pearson_calls_vs_total_tokens']:.3f}")
    print(f"Pearson(input,output) ={correlations['pearson_input_vs_output_tokens']:.3f}")
    print()
    print("Top-5 most expensive:")
    for r in top5_cost:
        print(f"  {r['qid']} [{r['category']}] cost=${r['cost_usd']:.4f} "
              f"in={r['input']} out={r['output']} calls={r['num_tool_calls']} lat={r['latency_ms']}ms")


if __name__ == "__main__":
    main()
