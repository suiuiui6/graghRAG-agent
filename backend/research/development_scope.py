"""Conservative explicit section selection using source-proven structure indexes."""
import hashlib
import re
from typing import Sequence
from .scope_v2 import Source, Span, Resolution, assemble_scope
from .development_structure import StructureIndex


def resolve_development_scope(query: str, sources: Sequence[Source],
                              indexes: Sequence[StructureIndex]) -> Resolution:
    """Return native Resolution; no answer labels, query IDs or source-specific rules.

    A single section includes descendants. A connected range must cover every
    sibling number between ordered endpoints. Opening tables retain the whole
    introductory region before the first child heading, or abstain if ambiguous.
    """
    def abstain(reason):
        return Resolution("UNRESOLVED", reason=reason)

    if len(sources) != 1 or len(indexes) != 1:
        return abstain("必须显式唯一来源及结构索引")
    source, index = sources[0], indexes[0]
    if index.source_id != source.key or index.source_sha256 != hashlib.sha256(source.text.encode("utf-8")).hexdigest():
        return abstain("结构索引来源身份不匹配")
    if index.metadata.get("diagnostics"):
        return abstain("PDF标题边界存在不唯一或缺失映射")
    if any(not 0 <= node.start < node.end <= len(source.text) for node in index.nodes):
        return abstain("结构索引坐标无效")
    headings = sorted((n for n in index.nodes if n.kind == "heading"), key=lambda n: n.start)
    numbers = re.findall(r"(?<![\d.])(\d+(?:\.\d+)+)(?!\d|\.\d)", query)
    if not numbers:
        numbers = re.findall(r"(?:第\s*|section\s+)(\d+)\s*(?:[章节]|\b)", query, re.I)
    if not numbers:
        return abstain("未提供显式章节范围")
    if len(numbers) != len(set(numbers)):
        return abstain("重复章节选择")

    def find(number):
        found = [h for h in headings if h.number == number]
        return found[0] if len(found) == 1 else None

    selected = [find(number) for number in numbers]
    if any(h is None for h in selected):
        return abstain("章节缺失或重复")
    first, last = selected[0], selected[-1]
    if len(numbers) > 1:
        if len(numbers) != 2 or not re.search(re.escape(numbers[0]) + r"\s*[–—−~至到\-]\s*" + re.escape(numbers[1]), query):
            return abstain("离散多选不是连续范围")
        a, b = numbers[0].split("."), numbers[1].split(".")
        if a[:-1] != b[:-1] or len(a) != len(b) or int(a[-1]) >= int(b[-1]) or first.level != last.level:
            return abstain("反向或跨父级范围")
        expected = [".".join(a[:-1] + [str(i)]) for i in range(int(a[-1]), int(b[-1]) + 1)]
        siblings = [h.number for h in headings if first.start <= h.start <= last.start and h.level == first.level]
        if siblings != expected or any(find(number) is None for number in expected):
            return abstain("范围中间编号缺失、重复或顺序不一致")
    end = len(source.text)
    for heading in headings:
        if heading.start > last.start and heading.level <= last.level:
            end = heading.start
            break
    kind = "section_range" if len(numbers) > 1 else "section"
    opening = re.search(r"(?:开头|起始|opening|initial).{0,12}(?:表格|表|table)", query, re.I)
    if opening:
        if len(numbers) != 1:
            return abstain("开头表格要求单一章节")
        children = [h for h in headings if first.end <= h.start < end and h.level > first.level]
        intro_end = children[0].start if children else end
        tables = [n for n in index.nodes if n.kind == "table" and first.end <= n.start and n.end <= intro_end]
        if len(tables) != 1:
            return abstain("开头区域没有唯一原生表格")
        end, kind = intro_end, "opening_table_region"
    return Resolution("RESOLVED", (Span(source.key, first.start, end),), kind=kind,
                      scan_proof={"status": "SOURCE_VERIFIED_STRUCTURE", "source": source.key,
                                  "source_lf_sha256": index.source_sha256,
                                  "detector_version": "development-source-structure-v1",
                                  "structure_metadata": index.metadata,
                                  "coverage_claim": "结构选择不证明答案条目穷尽"})
