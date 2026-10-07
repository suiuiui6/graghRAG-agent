"""
Comprehensive RAG Evaluation Script — §3.2 of rag-engineering-blueprint-v1.0.

Evaluates retrieval + generation quality across 10 queries using LLM-as-judge
for metrics requiring ground truth, plus automated faithfulness computation.

Usage:
  cd backend && source .venv/bin/activate && python run_evaluation.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Ensure backend is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluation import Evaluator
from retrieval import RetrievalPipeline
from generator import generate_answer
from embedding import EmbeddingClient
from vector_store import VectorStore


# ═══════════════════════════════════════════════════════════════════════════════
# Test Set — 10 queries across 4 intent types, based on actual KG content
# ═══════════════════════════════════════════════════════════════════════════════

# NOTE: Ground truth relevance is judged by LLM-as-judge, so we don't need
# ground_truth_chunks pre-annotated. The EvalDataset ground_truth_chunks field
# is populated post-hoc via LLM judgment.

TEST_QUERIES = [
    # --- policy_lookup (3 queries) ---
    {
        "query": "绿电直连项目的合规标准是什么？需要满足哪些核心指标？",
        "intent": "policy_lookup",
    },
    {
        "query": "电氢氨园区有哪些运行约束条件？氢平衡如何保证？",
        "intent": "policy_lookup",
    },
    {
        "query": "绿电消纳的合规要求和考核指标有哪些规定？",
        "intent": "policy_lookup",
    },
    # --- process_attribution (2 queries) ---
    {
        "query": "碱性电解槽在系统中的作用是什么？如何与储氢罐协同工作？",
        "intent": "process_attribution",
    },
    {
        "query": "园区源荷匹配的控制流程是怎样的？各设备之间的能量关系如何分配？",
        "intent": "process_attribution",
    },
    # --- metric (3 queries) ---
    {
        "query": "电解槽的额定功率和产氢速率是多少？不同场景下的运行参数有何区别？",
        "intent": "metric",
    },
    {
        "query": "园区购售电策略的经济效益如何？各场景的成本和利润对比数据是什么？",
        "intent": "metric",
    },
    {
        "query": "可再生能源消纳率和弃电率在不同场景下的表现如何？",
        "intent": "metric",
    },
    # --- hybrid (2 queries) ---
    {
        "query": "对比不同运行场景下绿电合规性与经济效益的权衡关系，哪个场景综合最优？",
        "intent": "hybrid",
    },
    {
        "query": "园区整体优化运行策略是什么？如何在满足合规要求的同时最大化经济效益？",
        "intent": "hybrid",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# LLM-as-Judge Evaluator
# ═══════════════════════════════════════════════════════════════════════════════

JUDGE_PROMPT = """\
You are an impartial RAG quality evaluator. Score the following RAG response against the user's question.

## User Question
{query}

## Retrieved Context (chunks fed to the LLM)
{context}

## Generated Answer
{answer}

## Scoring Rubric

Rate each dimension on a 1-5 scale (1=poor, 5=excellent):

1. **Retrieval-Recall (1-5)**: Based on the context provided, were ALL relevant information pieces from the knowledge base retrieved?
   5=all key info present in context, 1=most key info missing

2. **Retrieval-Precision (1-5)**: Were the retrieved chunks relevant to the question?
   5=all chunks highly relevant, 1=mostly irrelevant chunks

3. **Generation-Relevance (1-5)**: Does the answer directly address the question without going off-topic?
   5=perfectly on-topic, 1=completely off-topic

4. **Generation-Accuracy (1-5)**: Is the answer strictly based on the retrieved context? No fabrication or hallucination?
   5=fully grounded in context, 1=mostly fabricated

5. **Generation-Comprehensiveness (1-5)**: Does the answer cover ALL key information points from the question?
   5=covers everything, 1=misses most key points

## Output Format
Respond with ONLY a JSON object (no markdown, no explanation):
{{"recall": N, "precision": N, "relevance": N, "accuracy": N, "comprehensiveness": N, "notes": "1-2 sentence summary"}}
"""


def llm_judge(query: str, answer: str, context_chunks: list[dict]) -> dict:
    """Use LLM to judge retrieval and generation quality on 1-5 scale."""
    context_text = "\n\n---\n\n".join(
        f"[{c.get('source','?')}] {c.get('text','')[:500]}" for c in context_chunks
    )
    if len(context_text) > 6000:
        context_text = context_text[:6000] + "\n\n[...truncated...]"

    prompt = JUDGE_PROMPT.format(
        query=query,
        context=context_text,
        answer=answer[:3000],
    )

    try:
        import requests
        api_key = os.getenv("LANGEXTRACT_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
        base_url = os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com")

        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 300,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        # Extract JSON from possible markdown block
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
        return json.loads(raw)
    except Exception as e:
        print(f"  [WARN] LLM judge failed: {e}")
        return {
            "recall": 0, "precision": 0, "relevance": 0,
            "accuracy": 0, "comprehensiveness": 0,
            "notes": f"Judge error: {e}",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Enhanced Evaluator — wraps existing Evaluator + LLM judge
# ═══════════════════════════════════════════════════════════════════════════════

class ComprehensiveEvaluator:
    """Combines automated metrics + LLM-as-judge for full evaluation."""

    def __init__(self, pipeline: RetrievalPipeline, llm_config=None):
        self.pipeline = pipeline
        self.automated = Evaluator()
        self.llm_config = llm_config

    def evaluate_single(self, query_info: dict) -> dict:
        """Run retrieval + generation for one query, return all metrics."""
        query = query_info["query"]

        # --- Retrieval ---
        t0 = time.perf_counter()
        retrieval_result = self.pipeline.retrieve(query)
        retrieval_ms = int((time.perf_counter() - t0) * 1000)

        context_dicts = [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "source": c.source,
                "score": c.score,
            }
            for c in retrieval_result.chunks
        ]

        # --- Generation ---
        try:
            from prompt_builder import build_prompt
            messages = build_prompt(retrieval_result, query)
            gen_result = generate_answer(
                messages=messages,
                context_chunks=context_dicts,
            )
            answer = gen_result.answer_text
            gen_ms = gen_result.latency_ms
        except Exception as e:
            answer = f"[生成失败: {e}]"
            gen_ms = 0

        total_ms = retrieval_ms + gen_ms

        # --- Automated metrics ---
        auto_faith = self.automated.evaluate_generation(answer, context_dicts)

        # --- LLM judge ---
        judge_scores = llm_judge(query, answer, context_dicts)

        return {
            "query": query,
            "expected_intent": query_info.get("intent", "unknown"),
            "actual_intent": retrieval_result.query_intent,
            "num_chunks": len(retrieval_result.chunks),
            "chunk_sources": list(set(c.source for c in retrieval_result.chunks)),
            "retrieval_ms": retrieval_ms,
            "generation_ms": gen_ms,
            "total_ms": total_ms,
            "answer": answer,
            "context_snippets": [
                {"source": c.source, "score": c.score, "text": c.text[:200]}
                for c in retrieval_result.chunks
            ],
            # Automated metrics
            "auto_faithfulness": auto_faith["faithfulness"],
            "auto_hallucination_rate": auto_faith["hallucination_rate"],
            "auto_grounded_count": auto_faith["grounded_count"],
            "auto_sentence_count": auto_faith["sentence_count"],
            # Pre-RRF diagnostic
            "pre_rrf_candidates": retrieval_result.total_candidates,
            # LLM judge metrics (1-5 scale)
            "judge_recall": judge_scores.get("recall", 0),
            "judge_precision": judge_scores.get("precision", 0),
            "judge_relevance": judge_scores.get("relevance", 0),
            "judge_accuracy": judge_scores.get("accuracy", 0),
            "judge_comprehensiveness": judge_scores.get("comprehensiveness", 0),
            "judge_notes": judge_scores.get("notes", ""),
        }

    def run_full_eval(self, queries: list[dict]) -> dict:
        """Run evaluation on all queries and produce final report."""
        results = []
        for i, q in enumerate(queries):
            print(f"\n{'='*60}")
            print(f"[{i+1}/{len(queries)}] {q['query'][:60]}...")
            print(f"{'='*60}")
            result = self.evaluate_single(q)
            results.append(result)
            print(f"  Intent: {result['actual_intent']} | Chunks: {result['num_chunks']}")
            print(f"  Faithfulness: {result['auto_faithfulness']:.2%} | Hallucination: {result['auto_hallucination_rate']:.2%}")
            print(f"  Judge → Recall:{result['judge_recall']} Prec:{result['judge_precision']} "
                  f"Relev:{result['judge_relevance']} Acc:{result['judge_accuracy']} Comp:{result['judge_comprehensiveness']}")
            print(f"  {result['judge_notes'][:120]}")

        # Aggregate
        n = len(results)
        def avg(key):
            return round(sum(r[key] for r in results) / n, 4)

        # Pre-RRF candidate stats
        avg_pre_rrf = sum(r.get("pre_rrf_candidates", 0) for r in results) / max(n, 1)

        report = {
            "eval_metadata": {
                "total_queries": n,
                "intent_distribution": {},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "model": "deepseek-chat",
                "embedding_model": "BAAI/bge-small-zh-v1.5",
            },
            # --- Retrieval Layer Summary ---
            "retrieval_layer": {
                "avg_judge_recall": avg("judge_recall"),
                "avg_judge_precision": avg("judge_precision"),
                "avg_chunks_retrieved": avg("num_chunks"),
                "avg_pre_rrf_candidates": round(avg_pre_rrf, 1),
                "avg_retrieval_ms": avg("retrieval_ms"),
                "source_coverage": self._summarize_sources(results),
            },
            # --- Generation Layer Summary ---
            "generation_layer": {
                "avg_faithfulness": avg("auto_faithfulness"),
                "avg_hallucination_rate": avg("auto_hallucination_rate"),
                "avg_judge_relevance": avg("judge_relevance"),
                "avg_judge_accuracy": avg("judge_accuracy"),
                "avg_judge_comprehensiveness": avg("judge_comprehensiveness"),
                "avg_generation_ms": avg("generation_ms"),
                "avg_total_ms": avg("total_ms"),
            },
            # --- Per-query details ---
            "per_query": results,
        }

        # Intent distribution
        intent_dist = {}
        for r in results:
            intent = r["expected_intent"]
            intent_dist[intent] = intent_dist.get(intent, 0) + 1
        report["eval_metadata"]["intent_distribution"] = intent_dist

        # Overall assessment
        report["overall_assessment"] = self._generate_assessment(report)
        report["optimization_recommendations"] = self._generate_recommendations(report)

        return report

    def _summarize_sources(self, results: list[dict]) -> dict:
        """Summarize retrieval source usage across queries."""
        source_counts = {}
        for r in results:
            for src in r.get("chunk_sources", []):
                source_counts[src] = source_counts.get(src, 0) + 1
        return source_counts

    def _generate_assessment(self, report: dict) -> dict:
        """Generate overall assessment based on metrics."""
        r = report["retrieval_layer"]
        g = report["generation_layer"]

        # Convert 1-5 judge scores to qualitative ratings
        def rating(score_1to5, thresholds=(2.5, 3.5, 4.2)):
            if score_1to5 < thresholds[0]:
                return "poor"
            elif score_1to5 < thresholds[1]:
                return "fair"
            elif score_1to5 < thresholds[2]:
                return "good"
            else:
                return "excellent"

        return {
            "retrieval_quality": {
                "overall": rating((r["avg_judge_recall"] + r["avg_judge_precision"]) / 2),
                "recall_rating": rating(r["avg_judge_recall"]),
                "precision_rating": rating(r["avg_judge_precision"]),
                "key_strength": (
                    "检索结果与问题高度相关，精确率高"
                    if r["avg_judge_precision"] >= 3.5
                    else "多路召回覆盖多个检索源"
                    if r["avg_judge_precision"] >= 2.5
                    else "检索基础框架已搭建完毕"
                ),
                "key_weakness": (
                    "部分查询召回不够全面，遗漏关键信息"
                    if r["avg_judge_recall"] < 3.5
                    else "跨源融合的一致性需要提升"
                    if r["avg_judge_recall"] < 4.0
                    else "无明显短板"
                ),
            },
            "generation_quality": {
                "overall": rating((g["avg_judge_relevance"] + g["avg_judge_accuracy"] + g["avg_judge_comprehensiveness"]) / 3),
                "relevance_rating": rating(g["avg_judge_relevance"]),
                "accuracy_rating": rating(g["avg_judge_accuracy"]),
                "comprehensiveness_rating": rating(g["avg_judge_comprehensiveness"]),
                "faithfulness": f"{g['avg_faithfulness']:.1%}",
                "hallucination_rate": f"{g['avg_hallucination_rate']:.1%}",
                "key_strength": (
                    "回答准确基于检索内容，幻觉率低"
                    if g["avg_hallucination_rate"] < 0.25
                    else "生成延迟在可接受范围内"
                ),
                "key_weakness": (
                    "部分回答不够全面，遗漏问题要求的要点"
                    if g["avg_judge_comprehensiveness"] < 3.5
                    else "回答可进一步优化结构化程度"
                    if g["avg_judge_comprehensiveness"] < 4.0
                    else "无明显短板"
                ),
            },
            "avg_latency_ms": g["avg_total_ms"],
        }

    def _generate_recommendations(self, report: dict) -> list[dict]:
        """Generate prioritized optimization recommendations."""
        r = report["retrieval_layer"]
        g = report["generation_layer"]
        recs = []

        # Priority based on metric gaps
        if r["avg_judge_recall"] < 3.5:
            recs.append({
                "priority": "P0-高",
                "layer": "检索层",
                "metric": "召回率",
                "current": f"{r['avg_judge_recall']:.1f}/5",
                "recommendation": "增加查询改写多样性（同义词扩展、上下位词），提升多查询召回覆盖度；考虑引入HyDE (Hypothetical Document Embeddings) 技术生成假设文档以桥接语义gap",
                "expected_impact": "预计召回率提升20-40%",
            })

        if r["avg_judge_precision"] < 3.5:
            recs.append({
                "priority": "P0-高",
                "layer": "检索层",
                "metric": "精确率",
                "current": f"{r['avg_judge_precision']:.1f}/5",
                "recommendation": "启用 Cross-Encoder Rerank (设置 enable_cross_encoder=True)；调低 RRF top_n；增加冗余过滤的 Jaccard 阈值到 0.80",
                "expected_impact": "预计精确率提升15-30%，增加约200ms延迟",
            })

        if g["avg_hallucination_rate"] > 0.30:
            recs.append({
                "priority": "P1-中",
                "layer": "生成层",
                "metric": "幻觉率",
                "current": f"{g['avg_hallucination_rate']:.1%}",
                "recommendation": "启用 Self-Correction 模块进行引用验证和数字一致性检查；在 Prompt 中强化'仅基于提供的上下文回答'的约束",
                "expected_impact": "预计幻觉率降低30-50%",
            })

        if g["avg_judge_comprehensiveness"] < 3.8:
            recs.append({
                "priority": "P1-中",
                "layer": "生成层",
                "metric": "全面性",
                "current": f"{g['avg_judge_comprehensiveness']:.1f}/5",
                "recommendation": "增加检索 Top-K 从5到10；在 Prompt 中增加 '请逐一覆盖问题的每个子问题' 的输出格式要求；引入 Chain-of-Thought 分步回答",
                "expected_impact": "预计全面性提升15-25%，但会增加生成延迟",
            })

        if g["avg_total_ms"] > 15000:
            recs.append({
                "priority": "P2-低",
                "layer": "系统层",
                "metric": "延迟",
                "current": f"{g['avg_total_ms']:.0f}ms",
                "recommendation": "启用 Embedding 结果缓存；预加载 KG 数据到内存；考虑异步流式生成 (SSE streaming)",
                "expected_impact": "预计延迟降低30-50%",
            })

        # Always add these foundational recommendations
        recs.append({
            "priority": "P2-低",
            "layer": "评估体系",
            "metric": "评估自动化",
            "current": "LLM-as-Judge (非确定性)",
            "recommendation": "建立人工标注的 Ground Truth 测试集（至少50条），包括标注相关的 chunk IDs 和标准答案；迁移到 RAGAS 框架进行确定性评估",
            "expected_impact": "评估可靠性从 ~85% 提升到 ~95%",
        })

        recs.append({
            "priority": "P2-低",
            "layer": "检索层",
            "metric": "MRR/排序质量",
            "current": "RRF Fusion (无 Cross-Encoder)",
            "recommendation": "引入 Cross-Encoder Rerank 模型（如 bge-reranker-v2-m3）替代纯 RRF；对 metric 类查询优先 BM25+Table 结果",
            "expected_impact": "最相关文档排到 Top-3 的概率提升 15-25%",
        })

        return recs


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("RAG 系统综合评估 — §3.2 评估框架")
    print("=" * 60)

    # Initialize components
    print("\n[1/4] 初始化向量数据库...")
    vector_store = VectorStore()
    print(f"  ChromaDB: {vector_store.count()} chunks in '{vector_store.collection_name}'")

    print("\n[2/4] 初始化 Embedding 模型 (BAAI/bge-small-zh-v1.5)...")
    embedding_client = EmbeddingClient()
    print(f"  Model: {embedding_client.model}, dim={embedding_client.dim}")

    # Load KG
    print("\n[3/4] 加载知识图谱...")
    kg_graph = None
    try:
        import glob
        import networkx as nx
        G = nx.Graph()
        for nodes_file in glob.glob("output/kg/*/nodes.json"):
            with open(nodes_file, encoding="utf-8") as f:
                data = json.load(f)
                nodes_list = data.get("nodes", data) if isinstance(data, dict) else data
                if isinstance(nodes_list, list):
                    for n in nodes_list:
                        nid = n.get("node_id", n.get("id", str(len(G.nodes))))
                        attrs = {k: v for k, v in n.items() if k != "node_id"}
                        G.add_node(nid, **attrs)
        for edges_file in glob.glob("output/kg/*/edges.json"):
            with open(edges_file, encoding="utf-8") as f:
                data = json.load(f)
                edges_list = data.get("edges", data) if isinstance(data, dict) else data
                if isinstance(edges_list, list):
                    for e in edges_list:
                        src = e.get("source_node_id", e.get("from", e.get("source", "")))
                        tgt = e.get("target_node_id", e.get("to", e.get("target", "")))
                        if src and tgt:
                            edge_attrs = {k: v for k, v in e.items() if k not in ("edge_id", "source_node_id", "target_node_id", "from", "source", "to", "target")}
                            G.add_edge(src, tgt, **edge_attrs)
        kg_graph = G
        print(f"  KG: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    except Exception as e:
        print(f"  [WARN] KG load failed: {e}")

    # Build optional indices from vector store if not already available
    bm25_index = None
    table_index = None
    try:
        from index_registry import (
            get_bm25_index, get_table_index, set_bm25_index, set_table_index,
            build_bm25_from_chunks, build_table_index_from_chunks,
        )
        from doc_processor import Chunk
        bm25_index = get_bm25_index()
        table_index = get_table_index()
        if not bm25_index or not table_index:
            print("  Building BM25 + TableIndex from existing chunks...")
            all_data = vector_store._collection.get(include=["documents", "metadatas"])
            all_chunks = []
            for i, cid in enumerate(all_data.get("ids", [])):
                text = all_data["documents"][i] if all_data.get("documents") else ""
                meta = all_data["metadatas"][i] if all_data.get("metadatas") else {}
                all_chunks.append(Chunk(
                    chunk_id=cid, text=text,
                    content_type=meta.get("content_type", "text"),
                ))
            if not bm25_index:
                bm25_index = build_bm25_from_chunks(all_chunks)
                if bm25_index:
                    set_bm25_index(bm25_index)
            if not table_index:
                table_chunks = [c for c in all_chunks if c.content_type == "table" or "<table>" in c.text.lower()]
                table_index = build_table_index_from_chunks(table_chunks if table_chunks else all_chunks)
                if table_index:
                    set_table_index(table_index)
        print(f"  BM25: {'ready' if bm25_index else 'not built'}")
        print(f"  TableIndex: {'ready' if table_index else 'not built'} ({table_index.count() if table_index else 0} rows)")
    except Exception as e:
        print(f"  [WARN] Index building: {e}")

    # Build pipeline
    print("\n[4/4] 构建 RAG Pipeline 并运行评估...")
    pipeline = RetrievalPipeline(
        vector_store=vector_store,
        embedding_client=embedding_client,
        kg_graph=kg_graph,
        bm25_index=bm25_index,
        table_index=table_index,
    )

    evaluator = ComprehensiveEvaluator(pipeline)
    report = evaluator.run_full_eval(TEST_QUERIES)

    # Save report
    output_dir = Path("output/eval")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "eval_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, ensure_ascii=False, indent=2, fp=f)
    print(f"\n\n评估报告已保存至: {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("评估总结")
    print("=" * 60)
    r = report["retrieval_layer"]
    g = report["generation_layer"]
    a = report["overall_assessment"]

    r_recall = r["avg_judge_recall"]
    r_prec = r["avg_judge_precision"]
    r_chunks = r["avg_chunks_retrieved"]
    r_lat = r["avg_retrieval_ms"]
    r_src = r["source_coverage"]
    rq = a["retrieval_quality"]
    r_strength = rq["key_strength"][:45]
    r_weakness = rq["key_weakness"][:45]

    g_faith = g["avg_faithfulness"]
    g_hallu = g["avg_hallucination_rate"]
    g_rel = g["avg_judge_relevance"]
    g_acc = g["avg_judge_accuracy"]
    g_comp = g["avg_judge_comprehensiveness"]
    g_gen_ms = g["avg_generation_ms"]
    g_tot_ms = g["avg_total_ms"]
    gq = a["generation_quality"]
    g_strength = gq["key_strength"][:45]
    g_weakness = gq["key_weakness"][:45]

    print(f"""
┌─────────────────────────────────────────────────────────────┐
│                     检索层评估结果                            │
├─────────────────────────────────────────────────────────────┤
│  召回率 (LLM Judge):    {r_recall:.1f}/5  ({rq["recall_rating"]})           │
│  精确率 (LLM Judge):    {r_prec:.1f}/5  ({rq["precision_rating"]})           │
│  平均检索块数:          {r_chunks:.1f}                              │
│  平均检索延迟:          {r_lat:.0f}ms                          │
│  Pre-RRF候选数:         {r["avg_pre_rrf_candidates"]:.0f}                              │
│  最终检索源覆盖:        {r_src}                │
├─────────────────────────────────────────────────────────────┤
│  优势: {r_strength}                  │
│  短板: {r_weakness}                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     生成层评估结果                            │
├─────────────────────────────────────────────────────────────┤
│  Faithfulness (引用率): {g_faith:.1%}                             │
│  Hallucination Rate:    {g_hallu:.1%}                             │
│  相关性 (LLM Judge):    {g_rel:.1f}/5  ({gq["relevance_rating"]})           │
│  准确性 (LLM Judge):    {g_acc:.1f}/5  ({gq["accuracy_rating"]})           │
│  全面性 (LLM Judge):    {g_comp:.1f}/5  ({gq["comprehensiveness_rating"]})           │
│  平均生成延迟:          {g_gen_ms:.0f}ms                          │
│  平均总延迟:            {g_tot_ms:.0f}ms                          │
├─────────────────────────────────────────────────────────────┤
│  优势: {g_strength}                  │
│  短板: {g_weakness}                  │
└─────────────────────────────────────────────────────────────┘
""")

    print("优化建议 (按优先级排序):")
    for rec in report["optimization_recommendations"]:
        print(f"  [{rec['priority']}] {rec['layer']} · {rec['metric']}")
        print(f"    现状: {rec['current']}")
        print(f"    建议: {rec['recommendation'][:120]}...")
        print(f"    预期: {rec['expected_impact']}")
        print()

    return report


if __name__ == "__main__":
    main()
