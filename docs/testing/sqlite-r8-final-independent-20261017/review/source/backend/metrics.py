"""
Prometheus metrics — §3.2 of enterprise-evolution-blueprint.

Exposes GET /metrics (Prometheus text format) and provides instrumentation
helpers for request counting, latency histograms, and retrieval source tracking.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# Request metrics
rag_requests_total = Counter(
    "rag_requests_total",
    "Total RAG requests served",
    ["endpoint", "status"],
)

rag_request_duration_seconds = Histogram(
    "rag_request_duration_seconds",
    "RAG request latency in seconds",
    ["endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# Retrieval metrics
rag_retrieval_candidates = Gauge(
    "rag_retrieval_candidates",
    "Pre-RRF candidate count per retrieval source",
    ["source"],
)

rag_retrieval_latency_ms = Histogram(
    "rag_retrieval_latency_ms",
    "Per-step retrieval latency",
    ["step"],
    buckets=[10, 50, 100, 250, 500, 1000, 2000, 5000, 15000],
)

rag_query_budget_tokens = Histogram(
    "rag_query_budget_tokens",
    "Context token budget used for RAG answers",
    buckets=[128, 256, 512, 1024, 2048, 4096, 8192, 16000],
)

rag_cache_hits_total = Counter(
    "rag_cache_hits_total",
    "Rewrite/coreference/runtime cache hits",
    ["cache"],
)

rag_rerank_duration_seconds = Histogram(
    "rag_rerank_duration_seconds",
    "Cross-encoder rerank latency in seconds",
    buckets=[0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

rag_retrieval_stage_duration_seconds = Histogram(
    "rag_retrieval_stage_duration_seconds",
    "Retrieval stage duration in seconds",
    ["stage"],
    buckets=[0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 15.0],
)

rag_degraded_mode_total = Counter(
    "rag_degraded_mode_total",
    "RAG degraded-mode occurrences",
    ["mode"],
)

rag_query_mode_total = Counter(
    "rag_query_mode_total",
    "Query mode selections",
    ["mode"],
)

# Business metrics
rag_documents_total = Gauge(
    "rag_documents_total",
    "Total indexed documents",
)
rag_kg_nodes_total = Gauge(
    "rag_kg_nodes_total",
    "Total KG nodes",
)
rag_kg_edges_total = Gauge(
    "rag_kg_edges_total",
    "Total KG edges",
)

# Error metrics
rag_errors_total = Counter(
    "rag_errors_total",
    "Error count by type",
    ["error_type"],
)

# ── Phase 2: Data Quality Metrics (§5.5) ───────────────────────────────

rag_grounding_rate = Gauge(
    "rag_grounding_rate",
    "Entity grounding rate (grounded / total)",
)

rag_positive_feedback_ratio = Gauge(
    "rag_positive_feedback_ratio",
    "Positive feedback ratio over last 7 days",
)

rag_zero_result_queries = Counter(
    "rag_zero_result_queries_total",
    "Queries that returned no results",
)

rag_stale_entities = Gauge(
    "rag_stale_entities",
    "Entities not retrieved in last 30 days",
)

rag_data_freshness_days = Gauge(
    "rag_data_freshness_days",
    "Days since last document ingest",
)

rag_quality_score = Gauge(
    "rag_quality_score",
    "Overall data quality score (0-100)",
)


def record_query_budget(context_tokens: int | float | None) -> None:
    if context_tokens is None:
        return
    rag_query_budget_tokens.observe(float(context_tokens))


def record_cache_hit(cache_name: str) -> None:
    rag_cache_hits_total.labels(cache=cache_name).inc()


def record_rerank_duration_ms(duration_ms: int | float | None) -> None:
    if duration_ms is None:
        return
    rag_rerank_duration_seconds.observe(float(duration_ms) / 1000.0)
    rag_retrieval_stage_duration_seconds.labels(stage="rerank").observe(float(duration_ms) / 1000.0)


def record_query_mode(mode: str | None) -> None:
    if not mode:
        return
    rag_query_mode_total.labels(mode=mode).inc()


def record_degraded_mode(mode: str | None) -> None:
    rag_degraded_mode_total.labels(mode=mode or "none").inc()


def record_rag_response_observability(payload: dict | None) -> None:
    if not isinstance(payload, dict):
        return

    metadata = payload.get("metadata", {}) or {}
    token_usage = metadata.get("token_usage", {}) or {}

    context_tokens = token_usage.get("context_tokens_used")
    if context_tokens is None:
        prompt_meta = metadata.get("prompt", {}) or {}
        context_tokens = prompt_meta.get("context_tokens")
    record_query_budget(context_tokens)

    record_query_mode(metadata.get("query_mode"))
    record_rerank_duration_ms(token_usage.get("rerank_latency_ms"))
    record_degraded_mode(metadata.get("degraded_mode"))

    cache_name = token_usage.get("cache_hit")
    if cache_name:
        record_cache_hit(str(cache_name))


async def metrics_endpoint() -> Response:
    """Prometheus /metrics endpoint handler."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
