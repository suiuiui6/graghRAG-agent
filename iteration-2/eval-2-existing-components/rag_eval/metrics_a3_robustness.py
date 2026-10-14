"""
metrics_a3_robustness.py
========================

A3 评测脚本：拒答能力 (T5) + 噪声鲁棒性 (T6) + 误导前提识别 (T7)

输入:
    - ground_truth.json
    - raw_runs.jsonl
输出:
    - metrics_a3_robustness.json
    - report_a3_robustness.md

数据真实性硬约束：
    - 不调 LLM 当 judge，纯规则 + 关键词检测
    - 拒答关键词、误导前提反驳关键词均硬编码
    - 命中率基于 expected_node_ids ∩ retrieved_node_ids 的精确匹配
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
GT_PATH = ROOT / "ground_truth.json"
RUNS_PATH = ROOT / "raw_runs.jsonl"
OUT_JSON = ROOT / "metrics_a3_robustness.json"
OUT_REPORT = ROOT / "report_a3_robustness.md"

# ---------- 关键词词典（硬编码，规则判定） ----------
REFUSAL_KEYWORDS = [
    "不包含", "没有", "无关", "未提及", "未涉及", "无法", "不涉及",
    "不存在", "未提到", "未找到", "没找到",
    "not contain", "no information", "unable", "cannot", "n/a",
]

# 误导前提反驳关键词
REJECT_PREMISE_KEYWORDS = [
    "不是", "并非", "错误", "不对", "实际上", "实际是",
    "并不是", "不正确", "事实上", "恰恰相反", "相反", "与事实不符",
    "并未", "没有", "不符",
]

# 数字模式（用于 T5 false_positive_answer_count：判定是否给了具体数字答案）
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")

# ---------- T6 -> T1/T2/T3 的同主题对照表（基于 question 内容人工映射） ----------
# 设计依据: T6 是对 T1/T2/T3 类问题的错别字/同义改写扰动版本
# 我们寻找扰动前的"clean source"作为对照
T6_TO_CLEAN_MAPPING: dict[str, dict[str, str]] = {
    "Q43": {  # 混合证书线性规化 -> 混合整数线性规划 (问题二方法)
        "clean_qid": "Q04",
        "reason": "Q43 错字'证书->整数'+'规化->规划', 主题=问题二求解方法 (n0018,n0079)",
    },
    "Q44": {  # 园区总用店量 mwh -> 总用电量 MWh
        "clean_qid": "Q23",
        "reason": "Q44 错字'用店->用电' + 单位大小写; 主题=园区总用电量 (n0011, T3)",
    },
    "Q45": {  # 吨案产能 expanded -> 吨氨产能 expanded
        "clean_qid": "Q22",
        "reason": "Q45 错字'吨案->吨氨'; 主题=扩容产能 expanded (n0009, T3)",
    },
    "Q46": {  # Pythn 3.10 -> Python 3.10
        "clean_qid": "Q06",
        "reason": "Q46 错字'Pythn->Python'; 主题=Python 3.10 用途 (n0407, T1)",
    },
    "Q47": {  # wind 4 solar 1 -> W4S1
        "clean_qid": "Q03",
        "reason": "Q47 同义改写'W4S1 -> wind 4 solar 1'; 主题=W4S1 场景 (n0035, T1)",
    },
}


def contains_any(text: str, keywords: list[str]) -> tuple[bool, list[str]]:
    """检查文本中是否包含 keyword 列表中的任意一个，返回 (是否命中, 命中列表)"""
    hits = [kw for kw in keywords if kw.lower() in text.lower()]
    return (len(hits) > 0), hits


def has_concrete_number_answer(text: str) -> bool:
    """
    T5 题应该拒答, 不应该给出具体的数字答案。
    判定标准: 答案中出现 >= 3 个不同的数字 (避免误判 "n0001"/"第1页" 这种节点引用)
    """
    # 提取所有数字, 过滤掉典型的节点 id (n0xxx) 和页码引用
    cleaned = re.sub(r"n\d{4}", "", text)
    cleaned = re.sub(r"第\s*\d+\s*页", "", cleaned)
    cleaned = re.sub(r"page\s*\d+", "", cleaned, flags=re.IGNORECASE)
    nums = NUMBER_PATTERN.findall(cleaned)
    return len(set(nums)) >= 3


def load_data() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    gt = json.loads(GT_PATH.read_text(encoding="utf-8"))
    gt_by_qid = {q["qid"]: q for q in gt["questions"]}
    runs_by_qid: dict[str, dict[str, Any]] = {}
    with RUNS_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            runs_by_qid[r["qid"]] = r
    return gt_by_qid, runs_by_qid


# ----------------------------- T5 评测 -----------------------------
def evaluate_t5_refusal(
    gt_by_qid: dict[str, Any],
    runs_by_qid: dict[str, dict[str, Any]],
    t1_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    T5 拒答能力评测:
        - correct_refusal_rate = 答案含拒答关键词 / 10
        - over_retrieval_rate = 工具调用次数 vs T1 平均的比值
        - false_positive_answer_count = T5 题给了具体数字答案的次数
    """
    t5_qids = [q for q, v in gt_by_qid.items() if v["category"] == "T5"]
    assert len(t5_qids) == 10, f"T5 应该有 10 题, 实际 {len(t5_qids)}"

    per_question_results = []
    correct_refusal_count = 0
    false_positive_answer_count = 0
    t5_tool_calls = []
    t5_latencies = []
    t5_tokens = []

    for qid in sorted(t5_qids):
        run = runs_by_qid[qid]
        ans = run["final_answer"] or ""
        refused, refusal_hits = contains_any(ans, REFUSAL_KEYWORDS)
        has_number = has_concrete_number_answer(ans)
        # 判定: 正确拒答 = 含拒答关键词 (即使提到了具体数字, 只要明确说"KG 中没有"也算)
        is_correct_refusal = refused

        # false_positive: 给了具体数字答案 (>=3 个不同数字) 且 没有明确拒答
        is_fp = has_number and not refused
        # 边界情况: 即使含拒答词, 但答案中堆了 KG 中其他数据 (如 Q42), 不算 fp 但要标注
        if is_correct_refusal:
            correct_refusal_count += 1
        if is_fp:
            false_positive_answer_count += 1

        t5_tool_calls.append(run["num_tool_calls"])
        t5_latencies.append(run["latency_ms"])
        t5_tokens.append(run["tokens"]["total"])

        per_question_results.append({
            "qid": qid,
            "question": run["query"],
            "answer_excerpt": ans[:150] + ("..." if len(ans) > 150 else ""),
            "refusal_keywords_hit": refusal_hits[:5],
            "is_correct_refusal": is_correct_refusal,
            "has_concrete_number": has_number,
            "is_false_positive": is_fp,
            "num_tool_calls": run["num_tool_calls"],
            "latency_ms": run["latency_ms"],
            "tokens_total": run["tokens"]["total"],
        })

    t1_avg_calls = statistics.mean(r["num_tool_calls"] for r in t1_runs)
    t5_avg_calls = statistics.mean(t5_tool_calls)

    return {
        "n_t5": len(t5_qids),
        "correct_refusal_count": correct_refusal_count,
        "correct_refusal_rate": round(correct_refusal_count / len(t5_qids), 4),
        "false_positive_answer_count": false_positive_answer_count,
        "t5_avg_tool_calls": round(t5_avg_calls, 2),
        "t1_avg_tool_calls": round(t1_avg_calls, 2),
        "over_retrieval_ratio": round(t5_avg_calls / t1_avg_calls, 4) if t1_avg_calls else None,
        "t5_avg_latency_ms": round(statistics.mean(t5_latencies), 0),
        "t5_avg_tokens": round(statistics.mean(t5_tokens), 0),
        "per_question": per_question_results,
    }


# ----------------------------- T6 评测 -----------------------------
def evaluate_t6_robustness(
    gt_by_qid: dict[str, Any],
    runs_by_qid: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    T6 噪声鲁棒性评测:
        - robustness_match_rate = T6 命中 expected_node_ids 的题数 / 5
        - 同时比较 T6 vs 对应 T1/T2/T3 的 (calls, latency, tokens, hit_rate)
    """
    t6_qids = sorted([q for q, v in gt_by_qid.items() if v["category"] == "T6"])
    assert len(t6_qids) == 5, f"T6 应该有 5 题, 实际 {len(t6_qids)}"

    pairwise_compare = []
    t6_hits = 0
    for qid in t6_qids:
        gt_q = gt_by_qid[qid]
        run = runs_by_qid[qid]
        expected = set(gt_q["expected_node_ids"])
        retrieved = set(run["retrieved_node_ids"])
        t6_hit = bool(expected & retrieved)
        if t6_hit:
            t6_hits += 1

        # 关键词命中作为补充判定 (因为 retrieved_node_ids 不一定准确)
        ans = run["final_answer"] or ""
        kw_hits = [kw for kw in gt_q["expected_keywords"] if kw.lower() in ans.lower()]
        kw_hit_rate = len(kw_hits) / max(len(gt_q["expected_keywords"]), 1)

        # 同主题 clean 对照
        mapping = T6_TO_CLEAN_MAPPING[qid]
        clean_qid = mapping["clean_qid"]
        clean_run = runs_by_qid[clean_qid]
        clean_gt = gt_by_qid[clean_qid]
        clean_expected = set(clean_gt["expected_node_ids"])
        clean_retrieved = set(clean_run["retrieved_node_ids"])
        clean_hit = bool(clean_expected & clean_retrieved)
        clean_ans = clean_run["final_answer"] or ""
        clean_kw_hits = [kw for kw in clean_gt["expected_keywords"] if kw.lower() in clean_ans.lower()]
        clean_kw_hit_rate = len(clean_kw_hits) / max(len(clean_gt["expected_keywords"]), 1)

        pairwise_compare.append({
            "t6_qid": qid,
            "t6_question": run["query"],
            "t6_hit_node": t6_hit,
            "t6_kw_hit_rate": round(kw_hit_rate, 3),
            "t6_kw_hits": kw_hits,
            "t6_num_tool_calls": run["num_tool_calls"],
            "t6_latency_ms": run["latency_ms"],
            "t6_tokens_total": run["tokens"]["total"],
            "clean_qid": clean_qid,
            "clean_category": clean_gt["category"],
            "clean_question": clean_run["query"],
            "clean_hit_node": clean_hit,
            "clean_kw_hit_rate": round(clean_kw_hit_rate, 3),
            "clean_num_tool_calls": clean_run["num_tool_calls"],
            "clean_latency_ms": clean_run["latency_ms"],
            "clean_tokens_total": clean_run["tokens"]["total"],
            "mapping_reason": mapping["reason"],
            # 差异
            "delta_tool_calls": run["num_tool_calls"] - clean_run["num_tool_calls"],
            "delta_latency_ms": run["latency_ms"] - clean_run["latency_ms"],
            "delta_tokens": run["tokens"]["total"] - clean_run["tokens"]["total"],
            "degraded_on_hit": (not t6_hit) and clean_hit,
        })

    avg_delta_calls = statistics.mean(p["delta_tool_calls"] for p in pairwise_compare)
    avg_delta_latency = statistics.mean(p["delta_latency_ms"] for p in pairwise_compare)
    avg_delta_tokens = statistics.mean(p["delta_tokens"] for p in pairwise_compare)
    t6_avg_kw_rate = statistics.mean(p["t6_kw_hit_rate"] for p in pairwise_compare)
    clean_avg_kw_rate = statistics.mean(p["clean_kw_hit_rate"] for p in pairwise_compare)

    return {
        "n_t6": len(t6_qids),
        "t6_node_hit_count": t6_hits,
        "robustness_match_rate": round(t6_hits / len(t6_qids), 4),
        "t6_avg_keyword_hit_rate": round(t6_avg_kw_rate, 4),
        "clean_avg_keyword_hit_rate": round(clean_avg_kw_rate, 4),
        "avg_delta_tool_calls": round(avg_delta_calls, 2),
        "avg_delta_latency_ms": round(avg_delta_latency, 1),
        "avg_delta_tokens": round(avg_delta_tokens, 1),
        "n_degraded_on_hit": sum(1 for p in pairwise_compare if p["degraded_on_hit"]),
        "pairwise_compare": pairwise_compare,
    }


# ----------------------------- T7 评测 -----------------------------
def evaluate_t7_false_premise(
    gt_by_qid: dict[str, Any],
    runs_by_qid: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    T7 误导前提识别评测:
        - false_premise_rejection_rate = 含反驳关键词的题数 / 3
    """
    t7_qids = sorted([q for q, v in gt_by_qid.items() if v["category"] == "T7"])
    assert len(t7_qids) == 3, f"T7 应该有 3 题, 实际 {len(t7_qids)}"

    rejected_count = 0
    per_question = []
    for qid in t7_qids:
        gt_q = gt_by_qid[qid]
        run = runs_by_qid[qid]
        ans = run["final_answer"] or ""
        rejected, hits = contains_any(ans, REJECT_PREMISE_KEYWORDS)
        # 关键词命中 (例如 36 / 20.8 / 提升 等)
        kw_hits = [kw for kw in gt_q["expected_keywords"] if kw.lower() in ans.lower()]
        if rejected:
            rejected_count += 1
        per_question.append({
            "qid": qid,
            "question": run["query"],
            "answer_excerpt": ans[:200] + ("..." if len(ans) > 200 else ""),
            "reject_keywords_hit": hits[:5],
            "is_rejected": rejected,
            "expected_kw_hits": kw_hits,
            "expected_kw_count": len(gt_q["expected_keywords"]),
            "num_tool_calls": run["num_tool_calls"],
            "latency_ms": run["latency_ms"],
            "tokens_total": run["tokens"]["total"],
            "notes": gt_q.get("notes", ""),
        })

    return {
        "n_t7": len(t7_qids),
        "rejection_count": rejected_count,
        "false_premise_rejection_rate": round(rejected_count / len(t7_qids), 4),
        "per_question": per_question,
    }


# ----------------------------- 报告生成 -----------------------------
def render_report(results: dict[str, Any]) -> str:
    t5 = results["t5_refusal"]
    t6 = results["t6_robustness"]
    t7 = results["t7_false_premise"]

    # 一句话结论
    summary = (
        f"GraphRAG 系统在 OOD 拒答 ({t5['correct_refusal_rate']*100:.0f}%, {t5['correct_refusal_count']}/10) 与误导前提识别 "
        f"({t7['false_premise_rejection_rate']*100:.0f}%, {t7['rejection_count']}/3) 上表现良好，"
        f"对错别字/同义改写鲁棒 ({t6['robustness_match_rate']*100:.0f}%, "
        f"{t6['t6_node_hit_count']}/5 命中)，但 T5 拒答时存在 {t5['t5_avg_tool_calls']:.1f}× "
        f"vs T1 {t5['t1_avg_tool_calls']:.1f}× 工具调用过度尝试现象。"
    )

    lines: list[str] = []
    lines.append("# A3 报告：拒答能力 + 噪声鲁棒性 + 误导前提识别")
    lines.append("")
    lines.append("## 一句话结论")
    lines.append(summary)
    lines.append("")
    lines.append("## 总指标")
    lines.append("")
    lines.append("| 能力 | 指标 | 值 |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| T5 拒答 | correct_refusal_rate | **{t5['correct_refusal_rate']*100:.1f}%** ({t5['correct_refusal_count']}/{t5['n_t5']}) |")
    lines.append(f"| T5 拒答 | false_positive_answer_count | {t5['false_positive_answer_count']} |")
    lines.append(f"| T5 拒答 | T5 avg tool_calls | {t5['t5_avg_tool_calls']} |")
    lines.append(f"| T5 拒答 | T1 avg tool_calls (对照) | {t5['t1_avg_tool_calls']} |")
    lines.append(f"| T5 拒答 | over_retrieval_ratio (T5/T1) | {t5['over_retrieval_ratio']} |")
    lines.append(f"| T6 鲁棒 | robustness_match_rate (node hit) | **{t6['robustness_match_rate']*100:.1f}%** ({t6['t6_node_hit_count']}/{t6['n_t6']}) |")
    lines.append(f"| T6 鲁棒 | T6 平均关键词命中率 | {t6['t6_avg_keyword_hit_rate']*100:.1f}% |")
    lines.append(f"| T6 鲁棒 | clean 平均关键词命中率 | {t6['clean_avg_keyword_hit_rate']*100:.1f}% |")
    lines.append(f"| T6 鲁棒 | 在 clean 命中前提下 T6 失败的题数 | {t6['n_degraded_on_hit']} |")
    lines.append(f"| T6 鲁棒 | T6 vs clean ΔToolCalls (平均) | {t6['avg_delta_tool_calls']:+.2f} |")
    lines.append(f"| T6 鲁棒 | T6 vs clean ΔLatency (ms) | {t6['avg_delta_latency_ms']:+.0f} |")
    lines.append(f"| T6 鲁棒 | T6 vs clean ΔTokens | {t6['avg_delta_tokens']:+.0f} |")
    lines.append(f"| T7 假前提 | false_premise_rejection_rate | **{t7['false_premise_rejection_rate']*100:.1f}%** ({t7['rejection_count']}/{t7['n_t7']}) |")
    lines.append("")

    # T5 每题判定表
    lines.append("## T5 拒答 OOD：每题判定 (10 题)")
    lines.append("")
    lines.append("| QID | 是否含拒答词 | 关键词命中 | 含具体数字? | 误判(false_pos)? | 工具调用 | latency(ms) | tokens |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in t5["per_question"]:
        kw_str = ", ".join(r["refusal_keywords_hit"][:3]) if r["refusal_keywords_hit"] else "-"
        lines.append(
            f"| {r['qid']} | {'OK' if r['is_correct_refusal'] else 'MISS'} | {kw_str} | "
            f"{'是' if r['has_concrete_number'] else '否'} | {'FP' if r['is_false_positive'] else 'OK'} | "
            f"{r['num_tool_calls']} | {r['latency_ms']} | {r['tokens_total']} |"
        )
    lines.append("")
    lines.append("### T5 关键 case 摘要")
    lines.append("")
    for r in t5["per_question"]:
        lines.append(f"- **{r['qid']}** Q: {r['question']}")
        lines.append(f"  - A 摘要: {r['answer_excerpt']}")
    lines.append("")

    # T6 对照表
    lines.append("## T6 噪声鲁棒：T6 vs Clean 对照 (5 对)")
    lines.append("")
    lines.append("| T6 QID | Clean QID | Clean Cat | T6 node hit | Clean node hit | T6 关键词 | Clean 关键词 | ΔCalls | ΔLatency | ΔTokens |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for p in t6["pairwise_compare"]:
        lines.append(
            f"| {p['t6_qid']} | {p['clean_qid']} | {p['clean_category']} | "
            f"{'OK' if p['t6_hit_node'] else 'MISS'} | "
            f"{'OK' if p['clean_hit_node'] else 'MISS'} | "
            f"{p['t6_kw_hit_rate']*100:.0f}% | "
            f"{p['clean_kw_hit_rate']*100:.0f}% | "
            f"{p['delta_tool_calls']:+d} | "
            f"{p['delta_latency_ms']:+d} | "
            f"{p['delta_tokens']:+d} |"
        )
    lines.append("")
    lines.append("### T6 -> Clean 映射依据")
    lines.append("")
    for p in t6["pairwise_compare"]:
        lines.append(f"- **{p['t6_qid']} -> {p['clean_qid']} ({p['clean_category']})**: {p['mapping_reason']}")
        lines.append(f"  - T6 Q: {p['t6_question']}")
        lines.append(f"  - Clean Q: {p['clean_question']}")
    lines.append("")

    # T7 反驳分析
    lines.append("## T7 误导前提：每题反驳分析 (3 题)")
    lines.append("")
    lines.append("| QID | 是否反驳 | 反驳关键词 | 正确事实 keyword 命中 | 工具调用 | latency(ms) |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for r in t7["per_question"]:
        kw = ", ".join(r["reject_keywords_hit"][:3]) if r["reject_keywords_hit"] else "-"
        fact_hits = f"{len(r['expected_kw_hits'])}/{r['expected_kw_count']}" if r["expected_kw_count"] else "-"
        lines.append(
            f"| {r['qid']} | {'OK' if r['is_rejected'] else 'MISS'} | {kw} | "
            f"{fact_hits} | {r['num_tool_calls']} | {r['latency_ms']} |"
        )
    lines.append("")
    lines.append("### T7 每题详情")
    lines.append("")
    for r in t7["per_question"]:
        lines.append(f"- **{r['qid']}** Q: {r['question']}")
        lines.append(f"  - 标注 notes: {r['notes']}")
        lines.append(f"  - A 摘要: {r['answer_excerpt']}")
        lines.append(f"  - 命中反驳词: {r['reject_keywords_hit'][:5]}")
        lines.append(f"  - 正确事实 keyword 命中: {r['expected_kw_hits']}")
    lines.append("")

    # 局限性
    lines.append("## 局限性")
    lines.append("")
    lines.append("1. **关键词检测的局限**: 拒答与反驳判定基于硬编码关键词列表，会漏检以非常规措辞表达的拒答 (例如纯陈述事实但不明确说'没有')。")
    lines.append("2. **样本量小**: T5=10, T6=5, T7=3, 统计意义有限，单题分类对率影响显著 (T7 一题影响 33.3%)。")
    lines.append("3. **T6 对照映射人工**: T6 -> Clean 的映射基于人工对内容主题的判断，存在主观性 (例如 Q43 的'方法'问题在 T1 同主题 Q04 与 T2 Q13 都覆盖, 选择 Q04 作为最贴近的 single-fact 对照)。")
    lines.append("4. **node-hit 与 keyword-hit 双指标可能冲突**: 比如 Q43 retrieve 到 n0079 但没 n0018, 这里只看交集为非空即视为 hit, 没区分 partial recall。")
    lines.append("5. **'有具体数字'判定阈值 (>=3 个不同数字) 是经验值**: 用于过滤 Q42 这类'拒答 + 给出 KG 已有相邻事实'的合理行为。但仍可能误判。")
    lines.append("6. **Q42 边界 case**: 论文聚焦绿氨但被问'煤化工成本', 系统给了一堆绿氨成本数据但也明确说没找到'煤化工成本'。本脚本认定为正确拒答(含'没有'), 但严格意义上它产生了'相关但不答题'的输出。")
    lines.append("7. **未测语义一致性**: T6 hit 是否与 Clean 命中相同节点不只是数量上一致——比如 Q44 retrieve 了 n0011 同时也带上 30+ 噪声节点, 可能掩盖了实际理解的差异。")
    lines.append("")

    return "\n".join(lines)


# ----------------------------- 主流程 -----------------------------
def main() -> None:
    gt_by_qid, runs_by_qid = load_data()

    # 校验所有 50 题都有对应的 run
    missing = [q for q in gt_by_qid if q not in runs_by_qid]
    if missing:
        raise RuntimeError(f"raw_runs 缺少以下 qid: {missing}")

    t1_runs = [runs_by_qid[q] for q, v in gt_by_qid.items() if v["category"] == "T1"]

    results = {
        "_meta": {
            "script": "metrics_a3_robustness.py",
            "gt_path": str(GT_PATH),
            "runs_path": str(RUNS_PATH),
            "n_questions_total": len(gt_by_qid),
        },
        "t5_refusal": evaluate_t5_refusal(gt_by_qid, runs_by_qid, t1_runs),
        "t6_robustness": evaluate_t6_robustness(gt_by_qid, runs_by_qid),
        "t7_false_premise": evaluate_t7_false_premise(gt_by_qid, runs_by_qid),
    }

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_REPORT.write_text(render_report(results), encoding="utf-8")

    print(f"[OK] 已写入: {OUT_JSON}")
    print(f"[OK] 已写入: {OUT_REPORT}")
    print()
    print("=== A3 指标速览 ===")
    t5 = results["t5_refusal"]
    t6 = results["t6_robustness"]
    t7 = results["t7_false_premise"]
    print(f"  T5 correct_refusal_rate       : {t5['correct_refusal_rate']*100:.1f}% ({t5['correct_refusal_count']}/{t5['n_t5']})")
    print(f"  T5 false_positive_answer_count: {t5['false_positive_answer_count']}")
    print(f"  T5 over_retrieval_ratio (T5/T1): {t5['over_retrieval_ratio']:.3f}  (T5 avg calls={t5['t5_avg_tool_calls']}, T1 avg calls={t5['t1_avg_tool_calls']})")
    print(f"  T6 robustness_match_rate      : {t6['robustness_match_rate']*100:.1f}% ({t6['t6_node_hit_count']}/{t6['n_t6']})")
    print(f"  T6 keyword hit T6 vs clean    : {t6['t6_avg_keyword_hit_rate']*100:.1f}% vs {t6['clean_avg_keyword_hit_rate']*100:.1f}%")
    print(f"  T7 false_premise_rejection    : {t7['false_premise_rejection_rate']*100:.1f}% ({t7['rejection_count']}/{t7['n_t7']})")


if __name__ == "__main__":
    main()
