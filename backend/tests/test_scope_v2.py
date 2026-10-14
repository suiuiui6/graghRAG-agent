"""Offline scope contracts: coordinates are LF-normalized Unicode codepoints."""
from pathlib import Path
import importlib
import hashlib

import pytest


def api():
    assert importlib.util.find_spec("backend.research.scope_v2") is not None, "independent scope module must exist"
    return importlib.import_module("backend.research.scope_v2")


def test_no_selection_and_uncertain_queries_abstain():
    m = api()
    assert m.resolve_scope("section 3.2", []).status == "SOURCE_UNRESOLVED"
    source = m.Source("x", "# 3.2 Tools\ntext\n")
    assert m.resolve_scope("explain the system", [source]).status == "UNRESOLVED"


def test_normalization_number_hierarchy_and_fenced_comments():
    m = api()
    source = m.Source("x", "# 3.2 Tools\r\nintro\r# 3.2.1 A\n```python\n# fake\n```\nbody\n# 3.3 Next\nend")
    result = m.resolve_scope("规范3.2有哪些内容", [source])
    assert result.status == "RESOLVED"
    assert result.spans == (m.Span("x", 0, source.text.index("# 3.3")),)


def test_duplicate_sections_and_source_selection_are_ambiguous():
    m = api()
    source = m.Source("x", "# 2.1 A\nfirst\n# 2.1 B\nsecond\n")
    result = m.resolve_scope("section 2.1", [source])
    assert result.status == "UNRESOLVED"
    assert "候选" in result.reason
    assert m.resolve_scope("全文", [source, m.Source("y", "# other")]).status == "UNRESOLVED"


def test_abstract_subitem_and_title():
    m = api()
    source = m.Source("x", "# 摘 要\n摘要正文\n# 6.2 Limits\n(1) one\n\n(4) four\ncontinued\n\n# 7 End\n")
    assert source.text[m.resolve_scope("摘要", [source]).spans[0].start:].startswith("# 摘 要")
    result = m.resolve_scope("6.2第4项", [source])
    assert result.kind == "subitem"
    assert source.text[result.spans[0].start:result.spans[0].end] == "(4) four\ncontinued"
    assert m.resolve_scope("Limits章节", [source]).status == "RESOLVED"
    assert m.resolve_scope("第4项", [source]).status == "UNRESOLVED"


def test_caption_inventory_scan_proof_does_not_claim_source_coverage():
    m = api()
    source = m.Source("x", "# 1 Intro\nnot caption\nFigure 1: α\n\n图 2：乙\n\n# 2 End\n")
    result = m.resolve_scope("列出全文所有编号图的图注", [source])
    assert result.kind == "figure_captions"
    assert len(result.spans) == 2
    assert result.scan_proof["status"] == "COMPLETE_LOCAL_SCAN"
    assembly = m.assemble_scope(result, [source], 1000)
    assert assembly.status == "COMPLETE_SCOPE"
    assert "not caption" not in assembly.text
    assert len(assembly.text) < len(source.text)
    assert assembly.scan_proof == result.scan_proof


def test_tables_never_select_tools_by_title():
    m = api()
    source = m.Source("x", "# 3.2 Tools\n| Tool | Use |\n|---|---|\n| a | b |\n# 4 End\n")
    assert m.resolve_scope("列出全文所有表格", [source]).kind == "tables"
    assert m.resolve_scope("3.2工具表有哪些工具", [source]).kind == "section"


def test_plain_numbered_headings_and_figure_inventory_without_caption_keyword():
    m = api()
    source = m.Source("x", "1 Introduction\nhello\n1.1 Detail\ninside\n2 Results\nFigure 1: result\n")
    result = m.resolve_scope("section 1.1", [source])
    assert result.status == "RESOLVED"
    assert source.text[result.spans[0].start:result.spans[0].end] == "1.1 Detail\ninside\n"
    assert m.resolve_scope("列出论文所有编号的图", [source]).kind == "figure_captions"


def test_projection_respects_code_fences_and_empty_inventory():
    m = api()
    source = m.Source("x", "```\nFigure 9: code\n```\nno captions\n")
    result = m.resolve_scope("all figure captions", [source])
    assert result.status == "RESOLVED"
    assert result.spans == ()
    assert result.scan_proof["matched_spans"] == 0
    assert m.assemble_scope(result, [source], 0).status == "COMPLETE_SCOPE"


def test_actual_v2_inventory_query_exports_versioned_source_scan():
    m = api()
    source = m.Source("x", "Figure 1: primary\r\n\r\n# 附录 B\r\n图 1— 别名\r\n![](unnumbered.png)\r\n")
    query = "仅根据提供的Markdown文档，列出所有显式编号的图，按图号去重；以正文题注为主，附录B名称作为可接受别名。不把未编号图片文件算作额外图号。"
    result = m.resolve_scope(query, [source])
    assert result.kind == "figure_captions"
    assert len(result.spans) == 2
    assert result.scan_proof["source_lf_sha256"] == hashlib.sha256(source.text.encode("utf-8")).hexdigest()
    assert result.scan_proof["detector_version"]
    assert m.resolve_scope("列出所有表格", [source]).kind == "tables"


def test_numeric_only_title_never_becomes_empty_string_match():
    m = api()
    source = m.Source("x", "# 3.2\nbody\n")
    assert m.resolve_scope("explain the document", [source]).status == "UNRESOLVED"


def test_body_year_never_truncates_explicit_atx_section():
    m = api()
    source = m.Source("x", "# 3.2 Methods\n2026 年度预算为100\nmore\n# 3.3 Next\n")
    result = m.resolve_scope("3.2", [source])
    assert result.status == "RESOLVED"
    assert result.spans == (m.Span("x", 0, source.text.index("# 3.3")),)


def test_incoherent_plain_heading_numbers_abstain():
    m = api()
    source = m.Source("x", "3.2 Methods\n2026 年度预算为100\nmore\n3.3 Next\n")
    assert m.resolve_scope("3.2", [source]).status == "UNRESOLVED"


def test_fenced_subitem_cannot_be_an_anchor():
    m = api()
    source = m.Source("x", "# 6.2 Limitations\n```text\n(4) fake item in example\n```\n(1) real item\n# 7 End\n")
    assert m.resolve_scope("6.2第4项", [source]).status == "UNRESOLVED"


def test_real_subitem_outside_fence_has_the_unique_anchor():
    m = api()
    source = m.Source("x", "# 6.2 Limitations\n```text\n(4) fake item in example\n```\n(1) real item\n(4) actual item\n# 7 End\n")
    result = m.resolve_scope("6.2第4项", [source])
    assert result.status == "RESOLVED"
    assert result.spans == (m.Span("x", source.text.index("(4) actual"), source.text.index("\n# 7")),)


def test_multi_source_abstention_records_candidate_locations():
    m = api()
    result = m.resolve_scope("section 3.2", [m.Source("a", "# 3.2 A\n"), m.Source("b", "intro\n# 3.2 B\n")])
    assert result.status == "UNRESOLVED"
    assert "a@0" in result.reason and "b@6" in result.reason


def test_duplicate_heading_reason_is_metadata_only():
    m = api()
    source = m.Source("x", "# 3.2 PRIVATE-HEADING\nfirst\n# 3.2 PRIVATE-HEADING\nsecond\n")
    result = m.resolve_scope("3.2", [source])
    assert result.status == "UNRESOLVED"
    assert "PRIVATE-HEADING" not in result.reason
    assert "x@0" in result.reason


def test_unclosed_fence_cannot_certify_absence():
    m = api()
    source = m.Source("x", "intro\n```\nFigure 1: uncertain fenced content\n")
    result = m.resolve_scope("all figure captions", [source])
    assert result.status == "UNRESOLVED"
    assert result.scan_proof is None


@pytest.mark.parametrize("query", ["6.2第4项", "6.2"])
def test_unclosed_target_section_abstains_from_structural_completeness(query):
    m = api()
    source = m.Source("x", "# 6.2 Limits\n(4) real item\n```text\n(5) uncertain following item\n# 7 End\n")
    result = m.resolve_scope(query, [source])
    assert result.status == "UNRESOLVED"
    assert m.assemble_scope(result, [source], 1000).status == "UNRESOLVED"


@pytest.mark.parametrize("qid,selected", [
    ("D1-FIG-v2", "D1"), ("D1-COST-v2", "D1"),
    ("D1-LIMITS-v2", "D1"), ("D1-FUTURE-v2", "D1"),
    ("D2-ATTENTION-v2", "D2"), ("D2-DATA-v2", "D2"),
    ("D2-NONE-v2", "D2"), ("D3-TOOLS-v2", "D3"),
    ("D3-SUPERVISOR-v2", "D3"),
])
def test_nine_frozen_queries_with_explicit_test_fixture_only_selection(qid, selected):
    # Gold is accessible only here in TESTS. AUTO receives the query and the
    # independently selected TEST_FIXTURE_ONLY Source, never qid/range/answers.
    from backend.research.gold_v2 import load_gold
    package = load_gold(Path(__file__).resolve().parents[2])
    question = next(q for q in package.data["questions"] if q["id"] == qid)
    m = api()
    result = m.resolve_scope(question["query"], [m.Source(selected, package.texts[selected])])
    assert result.status == "RESOLVED", result.reason
    if qid == "D1-FIG-v2":
        assert result.kind == "figure_captions"
        assert len(result.spans) == 12
        assert result.scan_proof["status"] == "COMPLETE_LOCAL_SCAN"
    else:
        target = question.get("coverage_adjudication_target", question["scope"])
        assert [(span.start, span.end) for span in result.spans] == [(target["start"], target["end"])]


def test_html_table_projection_keeps_exact_table_interval():
    m = api()
    source = m.Source("x", "intro\n<table><tr><td>甲</td></tr></table>\noutside")
    result = m.resolve_scope("全文所有表格", [source])
    assembly = m.assemble_scope(result, [source], 1000)
    assert assembly.text == "<table><tr><td>甲</td></tr></table>"


def test_assembler_rejects_unknown_source_and_duplicate_source_keys():
    m = api()
    resolution = m.Resolution("RESOLVED", (m.Span("x", 0, 1),))
    with pytest.raises(ValueError):
        m.assemble_scope(resolution, [], 10)
    with pytest.raises(ValueError):
        m.assemble_scope(resolution, [m.Source("x", "a"), m.Source("x", "b")], 10)


def test_zero_budget_and_overlap_never_inflate_coverage():
    m = api()
    source = m.Source("x", "abcd")
    resolution = m.Resolution("RESOLVED", (m.Span("x", 0, 3), m.Span("x", 1, 4)))
    assembly = m.assemble_scope(resolution, [source], 0)
    assert (assembly.status, assembly.text, assembly.mappings) == ("PARTIAL_SCOPE", "", ())
    assert m.assemble_scope(resolution, [source], 4).text == "abcd"


def test_assembler_merges_ranges_and_counts_separator_budget():
    m = api()
    source = m.Source("x", "甲乙丙😀abc")
    result = m.Resolution("RESOLVED", (m.Span("x", 3, 5), m.Span("x", 0, 2), m.Span("x", 0, 1)))
    assembly = m.assemble_scope(result, [source], 12)
    assert assembly.status == "PARTIAL_SCOPE"
    assert assembly.text == "甲乙\n\n😀"
    assert assembly.utf8_bytes == 12
    assert assembly.characters == 5
    assert assembly.mappings[1] == {"source": "x", "start": 3, "end": 4, "output_start": 4, "output_end": 5}
    assert m.assemble_scope(result, [source], 13).status == "COMPLETE_SCOPE"


@pytest.mark.parametrize("start,end", [(-1, 1), (2, 1), (0, 99), (0.5, 1)])
def test_assembler_rejects_invalid_ranges(start, end):
    m = api()
    with pytest.raises(ValueError):
        m.assemble_scope(m.Resolution("RESOLVED", (m.Span("x", start, end),)), [m.Source("x", "abc")], 100)


@pytest.mark.parametrize("budget", [-1, True, 1.5])
def test_invalid_budget_and_abstention(budget):
    m = api()
    with pytest.raises(ValueError):
        m.assemble_scope(m.Resolution("UNRESOLVED", ()), [], budget)
    assert m.assemble_scope(m.Resolution("UNRESOLVED", ()), [], 0).status == "UNRESOLVED"


@pytest.mark.parametrize("path,query,expected", [
    ("backend/output/mineru/ingest_2/full.md", "摘要", (55, 1097)),
    ("backend/output/mineru/ingest_2/full.md", "6.2", (19694, 20159)),
    ("backend/output/mineru/ingest_2/full.md", "6.2第4项", (20059, 20157)),
    ("backend/output/mineru/ingest_f/full.md", "section 3.2.3", (12251, 13474)),
    ("backend/output/mineru/ingest_f/full.md", "5.1", (20861, 21487)),
    ("integration/Agentic-RAG-Architecture.md", "规范3.2", (6399, 6809)),
    ("integration/Agentic-RAG-Architecture.md", "4.1", (11015, 11170)),
])
def test_real_source_coordinates(path, query, expected):
    m = api()
    source = m.Source(path, (Path(__file__).resolve().parents[2] / path).read_text(encoding="utf-8"))
    result = m.resolve_scope(query, [source])
    assert result.status == "RESOLVED", result.reason
    assert [(span.start, span.end) for span in result.spans] == [expected]
