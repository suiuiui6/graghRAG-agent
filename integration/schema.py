"""Integration pipeline data types."""
from __future__ import annotations
import dataclasses


@dataclasses.dataclass
class Segment:
    """Maps a character range in full.md to a content_list item."""
    char_start: int
    char_end: int
    source_item_idx: int
    page_idx: int
    bbox: list[float]
    block_type: str
    text_level: int | None = None
    text: str = ""


@dataclasses.dataclass
class PositionMap:
    """Bidirectional map: full.md char positions → content_list items."""
    segments: list[Segment]

    def lookup(self, global_char_pos: int) -> Segment | None:
        for seg in self.segments:
            if seg.char_start <= global_char_pos < seg.char_end:
                return seg
        return None

    def lookup_range(self, start: int, end: int) -> Segment | None:
        """Find segment that contains [start, end)."""
        for seg in self.segments:
            if seg.char_start <= start and end <= seg.char_end:
                return seg
        # Best-effort: return segment containing start
        return self.lookup(start)


@dataclasses.dataclass
class SectionSplit:
    """Metadata for one document section."""
    document_id: str
    title: str
    heading_level: int
    char_start: int
    char_end: int


@dataclasses.dataclass
class GroundedExtraction:
    """Extraction with source grounding resolved."""
    extraction_class: str
    extraction_text: str
    attributes: dict | None
    char_interval: tuple[int, int] | None
    page_idx: int | None
    bbox_norm: list[float] | None
    block_type: str | None
    grounding_status: str       # "grounded" | "ungrounded"


@dataclasses.dataclass
class KGNode:
    node_id: str
    entity_type: str
    label: str
    properties: dict
    page_idx: int | None
    bbox_norm: list[float] | None
    grounding_status: str


@dataclasses.dataclass
class KGEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str
    properties: dict
