import importlib
import sys
import types
import uuid
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


if "dotenv" not in sys.modules:
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None)


def test_mineru_output_to_sections_preserves_table_structure():
    import worker

    item = {
        "type": "table",
        "page_idx": 7,
        "table_caption": ["表 9 问题三各产量全年绿电指标满足情况（连续制氨）"],
        "table_body": (
            "<table>"
            "<tr><td>场景</td><td>绿电消纳率</td></tr>"
            "<tr><td>W2S2</td><td>95%</td></tr>"
            "<tr><td>W3S3</td><td>91%</td></tr>"
            "</table>"
        ),
    }

    table_json = worker._mineru_table_item_to_table_json(item)

    assert table_json is not None
    assert table_json["headers"] == ["场景", "绿电消纳率"]
    assert table_json["rows"] == [["W2S2", "95%"], ["W3S3", "91%"]]


def test_build_runtime_indexes_from_mineru_output_sets_bm25_and_table_indexes(monkeypatch):
    import worker

    worker = importlib.reload(worker)
    fixture_root = Path(__file__).resolve().parent / f"_tmp_worker_pdf_runtime_indexing_{uuid.uuid4().hex[:8]}"
    mineru_dir = fixture_root / "mineru"
    mineru_dir.mkdir(parents=True)

    try:
        (mineru_dir / "full.md").write_text(
            "# 5.3.2 求解结果\n"
            "表 9 问题三各产量全年绿电指标满足情况（连续制氨）\n"
            "W2S2 95%\n"
            "W3S3 91%\n",
            encoding="utf-8",
        )
        (mineru_dir / "sample_content_list.json").write_text(
            """
[
  {"type": "text", "text": "5.3.2 求解结果", "text_level": 2, "page_idx": 7},
  {
    "type": "table",
    "page_idx": 7,
    "table_caption": ["表 9 问题三各产量全年绿电指标满足情况（连续制氨）"],
    "table_body": "<table><tr><td>场景</td><td>绿电消纳率</td></tr><tr><td>W2S2</td><td>95%</td></tr><tr><td>W3S3</td><td>91%</td></tr></table>"
  }
]
""".strip(),
            encoding="utf-8",
        )

        captured = {}

        def fake_set_bm25_index(index, persist=True):
            captured["bm25"] = index

        def fake_set_table_index(index, persist=True):
            captured["table"] = index

        monkeypatch.setattr("index_registry.set_bm25_index", fake_set_bm25_index)
        monkeypatch.setattr("index_registry.set_table_index", fake_set_table_index)

        chunks = worker._build_runtime_indexes_from_mineru_output(str(mineru_dir), "paper.pdf")

        assert chunks
        assert any("W2S2" in chunk.text for chunk in chunks)
        assert any(getattr(chunk, "table_json", None) for chunk in chunks)
        assert "bm25" in captured
        assert "table" in captured
        rows = captured["table"].query(top_k=10)
        assert any(row["context"].get("场景") == "W2S2" for row in rows)
        assert any(row["context"].get("绿电消纳率") == "95%" for row in rows)
    finally:
        pass
