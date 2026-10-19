"""Offline format-adapter behavior, with unfamiliar synthetic documents."""
import importlib
import importlib.util
import socket
from xml.etree import ElementTree as ET

import pytest


def deny_network(*args, **kwargs):
    raise AssertionError("测试禁止网络")


@pytest.fixture(autouse=True)
def offline_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)


def module():
    assert importlib.util.find_spec("research.development_structure"), "结构适配模块尚未实现"
    return importlib.import_module("research.development_structure")


def html_fixture(raw):
    from research.scope_v2 import Source
    root = ET.fromstring(raw)
    paths = {root: "/html[1]"}
    blocks, text = [], ""
    for node in root.iter():
        counts = {}
        for child in node:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            paths[child] = paths[node] + f"/{child.tag}[{counts[child.tag]}]"
        if node.tag not in {"h1", "h2", "h3", "p", "pre", "tr"}:
            continue
        if node.tag == "tr":
            content = " | ".join(" ".join("".join(c.itertext()).split()) for c in node)
        else:
            content = "".join(node.itertext())
            content = content.strip() if node.tag == "pre" else " ".join(content.split())
        blocks.append(dict(tag=node.tag, xpath=paths[node], text=content, start=len(text), end=len(text)+len(content)))
        text += content + "\n\n"
    return Source("陌生源", text), blocks


def test_html_real_headings_and_grouped_table_ignore_pre_comments():
    raw = '<html><body><h2>8. Setup</h2><p>引导😀</p><table><tr><td>A</td><td>B</td></tr><tr><td>C</td><td>D</td></tr></table><h3>8.1. Detail</h3><pre># 99. Fake\nX=1</pre></body></html>'
    source, blocks = html_fixture(raw)
    index = module().build_html_structure(source, raw, blocks)
    assert [n.number for n in index.nodes if n.kind == "heading"] == ["8", "8.1"]
    table = next(n for n in index.nodes if n.kind == "table")
    assert source.text[table.start:table.end] == "A | B\n\nC | D"
    assert table.provenance["xpath"].endswith("/table[1]")
    assert next(n for n in index.nodes if n.kind == "pre").title == ""


def test_html_rejects_tampered_coordinate_and_nested_table():
    raw = '<html><body><h2>8. Setup</h2><table><tr><td><table><tr><td>X</td></tr></table></td></tr></table></body></html>'
    source, blocks = html_fixture(raw)
    with pytest.raises(ValueError, match="嵌套"):
        module().build_html_structure(source, raw, blocks)


def test_admonition_layout_table_is_distinct_from_data_table():
    raw = '<html><body><h2>8. Setup</h2><table><tr><td>A</td></tr></table><div class="admonitionblock"><table><tr><td>Note</td><td>直接说明</td></tr></table></div></body></html>'
    source, blocks = html_fixture(raw)
    index = module().build_html_structure(source, raw, blocks)
    assert [n.kind for n in index.nodes] == ["heading", "table", "admonition"]
    raw = '<html><body><h2>8. Setup</h2></body></html>'
    source, blocks = html_fixture(raw)
    blocks[0]["end"] -= 1
    with pytest.raises(ValueError):
        module().build_html_structure(source, raw, blocks)


def pdf_fixture(text):
    from research.scope_v2 import Source
    return Source("新PDF", text), [dict(pdf_page_one_based=1, start=0, end=len(text), text=text)]


def test_pdf_font_order_mapping_does_not_promote_body_numbered_list():
    text = "  7. Different heading\n正文😀\n1. body list\n  7.1. Child\n内容\n"
    xml = '<pdf2xml><page number="1"><fontspec id="1" family="Times,Bold"/><fontspec id="2" family="Times"/><text font="1" top="99"><b>7.</b></text><text font="2" top="99"> </text><text font="1" top="99"><b>Different heading</b></text><text font="2" top="99">1. body list</text><text font="1" top="99"><b>7.1. Child</b></text></page></pdf2xml>'
    source, pages = pdf_fixture(text)
    index = module().build_pdf_structure(source, pages, xml)
    assert [n.number for n in index.nodes] == ["7", "7.1"]
    assert source.text[index.nodes[0].start:index.nodes[0].end].strip() == "7. Different heading"
    assert index.nodes[0].provenance["pdf_page_one_based"] == 1


def test_pdf_duplicate_line_abstains_and_missing_font_evidence_abstains():
    source, pages = pdf_fixture("7. Heading\n7. Heading\n")
    xml = '<pdf2xml><page number="1"><fontspec id="1" family="Times,Bold"/><text font="1">7. Heading</text></page></pdf2xml>'
    assert module().build_pdf_structure(source, pages, xml).nodes == ()


def test_html_omitted_heading_block_cannot_certify_structure():
    raw = '<html><body><h2>8. Setup</h2><p>正文</p><h2>9. End</h2></body></html>'
    source, blocks = html_fixture(raw)
    with pytest.raises(ValueError, match="完整"):
        module().build_html_structure(source, raw, blocks[:-1])
    source, pages = pdf_fixture("7. Heading\n")
    xml = '<pdf2xml><page number="1"><text>7. Heading</text></page></pdf2xml>'
    assert module().build_pdf_structure(source, pages, xml).nodes == ()


@pytest.mark.parametrize("xml_pages", ['<page number="1"/>', '<page number="1"/><page number="2"/><page number="2"/>'])
def test_pdf_xml_must_cover_each_mapped_page_exactly_once(xml_pages):
    from research.scope_v2 import Source
    source = Source("陌生分页", "8. Start\n\f9. End\n")
    split = source.text.index("\f")
    pages = [dict(pdf_page_one_based=1,start=0,end=split,text=source.text[:split]),
             dict(pdf_page_one_based=2,start=split+1,end=len(source.text),text=source.text[split+1:])]
    with pytest.raises(ValueError, match="完整|重复"):
        module().build_pdf_structure(source, pages, "<pdf2xml>"+xml_pages+"</pdf2xml>")
