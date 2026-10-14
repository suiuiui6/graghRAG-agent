import re


NODE_ID_RE = re.compile(r"\b(?:d\d+_)?(n\d{4})\b")


def extract_node_ids_from_text(text: str) -> list[str]:
    if not text:
        return []
    return sorted({match.group(1) for match in NODE_ID_RE.finditer(text)})


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def extract_retrieved_node_ids_from_rag_sources(
    sources: list[dict] | None,
    metadata: dict | None = None,
) -> list[str]:
    collected: list[str] = []
    runtime_metadata = metadata or {}
    explicit_ids = (
        runtime_metadata.get("pre_rerank_node_ids")
        or runtime_metadata.get("retrieval_node_ids")
        or []
    )
    if isinstance(explicit_ids, list):
        for node_id in explicit_ids:
            collected.extend(extract_node_ids_from_text(str(node_id)))

    if collected:
        return _ordered_unique(collected)

    for source in sources or []:
        node_id = str(source.get("node_id") or "")
        node_match = NODE_ID_RE.fullmatch(node_id)
        if node_match:
            collected.append(node_match.group(1))

        chunk_id = str(source.get("chunk_id") or "")
        chunk_match = NODE_ID_RE.fullmatch(chunk_id)
        if chunk_match:
            collected.append(chunk_match.group(1))

        entity_ids = source.get("entity_ids") or []
        if isinstance(entity_ids, list):
            for node_id in entity_ids:
                collected.extend(extract_node_ids_from_text(str(node_id)))

        metadata = source.get("metadata") or {}
        metadata_entity_ids = metadata.get("entity_ids") or []
        if isinstance(metadata_entity_ids, list):
            for node_id in metadata_entity_ids:
                collected.extend(extract_node_ids_from_text(str(node_id)))

        properties = source.get("properties") or {}
        properties_entity_ids = properties.get("entity_ids") or []
        if isinstance(properties_entity_ids, list):
            for node_id in properties_entity_ids:
                collected.extend(extract_node_ids_from_text(str(node_id)))

        for text_field in ("text", "text_snippet", "label"):
            text_value = source.get(text_field)
            if isinstance(text_value, str):
                collected.extend(extract_node_ids_from_text(text_value))

    return _ordered_unique(collected)


def normalize_token_usage(token_usage: dict | None) -> dict[str, int]:
    usage = token_usage or {}
    input_tokens = int(
        usage.get("input")
        or usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or 0
    )
    output_tokens = int(
        usage.get("output")
        or usage.get("completion_tokens")
        or usage.get("output_tokens")
        or 0
    )
    total_tokens = int(
        usage.get("total")
        or usage.get("total_tokens")
        or (input_tokens + output_tokens)
    )
    return {
        "input": input_tokens,
        "output": output_tokens,
        "total": total_tokens,
    }
