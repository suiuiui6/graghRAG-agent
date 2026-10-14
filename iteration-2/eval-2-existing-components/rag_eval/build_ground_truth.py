"""
Build ground truth dataset for RAG evaluation.
Strictly grounded in real KG data — every expected_node_id is verified to exist.

Output: ground_truth.json with 50 questions across 7 categories.
"""
import json
import os
from pathlib import Path

KG_DIR = Path(r"D:/graghRAG-agent/backend/output/kg/doc_ingest_232e1611")
OUT = Path(r"D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/ground_truth.json")

with open(KG_DIR / "nodes.json", "r", encoding="utf-8") as f:
    nodes_raw = json.load(f)
with open(KG_DIR / "edges.json", "r", encoding="utf-8") as f:
    edges_raw = json.load(f)

NODES = {n["node_id"]: n for n in nodes_raw["nodes"]}
GROUNDED = {nid: n for nid, n in NODES.items() if n.get("grounding_status") == "grounded"}

QUESTIONS = []

def add(qid, cat, q, expected_ids=None, keywords=None, forbidden=None,
        should_refuse=False, hops=1, pages=None, notes=""):
    if expected_ids:
        for nid in expected_ids:
            assert nid in NODES, f"{qid}: node {nid} not in KG"
    QUESTIONS.append({
        "qid": qid,
        "category": cat,
        "question": q,
        "expected_node_ids": expected_ids or [],
        "expected_keywords": keywords or [],
        "forbidden_keywords": forbidden or [],
        "should_refuse": should_refuse,
        "reasoning_hops": hops,
        "evidence_pages": pages or [],
        "notes": notes,
    })

# =============================================================
# T1 简单事实查询 (12 题) — 单一节点定位，最基本的检索能力
# =============================================================
add("Q01","T1","这篇论文的标题是什么？", ["n0001"], ["绿电直连","电氢氨","园区","优化运行"], pages=[0])
add("Q02","T1","这篇论文的编号(ID)是什么？", ["n0002"], ["002196"], pages=[0])
add("Q03","T1","论文中提到的 W4S1 场景代表什么？", ["n0035"], ["最大弃电","maximum curtailment","173.7"], pages=[1])
add("Q04","T1","论文使用了什么优化方法来求解问题二？", ["n0018","n0079"], ["MILP","混合整数线性规划"], hops=1, pages=[1,3])
add("Q05","T1","问题三采用的优化建模方法是什么？", ["n0024"], ["LP","线性规划","连续"], pages=[1])
add("Q06","T1","代码实现使用了哪个版本的 Python？", ["n0407"], ["Python","3.10"], pages=[22])
add("Q07","T1","论文用什么库做可视化？", ["n0412"], ["Matplotlib"], pages=[22])
add("Q08","T1","碳-电-氢-氨多市场耦合优化模型属于什么改进方向？", ["n0395"], ["碳交易","carbon","耦合"], pages=[17])
add("Q09","T1","论文中处理不确定性的改进方法有哪些？", ["n0397"], ["鲁棒","随机规划","RO","SP"], pages=[17])
add("Q10","T1","图 5 展示了什么内容？", ["n0313"], ["问题四","三种模式","经济性","储能"], pages=[13])
add("Q11","T1","图 6 是什么图？", ["n0379"], ["全问题","汇总","吨氨成本","绿电指标"], pages=[17])
add("Q12","T1","Pandas 在论文中扮演什么角色？", ["n0411"], ["Pandas","data processing","数据处理"], pages=[22])

# =============================================================
# T2 类型聚合 (8 题) — 召回率测试，看是否漏关键节点
# =============================================================
add("Q13","T2","论文里采用了哪些优化建模方法？请尽量完整列出。",
    ["n0018","n0024","n0079","n0395","n0397"],
    ["MILP","混合整数","LP","线性规划","鲁棒"], hops=2, pages=[1,3,17])
add("Q14","T2","该论文实现部分(Python 代码)使用了哪些主要函数？",
    ["n0414","n0415","n0416","n0417","n0418"],
    ["load_all_data","generate_scenarios","solve_problem"], hops=2, pages=[22])
add("Q15","T2","论文中所有的图(figure)有哪些？",
    ["n0221","n0313","n0379"], ["图 2","图 5","图 6"], hops=2, pages=[10,13,17])
add("Q16","T2","论文摘要中提到的吨氨成本类经济指标分别有哪些？",
    ["n0015","n0019","n0021","n0022","n0025"],
    ["3554","5820","7111","3669","5652"], hops=2, pages=[1])
add("Q17","T2","论文摘要(p1)罗列出了哪些产能/装机的关键参数？",
    ["n0006","n0007","n0008","n0009"],
    ["0.75MW","6MW","36吨","72吨"], hops=2, pages=[1])
add("Q18","T2","论文需要解决几个问题？分别是什么主题？",
    ["n0057","n0076","n0077","n0078"],
    ["五个","递进","基准线","灵活性","离散启停"], hops=2, pages=[3])
add("Q19","T2","论文里出现了哪些关于'绿电指标合规率'的具体数值？",
    ["n0020","n0029"], ["39.2","69.2","合规率"], hops=2, pages=[1])
add("Q20","T2","在摘要中给出的电力流向相关 metric (购电、售电、自发自用率等)有哪些？",
    ["n0011","n0012","n0013","n0014","n0016","n0017"],
    ["558.72","603.45","172.04","216.77","28.2","35.9"], hops=2, pages=[1])

# =============================================================
# T3 数值精度 (8 题) — 严格数值匹配
# =============================================================
add("Q21","T3","论文摘要中给出的初始合成氨产能(initial)是多少吨/日？",
    ["n0008"], ["36"], forbidden=["72吨/日","9023","10903"], pages=[1])
add("Q22","T3","扩容后的合成氨产能(expanded)是多少吨/日？",
    ["n0009"], ["72"], forbidden=["36吨/日"], pages=[1])
add("Q23","T3","论文摘要给出的园区总用电量是多少 MWh？",
    ["n0011"], ["558.72"], forbidden=["603.45","172.04","216.77"], pages=[1])
add("Q24","T3","论文摘要中可再生能源发电量是多少 MWh？",
    ["n0012"], ["603.45"], forbidden=["558.72","172.04"], pages=[1])
add("Q25","T3","论文计算出的电网支撑价值是多少元/吨？",
    ["n0040","n0041"], ["1970"], forbidden=["3554","5820","7111"], pages=[1])
add("Q26","T3","论文摘要给出的可再生能源弃电率(curtailment rate)是多少？",
    ["n0034"], ["95.4"], pages=[1])
add("Q27","T3","离网带储能的最优储能配置容量/功率是多少？",
    ["n0036"], ["210.4","30"], pages=[1])
add("Q28","T3","摘要中给出的年度合成氨产量(无储能 vs 有储能)是多少吨？",
    ["n0032","n0037"], ["9023","10903"], pages=[1])

# =============================================================
# T4 多跳推理 (4 题) — 需图遍历
# =============================================================
add("Q29","T4","解决问题二的核心建模方法及其与问题三方法的差异是什么？",
    ["n0018","n0024","n0078","n0079"],
    ["MILP","LP","离散启停","连续","二进制","big-M"], hops=2, pages=[1,3])
add("Q30","T4","离网带储能场景相比无储能场景，产量提升了多少？",
    ["n0032","n0037","n0038"], ["20.8","9023","10903"], hops=2, pages=[1])
add("Q31","T4","成本最低和最高的两种运营模式分别对应多少元/吨？",
    ["n0015","n0019","n0021"], ["3554","7111"], hops=2, pages=[1])
add("Q32","T4","摘要中讨论的两种连续调节方式分别使绿电合规率达到了什么水平？",
    ["n0020","n0024","n0029","n0030"], ["39.2","69.2","线性","LP","连续"], hops=2, pages=[1])

# =============================================================
# T5 拒答 OOD (10 题) — 完全不在该 KG 范围
# =============================================================
add("Q33","T5","Transformer 模型用了多少层 encoder？",
    [], [], should_refuse=True, notes="Transformer 论文是 Attention is All You Need，与本 KG 无关")
add("Q34","T5","BERT 在 GLUE benchmark 上的得分是多少？",
    [], [], should_refuse=True, notes="BERT/GLUE 与本 KG 无关")
add("Q35","T5","ResNet-50 的参数量有多少？",
    [], [], should_refuse=True, notes="CV 模型与本 KG 无关")
add("Q36","T5","这篇论文的第一作者是谁？",
    [], [], should_refuse=True, notes="KG 中不含作者信息（仅 title 和 id）")
add("Q37","T5","本论文里有没有讨论太阳能电池板的转换效率参数？",
    [], [], should_refuse=True, notes="KG 中无该参数节点")
add("Q38","T5","论文使用 GPU 训练了多少个 epoch？",
    [], [], should_refuse=True, notes="该论文是优化建模题，没有训练过程")
add("Q39","T5","该研究的实验在多少个城市进行了部署？",
    [], [], should_refuse=True, notes="模拟研究无实际部署")
add("Q40","T5","ImageNet 的图像分类准确率是多少？",
    [], [], should_refuse=True, notes="ImageNet 不在 KG 中")
add("Q41","T5","本论文的影响因子(impact factor)是多少？",
    [], [], should_refuse=True, notes="影响因子是期刊属性，与论文 KG 无关")
add("Q42","T5","论文里讨论了煤化工成本是多少？",
    [], [], should_refuse=True, notes="论文聚焦绿电+电氢氨，未讨论煤化工")

# =============================================================
# T6 噪声鲁棒 (5 题) — 错别字 / 同义改写
# =============================================================
add("Q43","T6","这篇论文采用了什么方法求解问题2？(混合证书线性规化方法?)",
    ["n0018","n0079"], ["MILP","混合整数线性规划"], pages=[1,3], notes="错别字: 证书->整数, 规化->规划")
add("Q44","T6","摘要里说的园区总用店量是多少 mwh?",
    ["n0011"], ["558.72"], pages=[1], notes="用店->用电，单位大小写")
add("Q45","T6","本文计算的吨案产能 expanded 是多少？",
    ["n0009"], ["72"], pages=[1], notes="吨案->吨氨")
add("Q46","T6","Pythn 3.10 是用来做什么的?",
    ["n0407"], ["Python","实现","代码","implementation"], pages=[22], notes="Pythn->Python")
add("Q47","T6","论文中提到的wind 4 solar 1场景代表什么含义?",
    ["n0035"], ["最大弃电","173.7","curtailment"], pages=[1], notes="W4S1 同义改写为 wind 4 solar 1")

# =============================================================
# T7 误导性 / 假前提 (3 题) — 测能否纠错
# =============================================================
add("Q48","T7","论文用了 GPT-4 来辅助优化求解，对吗？",
    [], [], should_refuse=True, notes="错误前提：论文用 MILP/LP，不用 GPT-4")
add("Q49","T7","本论文证明了储能装置反而会降低园区产量，这个结论对吗？",
    ["n0032","n0037","n0038"], ["20.8","提升","增加","9023","10903"], should_refuse=False, pages=[1], notes="错误前提：实际储能使产量从 9023→10903 吨，提升 20.8%")
add("Q50","T7","该论文的初始产能是 100 吨氨/日，是吗？",
    ["n0008"], ["36","并非100","不是100"], should_refuse=False, pages=[1], notes="错误前提：实际是 36 吨/日")

# =============================================================
# Validation
# =============================================================
assert len(QUESTIONS) == 50, f"expected 50, got {len(QUESTIONS)}"
cat_count = {}
for q in QUESTIONS:
    cat_count[q["category"]] = cat_count.get(q["category"], 0) + 1
print("Total:", len(QUESTIONS))
print("Per-category:", cat_count)

# Verify all expected_node_ids exist
missing = []
for q in QUESTIONS:
    for nid in q["expected_node_ids"]:
        if nid not in NODES:
            missing.append((q["qid"], nid))
if missing:
    raise SystemExit(f"missing nodes: {missing}")
print("All expected_node_ids verified to exist in KG")

# Verify keyword grounding
print("\n--- Sample verification ---")
for q in QUESTIONS[:3]:
    print(f"\n{q['qid']}: {q['question']}")
    for nid in q["expected_node_ids"]:
        n = NODES[nid]
        print(f"  -> {nid} [{n['entity_type']}] {n['label'][:60]}")

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({
        "_meta": {
            "doc_id": "doc_ingest_232e1611",
            "doc_filename": "论文.pdf",
            "kg_nodes_total": len(NODES),
            "kg_nodes_grounded": len(GROUNDED),
            "kg_edges_total": len(edges_raw["edges"]),
            "version": "1.0",
            "category_legend": {
                "T1": "简单事实 (single-node, hops=1)",
                "T2": "类型聚合 (recall-focused)",
                "T3": "数值精度 (exact-number)",
                "T4": "多跳推理 (graph traversal)",
                "T5": "拒答 OOD (out-of-scope, should_refuse=true)",
                "T6": "噪声鲁棒 (typos / paraphrase)",
                "T7": "误导性 / 假前提 (false premise)",
            },
            "category_counts": cat_count,
        },
        "questions": QUESTIONS,
    }, f, ensure_ascii=False, indent=2)
print(f"\nWritten: {OUT}")
