"""Format Bridge: MinerU output → LangExtract list[Document] + PositionMap."""

import json
import os
import re
from pathlib import Path

from schema import PositionMap, Segment, SectionSplit


def load_content_list(content_list_path: str) -> list[dict]:
    with open(content_list_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_full_md(full_md_path: str) -> str:
    with open(full_md_path, "r", encoding="utf-8") as f:
        return f.read()


def build_position_map(
    content_list: list[dict], full_md: str
) -> PositionMap:
    """Build position map by matching content_list text into full.md."""
    segments = []
    search_from = 0

    for i, item in enumerate(content_list):
        text = _item_to_text(item)
        if not text:
            continue

        normalized = _normalize(text)
        # Find in full.md
        pos = full_md.find(normalized, search_from)
        if pos < 0:
            # Try first 40 chars
            short = normalized[:40]
            pos = full_md.find(short, search_from)

        if pos >= 0:
            end = pos + len(normalized)
            segments.append(Segment(
                char_start=pos,
                char_end=end,
                source_item_idx=i,
                page_idx=item.get("page_idx", 0),
                bbox=item.get("bbox", [0, 0, 1000, 1000]),
                block_type=item.get("type", "text"),
                text_level=item.get("text_level"),
                text=text,
            ))
            search_from = end
        else:
            # Fallback: use previous segment end as position
            prev_end = segments[-1].char_end if segments else 0
            segments.append(Segment(
                char_start=prev_end,
                char_end=prev_end + len(normalized),
                source_item_idx=i,
                page_idx=item.get("page_idx", 0),
                bbox=item.get("bbox", [0, 0, 1000, 1000]),
                block_type=item.get("type", "text"),
                text_level=item.get("text_level"),
                text=text,
            ))

    return PositionMap(segments=segments)


def _item_to_text(item: dict) -> str:
    """Extract display text from a content_list item."""
    t = item.get("type", "")
    if t == "text":
        return item.get("text", "")
    if t == "table":
        caption = " ".join(item.get("table_caption", []))
        return caption or "[Table]"
    if t == "equation":
        return item.get("text", "")
    if t == "image":
        caption = " ".join(item.get("image_caption", []))
        return caption or "[Image]"
    if t in ("page_number", "footer", "page_footnote", "aside_text"):
        return item.get("text", "")
    if t == "chart":
        caption = " ".join(item.get("chart_caption", []))
        return caption or "[Chart]"
    if t == "list":
        return item.get("text", "")
    if t == "page_number":
        return ""
    return ""


def _normalize(text: str) -> str:
    """Normalize whitespace for matching."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def find_section_boundaries(
    content_list: list[dict],
    full_md: str,
    position_map: PositionMap,
    min_level: int = 2,
) -> list[SectionSplit]:
    """Find section boundaries using text_level from content_list.

    min_level=2 means split at H1 and H2 headings.
    """
    sections = []
    current_start = 0
    current_title = "(Preamble)"
    current_level = 0
    section_idx = 0

    # Collect heading items with their text_level
    candidate_breaks = []
    for item in content_list:
        lv = item.get("text_level")
        if lv is not None and lv > 0 and lv <= min_level:
            candidate_breaks.append(item)

    if not candidate_breaks:
        # No headings found; use full text as one section
        return [SectionSplit(
            document_id="sec_0_full",
            title="(Full Document)",
            heading_level=0,
            char_start=0,
            char_end=len(full_md),
        )]

    # Find each heading in full_md and split
    for item in candidate_breaks:
        heading_text = _normalize(item.get("text", ""))
        if not heading_text:
            continue

        pos = full_md.find(heading_text, current_start)
        if pos < 0:
            continue

        if pos > current_start + 20:  # meaningful gap → split
            sections.append(SectionSplit(
                document_id=f"sec_{section_idx}_{_slugify(current_title)}",
                title=current_title,
                heading_level=current_level,
                char_start=current_start,
                char_end=pos,
            ))
            section_idx += 1

        current_start = pos
        current_title = heading_text
        current_level = item.get("text_level", 0)

    # Final section
    sections.append(SectionSplit(
        document_id=f"sec_{section_idx}_{_slugify(current_title)}",
        title=current_title,
        heading_level=current_level,
        char_start=current_start,
        char_end=len(full_md),
    ))

    # Merge short trailing sections
    sections = _merge_short_sections(sections, full_md, min_chars=150)
    return sections


def _merge_short_sections(
    sections: list[SectionSplit], full_md: str, min_chars: int = 150
) -> list[SectionSplit]:
    """Merge sections smaller than min_chars into the previous one."""
    if len(sections) <= 1:
        return sections

    merged = []
    for sec in sections:
        sec_len = sec.char_end - sec.char_start
        if sec_len < min_chars and merged:
            # Merge into previous
            merged[-1] = SectionSplit(
                document_id=merged[-1].document_id,
                title=merged[-1].title,
                heading_level=merged[-1].heading_level,
                char_start=merged[-1].char_start,
                char_end=sec.char_end,
            )
        else:
            merged.append(sec)
    return merged


def _slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    slug = re.sub(r"[^a-zA-Z0-9一-鿿]", "_", text)
    return slug[:40].strip("_").lower() or "section"


def extract_section_text(full_md: str, section: SectionSplit) -> str:
    """Extract the text for a section from full.md."""
    return full_md[section.char_start:section.char_end].strip()


def build_documents(
    sections: list[SectionSplit], full_md: str
) -> tuple[list, dict]:
    """Build LangExtract Document objects from sections.

    Returns (documents, document_offsets).
    document_offsets: dict[document_id] → global_char_offset in full_md
    """
    from langextract.core.data import Document

    documents = []
    offsets = {}

    for sec in sections:
        text = extract_section_text(full_md, sec)
        if not text or len(text) < 10:
            continue

        doc = Document(
            text=text,
            document_id=sec.document_id,
            additional_context=f"Section: {sec.title}",
        )
        documents.append(doc)
        offsets[sec.document_id] = sec.char_start

    return documents, offsets
