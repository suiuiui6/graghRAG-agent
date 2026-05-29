"""Compute answer-layer faithfulness / anti-hallucination metrics (A2)
for the GraphRAG eval.

Inputs
------
- ground_truth.json (questions list with expected_keywords, forbidden_keywords,
  should_refuse, category, ...).
- raw_runs.jsonl (one JSON record per line, fields: qid, category,
  final_answer, answer_node_ids, retrieved_node_ids, ...).
- nodes.json (KG node dump with shape {"metadata":..., "node_count":N,
  "nodes":[{"node_id":..., ...}, ...]}).

Outputs
-------
- metrics_a2_faithfulness.json — structured metrics with per_question +
  per_category + global aggregates, plus hallucinated-id and
  forbidden-keyword inventories.
- report_a2_faithfulness.md — Chinese human-readable report.

Deterministic rules (NO LLM):
  Let A_ids = set(answer_node_ids), R_ids = set(retrieved_node_ids),
  KG = set of all node_ids in nodes.json. Let answer = final_answer string,
  answer_lower = answer.lower().

  - node_id_validity (per Q)     = 1 if A_ids ⊆ KG  else 0.
                                   If A_ids is empty, define as None
                                   (vacuously true, excluded from macro avg).
  - hallucinated_node_ids        = sorted list of A_ids - KG.
  - cited_in_retrieved_rate      = |A_ids ∩ R_ids| / |A_ids|   if |A_ids|>0
                                   else None. Measures "answer cites only
                                   nodes the agent actually retrieved".
  - keyword_coverage             = (#expected_keywords found in answer) /
                                   |expected_keywords|. Matching:
                                     • lowercase both sides for ASCII tokens
                                     • a keyword is "found" iff
                                       keyword.lower() in answer.lower()
                                       (substring match; Chinese strings
                                       pass through .lower() unchanged).
                                   None if expected_keywords is empty.
  - forbidden_violation          = 1 if ANY forbidden_keyword appears in
                                   answer (same .lower() substring rule),
                                   else 0. None if forbidden_keywords empty.
  - forbidden_hits               = list of forbidden keywords that actually
                                   appeared.
  - refusal_for_t5 (T5 only)     = 1 if answer contains ANY of the refusal
                                   markers in REFUSAL_TOKENS else 0. For
                                   non-T5 questions: None.

Aggregation
-----------
Macro average per category (skip None values). Global = macro across all
questions where each metric is defined. We also report support counts.

Run with project venv:
    D:/graghRAG-agent/backend/.venv/Scripts/python.exe \
        D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

EVAL_DIR = Path(r"D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval")
KG_DIR = Path(r"D:/graghRAG-agent/backend/output/kg/doc_ingest_232e1611")
GT_PATH = EVAL_DIR / "ground_truth.json"
RUNS_PATH = EVAL_DIR / "raw_runs.jsonl"
NODES_PATH = KG_DIR / "nodes.json"
OUT_JSON = EVAL_DIR / "metrics_a2_faithfulness.json"
OUT_MD = EVAL_DIR / "report_a2_faithfulness.md"

# Tokens that signal a refusal / unknown-answer. Matched as substrings on
# the lowercased final_answer (Chinese passes through .lower() unchanged).
REFUSAL_TOKENS = [
    "不包含",
    "没有",
    "无法",
    "未提及",
    "未涉及",
    "无关",
    "无相关",
    "不相关",
    "not contain",
    "no information",
    "unable",
    # Note: the user's spec lists bare "无" but it is extremely common in
    # Chinese text and would over-trigger. We rely on the longer phrases
    # ("无法", "无关", "无相关") which the spec also lists. Plain "无" is
    # tested as a fallback only if none of the more specific phrases hit
    # (see _is_refusal).
]

# Fallback single-character marker. Only consulted if no specific phrase hit.
REFUSAL_FALLBACK = "无"


def _load_json(p: Path) -> Any:
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(p: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _macro(values: list[float | int | None]) -> float | None:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return None
    return statistics.fmean(vals)


def _keyword_hits(keywords: list[str], answer: str) -> tuple[list[str], list[str]]:
    """Return (found_keywords, missing_keywords). Case-insensitive substring."""
    answer_low = answer.lower()
    found: list[str] = []
    missing: list[str] = []
    for kw in keywords:
        if kw.lower() in answer_low:
            found.append(kw)
        else:
            missing.append(kw)
    return found, missing


def _is_refusal(answer: str) -> tuple[bool, list[str]]:
    """Return (refused, matched_markers)."""
    answer_low = answer.lower()
    matched = [tok for tok in REFUSAL_TOKENS if tok.lower() in answer_low]
    if matched:
        return True, matched
    if REFUSAL_FALLBACK in answer:
        return True, [REFUSAL_FALLBACK]
    return False, []


def _answer_snippet(answer: str, anchor: str | None = None, width: int = 60) -> str:
    """Return up to `width*2+len(anchor)` chars of context around anchor.

    If anchor not found (or None), returns the first `width*2` chars.
    """
    if not answer:
        return ""
    if anchor:
        idx = answer.find(anchor)
        if idx >= 0:
            start = max(0, idx - width)
            end = min(len(answer), idx + len(anchor) + width)
            s = answer[start:end].replace("\n", " ")
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(answer) else ""
            return f"{prefix}{s}{suffix}"
    s = answer[: width * 2].replace("\n", " ")
    return s + ("…" if len(answer) > width * 2 else "")


def per_question_metrics(
    q: dict[str, Any], run: dict[str, Any], kg_ids: set[str]
) -> dict[str, Any]:
    answer = run.get("final_answer") or ""
    a_ids = list(run.get("answer_node_ids") or [])
    r_ids = list(run.get("retrieved_node_ids") or [])
    a_set = set(a_ids)
    r_set = set(r_ids)

    # --- node_id_validity & hallucination ---
    halluc = sorted(a_set - kg_ids)
    if a_set:
        node_id_validity: int | None = 0 if halluc else 1
    else:
        node_id_validity = None

    # --- cited_in_retrieved_rate ---
    if a_set:
        cited_in_retrieved_rate: float | None = len(a_set & r_set) / len(a_set)
        uncited = sorted(a_set - r_set)
    else:
        cited_in_retrieved_rate = None
        uncited = []

    # --- keyword_coverage ---
    expected_kw = list(q.get("expected_keywords") or [])
    if expected_kw:
        found_kw, missing_kw = _keyword_hits(expected_kw, answer)
        keyword_coverage: float | None = len(found_kw) / len(expected_kw)
    else:
        found_kw, missing_kw = [], []
        keyword_coverage = None

    # --- forbidden_violation ---
    forbidden = list(q.get("forbidden_keywords") or [])
    if forbidden:
        forbidden_hits, _ = _keyword_hits(forbidden, answer)
        forbidden_violation: int | None = 1 if forbidden_hits else 0
    else:
        forbidden_hits = []
        forbidden_violation = None

    # --- refusal_for_t5 ---
    category = q.get("category")
    if category == "T5":
        refused, refusal_markers = _is_refusal(answer)
        refusal_for_t5: int | None = 1 if refused else 0
    else:
        refused = False
        refusal_markers = []
        refusal_for_t5 = None

    return {
        "qid": q["qid"],
        "category": category,
        "question": q["question"],
        "should_refuse": q.get("should_refuse", False),
        "answer_len_chars": len(answer),
        "answer_node_ids": a_ids,
        "retrieved_node_ids_size": len(r_set),
        "hallucinated_node_ids": halluc,
        "node_id_validity": node_id_validity,
        "cited_in_retrieved_rate": cited_in_retrieved_rate,
        "uncited_in_retrieved": uncited,
        "expected_keywords": expected_kw,
        "keyword_found": found_kw,
        "keyword_missing": missing_kw,
        "keyword_coverage": keyword_coverage,
        "forbidden_keywords": forbidden,
        "forbidden_hits": forbidden_hits,
        "forbidden_violation": forbidden_violation,
        "refusal_for_t5": refusal_for_t5,
        "refusal_markers_matched": refusal_markers,
        "answer_snippet": _answer_snippet(answer),
    }


def _agg_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Macro average each metric over rows where the metric is defined."""
    keys = [
        "node_id_validity",
        "cited_in_retrieved_rate",
        "keyword_coverage",
        "forbidden_violation",
        "refusal_for_t5",
    ]
    agg: dict[str, Any] = {"n_questions": len(rows)}
    for k in keys:
        defined = [r[k] for r in rows if r[k] is not None]
        agg[f"{k}_macro"] = statistics.fmean(defined) if defined else None
        agg[f"{k}_support"] = len(defined)
    # Hallucination summary
    halluc_qids = [r["qid"] for r in rows if r["hallucinated_node_ids"]]
    agg["n_questions_with_hallucination"] = len(halluc_qids)
    agg["hallucination_rate"] = (
        len(halluc_qids) / len(rows) if rows else None
    )
    return agg


def main() -> None:
    gt = _load_json(GT_PATH)
    runs = _load_jsonl(RUNS_PATH)

    nodes_blob = _load_json(NODES_PATH)
    nodes_list = nodes_blob.get("nodes") if isinstance(nodes_blob, dict) else nodes_blob
    kg_ids: set[str] = {n["node_id"] for n in nodes_list}
    if len(kg_ids) != nodes_blob.get("node_count", len(kg_ids)):
        # Just a sanity log; don't crash.
        pass

    runs_by_qid = {r["qid"]: r for r in runs}
    per_question: list[dict[str, Any]] = []
    missing_in_runs: list[str] = []
    for q in gt["questions"]:
        run = runs_by_qid.get(q["qid"])
        if run is None:
            missing_in_runs.append(q["qid"])
            continue
        per_question.append(per_question_metrics(q, run, kg_ids))

    # Per category + global
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for r in per_question:
        by_cat.setdefault(r["category"], []).append(r)
    per_category = {cat: _agg_block(rows) for cat, rows in sorted(by_cat.items())}
    global_agg = _agg_block(per_question)

    # Hallucination inventory
    halluc_inventory: list[dict[str, Any]] = []
    for r in per_question:
        for nid in r["hallucinated_node_ids"]:
            halluc_inventory.append(
                {
                    "qid": r["qid"],
                    "category": r["category"],
                    "hallucinated_node_id": nid,
                    "answer_snippet": _answer_snippet(
                        # Re-pull the answer from runs to anchor on the nid
                        runs_by_qid[r["qid"]].get("final_answer", "") or "",
                        anchor=nid,
                    ),
                }
            )

    # Forbidden inventory
    forbidden_inventory = [
        {
            "qid": r["qid"],
            "category": r["category"],
            "forbidden_hits": r["forbidden_hits"],
            "answer_snippet": _answer_snippet(
                runs_by_qid[r["qid"]].get("final_answer", "") or "",
                anchor=r["forbidden_hits"][0] if r["forbidden_hits"] else None,
            ),
        }
        for r in per_question
        if r["forbidden_violation"] == 1
    ]

    # Lowest keyword_coverage (only Qs where it's defined)
    kw_eligible = [r for r in per_question if r["keyword_coverage"] is not None]
    kw_eligible.sort(key=lambda r: (r["keyword_coverage"], r["qid"]))
    lowest_keyword_coverage = [
        {
            "qid": r["qid"],
            "category": r["category"],
            "question": r["question"],
            "keyword_coverage": r["keyword_coverage"],
            "expected_keywords": r["expected_keywords"],
            "keyword_found": r["keyword_found"],
            "keyword_missing": r["keyword_missing"],
        }
        for r in kw_eligible[:5]
    ]

    # T5 refusal detail
    t5_table = [
        {
            "qid": r["qid"],
            "question": r["question"],
            "refusal_for_t5": r["refusal_for_t5"],
            "refusal_markers_matched": r["refusal_markers_matched"],
            "answer_snippet": r["answer_snippet"],
        }
        for r in per_question
        if r["category"] == "T5"
    ]

    out: dict[str, Any] = {
        "_meta": {
            "ground_truth_path": str(GT_PATH),
            "raw_runs_path": str(RUNS_PATH),
            "nodes_path": str(NODES_PATH),
            "n_gt_questions": len(gt["questions"]),
            "n_run_records": len(runs),
            "kg_node_count": len(kg_ids),
            "missing_in_runs": missing_in_runs,
            "refusal_tokens": REFUSAL_TOKENS + [REFUSAL_FALLBACK + " (fallback)"],
            "metric_definitions": {
                "node_id_validity":
                    "1 iff every id in answer_node_ids exists in nodes.json; "
                    "None when answer cites no node ids.",
                "hallucinated_node_ids":
                    "answer_node_ids - KG-ids.",
                "cited_in_retrieved_rate":
                    "|answer_ids ∩ retrieved_ids| / |answer_ids|; None when "
                    "answer cites no node ids.",
                "keyword_coverage":
                    "fraction of expected_keywords found as case-insensitive "
                    "substrings in final_answer.",
                "forbidden_violation":
                    "1 iff ANY forbidden keyword appears (lowercased substring) "
                    "in final_answer; None when forbidden_keywords is empty.",
                "refusal_for_t5":
                    "1 iff final_answer contains any of: " + ", ".join(REFUSAL_TOKENS)
                    + " (fallback marker: '无'). Computed only for T5; None otherwise.",
            },
            "aggregation": "Macro average per category across questions where "
                            "each metric is defined. None values are skipped.",
        },
        "global": global_agg,
        "by_category": per_category,
        "hallucinated_node_id_inventory": halluc_inventory,
        "forbidden_violation_inventory": forbidden_inventory,
        "lowest_keyword_coverage_top5": lowest_keyword_coverage,
        "t5_refusal_table": t5_table,
        "per_question": per_question,
    }
    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # --- Markdown report -----------------------------------------------------
    md_lines: list[str] = []
    md_lines.append("# A2 答案忠实度 / 抗幻觉报告")
    md_lines.append("")
    # one-line conclusion
    g = global_agg
    nv = g["node_id_validity_macro"]
    cr = g["cited_in_retrieved_rate_macro"]
    kc = g["keyword_coverage_macro"]
    fv = g["forbidden_violation_macro"]
    refuse_cat = per_category.get("T5", {})
    refuse_rate = refuse_cat.get("refusal_for_t5_macro")
    fv_str = "无数据" if fv is None else f"{fv:.0%}"
    refuse_str = "无数据" if refuse_rate is None else f"{refuse_rate:.0%}"
    md_lines.append(
        f"**一句话结论**：在 50 题样本中，answer-side node id 合法率 "
        f"{nv:.0%}（{g['node_id_validity_support']} 题有引用），"
        f"answer→retrieved 引用一致率 {cr:.0%}，"
        f"expected keyword 覆盖率 {kc:.0%}（共 "
        f"{g['keyword_coverage_support']} 题），"
        f"forbidden keyword 违规率 {fv_str}，"
        f"T5 拒答关键词命中率 {refuse_str}。"
    )
    md_lines.append("")

    # global table
    md_lines.append("## 全局指标 (macro avg, 仅统计该指标有定义的题目)")
    md_lines.append("")
    md_lines.append("| 指标 | 全局值 | 有效题数 |")
    md_lines.append("| --- | --- | --- |")
    def _fmt(v: float | None) -> str:
        return "—" if v is None else f"{v:.3f}"
    md_lines.append(f"| node_id_validity | {_fmt(g['node_id_validity_macro'])} | {g['node_id_validity_support']} |")
    md_lines.append(f"| cited_in_retrieved_rate | {_fmt(g['cited_in_retrieved_rate_macro'])} | {g['cited_in_retrieved_rate_support']} |")
    md_lines.append(f"| keyword_coverage | {_fmt(g['keyword_coverage_macro'])} | {g['keyword_coverage_support']} |")
    md_lines.append(f"| forbidden_violation | {_fmt(g['forbidden_violation_macro'])} | {g['forbidden_violation_support']} |")
    md_lines.append(f"| refusal_for_t5 | {_fmt(g['refusal_for_t5_macro'])} | {g['refusal_for_t5_support']} |")
    md_lines.append(f"| 含幻觉 node_id 题数 / 总数 | {g['n_questions_with_hallucination']} / {g['n_questions']} | — |")
    md_lines.append("")

    md_lines.append("### 各 category 拆解")
    md_lines.append("")
    md_lines.append(
        "| Cat | n | node_id_valid | cited_in_retr | kw_cov | "
        "forbidden_viol | refusal_T5 | 幻觉题数 |"
    )
    md_lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for cat, agg in per_category.items():
        md_lines.append(
            f"| {cat} | {agg['n_questions']} | "
            f"{_fmt(agg['node_id_validity_macro'])} ({agg['node_id_validity_support']}) | "
            f"{_fmt(agg['cited_in_retrieved_rate_macro'])} ({agg['cited_in_retrieved_rate_support']}) | "
            f"{_fmt(agg['keyword_coverage_macro'])} ({agg['keyword_coverage_support']}) | "
            f"{_fmt(agg['forbidden_violation_macro'])} ({agg['forbidden_violation_support']}) | "
            f"{_fmt(agg['refusal_for_t5_macro'])} ({agg['refusal_for_t5_support']}) | "
            f"{agg['n_questions_with_hallucination']} |"
        )
    md_lines.append("")

    # Hallucinated node id inventory
    md_lines.append("## 幻觉 node_id 清单")
    md_lines.append("")
    if not halluc_inventory:
        md_lines.append("无：所有 answer 引用的 node_id 均存在于 KG (439 节点) 中。")
    else:
        md_lines.append("| qid | category | hallucinated_node_id | answer 片段 |")
        md_lines.append("| --- | --- | --- | --- |")
        for item in halluc_inventory:
            snippet = item["answer_snippet"].replace("|", "\\|")
            md_lines.append(
                f"| {item['qid']} | {item['category']} | "
                f"`{item['hallucinated_node_id']}` | {snippet} |"
            )
    md_lines.append("")

    # Lowest keyword coverage
    md_lines.append("## keyword_coverage 最低的 5 题")
    md_lines.append("")
    if not lowest_keyword_coverage:
        md_lines.append("无：没有题目带 expected_keywords。")
    else:
        md_lines.append("| qid | cat | coverage | 命中 | 缺失 | 问题 |")
        md_lines.append("| --- | --- | --- | --- | --- | --- |")
        for r in lowest_keyword_coverage:
            md_lines.append(
                f"| {r['qid']} | {r['category']} | "
                f"{r['keyword_coverage']:.2f} | "
                f"{', '.join(r['keyword_found']) or '—'} | "
                f"{', '.join(r['keyword_missing']) or '—'} | "
                f"{r['question'].replace('|', '\\|')} |"
            )
    md_lines.append("")

    # Forbidden violations
    md_lines.append("## forbidden_keywords 违规清单")
    md_lines.append("")
    if not forbidden_inventory:
        md_lines.append("无：所有定义了 forbidden_keywords 的题目均未触发。")
    else:
        md_lines.append("| qid | category | 命中 forbidden | answer 片段 |")
        md_lines.append("| --- | --- | --- | --- |")
        for item in forbidden_inventory:
            snippet = item["answer_snippet"].replace("|", "\\|")
            md_lines.append(
                f"| {item['qid']} | {item['category']} | "
                f"{', '.join(item['forbidden_hits'])} | {snippet} |"
            )
    md_lines.append("")

    # T5 table
    md_lines.append("## T5 拒答关键词命中表 (10 题)")
    md_lines.append("")
    md_lines.append("| qid | refused (1/0) | 命中的拒答词 | answer 片段 | 问题 |")
    md_lines.append("| --- | --- | --- | --- | --- |")
    # join with question text
    gt_by_qid = {q["qid"]: q for q in gt["questions"]}
    for item in t5_table:
        markers = ", ".join(item["refusal_markers_matched"]) if item["refusal_markers_matched"] else "—"
        snippet = item["answer_snippet"].replace("|", "\\|")
        qtext = gt_by_qid[item["qid"]]["question"].replace("|", "\\|")
        md_lines.append(
            f"| {item['qid']} | {item['refusal_for_t5']} | "
            f"{markers} | {snippet} | {qtext} |"
        )
    md_lines.append("")

    # Limitations
    md_lines.append("## 局限性")
    md_lines.append("")
    md_lines.append(
        "- 所有判定均为 **确定性字符串规则**，不调用 LLM。这避免了二次"
        "幻觉与评测漂移，但也意味着：(1) keyword_coverage 只反映"
        "字面命中，answer 用同义词或换序表述会被低估；(2) forbidden_violation"
        "同样按字面匹配，若 answer 用别名规避将无法捕获。"
    )
    md_lines.append(
        "- 拒答检测使用关键词集合（不包含/没有/无法/未提及/未涉及/无关/not contain/no information/unable，"
        "并以单字符 '无' 作为兜底）。中文 '无' 易触发误报，因此先尝试更长的短语；"
        "若仍未命中再回退到 '无'。这是一种 **召回优先** 的策略，可能高估真实拒答率。"
    )
    md_lines.append(
        "- node_id_validity 仅检查 ID 是否存在于 KG，**不**验证该 node 的内容"
        "是否与 answer 中的事实陈述吻合。即使 ID 合法，回答也可能错误归因。"
    )
    md_lines.append(
        "- cited_in_retrieved_rate 衡量 answer 引用的节点是否经过 retriever，"
        "但只有 retrieved_node_ids 包含了 agent 在所有 tool_calls 中累计返回的节点，"
        "并非 retriever 的相关性排序结果。"
    )
    md_lines.append(
        "- 仅 5 题定义了 forbidden_keywords，T5 共 10 题，样本量小，比率波动较大。"
    )
    md_lines.append("")

    with OUT_MD.open("w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # --- Console summary -----------------------------------------------------
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print()
    print(f"n_questions={g['n_questions']}  KG ids loaded={len(kg_ids)}")
    print(
        f"GLOBAL  node_id_validity={_fmt(g['node_id_validity_macro'])}  "
        f"cited_in_retr={_fmt(g['cited_in_retrieved_rate_macro'])}  "
        f"kw_cov={_fmt(g['keyword_coverage_macro'])}  "
        f"forbidden_viol={_fmt(g['forbidden_violation_macro'])}  "
        f"refusal_T5={_fmt(g['refusal_for_t5_macro'])}"
    )
    print(f"hallucinated_node_id_events={len(halluc_inventory)}  "
          f"questions_with_hallucination={g['n_questions_with_hallucination']}")
    print()
    print("By category:")
    for cat, agg in per_category.items():
        print(
            f"  {cat}: n={agg['n_questions']}  "
            f"nv={_fmt(agg['node_id_validity_macro'])}  "
            f"cr={_fmt(agg['cited_in_retrieved_rate_macro'])}  "
            f"kw={_fmt(agg['keyword_coverage_macro'])}  "
            f"fv={_fmt(agg['forbidden_violation_macro'])}  "
            f"refuse={_fmt(agg['refusal_for_t5_macro'])}  "
            f"halluc={agg['n_questions_with_hallucination']}"
        )


if __name__ == "__main__":
    main()
