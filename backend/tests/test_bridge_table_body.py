from bridge import _item_to_text, build_documents
from schema import SectionSplit


def test_item_to_text_includes_table_body_for_table_items():
    item = {
        "type": "table",
        "table_caption": ["表 9 问题三各产量全年绿电指标满足情况（连续制氨）"],
        "table_body": "<table><tr><td>W2S2</td><td>95%</td></tr><tr><td>W3S3</td><td>91%</td></tr></table>",
    }

    text = _item_to_text(item)

    assert "W2S2" in text
    assert "W3S3" in text
    assert "95%" in text
    assert "91%" in text


def test_build_documents_includes_table_body_text():
    full_md = (
        "5.3.2 求解结果\n"
        "表 9 问题三各产量全年绿电指标满足情况（连续制氨）\n"
        "<table><tr><td>72</td><td>18</td><td>6</td><td>0</td><td>7111 ± 1424</td></tr>"
        "<tr><td>54</td><td>16</td><td>3</td><td>5</td><td>5416 ± 1632</td></tr></table>\n"
        "全年总吨氨成本为 5652元/吨。"
    )
    sections = [
        SectionSplit(
            document_id="sec_0_test",
            title="5.3.2 求解结果",
            heading_level=2,
            char_start=0,
            char_end=len(full_md),
        )
    ]

    documents, offsets = build_documents(sections, full_md)

    assert documents
    assert "7111 ± 1424" in documents[0].text
    assert "5416 ± 1632" in documents[0].text
    assert offsets["sec_0_test"] == 0
