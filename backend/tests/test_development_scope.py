import importlib
import importlib.util
import socket
import pytest
from tests.test_development_structure import html_fixture, deny_network

@pytest.fixture(autouse=True)
def offline_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)


def resolve(query, raw):
    assert importlib.util.find_spec("research.development_scope"), "范围适配模块尚未实现"
    structure = importlib.import_module("research.development_structure")
    scope = importlib.import_module("research.development_scope")
    source, blocks = html_fixture(raw)
    index = structure.build_html_structure(source, raw, blocks)
    return source, scope.resolve_development_scope(query, [source], [index])


RAW = '<html><body><h2>8. Setup</h2><p>说明😀</p><table><tr><td>A</td></tr></table><p>直接说明</p><h3>8.1. One</h3><pre># 99. Fake\nX=1</pre><h3>8.2. Two</h3><p>二</p><h3>8.3. Three</h3><p>三</p><h2>9. Other</h2><p>不应包含</p></body></html>'


def test_single_section_contains_children_code_and_notes():
    source, result = resolve("第8节全部内容", RAW)
    assert result.status == "RESOLVED"
    text = source.text[result.spans[0].start:result.spans[0].end]
    assert "8.3. Three" in text and "# 99. Fake" in text and "9. Other" not in text


def test_contiguous_same_parent_range_includes_last_section_body():
    source, result = resolve("只依据8.1–8.3", RAW)
    assert result.status == "RESOLVED"
    assert source.text[result.spans[0].start:result.spans[0].end].rstrip().endswith("三")


@pytest.mark.parametrize("query,raw", [("8.3–8.1",RAW),("8.1和8.3",RAW),("8.1–9.1",RAW),("8.1–8.3",RAW.replace('<h3>8.2. Two</h3><p>二</p>','')),("8.1–8.3",RAW.replace('<h3>8.2. Two</h3>','<h3>8.1. Duplicate</h3>'))])
def test_ambiguous_ranges_abstain(query, raw):
    _, result = resolve(query, raw)
    assert result.status == "UNRESOLVED" and not result.spans


def test_opening_table_preserves_intro_and_direct_description():
    source, result = resolve("按第8节开头的表格", RAW)
    assert result.status == "RESOLVED"
    assert source.text[result.spans[0].start:result.spans[0].end].rstrip().endswith("直接说明")
    _, result = resolve("按第8节开头的表格", RAW.replace('<p>直接说明</p>','<table><tr><td>B</td></tr></table>'))
    assert result.status == "UNRESOLVED"


def test_unicode_assembly_budget_is_bytes_not_tokens():
    from research.scope_v2 import assemble_scope
    source, result = resolve("第8节", RAW)
    assembled = assemble_scope(result, [source], 19)
    assert assembled.status == "PARTIAL_SCOPE"
    assert assembled.utf8_bytes <= 19
    assert assembled.text == source.text[result.spans[0].start:result.spans[0].start+assembled.characters]


def test_uncertain_pdf_boundary_cannot_produce_complete_section():
    structure = importlib.import_module("research.development_structure")
    scope = importlib.import_module("research.development_scope")
    from research.scope_v2 import Source
    source = Source("pdf", "1. Start\nbody\n2. End\n2. End\n")
    pages = [dict(pdf_page_one_based=1,start=0,end=len(source.text),text=source.text)]
    xml = '<pdf2xml><page number="1"><fontspec id="1" family="Bold"/><text font="1">1. Start</text><text font="1">2. End</text></page></pdf2xml>'
    index = structure.build_pdf_structure(source,pages,xml)
    assert scope.resolve_development_scope("第1节",[source],[index]).status == "UNRESOLVED"


@pytest.mark.parametrize("boundary", ['<text font="missing">9. End</text>', '<text font="missing"><b>9. End</b></text>', '<text>9. End</text>'])
def test_missing_pdf_font_boundary_abstains_instead_of_reading_next_section(boundary):
    structure = importlib.import_module("research.development_structure")
    scope = importlib.import_module("research.development_scope")
    from research.scope_v2 import Source
    source = Source("陌生PDF", "8. Start\n内容😀\n9. End\n不属于8节\n")
    pages = [dict(pdf_page_one_based=1, start=0, end=len(source.text), text=source.text)]
    xml = '<pdf2xml><page number="1"><fontspec id="b" family="Times,Bold"/><text font="b">8. Start</text>' + boundary + '</page></pdf2xml>'
    index = structure.build_pdf_structure(source, pages, xml)
    result = scope.resolve_development_scope("第8节", [source], [index])
    assert result.status == "UNRESOLVED" and not result.spans
    assert index.metadata["diagnostics"][0]["status"] == "MISSING_FONT_EVIDENCE"


def test_known_normal_pdf_numbered_body_does_not_block_section():
    structure = importlib.import_module("research.development_structure")
    scope = importlib.import_module("research.development_scope")
    from research.scope_v2 import Source
    source = Source("陌生PDF", "8. Start\n1. 正文编号\n9. End\n不属于8节\n")
    pages = [dict(pdf_page_one_based=1, start=0, end=len(source.text), text=source.text)]
    xml = '<pdf2xml><page number="1"><fontspec id="b" family="Times,Bold"/><fontspec id="n" family="Times"/><text font="b">8. Start</text><text font="n">1. 正文编号</text><text font="b">9. End</text></page></pdf2xml>'
    index = structure.build_pdf_structure(source, pages, xml)
    result = scope.resolve_development_scope("第8节", [source], [index])
    assert result.status == "RESOLVED" and not index.metadata["diagnostics"]
    assert source.text[result.spans[0].start:result.spans[0].end] == "8. Start\n1. 正文编号\n"


@pytest.mark.parametrize("following", ['<text font="missing">End</text>', '<text font="n">End</text>', ''])
def test_bold_number_fragment_without_proven_title_abstains(following):
    structure = importlib.import_module("research.development_structure")
    scope = importlib.import_module("research.development_scope")
    from research.scope_v2 import Source
    source = Source("拆分PDF", "8. Start\n内容\n9. End\n不得越界\n")
    pages = [dict(pdf_page_one_based=1, start=0, end=len(source.text), text=source.text)]
    xml = '<pdf2xml><page number="1"><fontspec id="b" family="Times,Bold"/><fontspec id="n" family="Times"/><text font="b">8. Start</text><text font="b">9.</text>' + following + '</page></pdf2xml>'
    index = structure.build_pdf_structure(source, pages, xml)
    result = scope.resolve_development_scope("第8节", [source], [index])
    assert result.status == "UNRESOLVED" and not result.spans
    assert index.metadata["diagnostics"][0]["status"] == "INCOMPLETE_HEADING_FRAGMENTS"
