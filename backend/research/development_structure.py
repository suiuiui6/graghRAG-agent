"""Source-grounded, offline structure bridges over unchanged canonical text.

Inputs are original XHTML / Poppler XML and verified block/page maps. No labels,
provider calls, guessed Markdown headings, or visual-coordinate clustering.
Invalid source maps raise ValueError; uncertain PDF headings are omitted with
diagnostics, so consumers can abstain rather than fabricate a boundary.
"""
from dataclasses import dataclass, field
import hashlib
import re
from typing import Sequence
from xml.etree import ElementTree as ET

from .scope_v2 import Source


@dataclass(frozen=True)
class StructureNode:
    kind: str
    start: int
    end: int
    level: int = 0
    number: str = ""
    title: str = ""
    provenance: dict = field(default_factory=dict)
    source_id: str = ""


@dataclass(frozen=True)
class StructureIndex:
    source_id: str
    source_sha256: str
    nodes: tuple[StructureNode, ...]
    metadata: dict = field(default_factory=dict)


def _sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _norm(text: str) -> str:
    return " ".join(text.split())


def _number(title: str) -> str:
    match = re.match(r"^(\d+(?:\.\d+)*)(?:\.)?\s+\S", title)
    return match[1] if match else ""


def _tag(node) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _validate_span(source: Source, record: dict) -> None:
    a, b = record["start"], record["end"]
    if type(a) is not int or type(b) is not int or not 0 <= a < b <= len(source.text):
        raise ValueError("结构坐标不是合法Unicode区间")
    if source.text[a:b] != record["text"]:
        raise ValueError("结构文本与canonical坐标不一致")


def build_html_structure(source: Source, raw_html: str | bytes,
                         blocks: Sequence[dict]) -> StructureIndex:
    """Verify every supplied XHTML block, preserving native heading/table/pre tags."""
    root = ET.fromstring(raw_html)
    paths, parents = {root: f"/{_tag(root)}[1]"}, {}
    for node in root.iter():
        counts = {}
        for child in node:
            tag = _tag(child)
            counts[tag] = counts.get(tag, 0) + 1
            paths[child] = paths[node] + f"/{tag}[{counts[tag]}]"
            parents[child] = node
    lookup = {path: node for node, path in paths.items()}
    if any(_tag(node) == "table" and any(_tag(child) == "table" for child in node.iter() if child is not node)
           for node in root.iter()):
        raise ValueError("嵌套表格不能安全分组")
    selected_tags = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "tr", "figcaption"}
    expected_paths = []
    for node in root.iter():
        if _tag(node) not in selected_tags or not _norm("".join(node.itertext())):
            continue
        ancestor, excluded = parents.get(node), False
        while ancestor is not None:
            if _tag(ancestor) in selected_tags | {"head", "script", "style"}:
                excluded = True
            ancestor = parents.get(ancestor)
        if not excluded:
            expected_paths.append(paths[node])
    if [block["xpath"] for block in blocks] != expected_paths:
        raise ValueError("结构块不是原件完整顺序映射")
    nodes, tables, previous_end = [], {}, -1
    for block in blocks:
        _validate_span(source, block)
        if block["start"] < previous_end:
            raise ValueError("结构块重叠或顺序错误")
        previous_end = block["end"]
        node = lookup.get(block["xpath"])
        if node is None or _tag(node) != block["tag"]:
            raise ValueError("XPath/tag与原件不一致")
        tag = _tag(node)
        if tag == "tr":
            actual = " | ".join(_norm("".join(c.itertext())) for c in node if _tag(c) in {"td", "th"})
        else:
            actual = "".join(node.itertext())
            actual = actual.strip() if tag == "pre" else _norm(actual)
        if actual != block["text"]:
            raise ValueError("原件文本与结构块不一致")
        provenance = {"xpath": block["xpath"], "tag": tag, "block_sha256": _sha(actual)}
        if re.fullmatch(r"h[1-6]", tag):
            nodes.append(StructureNode("heading", block["start"], block["end"], int(tag[1]), _number(actual), actual, provenance, source.key))
        elif tag == "pre":
            nodes.append(StructureNode("pre", block["start"], block["end"], provenance=provenance, source_id=source.key))
        elif tag == "tr":
            ancestors, ancestor = [], parents.get(node)
            while ancestor is not None:
                if _tag(ancestor) == "table":
                    ancestors.append(ancestor)
                ancestor = parents.get(ancestor)
            if len(ancestors) != 1:
                raise ValueError("嵌套或缺失table祖先，不能安全分组")
            table = ancestors[0]
            if any(_tag(n) == "table" for n in table.iter() if n is not table):
                raise ValueError("嵌套表格不能安全分组")
            tables.setdefault(paths[table], []).append(block)
    for path, rows in tables.items():
        a, b = rows[0]["start"], rows[-1]["end"]
        if any(block["start"] >= a and block["end"] <= b and block not in rows for block in blocks):
            raise ValueError("混合表格块不能安全分组")
        table = lookup[path]
        ancestor, admonition = table, False
        while ancestor is not None:
            if "admonitionblock" in ancestor.get("class", "").split():
                admonition = True
            ancestor = parents.get(ancestor)
        nodes.append(StructureNode("admonition" if admonition else "table", a, b,
                                   provenance={"xpath": path, "row_xpaths": [row["xpath"] for row in rows],
                                               "classification": "NATIVE_ADMONITION_CLASS" if admonition else "NATIVE_TABLE"}, source_id=source.key))
    return StructureIndex(source.key, _sha(source.text), tuple(sorted(nodes, key=lambda n: (n.start, n.end))),
                          {"format": "XHTML", "raw_sha256": _sha(raw_html), "coordinate_system": "LF_UNICODE_HALF_OPEN"})


def build_pdf_structure(source: Source, pages: Sequence[dict],
                        poppler_xml: str | bytes) -> StructureIndex:
    """Map font/bold-proven numbered headings to unique whole canonical lines.

    Consecutive bold number + title fragments are joined in XML node order,
    allowing whitespace fragments between them. PDF y values are never used.
    """
    root = ET.fromstring(poppler_xml)
    by_page = {}
    previous_end = -1
    for page in pages:
        _validate_span(source, page)
        number = page["pdf_page_one_based"]
        if number in by_page or page["start"] < previous_end:
            raise ValueError("PDF页重复或页坐标重叠")
        by_page[number] = page
        previous_end = page["end"]
    xml_pages = root.findall("page")
    xml_page_numbers = [int(page.get("number", "0")) for page in xml_pages]
    if len(xml_page_numbers) != len(set(xml_page_numbers)):
        raise ValueError("XML页重复，无法证明完整边界")
    if set(xml_page_numbers) != set(by_page):
        raise ValueError("XML与canonical页集合不完整或不一致")
    nodes, diagnostics, fonts = [], [], {}
    for xml_page in xml_pages:
        for font in xml_page.findall("fontspec"):
            fonts[font.get("id")] = dict(font.attrib)
        page_number = int(xml_page.get("number", "0"))
        page = by_page.get(page_number)
        if page is None:
            raise ValueError("XML页无canonical映射")
        texts = list(xml_page.findall("text"))
        lines, offset = [], page["start"]
        for line in page["text"].splitlines(keepends=True):
            lines.append((_norm(line), offset, offset + len(line.rstrip("\r\n"))))
            offset += len(line)
        for i, element in enumerate(texts):
            text = _norm("".join(element.itertext()))
            font = fonts.get(element.get("font"), {})
            bold = "bold" in font.get("family", "").lower() or element.find("b") is not None
            if not re.match(r"^\d+(?:\.\d+)*\.(?:\s|$)", text):
                continue
            if not font.get("family"):
                diagnostics.append({"page": page_number, "xml_nodes": [i],
                                    "status": "MISSING_FONT_EVIDENCE", "font_id": element.get("font")})
                continue
            if not bold:
                continue
            fragments, evidence = [text], [i]
            if not _number(text):
                for j in range(i + 1, len(texts)):
                    next_text = _norm("".join(texts[j].itertext()))
                    if not next_text:
                        continue
                    next_font = fonts.get(texts[j].get("font"), {})
                    if (texts[j].find("b") is not None or "bold" in next_font.get("family", "").lower()) and next_font:
                        fragments.append(next_text)
                        evidence.append(j)
                    break
            title = " ".join(fragments)
            number = _number(title)
            if not number:
                diagnostics.append({"page": page_number, "xml_nodes": evidence,
                                    "status": "INCOMPLETE_HEADING_FRAGMENTS"})
                continue
            matches = [(a, b) for line, a, b in lines if line == title]
            if len(matches) != 1:
                diagnostics.append({"page": page_number, "xml_nodes": evidence, "status": "NONUNIQUE_OR_MISSING_LINE"})
                continue
            a, b = matches[0]
            nodes.append(StructureNode("heading", a, b, len(number.split(".")), number, title,
                                       {"pdf_page_one_based": page_number, "xml_text_nodes_zero_based": evidence,
                                        "font": font, "matching": "UNIQUE_NORMALIZED_FULL_LINE"}, source.key))
    return StructureIndex(source.key, _sha(source.text), tuple(sorted(nodes, key=lambda n: n.start)),
                          {"format": "PDF_POPPLER_XML", "xml_sha256": _sha(poppler_xml),
                           "coordinate_system": "LF_UNICODE_HALF_OPEN", "diagnostics": diagnostics})
