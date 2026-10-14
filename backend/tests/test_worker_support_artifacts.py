import importlib
import json
import sys
import types
import uuid
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


if "dotenv" not in sys.modules:
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None)


def _make_local_fixture_dir(test_name: str) -> Path:
    root = Path(__file__).resolve().parent / f"_tmp_{test_name}_{uuid.uuid4().hex[:8]}"
    mineru_dir = root / "mineru"
    mineru_dir.mkdir(parents=True)
    return mineru_dir


def test_mineru_output_to_sections_prefers_v2_appendix_support_artifact_text():
    import worker

    worker = importlib.reload(worker)
    mineru_dir = _make_local_fixture_dir("worker_support_artifacts")
    (mineru_dir / "full.md").write_text("占位 full.md", encoding="utf-8")
    (mineru_dir / "sample_content_list.json").write_text(
        json.dumps(
            [
                {"type": "text", "text": "正文内容", "page_idx": 0},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (mineru_dir / "sample_content_list_v2.json").write_text(
        json.dumps(
            [
                [
                    {"type": "title", "content": {"title_content": [{"type": "text", "content": "附录 B：支撑材料文件说明"}], "level": 2}},
                    {"type": "paragraph", "content": {"paragraph_content": [{"type": "text", "content": "scenario_summary.csv — 24 种风光场景汇总信息"}]}},
                    {"type": "paragraph", "content": {"paragraph_content": [{"type": "text", "content": "result3_continuous_all.csv — 问题三全部 120 条连续 LP 结果"}]}},
                ]
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    sections = worker._mineru_output_to_sections(str(mineru_dir), "paper.pdf")
    texts = [section.text for section in sections]

    assert any("scenario_summary.csv" in text for text in texts)
    assert any("result3_continuous_all.csv" in text for text in texts)


def test_build_runtime_indexes_from_mineru_output_indexes_v2_support_artifact_sections(monkeypatch):
    import worker

    worker = importlib.reload(worker)
    mineru_dir = _make_local_fixture_dir("worker_support_artifacts_index")
    (mineru_dir / "full.md").write_text("占位 full.md", encoding="utf-8")
    (mineru_dir / "sample_content_list.json").write_text(
        json.dumps(
            [
                {"type": "text", "text": "正文内容", "page_idx": 0},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (mineru_dir / "sample_content_list_v2.json").write_text(
        json.dumps(
            [
                [
                    {"type": "title", "content": {"title_content": [{"type": "text", "content": "附录 B：支撑材料文件说明"}], "level": 2}},
                    {"type": "paragraph", "content": {"paragraph_content": [{"type": "text", "content": "scenario_summary.csv — 24 种风光场景汇总信息"}]}},
                    {"type": "paragraph", "content": {"paragraph_content": [{"type": "text", "content": "W3S3 — 连续 LP 场景结果索引"}]}},
                ]
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured = {}

    def fake_set_bm25_index(index, persist=True):
        captured["bm25"] = index

    monkeypatch.setattr("index_registry.set_bm25_index", fake_set_bm25_index)

    chunks = worker._build_runtime_indexes_from_mineru_output(str(mineru_dir), "paper.pdf")

    assert chunks
    assert any("scenario_summary.csv" in chunk.text for chunk in chunks)
    assert any("W3S3" in chunk.text for chunk in chunks)
    assert "bm25" in captured


def test_build_runtime_indexes_from_mineru_output_expands_scenario_summary_support_artifact(monkeypatch):
    import worker

    worker = importlib.reload(worker)
    mineru_dir = _make_local_fixture_dir("worker_support_artifacts_scenario")
    (mineru_dir / "full.md").write_text("占位 full.md", encoding="utf-8")
    (mineru_dir / "sample_content_list.json").write_text(
        json.dumps(
            [
                {"type": "text", "text": "正文内容", "page_idx": 0},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (mineru_dir / "sample_content_list_v2.json").write_text(
        json.dumps(
            [
                [
                    {"type": "title", "content": {"title_content": [{"type": "text", "content": "附录 B：支撑材料文件说明"}], "level": 2}},
                    {"type": "paragraph", "content": {"paragraph_content": [{"type": "text", "content": "scenario_summary.csv — 24 种风光场景汇总信息"}]}},
                    {"type": "paragraph", "content": {"paragraph_content": [{"type": "text", "content": "W2S2 — 连续 LP 场景结果索引"}]}},
                    {"type": "paragraph", "content": {"paragraph_content": [{"type": "text", "content": "W3S3 — 连续 LP 场景结果索引"}]}},
                ]
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured = {}

    def fake_set_table_index(index, persist=True):
        captured["table"] = index

    monkeypatch.setattr("index_registry.set_table_index", fake_set_table_index)

    chunks = worker._build_runtime_indexes_from_mineru_output(str(mineru_dir), "paper.pdf")

    assert chunks
    assert any("scenario_summary.csv" in chunk.text for chunk in chunks)
    assert any("W2S2" in chunk.text for chunk in chunks)
    assert any("W3S3" in chunk.text for chunk in chunks)
    assert "table" in captured
    rows = captured["table"].export_rows() if hasattr(captured["table"], "export_rows") else captured["table"].query(top_k=20)
    assert any(row["context"].get("场景") == "W2S2" for row in rows)
    assert any(row["context"].get("场景") == "W3S3" for row in rows)


def test_build_runtime_indexes_from_mineru_output_loads_referenced_support_csv_from_source_directory(monkeypatch):
    import worker

    worker = importlib.reload(worker)
    mineru_dir = _make_local_fixture_dir("worker_support_artifacts_sidecar_csv")
    source_dir = mineru_dir.parent / "uploads"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_pdf = source_dir / "paper.pdf"
    source_pdf.write_text("stub pdf placeholder", encoding="utf-8")
    (source_dir / "scenario_summary.csv").write_text(
        "\n".join(
            [
                "场景,绿电消纳率,弃电量",
                "W2S2,95%,12.0 MWh/日",
                "W3S3,91%,18.5 MWh/日",
            ]
        ),
        encoding="utf-8",
    )
    (mineru_dir / "full.md").write_text("占位 full.md", encoding="utf-8")
    (mineru_dir / "sample_content_list.json").write_text(
        json.dumps(
            [
                {"type": "text", "text": "正文内容", "page_idx": 0},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (mineru_dir / "sample_content_list_v2.json").write_text(
        json.dumps(
            [
                [
                    {"type": "title", "content": {"title_content": [{"type": "text", "content": "附录 B：支撑材料文件说明"}], "level": 2}},
                    {"type": "paragraph", "content": {"paragraph_content": [{"type": "text", "content": "scenario_summary.csv — 24 种风光场景汇总信息"}]}},
                ]
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured = {}

    def fake_set_table_index(index, persist=True):
        captured["table"] = index

    monkeypatch.setattr("index_registry.set_table_index", fake_set_table_index)

    chunks = worker._build_runtime_indexes_from_mineru_output(
        str(mineru_dir),
        "paper.pdf",
        source_path=str(source_pdf),
    )

    assert chunks
    assert any("scenario_summary.csv" in chunk.text for chunk in chunks)
    assert any("95%" in chunk.text for chunk in chunks)
    assert "table" in captured
    rows = captured["table"].export_rows() if hasattr(captured["table"], "export_rows") else captured["table"].query(top_k=20)
    assert any(row["context"].get("场景") == "W2S2" and row["context"].get("绿电消纳率") == "95%" for row in rows)
    assert any(row["context"].get("场景") == "W3S3" and row["context"].get("弃电量") == "18.5 MWh/日" for row in rows)


def test_build_runtime_indexes_from_mineru_output_loads_referenced_support_csv_from_mineru_directory(monkeypatch):
    import worker

    worker = importlib.reload(worker)
    mineru_dir = _make_local_fixture_dir("worker_support_artifacts_sidecar_csv_recovery")
    (mineru_dir / "scenario_summary.csv").write_text(
        "\n".join(
            [
                "场景,绿电消纳率,弃电量",
                "W2S2,95%,12.0 MWh/日",
                "W3S3,91%,18.5 MWh/日",
            ]
        ),
        encoding="utf-8",
    )
    (mineru_dir / "full.md").write_text("占位 full.md", encoding="utf-8")
    (mineru_dir / "sample_content_list.json").write_text(
        json.dumps(
            [
                {"type": "text", "text": "正文内容", "page_idx": 0},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (mineru_dir / "sample_content_list_v2.json").write_text(
        json.dumps(
            [
                [
                    {"type": "title", "content": {"title_content": [{"type": "text", "content": "附录 B：支撑材料文件说明"}], "level": 2}},
                    {"type": "paragraph", "content": {"paragraph_content": [{"type": "text", "content": "scenario_summary.csv — 24 种风光场景汇总信息"}]}},
                ]
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured = {}

    def fake_set_table_index(index, persist=True):
        captured["table"] = index

    monkeypatch.setattr("index_registry.set_table_index", fake_set_table_index)

    worker._build_runtime_indexes_from_mineru_output(str(mineru_dir), "paper.pdf")

    assert "table" in captured
    rows = captured["table"].export_rows() if hasattr(captured["table"], "export_rows") else captured["table"].query(top_k=20)
    assert any(row["context"].get("场景") == "W2S2" and row["context"].get("绿电消纳率") == "95%" for row in rows)
    assert any(row["context"].get("场景") == "W3S3" and row["context"].get("弃电量") == "18.5 MWh/日" for row in rows)
