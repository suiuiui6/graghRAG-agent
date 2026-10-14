"""Source grounding: LangExtract char_interval → PDF bbox + page_idx."""

from langextract.core.data import AnnotatedDocument, Extraction

from schema import PositionMap, GroundedExtraction


def resolve_grounding(
    annotated_documents: list[AnnotatedDocument],
    position_map: PositionMap,
    document_offsets: dict[str, int],
) -> list[GroundedExtraction]:
    """Resolve source grounding for all extractions across documents.

    Args:
        annotated_documents: LangExtract output per document.
        position_map: char ranges → content_list items.
        document_offsets: document_id → global char offset in full.md.

    Returns:
        Grounded extractions with page_idx, bbox_norm, block_type.
    """
    results: list[GroundedExtraction] = []

    for adoc in annotated_documents:
        doc_id = adoc.document_id
        doc_offset = document_offsets.get(doc_id, 0)
        extractions = adoc.extractions or []

        for ext in extractions:
            grounded = _ground_one(ext, doc_offset, position_map)
            results.append(grounded)

    return results


def _ground_one(
    ext: Extraction, doc_offset: int, position_map: PositionMap
) -> GroundedExtraction:
    """Ground a single extraction."""
    ci = ext.char_interval

    if ci is None or ci.start_pos is None or ci.end_pos is None:
        return GroundedExtraction(
            extraction_class=ext.extraction_class,
            extraction_text=ext.extraction_text,
            attributes=ext.attributes,
            char_interval=None,
            page_idx=None,
            bbox_norm=None,
            block_type=None,
            grounding_status="ungrounded",
        )

    # Map to global full.md position
    global_start = doc_offset + ci.start_pos
    global_end = doc_offset + ci.end_pos

    seg = position_map.lookup_range(global_start, global_end)

    if seg is None:
        return GroundedExtraction(
            extraction_class=ext.extraction_class,
            extraction_text=ext.extraction_text,
            attributes=ext.attributes,
            char_interval=(global_start, global_end),
            page_idx=None,
            bbox_norm=None,
            block_type=None,
            grounding_status="ungrounded",
        )

    return GroundedExtraction(
        extraction_class=ext.extraction_class,
        extraction_text=ext.extraction_text,
        attributes=ext.attributes,
        char_interval=(global_start, global_end),
        page_idx=seg.page_idx,
        bbox_norm=seg.bbox,
        block_type=seg.block_type,
        grounding_status="grounded",
    )


def grounding_stats(grounded_extractions: list[GroundedExtraction]) -> dict:
    """Compute grounding statistics."""
    total = len(grounded_extractions)
    ok = sum(1 for g in grounded_extractions if g.grounding_status == "grounded")
    return {
        "total": total,
        "grounded": ok,
        "ungrounded": total - ok,
        "grounding_rate": ok / total if total > 0 else 0.0,
    }
