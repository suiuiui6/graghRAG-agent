"""
Prompt Module — §2.5 of rag-engineering-blueprint-v1.0.

Constructs structured prompts from retrieval results with token budget
control, output format constraints, and citation requirements.
"""

from __future__ import annotations

import re
from copy import deepcopy
from evidence_trace import chunk_candidate, identify, digest

from retrieval import RetrievalResult, RetrievalChunk, trim_results_by_source_budget


# ── Prompt Templates ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a knowledge-based QA assistant for enterprise project documents.
Follow these rules strictly:

1. Answer ONLY using the provided context below. Do NOT fabricate information.
2. EVERY factual statement MUST end with a source citation marker like [c00042] or [n0019].
   - One citation per sentence minimum. Do NOT batch citations at the end of paragraphs.
   - Example: "The system uses 20MW electrolyzers [c00014]. Hydrogen production rate is 280kg/h [c00017]."
3. If the context is insufficient, clearly state: "文档中未提及此信息" (for Chinese queries) or "This information is not mentioned in the documents" (for English queries).
4. For numerical/quantitative answers, use Markdown tables for clarity.
   - Each table cell containing a fact must also include its citation marker.
5. Respond in the same language as the user's question.
6. Prioritize the most recent/production data when multiple sources conflict.
"""

CONTEXT_TEMPLATE = """\
Below are relevant document excerpts retrieved from the knowledge base:

{context_sections}

---

[QUESTION]
{question}

[OUTPUT FORMAT]
- Use a Markdown table only when comparing 3 or more facts. Each factual cell must have a citation.
- For 1-2 facts, prefer one short cited sentence or a compact bullet list instead of a table.
- EVERY factual sentence must end with a [chunk_id] citation marker. No uncited facts.
- Keep the answer concise and directly address the question.{inventory_instruction}"""


# ── Token Budget ─────────────────────────────────────────────────────────────

# Approximate token estimation (4 chars ≈ 1 token)
CHARS_PER_TOKEN = 4

# Token budget allocation
BUDGET = {
    "system": 500,
    "context": 12000,
    "question": 200,
    "output_reserve": 4000,
}


def _is_inventory_query(user_query: str) -> bool:
    query = user_query or ""
    lowered = query.lower()
    inventory_terms = ("所有", "哪些", "有哪些", "分别", "一览", "汇总", "list", "all ")
    return any(term in query or term in lowered for term in inventory_terms)


# ── Prompt Builder ───────────────────────────────────────────────────────────


def build_prompt(
    retrieval_result: RetrievalResult,
    user_query: str,
    max_context_tokens: int = 12000,
    output_language: str = "auto",
    return_metadata: bool = False,
    include_evidence_trace: bool = False,
) -> list[dict] | tuple[list[dict], dict]:
    """Build a LangChain-compatible messages list from retrieval results.

    Args:
        retrieval_result: Output from RetrievalPipeline.retrieve().
        user_query: Original user question.
        max_context_tokens: Maximum tokens for context section.
        output_language: "auto", "zh", "en" — "auto" matches query language.

    Returns:
        List of message dicts compatible with LangChain ChatOpenAI.
        When return_metadata=True, also returns prompt budget metadata.
    """
    visible_records = [] if include_evidence_trace else None
    context_sections = _build_budgeted_context_sections(
        retrieval_result=retrieval_result,
        max_context_tokens=max_context_tokens,
        user_query=user_query,
        visible_records=visible_records,
    )

    # Build system message
    system_msg = SYSTEM_PROMPT
    if output_language == "zh":
        system_msg += "\n请用中文回答。"
    elif output_language == "en":
        system_msg += "\nPlease answer in English."

    inventory_instruction = ""
    if _is_inventory_query(user_query):
        inventory_instruction = (
            "\n- 对于所有/哪些/分别/list/figure 这类枚举题，尽量完整列出所有由上下文支持的 distinct items，不要只回答其中一项。"
            "\n- Completeness overrides brevity for inventory questions: 即使答案较长，也要优先列全。"
            "\n- One bullet per supported item；当证据分散在多个 chunks 时，先合并 distinct items，再作答；不要压缩成单句总结。"
        )

    # Build user message
    user_msg = CONTEXT_TEMPLATE.format(
        context_sections=context_sections,
        question=user_query,
        inventory_instruction=inventory_instruction,
    )

    # Build token report
    system_tokens = len(system_msg) // CHARS_PER_TOKEN
    context_tokens = len(context_sections) // CHARS_PER_TOKEN
    question_tokens = len(user_query) // CHARS_PER_TOKEN

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

    prompt_meta = {
        "system_tokens": system_tokens,
        "context_tokens": context_tokens,
        "question_tokens": question_tokens,
        "total_tokens": system_tokens + context_tokens + question_tokens,
        "max_context_tokens": max_context_tokens,
    }
    if include_evidence_trace:
        prompt_meta["evidence_context"] = {
            "messages": deepcopy(messages), "messages_sha256": digest(messages),
            "context_text": context_sections, "context_sha256": digest(context_sections),
            "visible_evidence": visible_records, "offset_unit": "unicode_codepoint",
            "budget_unit": "character_estimate_4_chars_per_token",
        }

    if return_metadata:
        return messages, prompt_meta

    return messages


def _build_context_sections(
    chunks: list[RetrievalChunk],
    max_tokens: int = 12000,
    visible_records: list | None = None,
    context_offset: int = 0,
) -> str:
    """Build formatted context sections from retrieval chunks.

    Format: [Chunk ID | Section | Page] text...
    """
    sections = []
    total_chars = 0
    max_chars = max_tokens * CHARS_PER_TOKEN

    for chunk in chunks:
        # Build chunk header
        header_parts = [f"[{chunk.chunk_id}]"]
        if chunk.section_title:
            header_parts.append(f"Section: {chunk.section_title}")
        if chunk.page_idx is not None:
            header_parts.append(f"Page {chunk.page_idx}")
        header = " | ".join(header_parts)

        # For KG entities, format differently
        if chunk.source == "kg":
            section = _format_kg_chunk(chunk, header)
        else:
            section = _format_text_chunk(chunk, header)
        body_start = len(header) + 1
        if chunk.source == "kg":
            body_start += len(f" | Type: {chunk.metadata.get('entity_type', 'unknown')}")
        retained_end = len(section)
        separator_chars = 2 if sections else 0

        section_chars = len(section)
        truncated = total_chars + separator_chars + section_chars > max_chars
        if truncated:
            # Truncate last section to fit
            remaining = max_chars - total_chars - separator_chars
            if remaining > 100:
                suffix = "\n[...truncated]"
                cutoff = max(0, remaining - len(suffix))
                retained_end = cutoff
                section = section[:cutoff] + suffix
            else:
                break
        if visible_records is not None:
            body_end = min(retained_end, body_start + min(len(chunk.text),
                chunk.metadata.get("retained_text_prefix_length", len(chunk.text)), (4000 if chunk.source == "kg" else 8000)))
            if body_end > body_start:
                evidence = identify(chunk_candidate(chunk))
                text = section[body_start:body_end]
                verified = next((p.get("original_span") for p in evidence["provenance"] if p.get("original_span")), None)
                # Mapping is only valid for an observed prefix of verified original text.
                original_span = [verified[0], verified[0] + len(text)] if verified and len(text) <= verified[1] - verified[0] else None
                visible_records.append({"evidence_id": evidence["evidence_id"], "chunk_id": chunk.chunk_id,
                    "visible_text": text, "context_span": [context_offset + total_chars + separator_chars + body_start,
                                                              context_offset + total_chars + separator_chars + body_end],
                    "observed_text_span": [0, len(text)], "original_span": original_span,
                    "source_paths": evidence["source_paths"], "provenance": evidence["provenance"]})
        sections.append(section)
        total_chars += separator_chars + len(section)
        if truncated:
            break

    return "\n\n".join(sections)


def _build_budgeted_context_sections(
    retrieval_result: RetrievalResult,
    max_context_tokens: int,
    user_query: str = "",
    visible_records: list | None = None,
) -> str:
    """Build a single context string that keeps domain hints inside the same budget."""
    chunks = sorted(
        _apply_prompt_source_caps(retrieval_result),
        key=lambda chunk: _prompt_chunk_rank(chunk, user_query),
    )
    domain_hint = getattr(retrieval_result, "domain_hint", "")
    max_chars = max_context_tokens * CHARS_PER_TOKEN

    if not domain_hint:
        return _build_context_sections(
            chunks,
            max_tokens=max_context_tokens,
            visible_records=visible_records,
        )

    domain_hint = _truncate_text(domain_hint, max_chars)
    remaining_chars = max(0, max_chars - len(domain_hint) - 2)

    if remaining_chars <= 0:
        return domain_hint

    context_sections = _build_context_sections(
        chunks,
        max_tokens=max(1, remaining_chars // CHARS_PER_TOKEN),
        visible_records=visible_records,
        context_offset=len(domain_hint) + 2,
    )
    combined = domain_hint
    if context_sections:
        combined = f"{domain_hint}\n\n{context_sections}"

    return _truncate_text(combined, max_chars)


def _prompt_chunk_rank(chunk: RetrievalChunk, user_query: str = "") -> tuple[int, float]:
    """Prefer grounded KG/entity evidence ahead of generic background context."""
    grounded_kg = chunk.source == "kg" and bool(chunk.entity_ids)
    grounded_any = bool(chunk.entity_ids)
    table_scenario_metric = _table_chunk_matches_scenario_metric_query(chunk, user_query)
    if _figure_reference_match(user_query, chunk.text):
        priority = -1
    elif table_scenario_metric:
        priority = 0
    elif grounded_kg:
        priority = 1
    elif grounded_any:
        priority = 2
    else:
        priority = 3
    return (priority, -float(chunk.score or 0.0), identify(chunk_candidate(chunk))["evidence_id"])


def _table_chunk_matches_scenario_metric_query(chunk: RetrievalChunk, user_query: str) -> bool:
    if chunk.source != "table":
        return False

    query = user_query or ""
    alias_match = re.search(r"w\d+s\d+", query, flags=re.IGNORECASE)
    if not alias_match:
        return False

    table_data = (chunk.metadata or {}).get("table_data", {}) or {}
    table_context = table_data.get("context", {}) or {}
    haystack = " ".join(
        str(part)
        for part in [
            chunk.text,
            table_data.get("column_name", ""),
            table_data.get("column_value", ""),
            *(table_context.values() if isinstance(table_context, dict) else []),
        ]
        if part
    ).lower()

    alias = alias_match.group(0).lower()
    if alias not in haystack:
        return False

    metric_terms = ("消纳率", "utilization rate", "绿电", "弃电量", "curtailment", "mwh")
    return any(term in query.lower() or term in query for term in metric_terms) and any(
        term in haystack for term in [t.lower() for t in metric_terms]
    )


def _figure_reference_match(user_query: str, chunk_text: str) -> bool:
    query = user_query or ""
    text = chunk_text or ""

    query_match = re.search(r"(图|figure)\s*(\d+)", query, flags=re.IGNORECASE)
    if not query_match:
        return False

    figure_no = query_match.group(2)
    return re.search(rf"(图|figure)\s*{re.escape(figure_no)}", text, flags=re.IGNORECASE) is not None


def _truncate_text(text: str, max_chars: int) -> str:
    """Trim arbitrary text to a character budget while preserving a truncation marker."""
    if len(text) <= max_chars:
        return text

    if max_chars <= 0:
        return ""

    suffix = "\n[...truncated]"
    if max_chars <= len(suffix):
        return suffix[:max_chars]

    return text[: max_chars - len(suffix)] + suffix


def _apply_prompt_source_caps(retrieval_result: RetrievalResult) -> list[RetrievalChunk]:
    """Reapply source caps before prompt build as a final safety check."""
    pipeline_meta = retrieval_result.pipeline or {}
    caps = pipeline_meta.get("per_source_caps")
    max_total = pipeline_meta.get("max_total_candidates")
    if not isinstance(caps, dict) or not isinstance(max_total, int):
        return retrieval_result.chunks

    chunk_dicts = [
        {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "score": chunk.score,
            "source": chunk.source,
            "page_idx": chunk.page_idx,
            "section_title": chunk.section_title,
            "entity_ids": list(chunk.entity_ids),
            "metadata": dict(chunk.metadata),
        }
        for chunk in retrieval_result.chunks
    ]
    trimmed = trim_results_by_source_budget(chunk_dicts, caps, max_total)
    return [
        RetrievalChunk(
            chunk_id=item["chunk_id"],
            text=item.get("text", ""),
            score=float(item.get("score", 0.0)),
            source=item.get("source", ""),
            page_idx=item.get("page_idx"),
            section_title=item.get("section_title", ""),
            entity_ids=item.get("entity_ids", []),
            metadata=item.get("metadata", {}),
        )
        for item in trimmed
    ]


def _format_text_chunk(chunk: RetrievalChunk, header: str) -> str:
    """Format a text/table chunk for the prompt."""
    text = chunk.text
    # Truncate individual chunk to ~2000 tokens
    max_chunk_chars = 2000 * CHARS_PER_TOKEN
    if len(text) > max_chunk_chars:
        text = text[:max_chunk_chars] + "..."

    return f"{header}\n{text}"


def _format_kg_chunk(chunk: RetrievalChunk, header: str) -> str:
    """Format a KG entity chunk for the prompt."""
    text = chunk.text
    # KG JSON is compact — keep as-is but cap at ~1000 tokens
    max_kg_chars = 1000 * CHARS_PER_TOKEN
    if len(text) > max_kg_chars:
        text = text[:max_kg_chars] + "..."

    entity_type = chunk.metadata.get("entity_type", "unknown")
    return f"{header} | Type: {entity_type}\n{text}"


def estimate_tokens(messages: list[dict]) -> dict:
    """Estimate token usage per section of the prompt."""
    system_content = next(
        (m["content"] for m in messages if m["role"] == "system"), ""
    )
    user_content = next(
        (m["content"] for m in messages if m["role"] == "user"), ""
    )

    return {
        "system": len(system_content) // CHARS_PER_TOKEN,
        "user": len(user_content) // CHARS_PER_TOKEN,
        "total": (len(system_content) + len(user_content)) // CHARS_PER_TOKEN,
    }


def get_token_budget_report(messages: list[dict]) -> dict:
    """Return token budget allocation report."""
    estimated = estimate_tokens(messages)
    return {
        "total": estimated["total"],
        "system": estimated["system"],
        "context_query": estimated["user"],
        "remaining": BUDGET.get("context", 12000) - estimated["user"],
        "budget_limit": BUDGET.copy(),
    }

