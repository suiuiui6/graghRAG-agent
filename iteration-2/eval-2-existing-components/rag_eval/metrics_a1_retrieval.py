"""Compute retrieval-layer metrics (Precision/Recall/F1/HitRate/StrictHit/MRR)
for the GraphRAG eval (A1).

Inputs
------
- ground_truth.json (top-level keys: _meta, questions; questions is a list of
  dicts with keys: qid, category, question, expected_node_ids, should_refuse, ...)
- raw_runs.jsonl (one JSON record per line, keys include: qid, category,
  expected_node_ids, retrieved_node_ids, tool_calls, final_answer, ...)

Outputs
-------
- metrics_a1_retrieval.json — structured metrics: per-question rows,
  per-category macro aggregates, global aggregates, and a T1/T6 comparison.
- The script prints a short summary to stdout when run directly.

Definitions (set-based per question)
------------------------------------
Let R_i = set(retrieved_node_ids), E_i = set(expected_node_ids).
- Precision = |R ∩ E| / |R|   (0 if |R|=0)
- Recall    = |R ∩ E| / |E|   (only defined when |E|>0; we skip questions
                              with empty E for P/R/F1/MRR/Strict aggregates)
- F1        = 2PR / (P+R)     (0 if P+R=0)
- HitRate   = 1 iff |R ∩ E|>=1
- StrictHit = 1 iff E ⊆ R
- MRR       = 1 / rank of first relevant id in the *list* retrieved_node_ids.
              The agent's `retrieved_node_ids` is stored as an ordered list
              (no duplicates), so MRR is well-defined here; however the order
              reflects insertion order from concatenated tool results, not a
              true relevance ranking from a retriever — see report caveats.

Aggregation
-----------
Macro averaging by category: arithmetic mean of per-question metrics.
T5 (should_refuse=true, expected_node_ids empty) is excluded from
retrieval metric aggregates (no ground truth set to match against).
T7 is handled per-question: Q48 has empty E (refuse), so it is excluded
from P/R/F1/MRR; Q49 and Q50 have E and are included.

Reproducibility
---------------
Run with the project venv:
    D:/graghRAG-agent/backend/.venv/Scripts/python.exe \
        D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.py
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

EVAL_DIR = Path(r"D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval")
GT_PATH = EVAL_DIR / "ground_truth.json"
RUNS_PATH = EVAL_DIR / "raw_runs.jsonl"
OUT_JSON = EVAL_DIR / "metrics_a1_retrieval.json"


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def per_question_metrics(retrieved: list[str], expected: list[str]) -> dict[str, Any]:
    """Compute set-based retrieval metrics for one question.

    Returns a dict with keys: precision, recall, f1, hit, strict_hit, mrr,
    intersection_size, retrieved_size, expected_size, mrr_rank.
    Metrics that depend on |E| (recall, f1, mrr, strict_hit) are set to None
    when expected is empty.
    """
    R = list(retrieved)  # preserve order for MRR
    R_set = set(R)
    E_set = set(expected)
    inter = R_set & E_set

    precision = _safe_div(len(inter), len(R_set))
    if not E_set:
        return {
            "precision": precision,
            "recall": None,
            "f1": None,
            "hit": None,
            "strict_hit": None,
            "mrr": None,
            "mrr_rank": None,
            "intersection_size": len(inter),
            "retrieved_size": len(R_set),
            "expected_size": 0,
            "missing_expected": [],
            "extras_retrieved": sorted(R_set),
        }

    recall = _safe_div(len(inter), len(E_set))
    f1 = _safe_div(2 * precision * recall, precision + recall)
    hit = 1 if inter else 0
    strict_hit = 1 if E_set.issubset(R_set) else 0

    mrr_rank = None
    for idx, nid in enumerate(R, start=1):
        if nid in E_set:
            mrr_rank = idx
            break
    mrr = _safe_div(1.0, mrr_rank) if mrr_rank else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "hit": hit,
        "strict_hit": strict_hit,
        "mrr": mrr,
        "mrr_rank": mrr_rank,
        "intersection_size": len(inter),
        "retrieved_size": len(R_set),
        "expected_size": len(E_set),
        "missing_expected": sorted(E_set - R_set),
        "extras_retrieved": sorted(R_set - E_set),
    }


def macro_avg(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return statistics.fmean(vals)


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Macro-average metrics across a list of per-question rows.

    Rows with `expected_size == 0` are excluded from recall/f1/hit/strict/mrr
    (they keep contributing to precision only if the user asks — by default
    we also exclude them, see returned counts).
    """
    elig = [r for r in rows if r["expected_size"] > 0]
    return {
        "n_questions": len(rows),
        "n_with_expected": len(elig),
        "precision_macro": macro_avg([r["precision"] for r in elig]),
        "recall_macro": macro_avg([r["recall"] for r in elig]),
        "f1_macro": macro_avg([r["f1"] for r in elig]),
        "hit_rate_macro": macro_avg([r["hit"] for r in elig]),
        "strict_hit_macro": macro_avg([r["strict_hit"] for r in elig]),
        "mrr_macro": macro_avg([r["mrr"] for r in elig]),
        "avg_retrieved_size": macro_avg([r["retrieved_size"] for r in rows]),
        "avg_expected_size": macro_avg([r["expected_size"] for r in elig]),
    }


def main() -> None:
    with GT_PATH.open(encoding="utf-8") as f:
        gt = json.load(f)
    gt_by_qid = {q["qid"]: q for q in gt["questions"]}

    runs: list[dict[str, Any]] = []
    with RUNS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                runs.append(json.loads(line))

    # Build per-question rows. Always use the ground-truth file as the source
    # of truth for expected_node_ids — do not trust the (cached) field in
    # raw_runs.jsonl in case it drifted.
    per_question: list[dict[str, Any]] = []
    missing_in_runs: list[str] = []
    for q in gt["questions"]:
        qid = q["qid"]
        run = next((r for r in runs if r["qid"] == qid), None)
        if run is None:
            missing_in_runs.append(qid)
            continue
        retrieved = list(run.get("retrieved_node_ids") or [])
        expected = list(q.get("expected_node_ids") or [])
        m = per_question_metrics(retrieved, expected)
        per_question.append(
            {
                "qid": qid,
                "category": q["category"],
                "question": q["question"],
                "should_refuse": q.get("should_refuse", False),
                "expected_node_ids": expected,
                "retrieved_node_ids": retrieved,
                "num_tool_calls": run.get("num_tool_calls"),
                "latency_ms": run.get("latency_ms"),
                **m,
            }
        )

    # Category aggregates (exclude T5 entirely, since all T5 have empty E).
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for row in per_question:
        by_cat.setdefault(row["category"], []).append(row)

    cat_aggregates: dict[str, dict[str, Any]] = {}
    for cat, rows in sorted(by_cat.items()):
        cat_aggregates[cat] = aggregate(rows)

    # Global aggregate: all questions whose expected_size>0.
    global_eligible = [r for r in per_question if r["expected_size"] > 0]
    global_agg = aggregate(per_question)
    global_agg["excluded_qids_empty_expected"] = [
        r["qid"] for r in per_question if r["expected_size"] == 0
    ]
    global_agg["included_qids"] = [r["qid"] for r in global_eligible]

    # T1 vs T6 noise-robustness comparison.
    t1 = aggregate(by_cat.get("T1", []))
    t6 = aggregate(by_cat.get("T6", []))
    t1_t6_delta = {
        k: (None if (t1.get(k) is None or t6.get(k) is None) else t6[k] - t1[k])
        for k in ("precision_macro", "recall_macro", "f1_macro",
                  "hit_rate_macro", "strict_hit_macro", "mrr_macro")
    }

    # Outliers: lowest F1 (among eligible), and highest |retrieved|/|expected| ratio.
    eligible_sorted_f1 = sorted(global_eligible, key=lambda r: (r["f1"], -r["retrieved_size"]))
    outliers_low_f1 = eligible_sorted_f1[:8]
    sorted_by_overshoot = sorted(
        global_eligible,
        key=lambda r: -(r["retrieved_size"] / max(r["expected_size"], 1)),
    )
    outliers_overshoot = sorted_by_overshoot[:8]

    out = {
        "_meta": {
            "ground_truth_path": str(GT_PATH),
            "raw_runs_path": str(RUNS_PATH),
            "n_gt_questions": len(gt["questions"]),
            "n_run_records": len(runs),
            "missing_in_runs": missing_in_runs,
            "metric_definitions": {
                "precision": "|R∩E| / |R|, 0 if |R|=0",
                "recall": "|R∩E| / |E|; undefined when |E|=0 (excluded)",
                "f1": "2PR/(P+R)",
                "hit": "1 if |R∩E|>=1 else 0",
                "strict_hit": "1 if E⊆R else 0",
                "mrr": "1/rank of first relevant node in the ordered "
                       "retrieved_node_ids list (insertion order from tool "
                       "results; not a learned relevance score — see report).",
            },
            "aggregation": "macro average across questions within a category; "
                            "T5 excluded from retrieval metrics (no expected_ids); "
                            "T7 Q48 also excluded (empty expected).",
        },
        "global": global_agg,
        "by_category": cat_aggregates,
        "t1_vs_t6_delta": {
            "t1": t1,
            "t6": t6,
            "delta_t6_minus_t1": t1_t6_delta,
        },
        "outliers_lowest_f1": [
            {k: r[k] for k in (
                "qid", "category", "precision", "recall", "f1", "hit",
                "strict_hit", "mrr", "mrr_rank", "expected_size",
                "retrieved_size", "intersection_size",
                "missing_expected", "extras_retrieved")}
            for r in outliers_low_f1
        ],
        "outliers_largest_overshoot": [
            {k: r[k] for k in (
                "qid", "category", "precision", "recall", "f1",
                "expected_size", "retrieved_size",
                "missing_expected")}
            for r in outliers_overshoot
        ],
        "per_question": per_question,
    }

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Console summary.
    print(f"Wrote {OUT_JSON}")
    print(f"n_questions={len(per_question)}  n_with_expected={len(global_eligible)}")
    print(f"GLOBAL P={global_agg['precision_macro']:.4f}  "
          f"R={global_agg['recall_macro']:.4f}  "
          f"F1={global_agg['f1_macro']:.4f}  "
          f"Hit={global_agg['hit_rate_macro']:.4f}  "
          f"StrictHit={global_agg['strict_hit_macro']:.4f}  "
          f"MRR={global_agg['mrr_macro']:.4f}")
    print()
    print("By category:")
    for cat, agg in cat_aggregates.items():
        if agg["n_with_expected"] == 0:
            print(f"  {cat}: n={agg['n_questions']}, all expected empty (skipped)")
            continue
        print(
            f"  {cat}: n={agg['n_questions']} (elig={agg['n_with_expected']})  "
            f"P={agg['precision_macro']:.3f}  R={agg['recall_macro']:.3f}  "
            f"F1={agg['f1_macro']:.3f}  Hit={agg['hit_rate_macro']:.3f}  "
            f"Strict={agg['strict_hit_macro']:.3f}  MRR={agg['mrr_macro']:.3f}  "
            f"avg|R|={agg['avg_retrieved_size']:.1f}  "
            f"avg|E|={agg['avg_expected_size']:.1f}"
        )
    print()
    print("T1 vs T6 (T6-T1):")
    for k, v in t1_t6_delta.items():
        if v is None:
            continue
        print(f"  Δ{k}={v:+.3f}")
    print()
    print("Lowest-F1 outliers:")
    for r in outliers_low_f1[:5]:
        print(f"  {r['qid']} [{r['category']}] P={r['precision']:.2f} "
              f"R={r['recall']:.2f} F1={r['f1']:.2f} "
              f"|R|={r['retrieved_size']} |E|={r['expected_size']} "
              f"missing={r['missing_expected']}")


if __name__ == "__main__":
    main()
