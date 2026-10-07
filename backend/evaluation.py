"""
RAG evaluation module — §3.2 of rag-engineering-blueprint-v1.0.md

Scaffold for evaluating retrieval and generation quality.
Output schema matches the eval_report.json spec in the blueprint.
Metrics that require external data (e.g., RAGAS) are placeholder-ready.
"""

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path


_CITATION_RE = re.compile(r'\[[cn]\d{3,}\]')
_SENTENCE_SPLIT_RE = re.compile(r'[.!?。！？\n]+')


@dataclass
class EvalDataset:
    """Single evaluation sample."""
    query: str
    ground_truth_chunks: list[str]
    ground_truth_answer: str | None = None


class Evaluator:
    """Evaluates retrieval and generation against ground truth."""

    @staticmethod
    def evaluate_retrieval(
        retrieved_chunk_ids: list[str], ground_truth: list[str]
    ) -> dict:
        """Compute recall@5, recall@10, precision@10, MRR per query."""
        gt_set = set(ground_truth)
        if not gt_set:
            return {"recall@5": 1.0, "recall@10": 1.0,
                    "precision@10": 0.0, "mrr": 0.0}

        top5, top10 = retrieved_chunk_ids[:5], retrieved_chunk_ids[:10]

        def _ratio(hits: set) -> float:
            return len(hits & gt_set) / len(gt_set)

        mrr = 0.0
        for rank, cid in enumerate(retrieved_chunk_ids, start=1):
            if cid in gt_set:
                mrr = 1.0 / rank
                break

        return {"recall@5": round(_ratio(set(top5)), 4),
                "recall@10": round(_ratio(set(top10)), 4),
                "precision@10": round(len(set(top10) & gt_set) / len(top10), 4)
                if top10 else 0.0,
                "mrr": round(mrr, 4)}

    @staticmethod
    def evaluate_generation(
        answer: str, context_chunks: list[dict] | None = None
    ) -> dict:
        """Faithfulness = fraction of sentences with >=1 citation marker
        ([c#####] or [n####]). Hallucination = 1.0 - faithfulness."""
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(answer) if s.strip()]
        if not sentences:
            return {"faithfulness": 0.0, "hallucination_rate": 1.0,
                    "sentence_count": 0, "grounded_count": 0}
        grounded = sum(1 for s in sentences if _CITATION_RE.search(s))
        faith = grounded / len(sentences)
        return {"faithfulness": round(faith, 4),
                "hallucination_rate": round(1.0 - faith, 4),
                "sentence_count": len(sentences),
                "grounded_count": grounded}

    def run_eval(
        self,
        dataset: list[EvalDataset],
        retrieval_fn,   # (query: str) -> list[str]
        generation_fn,  # (query: str, chunk_ids: list[str]) -> str
    ) -> dict:
        """Run full eval pipeline, returning blueprint-compliant report dict."""
        r_metrics: list[dict] = []
        g_metrics: list[dict] = []
        latencies: list[float] = []

        for sample in dataset:
            retrieved = retrieval_fn(sample.query)
            r_metrics.append(self.evaluate_retrieval(retrieved, sample.ground_truth_chunks))

            t0 = time.perf_counter()
            answer = generation_fn(sample.query, retrieved)
            latencies.append((time.perf_counter() - t0) * 1000)
            g_metrics.append(self.evaluate_generation(answer))

        n = max(len(dataset), 1)
        def avg(key, ms):
            return round(sum(m[key] for m in ms) / n, 4)

        rec10 = avg("recall@10", r_metrics)
        mrr_val = avg("mrr", r_metrics)
        faith = avg("faithfulness", g_metrics)
        avg_lat = round(sum(latencies) / n, 2)

        return {
            "retrieval": {
                "recall@5": avg("recall@5", r_metrics),
                "recall@10": rec10,
                "precision@10": avg("precision@10", r_metrics),
                "mrr": mrr_val,
            },
            "generation": {
                "faithfulness": faith,
                "hallucination_rate": avg("hallucination_rate", g_metrics),
                "avg_latency_ms": avg_lat,
            },
            "per_query": [
                {"query": ds.query, "retrieval": rm, "generation": gm,
                 "latency_ms": round(lt, 2)}
                for ds, rm, gm, lt in zip(dataset, r_metrics, g_metrics, latencies)
            ],
            "summary": (
                f"Evaluated {len(dataset)} queries. "
                f"Recall@10={rec10:.2%}, MRR={mrr_val:.2%}, "
                f"Faithfulness={faith:.2%}, Avg latency={avg_lat:.0f}ms"
            ) if dataset else "Empty dataset — nothing to evaluate.",
        }


def save_eval_report(report: dict, output_path: str) -> None:
    """Save eval report dict to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
