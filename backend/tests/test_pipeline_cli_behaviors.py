"""Offline CLI contracts with real MinerU fixtures and graph/JSONL serialization."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pipeline
from langextract.core.data import AnnotatedDocument, CharInterval, Extraction


@pytest.fixture(autouse=True)
def installed_langextract(monkeypatch):
    """Use the editable package, rather than the outer repository namespace."""
    import importlib
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "langextract"))
    monkeypatch.delitem(sys.modules, "langextract", raising=False)
    monkeypatch.setattr(pipeline, "lx", importlib.import_module("langextract"))


@pytest.fixture
def cached(tmp_path):
    root = tmp_path / "cached"
    root.mkdir()
    (root / "full.md").write_text("# 项目\n响应时间为10毫秒。", encoding="utf-8")
    (root / "sample_content_list.json").write_text(json.dumps([
        {"type": "text", "text": "项目", "text_level": 1, "page_idx": 0,
         "bbox": [0, 0, 100, 100]},
        {"type": "text", "text": "响应时间为10毫秒。", "page_idx": 1,
         "bbox": [100, 100, 500, 200]},
    ], ensure_ascii=False), encoding="utf-8")
    # V2 must never be selected by the V1 bridge.
    (root / "sample_v2_content_list.json").write_text("invalid", encoding="utf-8")
    return root


@pytest.fixture
def examples(tmp_path):
    path = tmp_path / "examples.yaml"
    path.write_text("examples:\n  - text: 响应时间为10毫秒。\n    extractions:\n"
                    "      - extraction_class: metric\n        extraction_text: 响应时间\n"
                    "        attributes:\n          value: 10\n  - text: 空示例\n", encoding="utf-8")
    return path


def extract_documents(**kwargs):
    """Model boundary: return the provider's real public data types."""
    return [AnnotatedDocument(document_id=d.document_id, text=d.text,
               extractions=[Extraction(extraction_class="metric", extraction_text="响应时间",
                            char_interval=CharInterval(start_pos=d.text.index("响应时间"),
                                                       end_pos=d.text.index("响应时间") + 4),
                            attributes={"value": 10})])
            for d in kwargs["text_or_documents"] if "响应时间" in d.text]


def test_bridge_loads_v1_and_maps_real_chinese_source(cached):
    documents, offsets, positions, text = pipeline.run_bridge(str(cached))
    assert "响应时间为10毫秒。" in "".join(d.text for d in documents)
    assert all(text[offsets[d.document_id]:].startswith(d.text) for d in documents)
    segment = positions.lookup(text.index("响应时间"))
    assert (segment.page_idx, segment.bbox) == (1, [100, 100, 500, 200])


def test_bridge_rejects_missing_v1_even_when_v2_exists(tmp_path):
    (tmp_path / "only_v2_content_list.json").write_text("[]", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="No content_list"):
        pipeline.run_bridge(str(tmp_path))


def test_examples_preserve_attributes_and_allow_empty_extractions(examples):
    loaded = pipeline.load_examples(str(examples))
    assert len(loaded) == 2
    assert loaded[0].extractions[0].attributes == {"value": 10}
    assert loaded[0].extractions[0].extraction_text == "响应时间"
    assert loaded[1].extractions == []


@pytest.mark.parametrize("singleton", [False, True])
def test_extraction_normalizes_provider_results_and_forwards_options(monkeypatch, cached, examples, singleton):
    documents, *_ = pipeline.run_bridge(str(cached))
    observed = {}
    def provider(**kwargs):
        observed.update(kwargs)
        results = extract_documents(**kwargs)
        results[0].extractions.append(Extraction(extraction_class="metric", extraction_text="未定位"))
        return results[0] if singleton else results
    monkeypatch.setattr(pipeline.lx, "extract", provider)
    monkeypatch.setenv("LANGEXTRACT_TEMPERATURE", "0.2")
    monkeypatch.setenv("LANGEXTRACT_MAX_CHAR_BUFFER", "500")
    result = pipeline.run_langextract(documents, str(examples), "只抽取指标")
    assert len(result) == 1 and len(result[0].extractions) == 2
    assert observed["prompt_description"] == "只抽取指标"
    assert observed["temperature"] == 0.2 and observed["max_char_buffer"] == 500
    assert observed["use_schema_constraints"] is False
    assert observed["examples"][0].extractions[0].attributes == {"value": 10}


@pytest.mark.parametrize("mode", ["cached", "pdf", "url"])
def test_main_writes_roundtrippable_jsonl_and_grounded_graph(monkeypatch, tmp_path, cached, examples, mode, capsys):
    output = tmp_path / "artifact"
    calls = []
    def cloud(**kwargs):
        calls.append(kwargs)
        return str(cached)
    monkeypatch.setattr(pipeline, "run_mineru", cloud)
    monkeypatch.setattr(pipeline.lx, "extract", extract_documents)
    source = str(cached) if mode == "cached" else "local.pdf" if mode == "pdf" else "https://example.invalid/a.pdf"
    monkeypatch.setattr(sys, "argv", ["pipeline", f"--{mode}", source, "--examples", str(examples), "--output", str(output)])
    pipeline.main()
    nodes = json.loads((output / "nodes.json").read_text(encoding="utf-8"))
    edges = json.loads((output / "edges.json").read_text(encoding="utf-8"))
    node = nodes["nodes"][0]
    assert node["label"] == "响应时间"
    assert node["page_idx"] == 1 and node["grounding_status"] == "grounded"
    assert node["properties"] == {"value": 10}
    assert edges["edges"] == []
    assert nodes["metadata"]["schema_version"] == "1.1"
    jsonl = list(output.glob("integrated_*.jsonl"))
    assert len(jsonl) == 1
    records = [json.loads(line) for line in jsonl[0].read_text(encoding="utf-8").splitlines()]
    assert records[0]["extractions"][0]["extraction_text"] == "响应时间"
    assert (not calls) if mode == "cached" else calls == [{"local_pdf": source if mode == "pdf" else None,
                                                         "file_url": source if mode == "url" else None}]
    assert "Pipeline Complete" in capsys.readouterr().out


def test_main_missing_input_exits_before_model(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["pipeline", "--output", str(tmp_path / "unused")])
    with pytest.raises(SystemExit) as failure:
        pipeline.main()
    assert failure.value.code == 1
    assert "Need --pdf, --url, or --cached" in capsys.readouterr().out


@pytest.mark.parametrize("args", [["--unknown"], ["--pdf"]])
def test_argparse_rejects_invalid_cli(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["pipeline", *args])
    with pytest.raises(SystemExit) as failure:
        pipeline.main()
    assert failure.value.code == 2


@pytest.mark.parametrize("response", ['{"success": true, "link": "https://example.invalid/pdf"}',
                                      '{"success": false}', 'not-json', '{"success": true}'])
def test_upload_requires_valid_public_link(monkeypatch, response):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=response))
    if '"link"' in response:
        assert pipeline._upload_local("fixture.pdf") == "https://example.invalid/pdf"
    else:
        with pytest.raises(RuntimeError, match="Cannot upload PDF"):
            pipeline._upload_local("fixture.pdf")


@pytest.mark.parametrize("outcome", ["done", "failed", "timeout", "submit-failed"])
def test_mineru_polling_download_cleanup_and_failure_contract(monkeypatch, tmp_path, outcome):
    monkeypatch.setattr(pipeline, "__file__", str(tmp_path / "pipeline.py"))
    monkeypatch.setenv("MINERU_MAX_WAIT_SECONDS", "2")
    monkeypatch.setenv("MINERU_POLL_INTERVAL", "1")
    monkeypatch.setattr(pipeline.time, "sleep", lambda _: None)
    calls = []
    def transport(command, **kwargs):
        calls.append(command)
        if "POST" in command:
            body = json.loads(command[-1])
            assert body["url"] == "https://example.invalid/pdf" and body["enable_table"] is True
            return SimpleNamespace(stdout=json.dumps({"code": 1 if outcome == "submit-failed" else 0,
                                                       "data": {"task_id": "123456789"}}))
        if command[0] == "unzip":
            with zipfile.ZipFile(command[2]) as archive:
                archive.extractall(command[4])
            return SimpleNamespace(returncode=0)
        if "-o" in command:
            with zipfile.ZipFile(command[command.index("-o") + 1], "w") as archive:
                archive.writestr("full.md", "真实本地产物")
            return SimpleNamespace(returncode=0)
        state = "running" if len(calls) == 2 or outcome == "timeout" else outcome
        return SimpleNamespace(stdout=json.dumps({"data": {"state": state, "err_msg": "bad parse",
                                                            "full_zip_url": "https://example.invalid/result.zip"}}))
    monkeypatch.setattr(subprocess, "run", transport)
    if outcome == "done":
        upload_inputs = []
        def upload(path):
            upload_inputs.append(path)
            return "https://example.invalid/pdf"
        monkeypatch.setattr(pipeline, "_upload_local", upload)
        result = Path(pipeline.run_mineru(local_pdf="fixture.pdf"))
        assert upload_inputs == ["fixture.pdf"]
        assert result.parent == tmp_path / "output" / "mineru"
        assert (result / "full.md").read_text(encoding="utf-8") == "真实本地产物"
        assert not (result / "result.zip").exists()
        assert len(calls) == 5
    else:
        error = TimeoutError if outcome == "timeout" else RuntimeError
        with pytest.raises(error, match="Timeout|Parse failed|Submit failed"):
            pipeline.run_mineru(file_url="https://example.invalid/pdf")
        assert not (tmp_path / "output").exists()


def test_mineru_requires_input():
    with pytest.raises(ValueError, match="Need --pdf or --url"):
        pipeline.run_mineru()
