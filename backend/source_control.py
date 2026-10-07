"""Request-local source policy and execution ledger (no network or shared state)."""

SOURCE_NAMES = ("vector", "kg", "bm25", "table", "multi_query")


class SourceRecallSkipped(Exception):
    """A recall helper did preparatory work but never queried its evidence source."""


def normalize_enabled_sources(value):
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("enabled_sources must be a non-empty source list or null")
    if any(not isinstance(source, str) or source not in SOURCE_NAMES for source in value):
        raise ValueError("Unsupported enabled_sources value")
    return tuple(source for source in SOURCE_NAMES if source in value)


def source_skip_reason(config, source: str) -> str | None:
    """Permission + dependency checks, distinct from intent/resource conditions."""
    source = "kg" if source == "community" else source
    requested = getattr(config, "enabled_sources", None)
    if source not in SOURCE_NAMES or (requested is not None and source not in requested):
        return "source_disabled"
    if source == "multi_query":
        if requested is not None and "vector" not in requested:
            return "vector_dependency_disabled"
        if not config.enable_multi_query:
            return "feature_disabled"
    return None


def source_allowed(config, source: str) -> bool:
    return source_skip_reason(config, source) is None


def build_effective_config(config) -> dict:
    requested = getattr(config, "enabled_sources", None)
    allowed = list(SOURCE_NAMES if requested is None else requested)
    return {
        "schema_version": "1.0",
        "requested_sources": None if requested is None else list(requested),
        "allowed_sources": allowed,
        "eligible_sources": [source for source in allowed if source_allowed(config, source)],
        "flags": {
            "enable_multi_query": config.enable_multi_query,
            "enable_global_mode": config.enable_global_mode,
            "enable_cross_encoder": config.enable_cross_encoder,
        },
        "budget": {
            "per_source_caps": dict(config.per_source_caps),
            "effective_per_source_caps": {
                source: config.per_source_caps.get(source, 0) if source_allowed(config, source) else 0
                for source in SOURCE_NAMES
            },
            "raw_source_top_k": {source: getattr(config, f"{source}_top_k") for source in SOURCE_NAMES},
            "raw_candidates_total": None,
            "pre_rerank_cap": config.max_total_candidates + 2,
            "max_total_candidates": config.max_total_candidates,
            "max_context_tokens": config.max_context_tokens,
            "rrf_k": config.rrf_k,
            "rerank_budget_ms": config.rerank_budget_ms,
            "rerank_max_candidates": config.rerank_max_candidates,
            "rerank_high_recall_max_candidates": config.rerank_high_recall_max_candidates,
            "rerank_max_chars": config.rerank_max_chars,
        },
        "stages": {},
        "attempted_sources": [],
        "executed_sources": [],
        "skipped_sources": {},
        "cross_encoder": {"requested": config.enable_cross_encoder, "attempted": False,
                          "executed": False, "skip_reason": None},
    }


def record_source(trace, stage, source, status, reason=None, candidate_count=0):
    if trace is None:
        return
    trace["stages"].setdefault(stage, {})[source] = {
        "status": status, "reason": reason, "candidate_count": candidate_count,
    }


def summarize_sources(trace):
    attempted, executed, skipped = set(), set(), {}
    for records in trace["stages"].values():
        for source, entry in records.items():
            source = "kg" if source == "community" else source
            if entry["status"] in {"executed", "failed"}:
                attempted.add(source)
            if entry["status"] == "executed":
                executed.add(source)
            elif entry["status"] == "skipped":
                skipped.setdefault(source, entry["reason"])
    trace["attempted_sources"] = [s for s in SOURCE_NAMES if s in attempted]
    trace["executed_sources"] = [s for s in SOURCE_NAMES if s in executed]
    trace["skipped_sources"] = {s: skipped[s] for s in SOURCE_NAMES if s in skipped and s not in attempted}
    return trace
