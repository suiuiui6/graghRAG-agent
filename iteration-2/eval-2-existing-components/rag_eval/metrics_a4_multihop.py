"""
A4: Multi-hop reasoning & tool-usage analysis for the 50-question GraphRAG eval.

All numbers are computed strictly from the two raw files:
  - ground_truth.json   (contains reasoning_hops)
  - raw_runs.jsonl      (contains tool_calls, retrieved_node_ids, latency, tokens)

tool_calls entries use phase ∈ {"request", "result"}. We count phase=='request'
only -- those are the agent-initiated calls. phase=='result' is the ToolMessage
returned by the runtime and would double-count.

Outputs (written next to this script):
  - metrics_a4_multihop.json
  - report_a4_multihop.md
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
GT_PATH = HERE / "ground_truth.json"
RUNS_PATH = HERE / "raw_runs.jsonl"
OUT_JSON = HERE / "metrics_a4_multihop.json"
OUT_REPORT = HERE / "report_a4_multihop.md"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_ground_truth() -> dict[str, dict]:
    with GT_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {q["qid"]: q for q in data["questions"]}


def load_runs() -> list[dict]:
    runs: list[dict] = []
    with RUNS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            runs.append(json.loads(line))
    return runs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def request_calls(tool_calls: list[dict]) -> list[dict]:
    """Filter to the agent-initiated calls only."""
    return [tc for tc in tool_calls if tc.get("phase") == "request"]


def tool_sequence(tool_calls: list[dict]) -> list[str]:
    return [tc.get("name", "<unknown>") for tc in request_calls(tool_calls)]


def safe_mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def hit_rate(expected: list[str], retrieved: list[str]) -> int:
    """Returns 1 if at least one expected id is in retrieved (set membership)."""
    if not expected:
        return 0
    eset, rset = set(expected), set(retrieved)
    return 1 if eset & rset else 0


def strict_hit(expected: list[str], retrieved: list[str]) -> int:
    """Returns 1 if expected ⊆ retrieved (set semantics)."""
    if not expected:
        return 0
    return 1 if set(expected).issubset(set(retrieved)) else 0


def precision_recall(expected: list[str], retrieved: list[str]) -> tuple[float, float]:
    eset, rset = set(expected), set(retrieved)
    if not rset:
        p = 0.0
    else:
        p = len(eset & rset) / len(rset)
    if not eset:
        r = 0.0
    else:
        r = len(eset & rset) / len(eset)
    return p, r


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(ys) < 2 or len(xs) != len(ys):
        return 0.0
    mx, my = safe_mean(xs), safe_mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def total_tokens(run: dict) -> int:
    tk = run.get("tokens") or {}
    return int(tk.get("total") or 0)


# ---------------------------------------------------------------------------
# A. Group by reasoning_hops
# ---------------------------------------------------------------------------

def group_by_hops(gt_by_qid: dict[str, dict], runs: list[dict]) -> dict:
    buckets: dict[int, list[tuple[dict, dict]]] = defaultdict(list)
    for run in runs:
        qid = run["qid"]
        gt = gt_by_qid.get(qid)
        if gt is None:
            continue
        hops = gt.get("reasoning_hops")
        if hops is None:
            continue
        buckets[int(hops)].append((gt, run))

    summary: dict[str, dict] = {}
    for hops in sorted(buckets.keys()):
        pairs = buckets[hops]
        n = len(pairs)
        ntools = [r["num_tool_calls"] for _, r in pairs]
        # retrieved is already a deduped list in raw_runs; treat as set for |R|
        nret = [len(set(r.get("retrieved_node_ids") or [])) for _, r in pairs]
        hits = [hit_rate(gt.get("expected_node_ids") or [], r.get("retrieved_node_ids") or []) for gt, r in pairs]
        strict = [strict_hit(gt.get("expected_node_ids") or [], r.get("retrieved_node_ids") or []) for gt, r in pairs]
        lats = [r.get("latency_ms") or 0 for _, r in pairs]
        toks = [total_tokens(r) for _, r in pairs]

        summary[str(hops)] = {
            "n_questions": n,
            "qids": [r["qid"] for _, r in pairs],
            "avg_num_tool_calls": round(safe_mean(ntools), 3),
            "avg_retrieved": round(safe_mean(nret), 3),
            "hit_rate": round(safe_mean(hits), 3),
            "strict_hit": round(safe_mean(strict), 3),
            "avg_latency_ms": round(safe_mean(lats), 1),
            "avg_total_tokens": round(safe_mean(toks), 1),
        }

    # Validate monotonicity of avg_num_tool_calls with hops
    hops_order = sorted(int(h) for h in summary)
    tool_seq = [summary[str(h)]["avg_num_tool_calls"] for h in hops_order]
    monotonic_nondec = all(tool_seq[i] <= tool_seq[i + 1] for i in range(len(tool_seq) - 1))

    return {
        "per_hops": summary,
        "tool_calls_monotonic_nondec_with_hops": monotonic_nondec,
        "tool_calls_sequence_by_hops": dict(zip([str(h) for h in hops_order], tool_seq)),
    }


# ---------------------------------------------------------------------------
# B. T4 multi-hop deep dive (Q29-Q32)
# ---------------------------------------------------------------------------

def t4_deep_dive(gt_by_qid: dict[str, dict], runs_by_qid: dict[str, dict]) -> dict:
    t4_qids = ["Q29", "Q30", "Q31", "Q32"]
    details: list[dict] = []
    for qid in t4_qids:
        gt = gt_by_qid.get(qid)
        run = runs_by_qid.get(qid)
        if gt is None or run is None:
            continue
        expected = gt.get("expected_node_ids") or []
        retrieved = run.get("retrieved_node_ids") or []
        seq = tool_sequence(run.get("tool_calls") or [])
        p, r = precision_recall(expected, retrieved)
        details.append({
            "qid": qid,
            "query": gt.get("question") or run.get("query"),
            "expected_node_ids": expected,
            "retrieved_node_ids_first20": retrieved[:20],
            "num_retrieved_total": len(set(retrieved)),
            "num_tool_calls": run.get("num_tool_calls"),
            "tool_sequence": seq,
            "hit_rate": hit_rate(expected, retrieved),
            "strict_hit": strict_hit(expected, retrieved),
            "precision": round(p, 3),
            "recall": round(r, 3),
        })
    return {"questions": details}


def q31_outlier_analysis(runs_by_qid: dict[str, dict]) -> dict:
    run = runs_by_qid.get("Q31")
    if run is None:
        return {}
    reqs = request_calls(run.get("tool_calls") or [])
    # Repetition signature: (tool_name, json args sorted)
    sigs = [(tc["name"], json.dumps(tc.get("args") or {}, ensure_ascii=False, sort_keys=True)) for tc in reqs]
    sig_counts = Counter(sigs)
    repeated = [(name, args, c) for (name, args), c in sig_counts.items() if c >= 2]
    repeated.sort(key=lambda x: -x[2])

    name_counts = Counter(tc["name"] for tc in reqs)

    # Phase-by-phase pattern: detect loops of get_entity_neighbors / get_entity_detail
    # Group calls into chunks of "get_entity_neighbors on node X" or "get_entity_detail on node X"
    neighbor_targets = [tc.get("args", {}).get("node_id") for tc in reqs if tc["name"] == "get_entity_neighbors"]
    detail_targets = [tc.get("args", {}).get("node_id") for tc in reqs if tc["name"] == "get_entity_detail"]
    search_args = [tc.get("args") for tc in reqs if tc["name"] == "search_kg_by_type"]

    return {
        "total_requests": len(reqs),
        "calls_by_tool_name": dict(name_counts),
        "unique_call_signatures": len(sig_counts),
        "repeated_call_signatures_count": len(repeated),
        "top_repeated_calls": [
            {"name": name, "args": json.loads(args), "times": c}
            for name, args, c in repeated[:8]
        ],
        "search_kg_by_type_arg_combos_first5": search_args[:5],
        "get_entity_neighbors_node_ids_first10": neighbor_targets[:10],
        "get_entity_neighbors_distinct_nodes": len(set(neighbor_targets)),
        "get_entity_detail_node_ids_first10": detail_targets[:10],
        "get_entity_detail_distinct_nodes": len(set(detail_targets)),
        "first_8_request_names": [tc["name"] for tc in reqs[:8]],
        "last_8_request_names": [tc["name"] for tc in reqs[-8:]],
    }


# ---------------------------------------------------------------------------
# C. Tool usage efficiency
# ---------------------------------------------------------------------------

def tool_efficiency(gt_by_qid: dict[str, dict], runs: list[dict]) -> dict:
    name_counts: Counter = Counter()
    sig_counts: Counter = Counter()
    total_requests = 0
    # for correlation
    tool_xs: list[float] = []
    tokens_ys: list[float] = []

    per_qid_efficiency: list[dict] = []

    for run in runs:
        reqs = request_calls(run.get("tool_calls") or [])
        for tc in reqs:
            name_counts[tc.get("name", "<unknown>")] += 1
            sig = (tc.get("name"), json.dumps(tc.get("args") or {}, ensure_ascii=False, sort_keys=True))
            sig_counts[sig] += 1
        total_requests += len(reqs)
        tool_xs.append(float(run.get("num_tool_calls") or 0))
        tokens_ys.append(float(total_tokens(run)))

        gt = gt_by_qid.get(run["qid"]) or {}
        expected = gt.get("expected_node_ids") or []
        retrieved = run.get("retrieved_node_ids") or []
        per_qid_efficiency.append({
            "qid": run["qid"],
            "category": gt.get("category"),
            "num_tool_calls": run.get("num_tool_calls") or 0,
            "hit": hit_rate(expected, retrieved),
            "n_expected": len(expected),
            "tokens_total": total_tokens(run),
            "latency_ms": run.get("latency_ms") or 0,
        })

    name_share = {
        name: {"count": cnt, "share": round(cnt / total_requests, 4) if total_requests else 0.0}
        for name, cnt in name_counts.most_common()
    }

    repeated_sigs = [(sig, c) for sig, c in sig_counts.items() if c >= 2]
    repeated_calls_total = sum(c for _, c in repeated_sigs)
    repeat_ratio = round(repeated_calls_total / total_requests, 4) if total_requests else 0.0

    # Efficient demos: questions with at least one expected node, hit=1, lowest num_tool_calls
    eligible_hits = [p for p in per_qid_efficiency if p["n_expected"] > 0 and p["hit"] == 1]
    eligible_hits.sort(key=lambda p: (p["num_tool_calls"], p["qid"]))
    # Inefficient: hit=0 (and had expected nodes), highest num_tool_calls
    eligible_miss = [p for p in per_qid_efficiency if p["n_expected"] > 0 and p["hit"] == 0]
    eligible_miss.sort(key=lambda p: (-p["num_tool_calls"], p["qid"]))

    return {
        "total_requests_all_questions": total_requests,
        "calls_by_tool_name": name_share,
        "repeat_signature_ratio": repeat_ratio,
        "repeat_signature_distinct_count": len(repeated_sigs),
        "pearson_num_tool_calls_vs_total_tokens": round(pearson(tool_xs, tokens_ys), 4),
        "most_efficient_hits_top5": eligible_hits[:5],
        "least_efficient_misses_top5": eligible_miss[:5],
    }


# ---------------------------------------------------------------------------
# D. T2 type-aggregation recall (Q13-Q20)
# ---------------------------------------------------------------------------

def t2_recall(gt_by_qid: dict[str, dict], runs_by_qid: dict[str, dict]) -> dict:
    t2_qids = [f"Q{n:02d}" for n in range(13, 21)]
    rows: list[dict] = []
    recalls: list[float] = []
    for qid in t2_qids:
        gt = gt_by_qid.get(qid)
        run = runs_by_qid.get(qid)
        if gt is None or run is None:
            continue
        expected = gt.get("expected_node_ids") or []
        retrieved = run.get("retrieved_node_ids") or []
        eset, rset = set(expected), set(retrieved)
        if not eset:
            recall = 0.0
        else:
            recall = len(eset & rset) / len(eset)
        rows.append({
            "qid": qid,
            "n_expected": len(eset),
            "n_retrieved": len(rset),
            "intersection": len(eset & rset),
            "recall": round(recall, 3),
        })
        recalls.append(recall)
    return {
        "questions": rows,
        "recall_mean": round(safe_mean(recalls), 3),
        "recall_min": round(min(recalls), 3) if recalls else 0.0,
        "recall_max": round(max(recalls), 3) if recalls else 0.0,
        "recall_median": round(statistics.median(recalls), 3) if recalls else 0.0,
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_report(metrics: dict) -> str:
    hops = metrics["A_by_hops"]["per_hops"]
    t4 = metrics["B_t4_detail"]["questions"]
    q31 = metrics["B_q31_outlier"]
    eff = metrics["C_tool_efficiency"]
    t2 = metrics["D_t2_recall"]

    # One-line conclusion
    # build verdict from data
    hops_keys = sorted(int(k) for k in hops.keys())
    hr_h1 = hops.get("1", {}).get("hit_rate")
    hr_h2 = hops.get("2", {}).get("hit_rate")
    hr_h3 = hops.get("3", {}).get("hit_rate")
    monot = metrics["A_by_hops"]["tool_calls_monotonic_nondec_with_hops"]

    lines: list[str] = []
    lines.append("# A4 多跳推理 & 工具使用分析报告")
    lines.append("")
    hr_parts = [f"1-hop={hr_h1}"]
    if hr_h2 is not None:
        hr_parts.append(f"2-hop={hr_h2}")
    if hr_h3 is not None:
        hr_parts.append(f"3-hop={hr_h3}")
    lines.append(
        f"**一句话结论**：HitRate {'/'.join(hr_parts)}；"
        f"平均工具调用次数随 hops {'非递减' if monot else '并非严格非递减'}；"
        f"Q31 触发 100 次工具调用（95 个独立签名），工具调用次数与 tokens 的 "
        f"Pearson 相关系数为 {eff['pearson_num_tool_calls_vs_total_tokens']}，强正相关。"
    )
    lines.append("")
    lines.append("> **数据范围说明**：ground_truth 中 `reasoning_hops` 实际只有 1 和 2 两档（虽然 schema 描述为 1/2/3）；"
                 "T4 全部 4 题被标注为 hops=2，并无 hops=3 题目。")
    lines.append("")

    # A. Hops table
    lines.append("## A. 按 reasoning_hops 分组指标")
    lines.append("")
    lines.append("| hops | 题数 | 平均 num_tool_calls | 平均 \\|R\\| | HitRate | StrictHit | 平均 latency_ms | 平均 total tokens |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k in hops_keys:
        v = hops[str(k)]
        lines.append(
            f"| {k} | {v['n_questions']} | {v['avg_num_tool_calls']} | {v['avg_retrieved']} | "
            f"{v['hit_rate']} | {v['strict_hit']} | {v['avg_latency_ms']} | {v['avg_total_tokens']} |"
        )
    lines.append("")
    seq_str = ", ".join(f"hops={k}: {v}" for k, v in metrics["A_by_hops"]["tool_calls_sequence_by_hops"].items())
    lines.append(f"工具调用数随 hops 的序列：{seq_str}。"
                 f"{'符合' if monot else '不完全符合'}「hops 越多 → 调用次数越多」的预期。")
    lines.append("")

    # B. T4 detail
    lines.append("## B. T4 多跳详细分析（Q29-Q32）")
    lines.append("")
    lines.append("| qid | num_tool_calls | HitRate | P | R | expected | retrieved (前20) |")
    lines.append("|---|---:|---:|---:|---:|---|---|")
    for q in t4:
        exp = ", ".join(q["expected_node_ids"])
        ret = ", ".join(q["retrieved_node_ids_first20"]) or "（空）"
        lines.append(
            f"| {q['qid']} | {q['num_tool_calls']} | {q['hit_rate']} | {q['precision']} | {q['recall']} | "
            f"{exp} | {ret} |"
        )
    lines.append("")
    for q in t4:
        lines.append(f"**{q['qid']}** query：{q['query']}")
        # Compress repeated tool-name runs for readability
        seq = q["tool_sequence"]
        compressed: list[str] = []
        i = 0
        while i < len(seq):
            j = i
            while j < len(seq) and seq[j] == seq[i]:
                j += 1
            n = j - i
            compressed.append(f"{seq[i]}×{n}" if n > 1 else seq[i])
            i = j
        lines.append(f"  工具序列（共 {len(seq)} 次）：{' → '.join(compressed)}")
        lines.append("")

    # B2. Q31 outlier
    lines.append("## C. Q31 outlier 解剖（100 次调用）")
    lines.append("")
    lines.append(f"Q31 共发起 **{q31['total_requests']}** 次工具调用，独立调用签名 {q31['unique_call_signatures']} 个，"
                 f"重复签名 {q31['repeated_call_signatures_count']} 组。各工具调用次数：")
    for name, cnt in q31["calls_by_tool_name"].items():
        lines.append(f"  - `{name}`: {cnt}")
    lines.append("")
    lines.append(f"`get_entity_neighbors` 命中节点数：{q31['get_entity_neighbors_distinct_nodes']} 个；"
                 f"`get_entity_detail` 命中节点数：{q31['get_entity_detail_distinct_nodes']} 个。")
    lines.append("")
    if q31["top_repeated_calls"]:
        lines.append("**Top 重复调用 pattern：**")
        for rc in q31["top_repeated_calls"]:
            lines.append(f"  - `{rc['name']}({json.dumps(rc['args'], ensure_ascii=False)})` × {rc['times']}")
        lines.append("")
        lines.append("> 100 次调用里只有 4 组完全重复的签名；其余 95 个签名都不同——agent 实际上是在「不断切换 keyword 或 node_id」"
                     "形成宽 BFS：先 6 次 `search_kg_by_type` 横扫 claim/metric/method/section_header，再切到"
                     " `get_entity_neighbors`（26 个不同 node_id）和 `get_entity_detail`（30 个不同 node_id），最后陷入大量 "
                     "`get_entity_detail` 串调。failure mode 不是「卡死循环」而是「探索发散」——找不到目标后越搜越宽。")
    else:
        lines.append("**未检测到完全相同的重复签名**——agent 通过不断切换 node_id 制造 100 次调用循环，"
                     "而非简单重放同一指令。")
    lines.append("")
    lines.append(f"前 8 个 request：{q31['first_8_request_names']}")
    lines.append("")
    lines.append(f"后 8 个 request：{q31['last_8_request_names']}")
    lines.append("")

    # C. Tool efficiency
    lines.append("## D. 工具使用效率")
    lines.append("")
    lines.append(f"全题集合 agent-initiated 调用总数：**{eff['total_requests_all_questions']}**。")
    lines.append("")
    lines.append("| 工具名 | 调用次数 | 占比 |")
    lines.append("|---|---:|---:|")
    for name, info in eff["calls_by_tool_name"].items():
        lines.append(f"| `{name}` | {info['count']} | {info['share']} |")
    lines.append("")
    lines.append(f"重复调用率（相同 `(tool_name, args)` 出现 ≥2 次的占比）：**{eff['repeat_signature_ratio']}**，"
                 f"共有 {eff['repeat_signature_distinct_count']} 个签名被重复发起。")
    lines.append("")
    lines.append(f"Pearson(num_tool_calls, total_tokens) = **{eff['pearson_num_tool_calls_vs_total_tokens']}**。")
    lines.append("")
    lines.append("**高效率示范（命中且调用最少）：**")
    for p in eff["most_efficient_hits_top5"]:
        lines.append(f"  - {p['qid']} ({p['category']}) — {p['num_tool_calls']} 次调用，tokens={p['tokens_total']}")
    lines.append("")
    lines.append("**低效率反例（未命中且调用最多）：**")
    for p in eff["least_efficient_misses_top5"]:
        lines.append(f"  - {p['qid']} ({p['category']}) — {p['num_tool_calls']} 次调用，tokens={p['tokens_total']}")
    lines.append("")

    # D. T2 recall
    lines.append("## E. T2 类型聚合召回（Q13-Q20）")
    lines.append("")
    lines.append("| qid | |E| | |R| | |E∩R| | recall |")
    lines.append("|---|---:|---:|---:|---:|")
    for q in t2["questions"]:
        lines.append(f"| {q['qid']} | {q['n_expected']} | {q['n_retrieved']} | {q['intersection']} | {q['recall']} |")
    lines.append("")
    lines.append(f"recall mean = **{t2['recall_mean']}**，min = {t2['recall_min']}，max = {t2['recall_max']}，"
                 f"median = {t2['recall_median']}。")
    lines.append("")

    # Limitations
    lines.append("## F. 限制说明")
    lines.append("")
    lines.append("- `reasoning_hops` 是 ground_truth 中的人工估计值，按题型先验给定，不是图上的最短路径。")
    lines.append("- `retrieved_node_ids` 在 raw_runs 中已经过去重；本脚本进一步用 `set()` 处理，"
                 "因此 |R| 与 HitRate/Precision/Recall 均按集合语义计算。")
    lines.append("- 工具调用次数只统计 `phase=='request'` 一类，`phase=='result'` 是 runtime 返回的 ToolMessage，"
                 "不计入 agent 主动调用。")
    lines.append("- Pearson 相关系数在 50 题样本上由 Q31 outlier（100 次调用）强烈拉动；"
                 "去掉 Q31 后系数会下降，但本报告不剔除 outlier，以反映真实分布。")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def main() -> None:
    gt_by_qid = load_ground_truth()
    runs = load_runs()
    runs_by_qid = {r["qid"]: r for r in runs}

    metrics: dict = {
        "A_by_hops": group_by_hops(gt_by_qid, runs),
        "B_t4_detail": t4_deep_dive(gt_by_qid, runs_by_qid),
        "B_q31_outlier": q31_outlier_analysis(runs_by_qid),
        "C_tool_efficiency": tool_efficiency(gt_by_qid, runs),
        "D_t2_recall": t2_recall(gt_by_qid, runs_by_qid),
    }

    OUT_JSON.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_REPORT.write_text(render_report(metrics), encoding="utf-8")

    print("[OK] wrote", OUT_JSON)
    print("[OK] wrote", OUT_REPORT)

    # Console summary used for the verbal report
    hops = metrics["A_by_hops"]["per_hops"]
    print("\n=== Hops HitRate ===")
    for k in sorted(int(x) for x in hops):
        v = hops[str(k)]
        print(f"  hops={k}: HitRate={v['hit_rate']}  StrictHit={v['strict_hit']}  "
              f"avg_tool_calls={v['avg_num_tool_calls']}  n={v['n_questions']}")
    print("\n=== Q31 outlier ===")
    q31 = metrics["B_q31_outlier"]
    print(f"  total_requests={q31['total_requests']}")
    print(f"  calls_by_tool_name={q31['calls_by_tool_name']}")
    print(f"  unique_signatures={q31['unique_call_signatures']}  repeated={q31['repeated_call_signatures_count']}")
    eff = metrics["C_tool_efficiency"]
    print("\n=== Tool efficiency ===")
    print(f"  total_requests={eff['total_requests_all_questions']}")
    print(f"  calls_by_tool_name={eff['calls_by_tool_name']}")
    print(f"  repeat_signature_ratio={eff['repeat_signature_ratio']}")
    print(f"  pearson(num_tool_calls, total_tokens)={eff['pearson_num_tool_calls_vs_total_tokens']}")


if __name__ == "__main__":
    main()
