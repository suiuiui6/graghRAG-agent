"""Independent, conservative query scope resolution over explicitly selected sources.

No retrieval, evaluation labels or provider calls are used. All coordinates refer
to LF-normalized Unicode codepoints, with an exclusive end offset.
"""
from dataclasses import dataclass
import hashlib
import re
from typing import Sequence


@dataclass(frozen=True)
class Source:
    key: str
    text: str

    def __post_init__(self):
        object.__setattr__(self, "text", self.text.replace("\r\n", "\n").replace("\r", "\n"))


@dataclass(frozen=True)
class Span:
    source: str
    start: int
    end: int


@dataclass(frozen=True)
class Resolution:
    status: str
    spans: tuple[Span, ...] = ()
    reason: str = ""
    kind: str = ""
    scan_proof: dict | None = None


@dataclass(frozen=True)
class Assembly:
    status: str
    text: str
    mappings: tuple[dict, ...]
    utf8_bytes: int
    characters: int
    scan_proof: dict | None = None


@dataclass(frozen=True)
class _Heading:
    start: int
    end: int
    level: int
    number: str
    title: str
    origin: str


def _lines(text: str):
    offset = 0
    fence = None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        marker = re.match(r"(`{3,}|~{3,})", stripped)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            offset += len(line)
            continue
        if fence is None:
            yield offset, line
        offset += len(line)


def _headings(text: str) -> list[_Heading]:
    raw = []
    for offset, line in _lines(text):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if not match:
            plain = re.match(r"^(\d+(?:\.\d+)*)[ \t]+(\S.*?)\s*$", line)
            if not plain:
                continue
            title = plain[1] + " " + plain[2]
            level = len(plain[1].split("."))
            origin = "plain"
        else:
            title = match[2]
            level = len(match[1])
            origin = "atx"
        number = re.match(r"^(\d+(?:\.\d+)*)(?:[.、]?)(?=\D|$)", title)
        raw.append((offset, level, number[1] if number else "", title, origin))
    if any(origin == "atx" for _, _, _, _, origin in raw):
        # Explicit Markdown boundaries take precedence over body years/list lines.
        raw = [entry for entry in raw if entry[4] == "atx"]
    else:
        if not any("." in number for _, _, number, _, _ in raw):
            return []
        roots = [int(number.split(".")[0]) for _, _, number, _, _ in raw]
        if any(right not in (left, left + 1) for left, right in zip(roots, roots[1:])):
            # Inferred plain headings with incoherent numbering are uncertain.
            return []
    result = []
    for i, (offset, level, number, title, origin) in enumerate(raw):
        end = len(text)
        for next_offset, next_level, next_number, _, _ in raw[i + 1:]:
            if number and next_number:
                child = next_number.startswith(number + ".")
                if child:
                    continue
                end = next_offset
                break
            if next_level <= level:
                end = next_offset
                break
        result.append(_Heading(offset, end, level, number, title, origin))
    return result


def _unclosed_fence(text: str) -> bool:
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
    return fence is not None


def _section_numbers(query: str) -> list[str]:
    # A sentence-ending dot after 3.2.3 is punctuation, not another component.
    return re.findall(r"(?<![\d.])(\d+(?:\.\d+)+)(?!\d|\.\d)", query)


def _scan(source: Source, kind: str, spans: tuple[Span, ...]) -> Resolution:
    return Resolution("RESOLVED", spans, kind=kind, scan_proof={
        "status": "COMPLETE_LOCAL_SCAN", "source": source.key,
        "scanned_start": 0, "scanned_end": len(source.text),
        "projection": kind, "matched_spans": len(spans),
        "source_lf_sha256": hashlib.sha256(source.text.encode("utf-8")).hexdigest(),
        "detector_version": "scope-v2-structural-1",
        "coverage_claim": "仅证明本地完整扫描，输入覆盖由组装映射单独证明",
    })


def resolve_scope(query: str, sources: Sequence[Source]) -> Resolution:
    """Resolve explicit structural intent; ambiguity results in abstention."""
    if not sources:
        return Resolution("SOURCE_UNRESOLVED", reason="未显式选择来源")
    if len(sources) != 1:
        requested = set(_section_numbers(query))
        locations = []
        for candidate in sources:
            matches = [h for h in _headings(candidate.text) if h.number in requested]
            if matches:
                locations.extend(f"{candidate.key}@{h.start}:{h.end}" for h in matches)
            else:
                locations.append(f"{candidate.key}@0:{len(candidate.text)}")
        return Resolution("UNRESOLVED", reason="多个来源候选，无法确定唯一文档：" + ", ".join(locations))
    source = sources[0]
    headings = _headings(source.text)
    compact = re.sub(r"\s+", "", query).lower()
    numbers = _section_numbers(query)
    if not numbers:
        numbers = re.findall(r"(?:section\s*|第\s*)(\d+)(?:\s*[章节])?", query, re.I)
    if len(set(numbers)) > 1:
        return Resolution("UNRESOLVED", reason="多个章节候选，无法确定单一范围")
    item = re.search(r"第\s*(\d+)\s*项", query)
    caption_intent = re.search(r"(?:图注|题注|图题|编号(?:的)?图|(?:所有|全部).{0,12}图|figure|caption)", compact)
    table_intent = re.search(r"(?:表格|所有表|全部表|tables?)", compact)
    if numbers:
        candidates = [h for h in headings if h.number == numbers[0]]
    elif "摘要" in compact or "abstract" in compact:
        candidates = [h for h in headings if re.sub(r"\s+", "", h.title).lower() in {"摘要", "abstract"}]
    elif (caption_intent or table_intent) and not re.search(r"(?:章节|section)", query, re.I):
        # Collection intent outranks incidental mentions such as appendix aliases.
        candidates = []
    else:
        candidates = [h for h in headings if len(h.title) > 1 and h.title.lower() in query.lower()]
        if not candidates:
            candidates = []
            for heading in headings:
                title = re.sub(r"^\d+(?:\.\d+)*[.、]?\s*", "", heading.title).strip().lower()
                if title and title in query.lower():
                    candidates.append(heading)
    if candidates:
        if len(candidates) != 1:
            details = ", ".join(f"{source.key}@{h.start}:{h.end}" for h in candidates)
            return Resolution("UNRESOLVED", reason=f"章节重复候选：{details}")
        heading = candidates[0]
        if _unclosed_fence(source.text[heading.start:heading.end]):
            return Resolution("UNRESOLVED", reason="目标章节代码块未闭合，结构边界不确定", kind="subitem" if item else "section")
        if item:
            body = source.text[heading.start:heading.end]
            items = []
            for offset, line in _lines(body):
                match = re.match(r"^[ \t]*(?:\((\d+)\)|（(\d+)）|(\d+)[.、])[ \t]+", line)
                if match:
                    items.append((offset, match))
            matches = [(i, offset, match) for i, (offset, match) in enumerate(items) if next(g for g in match.groups() if g) == item[1]]
            if len(matches) != 1:
                return Resolution("UNRESOLVED", reason="子项不存在或重复，无法唯一定位", kind="subitem")
            i, offset, match = matches[0]
            start = heading.start + offset + match.start()
            while start < heading.end and source.text[start].isspace():
                start += 1
            end = heading.start + (items[i + 1][0] if i + 1 < len(items) else len(body))
            while end > start and source.text[end - 1].isspace():
                end -= 1
            return Resolution("RESOLVED", (Span(source.key, start, end),), kind="subitem")
        end = heading.end
        if re.sub(r"\s+", "", heading.title).lower() in {"摘要", "abstract"}:
            keyword = re.search(r"(?im)^[ \t]*(?:关键词|关\s*键\s*词|key\s*words?)\s*[:：]", source.text[heading.start:end])
            if keyword:
                end = heading.start + keyword.start()
        return Resolution("RESOLVED", (Span(source.key, heading.start, end),), kind="section")
    if numbers or item:
        return Resolution("UNRESOLVED", reason="未定位唯一章节或子项")
    if caption_intent:
        if not re.search(r"(?:所有|全部|全文|all|every)", compact):
            return Resolution("UNRESOLVED", reason="图注查询未指定清单范围")
        if _unclosed_fence(source.text):
            return Resolution("UNRESOLVED", reason="未闭合代码块导致图注扫描范围不确定", kind="figure_captions")
        spans = []
        for start, line in _lines(source.text):
            if re.match(r"^\s*(?:图\s*\d+|(?:Figure|Fig\.)\s*\d+)\s*(?:[:：.—–-]|\s)", line, re.I):
                spans.append(Span(source.key, start, start + len(line.rstrip("\n"))))
        return _scan(source, "figure_captions", tuple(spans))
    if table_intent:
        if not re.search(r"(?:所有|全部|全文|all|every)", compact):
            return Resolution("UNRESOLVED", reason="表格查询未指定唯一章节或全文范围")
        if _unclosed_fence(source.text):
            return Resolution("UNRESOLVED", reason="未闭合代码块导致表格扫描范围不确定", kind="tables")
        spans = []
        lines = list(_lines(source.text))
        i = 0
        while i < len(lines):
            start, line = lines[i]
            if line.lstrip().startswith("<table"):
                end = source.text.find("</table>", start)
                if end < 0:
                    return Resolution("UNRESOLVED", reason="表格标签不完整")
                spans.append(Span(source.key, start, end + len("</table>")))
                while i < len(lines) and lines[i][0] < end + len("</table>"):
                    i += 1
                continue
            if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1][1]):
                j = i + 2
                while j < len(lines) and "|" in lines[j][1] and lines[j][1].strip():
                    j += 1
                end = lines[j - 1][0] + len(lines[j - 1][1].rstrip("\n"))
                spans.append(Span(source.key, start, end))
                i = j
                continue
            i += 1
        return _scan(source, "tables", tuple(spans))
    if re.search(r"(?:全文|整篇|整个文档|完整文档|whole\s*document|entire\s*document)", query, re.I):
        return Resolution("RESOLVED", (Span(source.key, 0, len(source.text)),), kind="whole_document")
    return Resolution("UNRESOLVED", reason="查询没有可确定的显式结构范围")


def assemble_scope(resolution: Resolution, sources: Sequence[Source], max_bytes: int) -> Assembly:
    """Budget and map AUTO or externally supplied oracle ranges identically."""
    if type(max_bytes) is not int or max_bytes < 0:
        raise ValueError("max_bytes 必须是非负整数")
    if resolution.status != "RESOLVED":
        return Assembly(resolution.status, "", (), 0, 0, resolution.scan_proof)
    by_key = {source.key: source for source in sources}
    if len(by_key) != len(sources):
        raise ValueError("来源标识重复")
    ranges = []
    for span in resolution.spans:
        if span.source not in by_key:
            raise ValueError("范围引用未知来源")
        if type(span.start) is not int or type(span.end) is not int or not 0 <= span.start <= span.end <= len(by_key[span.source].text):
            raise ValueError("范围必须是合法的 Unicode 码点区间")
        if span.start != span.end:
            ranges.append(span)
    merged = []
    for span in sorted(ranges, key=lambda s: (s.source, s.start, s.end)):
        if merged and merged[-1].source == span.source and span.start <= merged[-1].end:
            previous = merged[-1]
            merged[-1] = Span(span.source, previous.start, max(previous.end, span.end))
        else:
            merged.append(span)
    text = ""
    used = 0
    mappings = []
    complete = True
    for span in merged:
        separator = "\n\n" if mappings else ""
        available = max_bytes - used - len(separator.encode("utf-8"))
        fragment = by_key[span.source].text[span.start:span.end]
        prefix = fragment.encode("utf-8")[:max(0, available)].decode("utf-8", errors="ignore")
        if not prefix:
            complete = False
            break
        text += separator
        output_start = len(text)
        text += prefix
        used += len((separator + prefix).encode("utf-8"))
        mappings.append({"source": span.source, "start": span.start, "end": span.start + len(prefix), "output_start": output_start, "output_end": len(text)})
        if len(prefix) < len(fragment):
            complete = False
            break
    return Assembly("COMPLETE_SCOPE" if complete else "PARTIAL_SCOPE", text, tuple(mappings), used, len(text), resolution.scan_proof)
