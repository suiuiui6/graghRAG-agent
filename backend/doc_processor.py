"""
Document Processing Module — §2.1 of rag-engineering-blueprint-v1.0.

Multi-format document parsing (PDF/DOCX/XLSX/Markdown), smart chunking,
metadata extraction, and deduplication. Outputs standardized chunks for
downstream embedding and indexing.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from logging_config import get_logger

if TYPE_CHECKING:
    # python-docx 只在运行时按需导入（见本文件内的 `from docx import Document`），
    # 但两处字符串注解 "Paragraph | None" / "Table | None" 需要这两个名字可解析，
    # 否则是悬空的前向引用（ruff F821）。TYPE_CHECKING 下导入不产生运行时开销。
    from docx.table import Table
    from docx.text.paragraph import Paragraph

logger = get_logger(__name__)


# ── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class ChunkMetadata:
    chunk_id: str
    source_file: str
    source_format: str  # "pdf" | "docx" | "xlsx" | "md"
    page_idx: int | None = None
    section_path: list[str] = field(default_factory=list)
    content_type: str = "text"  # "text" | "table" | "mixed"
    table_json: dict | None = None
    entity_types: list[str] = field(default_factory=list)
    project_id: str | None = None
    token_count: int = 0
    char_start: int = 0
    char_end: int = 0


@dataclass
class Chunk:
    chunk_id: str
    text: str
    content_type: str  # "text" | "table" | "mixed"
    table_json: dict | None = None
    metadata: ChunkMetadata | None = None


@dataclass
class Section:
    title: str
    level: int
    text: str
    content_type: str  # "text" | "table" | "mixed"
    table_json: dict | None = None
    page_idx: int | None = None
    char_start: int = 0
    char_end: int = 0


# ── Constants ────────────────────────────────────────────────────────────────

# Enterprise entity types (aligned with blueprint §2.4.3 KG entity types)
ENTERPRISE_ENTITY_TYPES = [
    "project_metadata", "person_role", "process_step", "metric",
    "milestone", "deliverable", "risk_item", "regulation_ref",
    "department", "timeline_event",
]

# Chunking defaults
DEFAULT_CHUNK_SIZE = 512   # tokens
DEFAULT_CHUNK_OVERLAP = 64  # tokens

# Approximate token count (4 chars ≈ 1 token for Chinese, 4 chars ≈ 1 token for English)
CHARS_PER_TOKEN = 4


# ── Text Cleaning ────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Remove common header/footer artifacts, watermark patterns, and excess whitespace."""
    # Remove page numbers (standalone digits on a line)
    text = re.sub(r'^\d{1,4}\s*$', '', text, flags=re.MULTILINE)

    # Remove common header/footer patterns
    patterns = [
        r'^\s*第\s*\d+\s*页\s*(共\s*\d+\s*页)?\s*$',  # "第 X 页 共 Y 页"
        r'^\s*Page\s*\d+\s*(of\s*\d+)?\s*$',           # "Page X of Y"
        r'^\s*Confidential\s*$',
        r'^\s*内部资料\s*$',
        r'^\s*DRAFT\s*$',
    ]
    for pat in patterns:
        text = re.sub(pat, '', text, flags=re.MULTILINE | re.IGNORECASE)

    # Collapse multiple blank lines into single blank line
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip leading/trailing whitespace
    return text.strip()


# ── Format Router ────────────────────────────────────────────────────────────

def parse_document(file_path: str | Path) -> list[Section]:
    """Route to the correct parser based on file extension.

    Args:
        file_path: Path to the document file or a MinerU output directory.

    Returns:
        List of Section objects with parsed content.
    """
    file_path = Path(file_path)

    # If it's a directory, treat as MinerU output
    if file_path.is_dir():
        return _parse_pdf_via_mineru(str(file_path))

    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return _parse_pdf_via_mineru(str(file_path))
    elif ext == ".docx":
        return _parse_docx(file_path)
    elif ext == ".xlsx":
        return _parse_xlsx_structured(file_path)
    elif ext == ".md":
        return _parse_markdown(file_path)
    else:
        raise ValueError(f"Unsupported format: {ext}")


# ── PDF Parser (MinerU) ─────────────────────────────────────────────────────

def _parse_pdf_via_mineru(file_path: str | Path) -> list[Section]:
    """Parse PDF via existing MinerU output cache.

    For PDF files, we rely on the existing MinerU → BridgePipeline flow.
    This function reads already-parsed MinerU output and converts to Section format.
    """
    file_path = str(file_path)

    # If the path is a MinerU output directory, read it directly
    mineru_dir = file_path if os.path.isdir(file_path) else None

    if mineru_dir is None:
        # Try to find cached MinerU output
        base_output = os.path.join(os.path.dirname(__file__), "output", "mineru")
        if os.path.isdir(base_output):
            for entry in sorted(os.listdir(base_output), reverse=True):
                entry_path = os.path.join(base_output, entry)
                if os.path.isdir(entry_path):
                    full_md = os.path.join(entry_path, "full.md")
                    if os.path.exists(full_md):
                        mineru_dir = entry_path
                        break

    if mineru_dir is None:
        raise FileNotFoundError(f"No MinerU output found for: {file_path}")

    return _parse_mineru_output_dir(mineru_dir)


def _parse_mineru_output_dir(mineru_dir: str) -> list[Section]:
    """Parse a MinerU output directory into Section objects.

    Reads full.md and content_list.json from the MinerU output.
    """
    import glob as glob_mod

    full_md_path = os.path.join(mineru_dir, "full.md")
    cl_pattern = os.path.join(mineru_dir, "*_content_list.json")
    cl_files = [f for f in glob_mod.glob(cl_pattern) if "_v2" not in f]

    if not cl_files or not os.path.exists(full_md_path):
        raise FileNotFoundError(f"Incomplete MinerU output in: {mineru_dir}")

    # Read full markdown
    with open(full_md_path, "r", encoding="utf-8") as f:
        full_md = f.read()

    # Read content list
    with open(cl_files[0], "r", encoding="utf-8") as f:
        content_list = json.load(f)

    # Build position map and find section boundaries
    from bridge import build_position_map, find_section_boundaries

    position_map = build_position_map(content_list, full_md)
    sections = find_section_boundaries(content_list, full_md, position_map, min_level=2)

    # Convert SectionSplit objects to Section objects
    result = []
    char_offset = 0
    for i, sec in enumerate(sections):
        text = full_md[sec.char_start:sec.char_end].strip()
        if not text:
            continue

        # Find page_idx from the position map for this section's char range
        page_idx = None
        seg = position_map.lookup(sec.char_start)
        if seg:
            page_idx = seg.page_idx

        result.append(Section(
            title=sec.title or f"section_{i}",
            level=sec.heading_level,
            text=text,
            content_type="text",
            page_idx=page_idx,
            char_start=char_offset,
            char_end=char_offset + len(text),
        ))
        char_offset += len(text)

    return result


# ── DOCX Parser ──────────────────────────────────────────────────────────────

def _parse_docx(file_path: str | Path) -> list[Section]:
    """Parse DOCX files using python-docx.

    Extracts paragraphs and tables, preserving heading hierarchy and table structure.
    """
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx is required for DOCX parsing. Install: pip install python-docx")

    doc = Document(str(file_path))
    sections = []
    char_offset = 0
    current_section_title = ""
    current_level = 1

    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag == "p":
            para = _find_paragraph_in_doc(doc, element)
            if para is None:
                continue

            text = para.text.strip()
            if not text:
                continue

            # Check if this is a heading
            if para.style and para.style.name and para.style.name.startswith("Heading"):
                try:
                    current_level = int(para.style.name.split()[-1])
                except ValueError:
                    current_level = 1
                current_section_title = text
                continue

            sections.append(Section(
                title=current_section_title or os.path.basename(str(file_path)),
                level=current_level,
                text=text,
                content_type="text",
                char_start=char_offset,
                char_end=char_offset + len(text),
            ))
            char_offset += len(text)

        elif tag == "tbl":
            table = _find_table_in_doc(doc, element)
            if table is None:
                continue

            table_data = _extract_table_data_from_docx(table)
            table_text = _table_to_text(table_data)
            sections.append(Section(
                title=current_section_title or os.path.basename(str(file_path)),
                level=current_level,
                text=table_text,
                content_type="table",
                table_json=table_data,
                char_start=char_offset,
                char_end=char_offset + len(table_text),
            ))
            char_offset += len(table_text)

    return sections


def _find_paragraph_in_doc(doc, element) -> "Paragraph | None":
    """Find a Paragraph object matching an XML element."""
    for para in doc.paragraphs:
        if para._element is element:
            return para
    return None


def _find_table_in_doc(doc, element) -> "Table | None":
    """Find a Table object matching an XML element."""
    for table in doc.tables:
        if table._element is element:
            return table
    return None


def _extract_table_data_from_docx(table) -> dict:
    """Extract table structure from python-docx Table object."""
    headers = []
    rows = []
    for i, row in enumerate(table.rows):
        cells = [cell.text.strip() for cell in row.cells]
        if i == 0:
            headers = cells
        else:
            rows.append(cells)
    if not headers:
        headers = [f"col_{j}" for j in range(len(rows[0]) if rows else 1)]
    return {"headers": headers, "rows": rows}


# ── XLSX Parser ──────────────────────────────────────────────────────────────

def _parse_xlsx_structured(file_path: str | Path) -> list[Section]:
    """Parse XLSX files using openpyxl.

    Each sheet becomes an independent section with structured table data.
    """
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl is required for XLSX parsing. Install: pip install openpyxl")

    wb = openpyxl.load_workbook(str(file_path), data_only=True)
    sections = []
    char_offset = 0

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        headers = []
        rows = []

        for i, row in enumerate(ws.iter_rows(values_only=True)):
            row_values = [str(cell) if cell is not None else "" for cell in row]
            # Skip completely empty rows
            if all(v == "" for v in row_values):
                continue
            if i == 0:
                headers = row_values
            elif i == 1 and not headers:
                headers = row_values
            else:
                rows.append(row_values)

        if not headers and rows:
            headers = [f"col_{j}" for j in range(len(rows[0]))]

        if not rows:
            continue

        table_json = {"sheet_name": sheet_name, "headers": headers, "rows": rows}
        table_text = _table_to_text(table_json)

        sections.append(Section(
            title=sheet_name,
            level=1,
            text=table_text,
            content_type="table",
            table_json=table_json,
            page_idx=None,
            char_start=char_offset,
            char_end=char_offset + len(table_text),
        ))
        char_offset += len(table_text)

    wb.close()
    return sections


# ── Markdown Parser ──────────────────────────────────────────────────────────

def _parse_markdown(file_path: str | Path) -> list[Section]:
    """Parse Markdown files by splitting on headings."""
    with open(str(file_path), "r", encoding="utf-8") as f:
        content = f.read()

    sections = []
    char_offset = 0

    # Split by markdown headings
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    splits = list(heading_pattern.finditer(content))

    if not splits:
        # No headings, treat entire file as one section
        sections.append(Section(
            title=os.path.basename(str(file_path)),
            level=1,
            text=content.strip(),
            content_type="text",
            char_start=0,
            char_end=len(content),
        ))
        return sections

    for i, match in enumerate(splits):
        level = len(match.group(1))
        title = match.group(2).strip()
        start = match.end()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(content)
        text = content[start:end].strip()

        if text:
            sections.append(Section(
                title=title,
                level=min(level, 4),
                text=text,
                content_type="text",
                char_start=char_offset,
                char_end=char_offset + len(text),
            ))
            char_offset += len(text)

    return sections


# ── Smart Chunking ───────────────────────────────────────────────────────────

def chunk_sections(
    sections: list[Section],
    source_file: str,
    source_format: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    level: int = 2,  # 1=fixed-size, 2=semantic, 3=entity-aware
    mapping: dict[str, str] | None = None,
) -> list[Chunk]:
    """Convert Sections into Chunks using the specified chunking strategy.

    Level 1: Fixed-size chunking with overlap.
    Level 2: Semantic chunking — preserve section/chapter boundaries.
    Level 3: Entity-aware chunking — aggregate around entity mentions (reserved).
    """
    # Clean section texts before chunking
    for sec in sections:
        sec.text = clean_text(sec.text)

    chunks = []
    project_id = extract_project_id(source_file, "", "", mapping=mapping)

    if level == 1:
        chunks = _chunk_fixed_size(sections, source_file, source_format, chunk_size, overlap, project_id)
    elif level == 2:
        chunks = _chunk_semantic(sections, source_file, source_format, project_id)
    elif level == 3:
        chunks = _chunk_entity_aware(sections, source_file, source_format, project_id)
    else:
        chunks = _chunk_semantic(sections, source_file, source_format, project_id)

    # Assign chunk IDs
    for i, c in enumerate(chunks):
        c.chunk_id = f"c{i + 1:05d}"
        if c.metadata:
            c.metadata.chunk_id = c.chunk_id
            c.metadata.token_count = _estimate_tokens(c.text)

    return chunks


def _chunk_fixed_size(
    sections: list[Section],
    source_file: str,
    source_format: str,
    chunk_size: int,
    overlap: int,
    project_id: str | None,
) -> list[Chunk]:
    """Level 1: Fixed-size chunking with overlap."""
    chunks = []
    chunk_chars = chunk_size * CHARS_PER_TOKEN
    overlap_chars = overlap * CHARS_PER_TOKEN

    for section in sections:
        text = section.text
        start = 0
        while start < len(text):
            end = min(start + chunk_chars, len(text))
            chunk_text = text[start:end]

            if chunk_text.strip():
                metadata = ChunkMetadata(
                    chunk_id="",
                    source_file=source_file,
                    source_format=source_format,
                    page_idx=section.page_idx,
                    section_path=[section.title],
                    content_type=section.content_type,
                    table_json=section.table_json,
                    project_id=project_id,
                    char_start=section.char_start + start,
                    char_end=section.char_start + end,
                )
                chunks.append(Chunk(
                    chunk_id="",
                    text=chunk_text,
                    content_type=section.content_type,
                    table_json=section.table_json,
                    metadata=metadata,
                ))

            start += chunk_chars - overlap_chars
            if end >= len(text):
                break

    return chunks


def _chunk_semantic(
    sections: list[Section],
    source_file: str,
    source_format: str,
    project_id: str | None,
) -> list[Chunk]:
    """Level 2: Semantic chunking — keep sections/chapters intact.

    Table sections become independent chunks with structured JSON preserved.
    Text sections are kept as-is unless they exceed max size (then split).
    """
    chunks = []
    max_chars = 2000 * CHARS_PER_TOKEN  # 2000 tokens max per chunk

    for section in sections:
        text = section.text
        if not text.strip():
            continue

        # Tables always become independent chunks
        if section.content_type in ("table", "mixed") and section.table_json:
            metadata = ChunkMetadata(
                chunk_id="",
                source_file=source_file,
                source_format=source_format,
                page_idx=section.page_idx,
                section_path=[section.title],
                content_type=section.content_type,
                table_json=section.table_json,
                project_id=project_id,
                char_start=section.char_start,
                char_end=section.char_end,
            )
            chunks.append(Chunk(
                chunk_id="",
                text=text,
                content_type=section.content_type,
                table_json=section.table_json,
                metadata=metadata,
            ))
        elif len(text) <= max_chars:
            metadata = ChunkMetadata(
                chunk_id="",
                source_file=source_file,
                source_format=source_format,
                page_idx=section.page_idx,
                section_path=[section.title],
                content_type="text",
                project_id=project_id,
                char_start=section.char_start,
                char_end=section.char_end,
            )
            chunks.append(Chunk(
                chunk_id="",
                text=text,
                content_type="text",
                metadata=metadata,
            ))
        else:
            # Split long text sections at sentence boundaries
            sub_chunks = _split_long_text(text, max_chars)
            for j, sub_text in enumerate(sub_chunks):
                metadata = ChunkMetadata(
                    chunk_id="",
                    source_file=source_file,
                    source_format=source_format,
                    page_idx=section.page_idx,
                    section_path=[section.title, f"part_{j + 1}"],
                    content_type="text",
                    project_id=project_id,
                    char_start=section.char_start + (j * max_chars),
                    char_end=min(section.char_start + ((j + 1) * max_chars), section.char_end),
                )
                chunks.append(Chunk(
                    chunk_id="",
                    text=sub_text,
                    content_type="text",
                    metadata=metadata,
                ))

    return chunks


def _chunk_entity_aware(
    sections: list[Section],
    source_file: str,
    source_format: str,
    project_id: str | None,
) -> list[Chunk]:
    """Level 3: Entity-aware chunking — aggregate around entity mentions.

    Reserved for KG-enhanced retrieval scenarios. Falls back to semantic chunking
    when no entity annotations are available.
    """
    # For now, fall back to semantic chunking. Entity-aware chunking is activated
    # when KG entity extraction results are available to guide chunk boundaries.
    return _chunk_semantic(sections, source_file, source_format, project_id)


def _split_long_text(text: str, max_chars: int) -> list[str]:
    """Split long text at sentence boundaries (。！？\n) within max_chars."""
    if len(text) <= max_chars:
        return [text]

    # Try to split at sentence boundaries
    parts = []
    remaining = text

    while len(remaining) > max_chars:
        # Find the last sentence break within max_chars
        split_point = max_chars
        for m in re.finditer(r'[。！？\n]', remaining[:max_chars]):
            split_point = m.end()

        parts.append(remaining[:split_point].strip())
        remaining = remaining[split_point:].strip()

    if remaining.strip():
        parts.append(remaining.strip())

    return parts


# ── Project ID Mapping ─────────────────────────────────────────────────────────

def load_project_id_mapping(mapping_path: str | None = None) -> dict[str, str]:
    """Load filename → project_id mapping from a JSON configuration file.

    For mixed-directory ingestion (multiple project reports in one directory),
    this allows manual override of auto-detected project IDs.

    Args:
        mapping_path: Path to the mapping JSON file.
                      Defaults to ``backend/config/project_id_mapping.json``.

    Returns:
        Dict mapping filename (basename) → project_id string.
        Returns an empty dict if the file does not exist or is invalid.
    """
    if mapping_path is None:
        mapping_path = os.path.join(os.path.dirname(__file__), "config", "project_id_mapping.json")

    if not os.path.isfile(mapping_path):
        return {}

    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # The file may have comments via "_comment" keys; filter to string-only values
        return {k: v for k, v in data.items() if isinstance(v, str)}
    except (json.JSONDecodeError, IOError):
        return {}


# ── Project ID Extraction ────────────────────────────────────────────────────

def extract_project_id(
    file_path: str,
    section_title: str,
    chunk_text: str,
    mapping: dict[str, str] | None = None,
) -> str | None:
    """Auto-detect project identifier from file path, section title, and content.

    Priority (high to low):
    0. Manual mapping (if ``mapping`` provided and filename matches a key)
    1. File name project code pattern (e.g., "XX项目中期报告_v2.docx" → "XX项目")
    2. Section title project name (e.g., "三、XX项目建设进展" → "XX项目")
    3. First 500 chars for project number (e.g., "项目编号: PJ-2026-042")
    4. No match → None ("__unassigned__")
    """
    filename = os.path.basename(file_path)

    # Rule 0: Manual mapping (highest priority, overrides all auto-detection)
    if mapping:
        mapped_id = mapping.get(filename)
        if mapped_id is not None:
            return mapped_id

    # Rule 1: File name project code pattern
    # Match patterns like "XX项目", "PJ-2026-042"
    project_patterns = [
        r'([A-Z]{2,4}[-_]\d{4}[-_]\d{3,})',   # PJ-2026-042
        r'([一-鿿]{2,8}项目)',           # XX项目
        r'(项目编号[:：]\s*([A-Za-z0-9_-]+))',    # 项目编号: PJ-2026-042
    ]

    for pattern in project_patterns:
        match = re.search(pattern, filename)
        if match:
            return match.group(1) if len(match.groups()) == 1 else match.group(2)

    # Rule 2: Section title
    if section_title:
        for pattern in project_patterns:
            match = re.search(pattern, section_title)
            if match:
                return match.group(1) if len(match.groups()) == 1 else match.group(2)

    # Rule 3: First 500 chars
    search_text = chunk_text[:500]
    for pattern in project_patterns:
        match = re.search(pattern, search_text)
        if match:
            return match.group(1) if len(match.groups()) == 1 else match.group(2)

    # Rule 4: No match
    return None


# ── Deduplication ────────────────────────────────────────────────────────────

def deduplicate_chunks(chunks: list[Chunk], similarity_threshold: float = 0.85) -> list[Chunk]:
    """Remove near-duplicate chunks across documents.

    Uses Jaccard similarity on token sets. When two chunks exceed the threshold,
    the longer chunk is kept (more context).
    """
    if len(chunks) <= 1:
        return chunks

    # Tokenize each chunk for Jaccard comparison
    token_sets = [_tokenize(c.text) for c in chunks]
    keep = [True] * len(chunks)

    for i in range(len(chunks)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(chunks)):
            if not keep[j]:
                continue
            similarity = _jaccard_similarity(token_sets[i], token_sets[j])
            if similarity > similarity_threshold:
                # Keep the longer chunk
                if len(chunks[i].text) >= len(chunks[j].text):
                    keep[j] = False
                else:
                    keep[i] = False
                    break  # i was marked, move to next i

    return [c for c, k in zip(chunks, keep) if k]


def _tokenize(text: str) -> set[str]:
    """Simple tokenization: split on whitespace and punctuation for Jaccard."""
    tokens = re.findall(r'[一-鿿]|[a-zA-Z0-9]+', text.lower())
    return set(tokens)


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


# ── Utilities ────────────────────────────────────────────────────────────────

def _table_to_text(table_json: dict) -> str:
    """Convert table JSON to readable text representation."""
    headers = table_json.get("headers", [])
    rows = table_json.get("rows", [])

    if not rows:
        return ""

    lines = []
    if headers:
        lines.append(" | ".join(str(h) for h in headers))

    for row in rows:
        lines.append(" | ".join(str(cell) for cell in row))

    return "\n".join(lines)


def _estimate_tokens(text: str) -> int:
    """Rough token count estimation (4 chars ≈ 1 token)."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def save_chunks_jsonl(chunks: list[Chunk], output_path: str):
    """Save chunks to a JSONL file for downstream processing."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            record = {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "content_type": chunk.content_type,
                "table_json": chunk.table_json,
                "metadata": {
                    "chunk_id": chunk.metadata.chunk_id if chunk.metadata else "",
                    "source_file": chunk.metadata.source_file if chunk.metadata else "",
                    "source_format": chunk.metadata.source_format if chunk.metadata else "",
                    "page_idx": chunk.metadata.page_idx if chunk.metadata else None,
                    "section_path": chunk.metadata.section_path if chunk.metadata else [],
                    "content_type": chunk.metadata.content_type if chunk.metadata else "text",
                    "entity_types": chunk.metadata.entity_types if chunk.metadata else [],
                    "project_id": chunk.metadata.project_id if chunk.metadata else None,
                    "token_count": chunk.metadata.token_count if chunk.metadata else 0,
                    "char_start": chunk.metadata.char_start if chunk.metadata else 0,
                    "char_end": chunk.metadata.char_end if chunk.metadata else 0,
                },
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_chunks_jsonl(input_path: str) -> list[Chunk]:
    """Load chunks from a JSONL file."""
    chunks = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                meta = record.get("metadata", {})
                metadata = ChunkMetadata(
                    chunk_id=meta.get("chunk_id", ""),
                    source_file=meta.get("source_file", ""),
                    source_format=meta.get("source_format", ""),
                    page_idx=meta.get("page_idx"),
                    section_path=meta.get("section_path", []),
                    content_type=meta.get("content_type", "text"),
                    entity_types=meta.get("entity_types", []),
                    project_id=meta.get("project_id"),
                    token_count=meta.get("token_count", 0),
                    char_start=meta.get("char_start", 0),
                    char_end=meta.get("char_end", 0),
                )
                chunks.append(Chunk(
                    chunk_id=record["chunk_id"],
                    text=record["text"],
                    content_type=record.get("content_type", "text"),
                    table_json=record.get("table_json"),
                    metadata=metadata,
                ))
    return chunks


# ── Main Document Processor ──────────────────────────────────────────────────

class DocumentProcessor:
    """Top-level document processing orchestrator.

    Usage:
        processor = DocumentProcessor(chunk_strategy=2)
        chunks = processor.process("/data/project_reports/XX项目中期报告_v2.docx")
        processor.save(chunks, "output/chunks.jsonl")
    """

    def __init__(
        self,
        chunk_strategy: int = 2,
        dedup: bool = True,
        project_id_mapping: dict[str, str] | str | None = None,
    ):
        """Initialize the document processor.

        Args:
            chunk_strategy: 1=fixed-size, 2=semantic, 3=entity-aware.
            dedup: Whether to run cross-document deduplication.
            project_id_mapping: Either a dict of filename→project_id, a path to a
                mapping JSON file, or None. When None, defaults to
                ``backend/config/project_id_mapping.json`` (silently ignored if
                the file does not exist).
        """
        self.chunk_strategy = chunk_strategy
        self.dedup = dedup

        if isinstance(project_id_mapping, str):
            self._mapping = load_project_id_mapping(project_id_mapping)
        elif isinstance(project_id_mapping, dict):
            self._mapping = project_id_mapping
        else:
            self._mapping = load_project_id_mapping()

    def process(self, file_path: str | Path) -> list[Chunk]:
        """Parse a document and produce chunks."""
        file_path = str(file_path)
        source_format = Path(file_path).suffix.lower().lstrip(".")
        source_file = os.path.basename(file_path)

        sections = parse_document(file_path)
        chunks = chunk_sections(
            sections,
            source_file=source_file,
            source_format=source_format,
            level=self.chunk_strategy,
            mapping=self._mapping,
        )

        if self.dedup:
            chunks = deduplicate_chunks(chunks)

        return chunks

    def process_directory(self, dir_path: str) -> list[Chunk]:
        """Process all supported documents in a directory."""
        all_chunks = []
        supported_exts = {".pdf", ".docx", ".xlsx", ".md"}

        for root, _dirs, files in os.walk(dir_path):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in supported_exts:
                    fpath = os.path.join(root, fname)
                    try:
                        chunks = self.process(fpath)
                        all_chunks.extend(chunks)
                    except Exception as e:  # noqa: BLE001  # 目录批量解析时单文件失败仅跳过该文件，不影响其余文件的入库
                        logger.warning("doc_skipped", filename=fname, error=str(e), exc_info=True)

        if self.dedup and len(all_chunks) > 1:
            all_chunks = deduplicate_chunks(all_chunks)

        return all_chunks

    def save(self, chunks: list[Chunk], output_path: str):
        """Save chunks to JSONL."""
        save_chunks_jsonl(chunks, output_path)
