"""Versioned, request-local evidence identity and trace helpers; no I/O."""
from copy import deepcopy
from hashlib import sha256
import json
import math
import re

IDENTITY_VERSION = "evidence-v1"
SOURCE_ORDER = ("vector", "kg", "bm25", "table", "multi_query", "community")
TRACE_FIELDS = ("evidence_id", "identity_base", "identity_status", "original_id", "content_sha256",
                "source_paths", "provenance", "original_scores", "identity_conflicts", "rrf_score", "rerank_score", "score_observations")
LOCATION_FIELDS = ("document_sha256", "document_id", "source_file", "source_item_id", "object_type",
                   "char_start", "char_end", "span_verified", "page_idx", "bbox_norm")


def location_metadata(value):
    if isinstance(value, dict):
        return {key: deepcopy(value[key]) for key in LOCATION_FIELDS if key in value}
    return {key: deepcopy(getattr(value, key)) for key in LOCATION_FIELDS if hasattr(value, key)}


def digest(value):
    payload = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def numeric(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else 0.0
    except (TypeError, ValueError):
        return 0.0


def source_order(source):
    return (SOURCE_ORDER.index(source) if source in SOURCE_ORDER else len(SOURCE_ORDER), source)


def identify(candidate, source=None):
    """Identity is independent of retrieval route, score, completion order, or UUID."""
    item = deepcopy(candidate)
    meta = item.get("metadata", {}) or {}
    if item.get("evidence_id"):
        return item
    original = str(item.get("chunk_id", "") or "")
    text = str(item.get("text", "") or "")
    source = source or item.get("source", "unknown")
    namespace = meta.get("document_sha256") or meta.get("document_id") or meta.get("source_file")
    if not namespace and re.search(r"[:_]n\d+$", original):
        namespace = re.split(r"[:_]n\d+$", original)[0]
    start, end = meta.get("char_start"), meta.get("char_end")
    declared_span = ([start, end] if isinstance(start, int) and not isinstance(start, bool)
                     and isinstance(end, int) and not isinstance(end, bool) and 0 <= start < end else None)
    object_type = meta.get("object_type") or ("entity" if source in ("kg", "community") else "table_row" if source == "table" else "text")
    locator = {"version": IDENTITY_VERSION, "namespace": namespace,
               "object_type": object_type, "location": declared_span or meta.get("source_item_id") or original or digest(text)}
    base = digest(locator)
    content_hash = digest(text)
    evidence_id = f"ev1_{digest([base, content_hash])}"
    raw_span = declared_span if meta.get("span_verified") is True and declared_span and end - start == len(text) else None
    item.update(evidence_id=evidence_id, identity_base=base, original_id=original or None,
                identity_status="declared_namespace" if namespace else "unknown_document",
                content_sha256=content_hash, source_paths=[source], identity_conflicts=[],
                original_scores={source: [item.get("score")]},
                provenance=[{"source": source, "original_id": original or None, "document_namespace": namespace,
                             "document_sha256": meta.get("document_sha256"), "declared_span": declared_span,
                             "original_span": raw_span, "page_idx": meta.get("page_idx", item.get("page_idx")),
                             "bbox_norm": meta.get("bbox_norm", item.get("bbox_norm")),
                             "content_sha256": content_hash}])
    item.setdefault("metadata", {})["retained_text_prefix_length"] = len(text)
    if not original:
        item["chunk_id"] = evidence_id
    return item


def stable_key(item):
    return item.get("evidence_id") or identify(item)["evidence_id"]


def merge_evidence(items):
    """Merge identical observed evidence; retain differing content and conflict IDs."""
    grouped = {}
    for raw in sorted(items, key=lambda x: (source_order(x.get("source", "unknown")), stable_key(x), digest(x.get("metadata", {})))):
        item = identify(raw)
        key = item["evidence_id"]
        observations = item.setdefault("score_observations", {})
        for field in ("rrf_score", "rerank_score"):
            if field in item:
                observations[field] = sorted(set(observations.get(field, []) + [numeric(item[field])]))
        if key not in grouped:
            grouped[key] = item
            continue
        current = grouped[key]
        for score_field in ("rrf_score", "rerank_score"):
            if score_field in item:
                current[score_field] = max(numeric(current.get(score_field, item[score_field])), numeric(item[score_field]))
            values = current.setdefault("score_observations", {}).get(score_field, []) + item["score_observations"].get(score_field, [])
            if values:
                current["score_observations"][score_field] = sorted(set(values))
        if (item.get("metadata", {}) or {}).get("protected_evidence"):
            current.setdefault("metadata", {})["protected_evidence"] = True
        current["source_paths"] = sorted(set(current["source_paths"] + item["source_paths"]), key=source_order)
        current["provenance"] = sorted({digest(p): p for p in current["provenance"] + item["provenance"]}.values(), key=digest)
        for source, scores in item["original_scores"].items():
            current["original_scores"].setdefault(source, []).extend(scores)
            current["original_scores"][source] = sorted(current["original_scores"][source], key=numeric)
    bases, citation_ids = {}, {}
    for key, item in grouped.items():
        bases.setdefault(item["identity_base"], []).append(key)
        citation_ids.setdefault(item["chunk_id"], []).append(key)
    for key, item in grouped.items():
        item["identity_conflicts"] = sorted(k for k in bases[item["identity_base"]] if k != key)
        if len(citation_ids[item["chunk_id"]]) > 1:
            item["chunk_id"] = key
        item.setdefault("metadata", {}).update({field: deepcopy(item.get(field)) for field in TRACE_FIELDS if field in item})
    return sorted(grouped.values(), key=stable_key)


def trace_record(item):
    identified = identify(item)
    return {**{key: deepcopy(identified.get(key)) for key in TRACE_FIELDS},
            "chunk_id": identified["chunk_id"], "text": identified.get("text", ""),
            "source": identified.get("source"), "score": identified.get("score"),
            "observed_text_sha256": digest(identified.get("text", "")),
            "retained_text_prefix_length": (item.get("metadata", {}) or {}).get("retained_text_prefix_length"),
            "protected_evidence": bool((item.get("metadata", {}) or {}).get("protected_evidence"))}


def capture_stage(trace, stage, items, reason, previous_stage=None):
    if trace is not None:
        records = [trace_record(item) for item in items]
        trace["retrieval_stages"][stage] = {"reason": reason, "evidence": records}
        if previous_stage:
            kept = {r["evidence_id"] for r in records}
            previous = trace["retrieval_stages"][previous_stage]["evidence"]
            trace["retrieval_stages"][stage]["dropped"] = [
                {"evidence_id": r["evidence_id"], "reason": reason} for r in previous if r["evidence_id"] not in kept]


def chunk_candidate(chunk):
    item = {"chunk_id": chunk.chunk_id, "text": chunk.text, "score": chunk.score, "source": chunk.source,
            "metadata": deepcopy(chunk.metadata), "page_idx": chunk.page_idx, "bbox_norm": chunk.bbox_norm}
    item.update({key: deepcopy(chunk.metadata[key]) for key in TRACE_FIELDS if key in chunk.metadata})
    return item


def answer_stage(stage, before, after, reason=None):
    return {"stage": stage, "input_answer": before, "output_answer": after,
            "changed": before != after, "reason": reason}


def generation_trace(base, mode, context, decision_items, raw, stages, final,
                     attempted=False, received=False):
    trace = deepcopy(base or {"schema_version": "1.0", "identity_version": IDENTITY_VERSION, "retrieval_stages": {}})
    trace.update(generation_mode=mode, serialized_model_context=deepcopy(context),
                 model_call_attempted=attempted, model_output_received=received,
                 raw_model_answer=raw, answer_stages=deepcopy(stages), final_answer=final,
                 decision_evidence=[trace_record(item) for item in merge_evidence(decision_items)])
    return trace
